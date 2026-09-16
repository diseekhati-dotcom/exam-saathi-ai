"""
document_discovery.py
----------------------
The generic "find syllabus / question papers / answer keys for ANY
Rajasthan exam" engine described in the spec. It deliberately reuses the
low-level fetch/extract primitives already in `official_search.py`
(fetch_page, extract_pdf_links, is_relevant) instead of duplicating a
second scraper — it only adds what's new:

  - tiered classification (Final/Revised Final > Primary > Provisional
    for answer keys; Master Question Paper > regular for papers)
  - paper-number detection (Paper I/II/III... or Paper 1/2/3...)
  - per-(year, paper) "best document" selection using those tiers
  - PDF verification via pdf_validator before anything is returned
  - caching + rate limiting via exam_cache

Nothing here invents a PDF, a year, or a paper number that wasn't
actually present on an official archive page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from services import official_search, pdf_validator, exam_cache

PAPER_NUM_RE = re.compile(r"paper[\s\-]*(?:no\.?|number)?[\s\-]*([ivx]+|\d{1,2})(?!\d)", re.IGNORECASE)
ROMAN_MAP = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}

# Answer-key tiers: higher number = higher priority
ANSWER_KEY_TIERS = {
    "revised_final": 4,
    "final": 3,
    "primary": 2,
    "provisional": 1,
    "unknown": 0,
}
ANSWER_KEY_TIER_KEYWORDS = [
    (["revised final", "revised answer key"], "revised_final"),
    (["final answer key", "final key"], "final"),
    (["primary answer key"], "primary"),
    (["provisional answer key", "provisional key"], "provisional"),
]

QUESTION_PAPER_TIERS = {"master": 2, "regular": 1, "unknown": 0}
QP_TIER_KEYWORDS = [
    (["master question paper", "master paper"], "master"),
]

MAX_VERIFY_PER_REQUEST = 12  # cap how many links we actually HEAD-verify per call, for speed


@dataclass
class DocEntry:
    title: str
    url: str
    doc_type: str          # syllabus | question_paper | answer_key
    year: Optional[str]
    paper_number: Optional[int]
    tier_label: str
    tier_rank: int
    verified: bool
    source_domain: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title, "url": self.url, "doc_type": self.doc_type,
            "year": self.year, "paper_number": self.paper_number,
            "tier_label": self.tier_label, "tier_rank": self.tier_rank,
            "verified": self.verified, "source_domain": self.source_domain,
        }


def _detect_paper_number(text: str) -> Optional[int]:
    m = PAPER_NUM_RE.search(text.lower())
    if not m:
        return None
    raw = m.group(1).lower()
    if raw.isdigit():
        return int(raw)
    return ROMAN_MAP.get(raw)


def _answer_key_tier(text: str) -> tuple[str, int]:
    hay = text.lower()
    for keywords, label in ANSWER_KEY_TIER_KEYWORDS:
        if any(k in hay for k in keywords):
            return label, ANSWER_KEY_TIERS[label]
    return "unknown", ANSWER_KEY_TIERS["unknown"]


def _question_paper_tier(text: str) -> tuple[str, int]:
    hay = text.lower()
    for keywords, label in QP_TIER_KEYWORDS:
        if any(k in hay for k in keywords):
            return label, QUESTION_PAPER_TIERS[label]
    return "regular", QUESTION_PAPER_TIERS["regular"]


async def _fetch_candidates(page_url: str) -> list[tuple[str, str]]:
    """Fetch + extract PDF links from one archive page, cached."""
    cache_key = exam_cache.page_cache.make_key("page", page_url)
    cached = exam_cache.page_cache.get(cache_key)
    if cached is not None:
        return cached

    await exam_cache.rate_limiter.wait(page_url)
    html = await official_search.fetch_page(page_url)
    if not html:
        exam_cache.page_cache.set(cache_key, [], ttl_seconds=5 * 60)  # short TTL for failures
        return []

    links = official_search.extract_pdf_links(html, page_url)
    exam_cache.page_cache.set(cache_key, links)
    return links


async def discover_document_type(exam_entry: dict, authority: dict, doc_type: str) -> list[DocEntry]:
    """
    Discover + verify all documents of one type (syllabus / question_paper /
    answer_key) for one exam, from one authority's configured archive
    pages. Returns only verified, classified, deduplicated entries.
    """
    cache_key = exam_cache.doc_cache.make_key("doc", exam_entry["id"], authority["id"], doc_type)
    cached = exam_cache.doc_cache.get(cache_key)
    if cached is not None:
        return cached

    pages = authority.get("doc_pages", {}).get(doc_type, [])
    if not pages:
        exam_cache.doc_cache.set(cache_key, [])
        return []

    aliases = [exam_entry["name"]] + exam_entry.get("aliases", [])
    candidates: list[DocEntry] = []
    seen_urls = set()

    for page_url in pages:
        for text, href in await _fetch_candidates(page_url):
            if href in seen_urls:
                continue
            if not official_search.is_relevant(text, href, aliases):
                continue

            # Some authorities (e.g. RBSE/REET) publish syllabus, question
            # papers, and answer keys all linked from the SAME archive
            # page. Without this check, a syllabus PDF on that page would
            # leak into answer_key results as an unclassified "Document"
            # just because it was fetched while looking for answer keys.
            # Gate strictly by the link's own detected type.
            natural_type = official_search.classify_pdf(text, href)
            if doc_type == "answer_key" and natural_type != "answer_key":
                continue
            if doc_type == "question_paper" and natural_type != "question_paper":
                continue
            if doc_type == "syllabus" and natural_type not in ("syllabus", "notification"):
                continue

            seen_urls.add(href)

            year = official_search.detect_year(text, href)
            paper_number = _detect_paper_number(text)

            if doc_type == "answer_key":
                tier_label, tier_rank = _answer_key_tier(text)
            elif doc_type == "question_paper":
                tier_label, tier_rank = _question_paper_tier(text)
            else:
                tier_label, tier_rank = "syllabus", 1

            candidates.append(DocEntry(
                title=text[:150], url=href, doc_type=doc_type, year=year,
                paper_number=paper_number, tier_label=tier_label, tier_rank=tier_rank,
                verified=False, source_domain=urlparse(href).netloc,
            ))

    # --- Priority selection: keep the best-tier doc per (year, paper_number) ---
    best_by_group: dict[tuple, DocEntry] = {}
    for c in candidates:
        group_key = (c.year, c.paper_number)
        existing = best_by_group.get(group_key)
        if existing is None or c.tier_rank > existing.tier_rank:
            best_by_group[group_key] = c
    selected = list(best_by_group.values())

    # Sort newest year first, then paper number ascending
    def sort_key(d: DocEntry):
        year_val = int(d.year) if d.year else -1
        paper_val = d.paper_number if d.paper_number is not None else 0
        return (-year_val, paper_val)
    selected.sort(key=sort_key)

    # --- Verify (capped) so we never show a dead/fake link ---
    verified_results: list[DocEntry] = []
    for entry in selected[:MAX_VERIFY_PER_REQUEST]:
        result = await pdf_validator.verify_pdf_url(entry.url)
        if result.ok:
            entry.verified = True
            if result.final_url:
                entry.url = result.final_url
            verified_results.append(entry)
        # unverified/broken links are silently dropped — never shown

    exam_cache.doc_cache.set(cache_key, verified_results)
    return verified_results


async def discover_documents(exam_entry: dict, authority: dict) -> dict[str, list[DocEntry]]:
    """Discover syllabus + question_paper + answer_key together for one exam."""
    result = {}
    for doc_type in ("syllabus", "question_paper", "answer_key"):
        result[doc_type] = await discover_document_type(exam_entry, authority, doc_type)
    return result
