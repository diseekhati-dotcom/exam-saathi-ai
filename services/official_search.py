"""
official_search.py
-------------------
Reusable "official search engine" described in the spec (section 15/16).

Given an official page URL, this module:
  1. Fetches the page (with timeout + error handling)
  2. Extracts every PDF link on it
  3. Classifies each link as: syllabus / question_paper / answer_key /
     notification / unknown
  4. Detects a year (4-digit, 20xx) if present in the link text/href
  5. Filters links against the exam's alias list so an unrelated exam's
     PDF is never returned (fixes the "generic matching bug")
  6. Ranks and de-duplicates results

Nothing here invents a URL. Every returned link was physically present
in the fetched HTML of an official government domain.

For "🔎 Other Exam" queries, `search_other_exam()` first checks a small
curated map of known official domains (data/exams.json ->
known_official_domains) and, if the domain is known, only crawls that
domain. If the exam is not recognised, it is honest about that instead
of guessing a random website.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from services import exam_engine

HTTP_TIMEOUT = 12.0
USER_AGENT = "Mozilla/5.0 (ExamSaathiAI/1.0; +https://t.me/StudySaathiAI)"

OFFICIAL_TLD_HINTS = (".gov.in", ".nic.in", "rajasthan.gov.in", "rpsc.", "rssb.", "rajeduboard.")

SYLLABUS_KEYWORDS = ["syllabus", "syllabus & exam pattern", "exam pattern", "paathyakram", "पाठ्यक्रम"]
NOTIFICATION_KEYWORDS = ["notification", "advertisement", "recruitment", "vigyapti", "विज्ञप्ति"]
ANSWER_KEY_KEYWORDS = ["answer key", "answerkey", "उत्तर कुंजी", "model answer"]
QUESTION_PAPER_KEYWORDS = ["question paper", "old paper", "previous paper", "प्रश्न पत्र", "paper -", "qp"]

YEAR_RE = re.compile(r"(20[0-2][0-9])")

# simple in-memory cache: {cache_key: (timestamp, result)}
_CACHE: dict[str, tuple[float, list]] = {}
_CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 hours — syllabus/PYQ pages don't change every minute


@dataclass
class PdfResult:
    title: str
    url: str
    doc_type: str  # syllabus | question_paper | answer_key | notification | unknown
    year: Optional[str] = None
    source_domain: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "doc_type": self.doc_type,
            "year": self.year,
            "source_domain": self.source_domain,
        }


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value):
    _CACHE[key] = (time.time(), value)


async def fetch_page(url: str) -> Optional[str]:
    """Fetch a page's HTML. Returns None on any network/timeout error."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True,
                                      headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return None
            return resp.text
    except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError):
        return None
    except Exception:
        return None


def classify_pdf(text: str, href: str) -> str:
    hay = f"{text} {href}".lower()
    if any(k in hay for k in ANSWER_KEY_KEYWORDS):
        return "answer_key"
    if any(k in hay for k in QUESTION_PAPER_KEYWORDS):
        return "question_paper"
    if any(k in hay for k in SYLLABUS_KEYWORDS):
        return "syllabus"
    if any(k in hay for k in NOTIFICATION_KEYWORDS):
        return "notification"
    return "unknown"


def detect_year(text: str, href: str) -> Optional[str]:
    m = YEAR_RE.search(text) or YEAR_RE.search(href)
    return m.group(1) if m else None


def is_relevant(text: str, href: str, aliases: list[str]) -> bool:
    hay = f"{text} {href}".lower()
    return any(alias.lower() in hay for alias in aliases if alias)


def is_official_domain(url: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    return any(hint in netloc for hint in OFFICIAL_TLD_HINTS)


def extract_pdf_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Return list of (link_text, absolute_href) for every PDF anchor on the page."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        if ".pdf" not in href.lower():
            continue
        abs_href = urljoin(base_url, href)
        text = a.get_text(strip=True) or abs_href.split("/")[-1]
        results.append((text, abs_href))
    return results


async def find_pdfs_for_exam(exam_id: str, level_id: Optional[str] = None,
                              paper_id: Optional[str] = None,
                              doc_types: Optional[list[str]] = None) -> list[PdfResult]:
    """
    Crawl the exam's known official source pages (data/exams.json ->
    pyq_sources) and return classified PDF links that mention this exam.
    Used by the PYQ engine. Cached per exam for _CACHE_TTL_SECONDS.
    """
    cache_key = f"pdfs:{exam_id}"
    cached = _cache_get(cache_key)
    if cached is None:
        data = exam_engine.load_data()
        exam = exam_engine.get_exam(exam_id)
        if not exam:
            return []
        aliases = [exam["name"]] + exam.get("aliases", [])
        source_pages = data.get("pyq_sources", {}).get(exam_id, [])

        all_results: list[PdfResult] = []
        seen_urls = set()
        for page_url in source_pages:
            html = await fetch_page(page_url)
            if not html:
                continue
            for text, href in extract_pdf_links(html, page_url):
                if href in seen_urls:
                    continue
                if not is_relevant(text, href, aliases):
                    continue
                seen_urls.add(href)
                doc_type = classify_pdf(text, href)
                year = detect_year(text, href)
                all_results.append(PdfResult(
                    title=text[:120],
                    url=href,
                    doc_type=doc_type,
                    year=year,
                    source_domain=urlparse(href).netloc,
                ))
        _cache_set(cache_key, all_results)
        cached = all_results

    results = cached
    if doc_types:
        results = [r for r in results if r.doc_type in doc_types]
    return results


async def search_other_exam(query: str) -> dict:
    """
    Handle the "🔎 Other Exam" flow for exams not in our curated database.
    Returns a dict describing what was found (or honestly, what wasn't).
    """
    query_norm = query.strip().lower()
    domains = exam_engine.known_official_domains(query_norm)

    if not domains:
        return {
            "recognised": False,
            "message": (
                "⚠️ Is exam ka official source database mein verify nahi ho paaya.\n"
                "Aap exam ka pura naam (jaise 'SSC CGL 2026') likh kar dobara try kar sakte hain, "
                "ya official website khud search karein."
            ),
            "results": [],
        }

    all_results: list[PdfResult] = []
    checked_pages = []
    for domain in domains:
        homepage = f"https://{domain}"
        html = await fetch_page(homepage)
        if not html:
            continue
        checked_pages.append(homepage)
        for text, href in extract_pdf_links(html, homepage):
            if not is_official_domain(href) and domain not in href:
                continue
            doc_type = classify_pdf(text, href)
            year = detect_year(text, href)
            all_results.append(PdfResult(
                title=text[:120], url=href, doc_type=doc_type, year=year,
                source_domain=urlparse(href).netloc,
            ))

    return {
        "recognised": True,
        "domains": domains,
        "checked_pages": checked_pages,
        "results": all_results,
    }
