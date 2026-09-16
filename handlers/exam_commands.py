"""
handlers/exam_commands.py
--------------------------
New, additive entry point: `/exam <name>` plus a free-text fallback used
by bot.py when the old static exam_engine can't confidently match
something. This does NOT touch the existing /start menu, Syllabus, or
PYQ button flows — those keep working exactly as before.

Rendering matches the requested output format:

  🎓 <Exam Name>

  📚 Syllabus
  • <year> <label>  [button]

  📄 Previous Year Papers
  • <year> – Paper <n>  [button]

  ✅ Answer Keys
  • <year> – <tier label>  [button]

  🏛 Official Source: <authority>  [homepage button]
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services import authority_discovery, document_discovery

logger = logging.getLogger("exam_saathi_ai.exam_commands")

DOC_TYPE_LABELS = {
    "syllabus": "📚 Syllabus",
    "question_paper": "📄 Previous Year Papers",
    "answer_key": "✅ Answer Keys",
}

TIER_DISPLAY = {
    "revised_final": "Revised Final Answer Key",
    "final": "Final Answer Key",
    "primary": "Primary Answer Key",
    "provisional": "Provisional Answer Key",
    "master": "Master Question Paper",
    "regular": "Question Paper",
    "syllabus": "Official Syllabus",
    "unknown": "Document",
}


def _entry_label(doc_type: str, entry) -> str:
    year = entry.year or "Year N/A"
    tier_text = TIER_DISPLAY.get(entry.tier_label, "Document")
    if doc_type == "question_paper" and entry.paper_number:
        return f"{year} – Paper {entry.paper_number}"
    if doc_type == "answer_key" and entry.paper_number:
        return f"{year} – {tier_text} (Paper {entry.paper_number})"
    return f"{year} – {tier_text}"


def build_report_text(exam_name: str, authority: dict, docs: dict) -> str:
    lines = [f"🎓 <b>{exam_name}</b>", ""]
    for doc_type in ("syllabus", "question_paper", "answer_key"):
        lines.append(DOC_TYPE_LABELS[doc_type])
        entries = docs.get(doc_type, [])
        if entries:
            for e in entries[:10]:
                lines.append(f"• {_entry_label(doc_type, e)}")
        else:
            if authority.get("doc_pages", {}).get(doc_type):
                lines.append("⚠️ Official PDF not found.")
            else:
                lines.append("⚠️ Official PDF currently unavailable (source not yet configured).")
        lines.append("")
    lines.append(f"🏛 Official Source: {authority['name']}")
    return "\n".join(lines)


def build_report_keyboard(docs: dict, authority: dict) -> InlineKeyboardMarkup:
    rows = []
    for doc_type in ("syllabus", "question_paper", "answer_key"):
        for e in docs.get(doc_type, [])[:10]:
            rows.append([InlineKeyboardButton(f"📄 {_entry_label(doc_type, e)}", url=e.url)])
    if authority.get("base_url"):
        rows.append([InlineKeyboardButton(f"🏛 {authority['name']} Official Website", url=authority["base_url"])])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


async def render_exam_report(message_target, query_text: str) -> None:
    """
    message_target: an object with an async .reply_text(text, parse_mode=,
    reply_markup=) method — works for update.message directly.
    """
    result = authority_discovery.identify_exam(query_text)

    if result.exam and result.authority:
        await message_target.reply_text("🔎 Official source check kar rahe hain, ek moment...")
        try:
            docs = await document_discovery.discover_documents(result.exam, result.authority)
        except Exception:
            logger.exception("document_discovery failed for exam=%s", result.exam["id"])
            await message_target.reply_text(
                "⚠️ Official source abhi access nahi ho pa raha. Thodi der baad try karein.",
            )
            return

        text = build_report_text(result.exam["name"], result.authority, docs)
        kb = build_report_keyboard(docs, result.authority)
        await message_target.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    if result.authority and not result.exam:
        lines = [
            f"🏛 Conducting Authority (best guess): <b>{result.authority['name']}</b>",
            "",
            "Is exam ke liye specific document discovery abhi configured nahi hai, "
            "isliye main koi galat/fake PDF link nahi dikha sakta.",
            "",
            "Official website par khud check kar sakte hain:",
        ]
        rows = []
        if result.authority.get("base_url"):
            rows.append([InlineKeyboardButton(f"🏛 {result.authority['name']} Official Website",
                                               url=result.authority["base_url"])])
        rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
        await message_target.reply_text("\n".join(lines), parse_mode=ParseMode.HTML,
                                         reply_markup=InlineKeyboardMarkup(rows))
        return

    await message_target.reply_text(
        "⚠️ Is exam/authority ko official source se verify nahi kar paaya.\n\n"
        "Exam ka pura naam try karein (jaise: 'RSSB Patwari' ya 'RPSC 1st Grade')."
    )


async def cmd_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query_text = " ".join(context.args) if context.args else ""
    if not query_text:
        await update.message.reply_text(
            "Exam ka naam likhiye. Jaise:\n/exam CET 12\n/exam SI\n/exam Patwar\n/exam REET"
        )
        return
    try:
        await render_exam_report(update.message, query_text)
    except Exception:
        logger.exception("cmd_exam failed for query=%s", query_text)
        await update.message.reply_text("⚠️ Kuch gadbad ho gayi. Dobara try karein.")
