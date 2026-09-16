"""
Exam service: the orchestrator that handlers/exam_commands.py calls.

Responsible for:
  - resolving a free-text query to a known exam (via exam_normalizer)
  - dispatching to the right authority-specific source-page resolver
  - running generic discovery + real PDF verification
  - caching verified results
  - returning plain-data structures (dicts/dataclasses) — NOT
    telegram objects — so this module and its tests never need the
    telegram library installed.
"""
from dataclasses import asdict
from typing import Dict, List, Optional

from database.models import (
    Document,
    DOC_TYPE_SYLLABUS,
    DOC_TYPE_QUESTION_PAPER,
    DOC_TYPE_ANSWER_KEY,
    VERIFICATION_VERIFIED,
)
from services import (
    authority_registry,
    document_discovery,
    exam_cache,
    pdf_validator,
    rssb_parser,
    rpsc_parser,
    source_verifier,
)
from services.exam_normalizer import normalize_and_match, MatchResult
from services.exam_registry_data import EXAM_REGISTRY, EXAM_REGISTRY_BY_ID
from utils.logger import get_logger

log = get_logger(__name__)

DOC_TYPES = [DOC_TYPE_SYLLABUS, DOC_TYPE_QUESTION_PAPER, DOC_TYPE_ANSWER_KEY]

_AUTHORITY_PARSERS = {
    "rssb": rssb_parser,
    "rsmssb": rssb_parser,
    "rpsc": rpsc_parser,
}


def resolve_exam(query: str) -> MatchResult:
    """Resolve free-text like '/exam CET 12' -> a MatchResult pointing at
    an entry in EXAM_REGISTRY, or matched_exam_id=None if nothing is
    confident enough."""
    return normalize_and_match(query, EXAM_REGISTRY)


def get_exam(exam_id: str) -> Optional[dict]:
    return EXAM_REGISTRY_BY_ID.get(exam_id)


def _source_pages_for(authority_id: str, doc_type: Optional[str]) -> List[str]:
    parser = _AUTHORITY_PARSERS.get(authority_id)
    if parser is not None:
        return parser.get_source_pages(doc_type)
    authority = authority_registry.get_authority(authority_id)
    if authority is None:
        return []
    # Generic fallback: just crawl the authority's known official pages.
    return list(authority.official_pages.values())


def _official_source_page_for(authority_id: str, doc_type: Optional[str]) -> Optional[str]:
    parser = _AUTHORITY_PARSERS.get(authority_id)
    if parser is not None:
        return parser.get_official_source_page(doc_type)
    authority = authority_registry.get_authority(authority_id)
    if authority is None:
        return None
    pages = list(authority.official_pages.values())
    return pages[0] if pages else None


def find_documents(
    exam_id: str,
    doc_type: str,
    year: Optional[str] = None,
    use_cache: bool = True,
) -> List[Document]:
    """
    The main discovery+verification pipeline for one exam/doc_type
    (optionally filtered by year). Returns a list of Document objects,
    each already run through pdf_validator, with verification_status set
    to VERIFIED, REJECTED, or SOURCE_PAGE_ONLY (never a fabricated URL).
    """
    exam = get_exam(exam_id)
    if exam is None:
        return []

    cache_key = exam_cache.build_cache_key(
        authority=exam["authority_id"], exam=exam_id, document_type=doc_type,
        year=year or "",
    )
    if use_cache:
        cached = exam_cache.get(cache_key)
        if cached is not None:
            return [_document_from_dict(d) for d in cached]

    authority_id = exam["authority_id"]
    source_pages = _source_pages_for(authority_id, doc_type)
    candidates = document_discovery.discover_candidates(
        source_pages=source_pages, exam=exam, doc_type=doc_type, year=year,
    )

    documents: List[Document] = []
    for idx, candidate in enumerate(candidates):
        doc_id = f"{exam_id}:{doc_type}:{candidate.identity.year or 'na'}:{idx}"
        doc = Document(
            id=doc_id,
            exam_id=exam_id,
            authority_id=authority_id,
            doc_type=doc_type,
            title=candidate.link_text,
            source_page=candidate.source_page,
            year=candidate.identity.year,
            shift=candidate.identity.shift,
            doc_set=candidate.identity.doc_set,
            paper=candidate.identity.paper,
            level=candidate.identity.level,
            answer_key_status=candidate.identity.answer_key_status,
        )

        expected_tokens = list(candidate.identity.tokens)
        validation = pdf_validator.validate_pdf_url(candidate.url, expected_tokens=expected_tokens)
        if validation.passed:
            doc.pdf_url = validation.final_url
            doc.mark_verified(reason=f"PDF verified (identity={validation.identity_confidence})")
        else:
            doc.mark_rejected(reason=validation.reason_text())
        documents.append(doc)

    # If nothing verified, fall back to offering the official source page
    # (never a fake PDF) so the user still gets somewhere legitimate to look.
    if not any(d.verification_status == VERIFICATION_VERIFIED for d in documents):
        source_page = _official_source_page_for(authority_id, doc_type)
        if source_page:
            fallback = Document(
                id=f"{exam_id}:{doc_type}:source_only",
                exam_id=exam_id,
                authority_id=authority_id,
                doc_type=doc_type,
                title=f"Official {doc_type.replace('_', ' ').title()} Source",
                source_page=source_page,
                year=year,
            )
            fallback.mark_source_page_only(
                reason="No direct verified PDF found; offering official source page only"
            )
            documents.append(fallback)

    if use_cache:
        exam_cache.set(cache_key, [asdict(d) for d in documents])

    return documents


def _document_from_dict(d: dict) -> Document:
    return Document(**d)


def available_years(exam_id: str, doc_type: str) -> List[str]:
    docs = find_documents(exam_id, doc_type)
    years = sorted({d.year for d in docs if d.year}, reverse=True)
    return years
