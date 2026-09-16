"""
Exam command handlers — logic layer.

Deliberately returns plain dict/list data (never python-telegram-bot
objects) so this entire module can be unit-tested without the `telegram`
package installed. main.py's adapter layer turns these plain structures
into real InlineKeyboardMarkup/InlineKeyboardButton objects and wires
them to python-telegram-bot's Application.

Button spec shape used throughout this module:
    {"text": str, "callback_data": str}   -> a callback (in-bot navigation)
    {"text": str, "url": str}             -> a URL button (opens a link)

Message spec shape:
    {"text": str, "buttons": List[List[button_spec]], "parse_mode": "HTML"}
"""
from typing import List, Optional

from database.models import (
    Document,
    DOC_TYPE_SYLLABUS,
    DOC_TYPE_QUESTION_PAPER,
    DOC_TYPE_ANSWER_KEY,
    VERIFICATION_VERIFIED,
    VERIFICATION_SOURCE_PAGE_ONLY,
)
from services import authority_registry, exam_service

DOC_TYPE_LABELS = {
    DOC_TYPE_SYLLABUS: "📘 Syllabus",
    DOC_TYPE_QUESTION_PAPER: "📄 Question Papers",
    DOC_TYPE_ANSWER_KEY: "🔑 Answer Keys",
}

NOT_FOUND_TEXT = (
    "❌ Exam information could not be verified right now.\n\n"
    "I couldn't confidently match that to a known Rajasthan exam. "
    "Try a shorter name, e.g. <code>/exam SI</code>, <code>/exam Patwar</code>, "
    "or <code>/exam REET Level 1</code>."
)

UNAVAILABLE_TEXT = "⚠️ Official document is currently unavailable."


def build_exam_not_found_message(query: str) -> dict:
    return {"text": NOT_FOUND_TEXT, "buttons": [], "parse_mode": "HTML"}


def build_exam_card(exam_id: str) -> Optional[dict]:
    exam = exam_service.get_exam(exam_id)
    if exam is None:
        return None
    authority = authority_registry.get_authority(exam["authority_id"])
    authority_name = authority.name if authority else exam["authority_id"]

    text = (
        f"🎓 <b>Exam:</b> {exam['name']}\n"
        f"🏢 <b>Authority:</b> {authority_name}\n"
    )
    buttons = [
        [{"text": DOC_TYPE_LABELS[DOC_TYPE_SYLLABUS], "callback_data": f"dt:{exam_id}:{DOC_TYPE_SYLLABUS}"}],
        [{"text": DOC_TYPE_LABELS[DOC_TYPE_QUESTION_PAPER], "callback_data": f"dt:{exam_id}:{DOC_TYPE_QUESTION_PAPER}"}],
        [{"text": DOC_TYPE_LABELS[DOC_TYPE_ANSWER_KEY], "callback_data": f"dt:{exam_id}:{DOC_TYPE_ANSWER_KEY}"}],
    ]
    if authority and authority.official_pages:
        home = authority.official_pages.get("home") or next(iter(authority.official_pages.values()))
        buttons.append([{"text": "🌐 Official Source", "url": home}])

    return {"text": text, "buttons": buttons, "parse_mode": "HTML"}


def build_years_menu(exam_id: str, doc_type: str) -> dict:
    exam = exam_service.get_exam(exam_id)
    if exam is None:
        return build_exam_not_found_message(exam_id)

    years = exam_service.available_years(exam_id, doc_type)
    label = DOC_TYPE_LABELS.get(doc_type, doc_type)

    if not years:
        # No verified year-specific documents discovered — still show a
        # source-page fallback if one exists, never a fake year list.
        docs = exam_service.find_documents(exam_id, doc_type)
        buttons = _document_buttons(docs)
        text = f"{label}\n\n{UNAVAILABLE_TEXT}" if not buttons else f"{label}"
        return {"text": text, "buttons": buttons, "parse_mode": "HTML"}

    buttons = [
        [{"text": year, "callback_data": f"yr:{exam_id}:{doc_type}:{year}"}]
        for year in years
    ]
    return {"text": f"{label}\n\nSelect a year:", "buttons": buttons, "parse_mode": "HTML"}


def build_documents_for_year(exam_id: str, doc_type: str, year: str) -> dict:
    label = DOC_TYPE_LABELS.get(doc_type, doc_type)
    docs = exam_service.find_documents(exam_id, doc_type, year=year)
    docs = [d for d in docs if d.year == year or d.verification_status == VERIFICATION_SOURCE_PAGE_ONLY]
    buttons = _document_buttons(docs)
    if not buttons:
        text = f"{label} — {year}\n\n{UNAVAILABLE_TEXT}"
    else:
        text = f"{label} — {year}"
    return {"text": text, "buttons": buttons, "parse_mode": "HTML"}


def _document_title(doc: Document) -> str:
    parts = []
    if doc.paper:
        parts.append(f"Paper {doc.paper}")
    if doc.shift:
        parts.append(f"Shift {doc.shift}")
    if doc.doc_set:
        parts.append(f"Set {doc.doc_set}")
    if doc.level:
        parts.append(f"Level {doc.level}")
    if doc.answer_key_status:
        parts.append(doc.answer_key_status.replace("_", " ").title())
    if parts:
        return " – ".join(parts)
    return doc.title[:60] if doc.title else "Document"


def _document_buttons(docs: List[Document]) -> List[List[dict]]:
    """
    Build one button per document. Only two kinds of button are ever
    produced:
      - VERIFIED  -> a URL button pointing at doc.pdf_url (the final,
        redirect-resolved, magic-byte-checked PDF URL — never the
        archive/listing page it was discovered on).
      - SOURCE_PAGE_ONLY -> a clearly-labelled "🌐 Official Source" URL
        button pointing at the source page, never disguised as a PDF.
    REJECTED documents produce no button at all (never shown as an
    option), satisfying "do not create empty/fake buttons".
    """
    buttons: List[List[dict]] = []
    for doc in docs:
        if doc.verification_status == VERIFICATION_VERIFIED and doc.pdf_url:
            icon = {
                DOC_TYPE_SYLLABUS: "📘",
                DOC_TYPE_QUESTION_PAPER: "📄",
                DOC_TYPE_ANSWER_KEY: "🔑",
            }.get(doc.doc_type, "📄")
            text = f"{icon} Download {_document_title(doc)} (PDF)"
            buttons.append([{"text": text, "url": doc.pdf_url}])
        elif doc.verification_status == VERIFICATION_SOURCE_PAGE_ONLY and doc.source_page:
            buttons.append([{"text": "🌐 Official Source", "url": doc.source_page}])
    return buttons
