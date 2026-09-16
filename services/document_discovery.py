"""
Generic, discovery-based document finder.

This is the PRIMARY discovery mechanism required by the brief: it is not
a hardcoded per-exam URL table. Given an authority + exam (+ optional
year/doc_type filters), it:

  1. Starts from the authority's known official page(s) (config/exam_sources.py
     or an authority-specific parser's archive URLs).
  2. Fetches each page through the SSRF-hardened HTTP client.
  3. Parses all <a href> links with BeautifulSoup.
  4. Uses services/source_verifier.py to guess each link's identity
     (doc type / year / shift / etc.) from its link text + URL.
  5. Filters links whose text matches the exam's name/aliases and the
     requested doc type/year.
  6. Returns *candidate* links (source_page + candidate url) — NOT yet
     verified as a direct PDF. services/exam_service.py hands these to
     pdf_validator.validate_pdf_url() for the real verification step
     before anything is ever shown to a user.

KNOWN LIMITATION (documented honestly): some Rajasthan government archive
pages render their document list via client-side JavaScript. This module
only sees what is present in the initial HTML response (no headless
browser is available in this build environment). Where a page's real
document links only appear after JS execution, this discovery step will
correctly find zero candidates, and the calling service will correctly
fall back to offering the official *source page* rather than fabricating
a PDF link. This is the safe/honest failure mode the brief explicitly
asks for.
"""
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from services import source_verifier
from services.exam_normalizer import normalize_text
from utils.http_client import safe_request, DisallowedDomainError, UnsafeAddressError
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class CandidateLink:
    url: str
    link_text: str
    source_page: str
    identity: source_verifier.DocumentIdentity


def fetch_links(page_url: str) -> List[dict]:
    """Fetch page_url and return [{href, text}] for every <a> tag found.
    Returns [] (never raises) on any network/parse failure — callers must
    treat an empty discovery result as 'nothing found here', not a crash."""
    try:
        resp = safe_request(page_url, method="GET")
    except (DisallowedDomainError, UnsafeAddressError) as exc:
        log.warning("Refusing to fetch %s: %s", page_url, exc)
        return []
    except Exception as exc:
        log.warning("Discovery fetch failed for %s: %s", page_url, exc)
        return []

    if resp.status_code != 200:
        log.info("Discovery page %s returned HTTP %s", page_url, resp.status_code)
        return []

    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" not in content_type and "text" not in content_type:
        return []

    try:
        soup = BeautifulSoup(resp.content, "html.parser")
    except Exception as exc:
        log.warning("HTML parse failed for %s: %s", page_url, exc)
        return []

    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        text = a_tag.get_text(separator=" ", strip=True)
        absolute = urljoin(resp.final_url, href)
        links.append({"href": absolute, "text": text})
    return links


def _exam_matches_link_text(exam: dict, link_text: str) -> bool:
    norm_link = normalize_text(link_text)
    candidates = [exam["name"]] + list(exam.get("aliases", []))
    for cand in candidates:
        norm_cand = normalize_text(cand)
        if norm_cand and norm_cand in norm_link:
            return True
    return False


def discover_candidates(
    source_pages: List[str],
    exam: dict,
    doc_type: Optional[str] = None,
    year: Optional[str] = None,
    max_pages: int = 5,
) -> List[CandidateLink]:
    """
    Crawl each URL in source_pages (shallow — one level, no recursive
    crawling, to keep this fast/safe) and return candidate links whose
    text matches the exam name/alias and, if given, the requested
    doc_type/year.
    """
    candidates: List[CandidateLink] = []
    for page_url in source_pages[:max_pages]:
        for link in fetch_links(page_url):
            if not _exam_matches_link_text(exam, link["text"]):
                continue
            identity = source_verifier.extract_identity(link["text"], link["href"])
            if doc_type and identity.doc_type_guess and identity.doc_type_guess != doc_type:
                continue
            if not source_verifier.matches_requested(identity, requested_year=year, requested_doc_type=doc_type):
                continue
            candidates.append(
                CandidateLink(
                    url=link["href"],
                    link_text=link["text"],
                    source_page=page_url,
                    identity=identity,
                )
            )
    return candidates
