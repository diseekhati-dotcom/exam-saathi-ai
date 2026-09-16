"""
pyq_engine.py
-------------
Implements the PYQ / Old Paper flow.

Rules enforced here (per spec section 12/16):
  - Never show the same generic list for every exam — every search is
    scoped to the selected exam's aliases + paper keywords.
  - Never invent a year or a PDF URL — years shown are only years that
    were actually detected on an official page (see official_search.py).
  - Answer keys are never labelled as question papers (doc_type is kept
    and shown separately).
  - If nothing verified is found, say so plainly and offer the official
    archive link instead of pretending it's the paper.
"""

from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services import exam_engine, official_search


async def get_years_for_paper(exam_id: str, level_id: str, paper_id: str) -> dict:
    """
    Returns {
        "years": {year: [PdfResult, ...]},   # question_paper + answer_key docs
        "archive_url": str or None,
    }
    """
    paper = exam_engine.get_paper(exam_id, level_id, paper_id)
    exam = exam_engine.get_exam(exam_id)
    level = exam_engine.get_level(exam_id, level_id)

    results = await official_search.find_pdfs_for_exam(
        exam_id, level_id, paper_id,
        doc_types=["question_paper", "answer_key"],
    )

    # Narrow by level aliases whenever the exam has more than one level, so
    # (e.g.) REET Level 2 documents never leak into a Level 1 search.
    level_aliases = [level.get("name", "")] + level.get("aliases", [])
    exam_levels = exam.get("levels", {})
    if len(exam_levels) > 1 and level_aliases:
        filtered = [
            r for r in results
            if any(a.lower() in r.title.lower() for a in level_aliases if a)
        ]
        if filtered:
            results = filtered

    # Further narrow by paper aliases when the exam has multiple papers
    paper_aliases = [paper.get("name", "")] + paper.get("aliases", [])
    multi_paper = any(len(lvl.get("papers", {})) > 1 for lvl in exam_levels.values())
    if multi_paper and paper_aliases:
        filtered = [
            r for r in results
            if any(a.lower() in r.title.lower() for a in paper_aliases if a)
        ]
        # only apply the narrower filter if it actually found something —
        # otherwise fall back to the exam-level result set rather than
        # showing nothing due to inconsistent official labelling
        if filtered:
            results = filtered

    years: dict[str, list] = {}
    for r in results:
        if r.year:
            years.setdefault(r.year, []).append(r)

    return {
        "years": dict(sorted(years.items(), key=lambda kv: kv[0], reverse=True)),
        "archive_url": exam.get("official_archive"),
        "source_label": exam.get("source_label"),
    }


def kb_years(exam_id: str, level_id: str, paper_id: str, years: dict, archive_url: Optional[str],
             user_data: dict) -> InlineKeyboardMarkup:
    """
    Builds year buttons. Because PDF URLs are long, we cache the actual
    PdfResult objects in user_data and reference them by short index in
    the callback_data, per the "keep callback_data small & safe" rule.
    """
    cache = user_data.setdefault("pyq_cache", {})
    rows = []
    for idx, (year, docs) in enumerate(years.items()):
        key = f"{exam_id}:{level_id}:{paper_id}:{idx}"
        cache[key] = docs
        label = f"📄 {year}"
        rows.append([InlineKeyboardButton(label, callback_data=f"pyq:year:{exam_id}:{level_id}:{paper_id}:{idx}")])

    if archive_url:
        rows.append([InlineKeyboardButton("🌐 Official Archive", url=archive_url)])

    exam = exam_engine.get_exam(exam_id)
    multi_level = len(exam.get("levels", {})) > 1
    back_target = f"pyq:exam:{exam_id}" if multi_level else "menu:pyq"
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=back_target)])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def format_no_results_message(exam_id: str) -> str:
    exam = exam_engine.get_exam(exam_id)
    return (
        f"⚠️ {exam['name']} ke liye official question paper PDF verified nahi mila.\n\n"
        "Yeh PDF official website par abhi available nahi hai ya link badal gaya hoga. "
        "Neeche diye gaye official archive se khud check kar sakte hain."
    )


def format_year_message(exam_id: str, level_id: str, paper_id: str, year: str, docs: list) -> str:
    exam = exam_engine.get_exam(exam_id)
    paper = exam_engine.get_paper(exam_id, level_id, paper_id)
    lines = [f"📝 <b>{exam['name']} — {paper['name']} — {year}</b>", ""]

    qp_docs = [d for d in docs if d.doc_type == "question_paper"]
    ak_docs = [d for d in docs if d.doc_type == "answer_key"]
    other_docs = [d for d in docs if d.doc_type not in ("question_paper", "answer_key")]

    if qp_docs:
        lines.append("📄 Question Paper mil gaya (neeche button se kholein).")
    if ak_docs:
        lines.append("🔑 Answer Key bhi available hai.")
    if not qp_docs and not ak_docs and other_docs:
        lines.append("⚠️ Is document ka type (question paper / answer key) confirm nahi ho paaya — link neeche hai, official source se verify karein.")

    lines.append("")
    lines.append(f"🔎 Source: {exam.get('source_label', 'Official Website')}")
    return "\n".join(lines)


def kb_year_docs(exam_id: str, level_id: str, paper_id: str, docs: list) -> InlineKeyboardMarkup:
    rows = []
    for d in docs:
        if d.doc_type == "question_paper":
            label = f"📄 Question Paper ({d.year})"
        elif d.doc_type == "answer_key":
            label = f"🔑 Answer Key ({d.year})"
        else:
            label = f"📎 Document ({d.year})"
        rows.append([InlineKeyboardButton(label, url=d.url)])

    exam = exam_engine.get_exam(exam_id)
    multi_level = len(exam.get("levels", {})) > 1
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"pyq:paper:{exam_id}:{level_id}:{paper_id}")])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)
