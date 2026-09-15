"""
exam_engine.py
--------------
Loads static exam/syllabus data from data/exams.json and provides:
  - lookup helpers
  - inline keyboard builders for the Syllabus flow
  - syllabus message formatting
  - lightweight natural-language matching (no external NLP deps)

IMPORTANT (anti-hallucination):
This module NEVER invents syllabus numbers. If a field is `null` in
exams.json it is rendered as "verify in official PDF" rather than a
fabricated number.
"""

from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "exams.json")

_cache: Optional[dict] = None


def load_data() -> dict:
    """Load and cache exams.json. Re-reads if the file changes on disk."""
    global _cache
    if _cache is None:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def reload_data() -> dict:
    global _cache
    _cache = None
    return load_data()


# ---------------------------------------------------------------------------
# Basic lookups
# ---------------------------------------------------------------------------

def get_exam(exam_id: str) -> Optional[dict]:
    return load_data()["exams"].get(exam_id)


def get_all_exams() -> dict:
    return load_data()["exams"]


def get_level(exam_id: str, level_id: str) -> Optional[dict]:
    exam = get_exam(exam_id)
    if not exam:
        return None
    return exam.get("levels", {}).get(level_id)


def get_paper(exam_id: str, level_id: str, paper_id: str) -> Optional[dict]:
    level = get_level(exam_id, level_id)
    if not level:
        return None
    return level.get("papers", {}).get(paper_id)


def known_official_domains(query: str) -> list[str]:
    query = query.lower().strip()
    domains_map = load_data().get("known_official_domains", {})
    for key, domains in domains_map.items():
        if key in query or query in key:
            return domains
    return []


# ---------------------------------------------------------------------------
# Keyboards - Syllabus flow
# ---------------------------------------------------------------------------

def kb_main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📋 Syllabus", callback_data="menu:syllabus"),
         InlineKeyboardButton("📝 PYQ / Old Paper", callback_data="menu:pyq")],
        [InlineKeyboardButton("🧠 Mock Test", callback_data="menu:mock"),
         InlineKeyboardButton("📝 Notes", callback_data="menu:notes")],
        [InlineKeyboardButton("🤖 Ask AI", callback_data="menu:ai"),
         InlineKeyboardButton("⏰ Reminder", callback_data="menu:reminder")],
    ]
    return InlineKeyboardMarkup(rows)


def kb_exam_list(prefix: str) -> InlineKeyboardMarkup:
    """prefix is 'syl' or 'pyq' — determines the callback namespace."""
    exams = get_all_exams()
    rows = []
    row = []
    for exam_id, exam in exams.items():
        row.append(InlineKeyboardButton(exam["name"], callback_data=f"{prefix}:exam:{exam_id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if prefix == "syl":
        rows.append([InlineKeyboardButton("🔎 Other Exam", callback_data="syl:other")])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def kb_level_list(prefix: str, exam_id: str) -> InlineKeyboardMarkup:
    exam = get_exam(exam_id)
    rows = []
    for level_id, level in exam.get("levels", {}).items():
        rows.append([InlineKeyboardButton(level["name"], callback_data=f"{prefix}:level:{exam_id}:{level_id}")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"menu:{'syllabus' if prefix == 'syl' else 'pyq'}")])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def kb_group_list(exam_id: str, level_id: str) -> InlineKeyboardMarkup:
    level = get_level(exam_id, level_id)
    rows = []
    for group_id, group in level.get("subject_groups", {}).items():
        rows.append([InlineKeyboardButton(group["name"], callback_data=f"syl:group:{exam_id}:{level_id}:{group_id}")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"syl:exam:{exam_id}")])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def kb_paper_list(prefix: str, exam_id: str, level_id: str) -> InlineKeyboardMarkup:
    level = get_level(exam_id, level_id)
    rows = []
    for paper_id, paper in level.get("papers", {}).items():
        rows.append([InlineKeyboardButton(paper["name"], callback_data=f"{prefix}:paper:{exam_id}:{level_id}:{paper_id}")])
    back_target = f"{prefix}:exam:{exam_id}" if len(get_exam(exam_id).get("levels", {})) > 1 else f"menu:{'syllabus' if prefix == 'syl' else 'pyq'}"
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=back_target)])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def kb_syllabus_detail(exam_id: str, level_id: str, paper_id: str) -> InlineKeyboardMarkup:
    exam = get_exam(exam_id)
    paper = get_paper(exam_id, level_id, paper_id)
    rows = []
    pdf_url = paper.get("official_pdf") or exam.get("official_syllabus_pdf")
    if pdf_url:
        rows.append([InlineKeyboardButton("📄 Official Syllabus PDF", url=pdf_url)])
    elif exam.get("official_archive"):
        rows.append([InlineKeyboardButton("🌐 Official Website", url=exam["official_archive"])])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"syl:exam:{exam_id}")])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------

def format_syllabus_message(exam_id: str, level_id: str, paper_id: str, group_id: Optional[str] = None) -> str:
    exam = get_exam(exam_id)
    level = get_level(exam_id, level_id)
    paper = get_paper(exam_id, level_id, paper_id)

    lines = ["📋 <b>SYLLABUS</b>", ""]
    lines.append(f"🎓 Exam: {exam['name']}")
    if level.get("classes"):
        lines.append(f"📚 Level: {level['name']} ({level['classes']})")
    else:
        lines.append(f"📚 Level: {level['name']}")
    lines.append(f"📄 Paper: {paper['name']}")
    lines.append("")

    if paper.get("pattern_verified"):
        lines.append(f"📊 Questions: {paper['questions']}")
        lines.append(f"🎯 Marks: {paper['marks']}")
        lines.append(f"⏱ Time: {paper['duration']}")
    else:
        lines.append("⚠️ Exam pattern (questions/marks/time) verify karein official PDF mein — yahan galat number nahi diya ja raha.")
    lines.append("")

    subjects = paper.get("subjects", [])
    if group_id:
        group = get_level(exam_id, level_id)["subject_groups"][group_id]
        lines.append(f"📚 Subject Group: {group['name']}")
    if subjects:
        lines.append("📚 Subjects:")
        for s in subjects:
            lines.append(f"• {s}")
    else:
        lines.append("📚 Subject-wise detailed syllabus abhi database mein nahi hai — official PDF check karein.")

    lines.append("")
    lines.append(f"🔎 Source: {exam.get('source_label', 'Official Website')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Natural language matching (lightweight, dependency-free)
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _contains_alias(cand_norm: str, norm_text: str) -> bool:
    """
    Substring containment, but word-boundary-safe for short aliases.
    Without this, a short alias like "si" is a trivial substring of
    completely unrelated words (e.g. "as-SI-stant"), causing false
    matches. Longer aliases (>=5 chars) are safe with plain containment.
    """
    if not cand_norm:
        return False
    if len(cand_norm) >= 5:
        return cand_norm in norm_text
    return re.search(rf"\b{re.escape(cand_norm)}\b", norm_text) is not None


def match_exam(text: str) -> tuple[Optional[str], float]:
    """Return (exam_id, confidence 0-1) best guess for free text."""
    norm_text = _norm(text)
    best_id, best_score = None, 0.0
    for exam_id, exam in get_all_exams().items():
        candidates = [exam["name"]] + exam.get("aliases", [])
        for cand in candidates:
            cand_norm = _norm(cand)
            if not cand_norm:
                continue
            if _contains_alias(cand_norm, norm_text):
                score = 0.9 + 0.1 * (len(cand_norm) / max(len(norm_text), 1))
                score = min(score, 1.0)
            elif len(cand_norm) >= 4:
                # Fuzzy fallback only for longer aliases (typo tolerance).
                # SequenceMatcher.ratio() is unreliable for short strings vs
                # long unrelated text (e.g. "si" scores ~0.9 against "Lab
                # Assistant" purely by chance) — dampen by length ratio so
                # very mismatched lengths can't produce a false positive.
                raw = _similarity(cand_norm, norm_text)
                length_ratio = min(len(cand_norm), len(norm_text)) / max(len(cand_norm), len(norm_text))
                score = raw * length_ratio
            else:
                score = 0.0
            if score > best_score:
                best_id, best_score = exam_id, score
    return best_id, best_score


def match_level(exam_id: str, text: str) -> Optional[str]:
    exam = get_exam(exam_id)
    if not exam:
        return None
    norm_text = _norm(text)
    for level_id, level in exam.get("levels", {}).items():
        candidates = [level["name"]] + level.get("aliases", [])
        for cand in candidates:
            if _norm(cand) in norm_text:
                return level_id
    return None


def match_paper(exam_id: str, level_id: str, text: str) -> Optional[str]:
    level = get_level(exam_id, level_id)
    if not level:
        return None
    norm_text = _norm(text)
    for paper_id, paper in level.get("papers", {}).items():
        candidates = [paper["name"]] + paper.get("aliases", [])
        for cand in candidates:
            if _norm(cand) in norm_text:
                return paper_id
    return None


def wants_pyq(text: str) -> bool:
    keywords = ["old paper", "pyq", "previous year", "purana paper", "question paper", "old papers"]
    norm_text = _norm(text)
    return any(k in norm_text for k in keywords)


def wants_syllabus(text: str) -> bool:
    keywords = ["syllabus", "syllbus", "course", "pattern"]
    norm_text = _norm(text)
    return any(k in norm_text for k in keywords)
