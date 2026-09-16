"""
Source / document-identity verification helpers.

Given the raw link text (and/or URL) discovered on an official archive
page — e.g. "Lab Assistant (Geography) Question Paper 2026 Shift 1" —
extract the structured identity fields the data model calls for: year,
subject, paper, shift, set, level, and a coarse document type guess.

This is regex/heuristic based (no ML, no network) and is used for two
things:
  1. Filtering discovered links down to the ones matching what the user
     actually asked for (right exam variant, right year).
  2. Building `expected_tokens` to pass into pdf_validator's identity
     check so a same-exam/wrong-year or same-exam/wrong-subject PDF is
     rejected rather than silently accepted.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from database.models import DOC_TYPE_SYLLABUS, DOC_TYPE_QUESTION_PAPER, DOC_TYPE_ANSWER_KEY

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_SHIFT_RE = re.compile(r"\bshift\s*-?\s*(\d+|[ivx]+)\b", re.IGNORECASE)
_SET_RE = re.compile(r"\bset\s*-?\s*([a-zA-Z0-9]+)\b", re.IGNORECASE)
_PAPER_RE = re.compile(r"\bpaper\s*-?\s*(\d{1,2}|[ivx]+)\b(?!\d)", re.IGNORECASE)
_LEVEL_RE = re.compile(r"\blevel\s*-?\s*(\d+|[ivx]+)\b", re.IGNORECASE)

_ANSWER_KEY_STATUS_PATTERNS = [
    ("FINAL_REVISED", re.compile(r"final\s*revised|revised\s*final", re.IGNORECASE)),
    ("FINAL", re.compile(r"\bfinal\b", re.IGNORECASE)),
    ("PRIMARY_MODEL", re.compile(r"\bprimary\b|\bmodel\b", re.IGNORECASE)),
    ("PROVISIONAL", re.compile(r"\bprovisional\b|\btentative\b", re.IGNORECASE)),
]

_DOC_TYPE_PATTERNS = [
    (DOC_TYPE_ANSWER_KEY, re.compile(r"answer\s*key|ans\s*key", re.IGNORECASE)),
    (DOC_TYPE_SYLLABUS, re.compile(r"syllabus|exam\s*pattern|scheme\s*of\s*exam", re.IGNORECASE)),
    (DOC_TYPE_QUESTION_PAPER, re.compile(
        r"question\s*paper|old\s*paper|previous\s*paper|paper\s*set|question\s*booklet",
        re.IGNORECASE,
    )),
]


@dataclass
class DocumentIdentity:
    doc_type_guess: Optional[str] = None
    year: Optional[str] = None
    shift: Optional[str] = None
    doc_set: Optional[str] = None
    paper: Optional[str] = None
    level: Optional[str] = None
    answer_key_status: Optional[str] = None
    tokens: List[str] = field(default_factory=list)


def extract_identity(link_text: str, url: str = "") -> DocumentIdentity:
    combined = f"{link_text} {url}"
    ident = DocumentIdentity()

    year_match = _YEAR_RE.search(combined)
    if year_match:
        ident.year = year_match.group(0)

    shift_match = _SHIFT_RE.search(combined)
    if shift_match:
        ident.shift = shift_match.group(1)

    set_match = _SET_RE.search(combined)
    if set_match:
        ident.doc_set = set_match.group(1)

    paper_match = _PAPER_RE.search(combined)
    if paper_match:
        ident.paper = paper_match.group(1)

    level_match = _LEVEL_RE.search(combined)
    if level_match:
        ident.level = level_match.group(1)

    for doc_type, pattern in _DOC_TYPE_PATTERNS:
        if pattern.search(combined):
            ident.doc_type_guess = doc_type
            break

    if ident.doc_type_guess == DOC_TYPE_ANSWER_KEY:
        for status, pattern in _ANSWER_KEY_STATUS_PATTERNS:
            if pattern.search(combined):
                ident.answer_key_status = status
                break

    # tokens used for pdf_validator's expected_tokens identity check
    tokens = []
    if ident.year:
        tokens.append(ident.year)
    if ident.shift:
        tokens.append(f"shift{ident.shift}")
        tokens.append(f"shift-{ident.shift}")
    if ident.doc_set:
        tokens.append(f"set{ident.doc_set}")
    if ident.paper:
        tokens.append(f"paper{ident.paper}")
    ident.tokens = tokens
    return ident


def matches_requested(
    identity: DocumentIdentity,
    requested_year: Optional[str] = None,
    requested_doc_type: Optional[str] = None,
) -> bool:
    """Return False if the discovered document clearly does NOT match what
    was requested (used to reject wrong-year / wrong-type documents before
    they are ever shown to a user)."""
    if requested_year and identity.year and identity.year != requested_year:
        return False
    if requested_doc_type and identity.doc_type_guess and identity.doc_type_guess != requested_doc_type:
        return False
    return True
