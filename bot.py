"""
EXAM SAATHI AI  (Telegram display name: Study Saathi AI)
=========================================================
Hindi-first AI exam study assistant. Phase 1: Syllabus + PYQ engines
are fully functional. Mock Test / Notes / Ask AI / Reminder exist in
the UI as clean placeholders ready for later phases (see README).

Runs as a FastAPI app (`api`) behind a Telegram webhook, per the
deployment spec: `uvicorn bot:api --host 0.0.0.0 --port $PORT`.

Environment variables:
    BOT_TOKEN     (required) — Telegram bot token
    WEBHOOK_URL   (optional) — full public base URL, e.g. https://your-app.onrender.com
                  If set, the webhook is (re)configured automatically on startup.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from services import exam_engine, pyq_engine, official_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("exam_saathi_ai")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. https://exam-saathi-ai.onrender.com
WEBHOOK_PATH = "/telegram/webhook"

if not BOT_TOKEN:
    logger.warning("BOT_TOKEN environment variable is not set. The bot will not be able to talk to Telegram.")

application: Application | None = Application.builder().token(BOT_TOKEN).build() if BOT_TOKEN else None

WELCOME_TEXT = (
    "🎓 <b>EXAM SAATHI AI</b>\n\n"
    "Exam या अपना सवाल सीधे लिखें.\n\n"
    "Neeche diye gaye buttons se bhi navigate kar sakte hain."
)

PLACEHOLDER_TEXT = {
    "mock": "🧠 <b>Mock Test</b>\n\nYeh feature abhi Phase 2 mein aa raha hai. Filhaal Syllabus aur PYQ / Old Paper use karein.",
    "notes": "📝 <b>Notes</b>\n\nYeh feature abhi Phase 3 mein aa raha hai.",
    "ai": "🤖 <b>Ask AI</b>\n\nYeh feature abhi Phase 4 mein aa raha hai.",
    "reminder": "⏰ <b>Reminder</b>\n\nYeh feature abhi Phase 5 mein aa raha hai.",
}


# ---------------------------------------------------------------------------
# /start and generic navigation
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=exam_engine.kb_main_menu()
    )


async def show_main_menu(update: Update) -> None:
    await _edit_or_send(update, WELCOME_TEXT, exam_engine.kb_main_menu())


async def _edit_or_send(update: Update, text: str, markup: InlineKeyboardMarkup) -> None:
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except Exception:
            # message may be identical or too old to edit — send a fresh one instead of crashing
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


# ---------------------------------------------------------------------------
# Callback query router
# ---------------------------------------------------------------------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # always ack, even on later errors, so Telegram doesn't show a spinner forever

    data = (query.data or "").strip()
    parts = data.split(":")

    try:
        if data == "menu:main":
            await show_main_menu(update)
            return

        if data == "menu:syllabus":
            await _edit_or_send(update, "📋 <b>Syllabus</b>\n\nExam chuniye:", exam_engine.kb_exam_list("syl"))
            return

        if data == "menu:pyq":
            await _edit_or_send(update, "📝 <b>PYQ / Old Paper</b>\n\nExam chuniye:", exam_engine.kb_exam_list("pyq"))
            return

        if data in ("menu:mock", "menu:notes", "menu:ai", "menu:reminder"):
            key = data.split(":")[1]
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")]])
            await _edit_or_send(update, PLACEHOLDER_TEXT[key], back_kb)
            return

        if data == "syl:other":
            context.user_data["awaiting_other_exam"] = True
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:syllabus")]])
            await _edit_or_send(update, "🔎 Exam ka naam likhiye (jaise: SSC CGL):", back_kb)
            return

        if len(parts) >= 3 and parts[0] in ("syl", "pyq") and parts[1] == "exam":
            exam_id = parts[2]
            exam = exam_engine.get_exam(exam_id)
            if not exam:
                await _edit_or_send(update, "⚠️ Exam nahi mila.", exam_engine.kb_exam_list(parts[0]))
                return
            levels = exam.get("levels", {})
            if len(levels) == 1:
                # skip straight to level
                level_id = next(iter(levels))
                await _route_level(update, context, parts[0], exam_id, level_id)
            else:
                await _edit_or_send(
                    update,
                    f"📋 <b>{exam['name']}</b>\n\nLevel/Stage chuniye:",
                    exam_engine.kb_level_list(parts[0], exam_id),
                )
            return

        if len(parts) >= 4 and parts[0] in ("syl", "pyq") and parts[1] == "level":
            _, _, exam_id, level_id = parts
            await _route_level(update, context, parts[0], exam_id, level_id)
            return

        if len(parts) >= 5 and parts[0] == "syl" and parts[1] == "group":
            _, _, exam_id, level_id, group_id = parts
            level = exam_engine.get_level(exam_id, level_id)
            papers = level.get("papers", {})
            paper_id = next(iter(papers))
            await _show_syllabus(update, exam_id, level_id, paper_id, group_id)
            return

        if len(parts) >= 5 and parts[0] == "syl" and parts[1] == "paper":
            _, _, exam_id, level_id, paper_id = parts
            await _show_syllabus(update, exam_id, level_id, paper_id)
            return

        if len(parts) >= 5 and parts[0] == "pyq" and parts[1] == "paper":
            _, _, exam_id, level_id, paper_id = parts
            await _show_pyq_years(update, context, exam_id, level_id, paper_id)
            return

        if len(parts) >= 6 and parts[0] == "pyq" and parts[1] == "year":
            _, _, exam_id, level_id, paper_id, idx = parts
            key = f"{exam_id}:{level_id}:{paper_id}:{idx}"
            docs = context.user_data.get("pyq_cache", {}).get(key)
            if not docs:
                await query.message.reply_text("⚠️ Session expire ho gaya, dobara try karein.")
                return
            year = docs[0].year
            text = pyq_engine.format_year_message(exam_id, level_id, paper_id, year, docs)
            kb = pyq_engine.kb_year_docs(exam_id, level_id, paper_id, docs)
            await _edit_or_send(update, text, kb)
            return

        # Unknown/legacy callback — never crash, just recover gracefully
        logger.warning("Unhandled callback_data: %s", data)
        await show_main_menu(update)

    except Exception:
        logger.exception("Error handling callback_data=%s", data)
        try:
            await query.message.reply_text("⚠️ Kuch gadbad ho gayi. Main Menu se dobara try karein.",
                                            reply_markup=exam_engine.kb_main_menu())
        except Exception:
            pass


async def _route_level(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix: str, exam_id: str, level_id: str) -> None:
    level = exam_engine.get_level(exam_id, level_id)
    if not level:
        await _edit_or_send(update, "⚠️ Level nahi mila.", exam_engine.kb_exam_list(prefix))
        return

    if prefix == "syl" and level.get("subject_groups"):
        exam = exam_engine.get_exam(exam_id)
        await _edit_or_send(
            update,
            f"📋 <b>{exam['name']} — {level['name']}</b>\n\nSubject group chuniye:",
            exam_engine.kb_group_list(exam_id, level_id),
        )
        return

    papers = level.get("papers", {})
    if len(papers) == 1:
        paper_id = next(iter(papers))
        if prefix == "syl":
            await _show_syllabus(update, exam_id, level_id, paper_id)
        else:
            await _show_pyq_years(update, context, exam_id, level_id, paper_id)
        return

    exam = exam_engine.get_exam(exam_id)
    label = "Syllabus" if prefix == "syl" else "Paper"
    await _edit_or_send(
        update,
        f"📋 <b>{exam['name']} — {level['name']}</b>\n\n{label} chuniye:",
        exam_engine.kb_paper_list(prefix, exam_id, level_id),
    )


async def _show_syllabus(update: Update, exam_id: str, level_id: str, paper_id: str, group_id: str | None = None) -> None:
    text = exam_engine.format_syllabus_message(exam_id, level_id, paper_id, group_id)
    kb = exam_engine.kb_syllabus_detail(exam_id, level_id, paper_id)
    await _edit_or_send(update, text, kb)


async def _show_pyq_years(update: Update, context: ContextTypes.DEFAULT_TYPE, exam_id: str, level_id: str, paper_id: str) -> None:
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text("🔎 Official source check kar rahe hain, ek moment...")
        except Exception:
            pass

    try:
        info = await pyq_engine.get_years_for_paper(exam_id, level_id, paper_id)
    except Exception:
        logger.exception("PYQ lookup failed for %s/%s/%s", exam_id, level_id, paper_id)
        info = {"years": {}, "archive_url": exam_engine.get_exam(exam_id).get("official_archive")}

    exam = exam_engine.get_exam(exam_id)
    paper = exam_engine.get_paper(exam_id, level_id, paper_id)

    if not info["years"]:
        text = pyq_engine.format_no_results_message(exam_id)
        kb_rows = []
        if info.get("archive_url"):
            kb_rows.append([InlineKeyboardButton("🌐 Official Archive", url=info["archive_url"])])
        kb_rows.append([InlineKeyboardButton("🔙 Back", callback_data="menu:pyq")])
        kb_rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
        await _edit_or_send(update, text, InlineKeyboardMarkup(kb_rows))
        return

    text = f"📝 <b>{exam['name']} — {paper['name']}</b>\n\nAvailable years:"
    kb = pyq_engine.kb_years(exam_id, level_id, paper_id, info["years"], info.get("archive_url"), context.user_data)
    await _edit_or_send(update, text, kb)


# ---------------------------------------------------------------------------
# Free-text natural language handling
# ---------------------------------------------------------------------------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return

    if context.user_data.pop("awaiting_other_exam", False):
        await handle_other_exam_query(update, text)
        return

    exam_id, confidence = exam_engine.match_exam(text)

    if not exam_id or confidence < 0.45:
        await update.message.reply_text(
            "Mujhe samajh nahi aaya. Neeche buttons se chuniye ya exam ka poora naam likhiye "
            "(jaise: 'REET Level 1 syllabus').",
            reply_markup=exam_engine.kb_main_menu(),
        )
        return

    exam = exam_engine.get_exam(exam_id)
    level_id = exam_engine.match_level(exam_id, text)
    is_pyq = exam_engine.wants_pyq(text)

    levels = exam.get("levels", {})
    if not level_id and len(levels) == 1:
        level_id = next(iter(levels))

    prefix = "pyq" if is_pyq else "syl"

    if not level_id:
        await update.message.reply_text(
            f"📋 <b>{exam['name']}</b>\n\nLevel/Stage chuniye:",
            parse_mode=ParseMode.HTML,
            reply_markup=exam_engine.kb_level_list(prefix, exam_id),
        )
        return

    level = exam.get("levels", {}).get(level_id, {})
    if prefix == "syl" and level.get("subject_groups"):
        await update.message.reply_text(
            f"📋 <b>{exam['name']} — {level['name']}</b>\n\nSubject group chuniye:",
            parse_mode=ParseMode.HTML,
            reply_markup=exam_engine.kb_group_list(exam_id, level_id),
        )
        return

    paper_id = exam_engine.match_paper(exam_id, level_id, text)
    papers = level.get("papers", {})
    if not paper_id and len(papers) == 1:
        paper_id = next(iter(papers))

    if not paper_id:
        await update.message.reply_text(
            f"📋 <b>{exam['name']} — {level['name']}</b>\n\nPaper chuniye:",
            parse_mode=ParseMode.HTML,
            reply_markup=exam_engine.kb_paper_list(prefix, exam_id, level_id),
        )
        return

    if prefix == "syl":
        text_out = exam_engine.format_syllabus_message(exam_id, level_id, paper_id)
        kb = exam_engine.kb_syllabus_detail(exam_id, level_id, paper_id)
        await update.message.reply_text(text_out, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text("🔎 Official source check kar rahe hain, ek moment...")
        try:
            info = await pyq_engine.get_years_for_paper(exam_id, level_id, paper_id)
        except Exception:
            logger.exception("PYQ lookup failed (text flow) for %s/%s/%s", exam_id, level_id, paper_id)
            info = {"years": {}, "archive_url": exam.get("official_archive")}

        if not info["years"]:
            kb_rows = []
            if info.get("archive_url"):
                kb_rows.append([InlineKeyboardButton("🌐 Official Archive", url=info["archive_url"])])
            kb_rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])
            await update.message.reply_text(pyq_engine.format_no_results_message(exam_id),
                                             reply_markup=InlineKeyboardMarkup(kb_rows))
        else:
            paper = exam_engine.get_paper(exam_id, level_id, paper_id)
            kb = pyq_engine.kb_years(exam_id, level_id, paper_id, info["years"], info.get("archive_url"), context.user_data)
            await update.message.reply_text(
                f"📝 <b>{exam['name']} — {paper['name']}</b>\n\nAvailable years:",
                parse_mode=ParseMode.HTML, reply_markup=kb,
            )


async def handle_other_exam_query(update: Update, query_text: str) -> None:
    await update.message.reply_text("🔎 Official source dhoond rahe hain, ek moment...")
    try:
        result = await official_search.search_other_exam(query_text)
    except Exception:
        logger.exception("Other-exam search failed for query=%s", query_text)
        await update.message.reply_text(
            "⚠️ Official source abhi access nahi ho pa raha. Thodi der baad try karein.",
            reply_markup=exam_engine.kb_main_menu(),
        )
        return

    if not result.get("recognised"):
        await update.message.reply_text(result["message"], reply_markup=exam_engine.kb_main_menu())
        return

    docs = result.get("results", [])
    if not docs:
        lines = [f"⚠️ '{query_text}' ke liye is samay koi verified official PDF nahi mila.", ""]
        for page in result.get("checked_pages", []):
            lines.append(f"🌐 {page}")
        await update.message.reply_text("\n".join(lines), reply_markup=exam_engine.kb_main_menu())
        return

    lines = [f"🔎 <b>{query_text}</b> — Official documents mile:", ""]
    rows = []
    label_map = {
        "syllabus": "📄 Syllabus",
        "question_paper": "📄 Question Paper",
        "answer_key": "🔑 Answer Key",
        "notification": "📢 Notification",
        "unknown": "📎 Document",
    }
    for d in docs[:8]:
        year_suffix = f" ({d.year})" if d.year else ""
        rows.append([InlineKeyboardButton(f"{label_map.get(d.doc_type, '📎')}{year_suffix}", url=d.url)])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu:main")])

    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows)
    )


# ---------------------------------------------------------------------------
# Global error handler (section 22: no unhandled crash)
# ---------------------------------------------------------------------------

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception while processing update: %s", context.error, exc_info=context.error)


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)


if application:
    register_handlers(application)


# ---------------------------------------------------------------------------
# FastAPI app + webhook wiring
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    if application:
        await application.initialize()
        await application.start()
        if WEBHOOK_URL:
            full_url = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
            try:
                await application.bot.set_webhook(url=full_url, allowed_updates=Update.ALL_TYPES)
                logger.info("Webhook set to %s", full_url)
            except Exception:
                logger.exception("Failed to set webhook on startup")
    yield
    # IMPORTANT: do NOT delete the webhook on shutdown — Render restarts
    # the service routinely and we want Telegram to keep delivering
    # updates to the same URL without needing to re-register it.
    if application:
        await application.stop()
        await application.shutdown()


api = FastAPI(title="Exam Saathi AI", lifespan=lifespan)


@api.get("/")
async def health_check():
    return {"status": "ok", "bot": "Exam Saathi AI"}


@api.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    if not application:
        return Response(status_code=503)
    try:
        data = await request.json()
    except Exception:
        return Response(status_code=400)

    try:
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception:
        logger.exception("Failed to process incoming update")
        # still return 200 so Telegram doesn't endlessly retry a bad update
        return Response(status_code=200)

    return Response(status_code=200)
