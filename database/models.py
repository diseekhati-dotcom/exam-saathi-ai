"""
Data model definitions.

Kept as plain dataclasses (not an ORM) so the whole project has zero
heavyweight dependencies beyond `requests` and the Telegram bot library.
database/db.py persists these to SQLite.
"""
from dataclasses import dataclass, field
from typing import Optional, List
import time


@dataclass
class Authority:
    id: str
    name: str
    official_domain: str
    official_pages: dict = field(default_factory=dict)
    verification_status: str = "UNVERIFIED"
    notes: str = ""


@dataclass
class Exam:
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    authority_id: str = ""
    category: str = ""
    levels: List[str] = field(default_factory=list)
    official_source: str = ""


VERIFICATION_VERIFIED = "VERIFIED"
VERIFICATION_REJECTED = "REJECTED"
VERIFICATION_UNVERIFIED = "UNVERIFIED"
VERIFICATION_SOURCE_PAGE_ONLY = "SOURCE_PAGE_ONLY"  # legit page, but no direct PDF found

DOC_TYPE_SYLLABUS = "SYLLABUS"
DOC_TYPE_QUESTION_PAPER = "QUESTION_PAPER"
DOC_TYPE_ANSWER_KEY = "ANSWER_KEY"

ANSWER_KEY_STATUS_ORDER = ["PROVISIONAL", "PRIMARY_MODEL", "FINAL", "FINAL_REVISED"]


@dataclass
class Document:
    id: str
    exam_id: str
    authority_id: str
    doc_type: str  # SYLLABUS | QUESTION_PAPER | ANSWER_KEY
    title: str
    source_page: str  # the page the link was discovered on (archive/listing page)
    pdf_url: Optional[str] = None  # the FINAL verified direct-PDF URL, or None
    year: Optional[str] = None
    subject: Optional[str] = None
    paper: Optional[str] = None
    shift: Optional[str] = None
    doc_set: Optional[str] = None
    level: Optional[str] = None
    answer_key_status: Optional[str] = None  # PROVISIONAL/PRIMARY_MODEL/FINAL/FINAL_REVISED
    verification_status: str = VERIFICATION_UNVERIFIED
    verification_reason: str = ""
    verified_at: Optional[float] = None

    def mark_verified(self, reason: str = "") -> None:
        self.verification_status = VERIFICATION_VERIFIED
        self.verification_reason = reason
        self.verified_at = time.time()

    def mark_rejected(self, reason: str) -> None:
        self.verification_status = VERIFICATION_REJECTED
        self.verification_reason = reason
        self.verified_at = time.time()

    def mark_source_page_only(self, reason: str = "") -> None:
        self.verification_status = VERIFICATION_SOURCE_PAGE_ONLY
        self.verification_reason = reason
        self.verified_at = time.time()
