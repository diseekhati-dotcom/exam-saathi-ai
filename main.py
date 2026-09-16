"""
Telegram bot entrypoint.

Wires the pure logic in handlers/*.py + services/exam_service.py to
python-telegram-bot (v20+, async API). This file is intentionally thin:
almost nothing here does real work — it converts plain dict/list message
specs (see handlers/exam_commands.py) into telegram.InlineKeyboardMarkup
objects and vice versa.

NOTE ON TESTING (documented honestly): python-telegram-bot is not
installed in the sandbox this project was built in, and the sandbox has
no network access to install it, so this specific file could not be
import-tested or run in that environment. Every function it calls
(exam_service.*, handlers.exam_commands.*, handlers.start.*) IS covered
by the offline test suite in tests/. Run `pip install -r requirements.txt`
and `python main.py` in a real environment (e.g. after deploying to
Render, or locally) to exercise this file itself.
"""
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config.settings import settings
from database import db
from handlers import start as start_handlers
from handlers import exam_commands
from services import authority_registry, exam_service
from utils.logger import get_logger

log = get_logger(__name__)


def _spec_to_markup(spec: dict) -> InlineKeyboardMarkup | None:
    buttons = spec.get("buttons") or []
    if not buttons:
        return None
    rows = []
    for row in buttons:
        tg_row = []
        for btn in row:
            if "url" in btn:
                tg_row.append(InlineKeyboardButton(btn["text"], url=btn["url"]))
            else:
                tg_row.append(InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]))
        rows.append(tg_row)
    return InlineKeyboardMarkup(rows)


async def _send_spec(update_or_query, spec: dict, edit: bool = False) -> None:
    markup = _spec_to_markup(spec)
    parse_mode = ParseMode.HTML if spec.get("parse_mode") == "HTML" else None
    text = spec["text"]
    try:
        if edit:
            await update_or_query.edit_message_text(text=text, reply_markup=markup, parse_mode=parse_mode)
        else:
            await update_or_query.reply_text(text=text, reply_markup=markup, parse_mode=parse_mode)
    except Exception as exc:  # never let a Telegram API hiccup crash the bot
        log.error("Failed to send/edit message: %s", exc)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    spec = start_handlers.build_start_message()
    await _send_spec(update.message, spec)


async def cmd_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query_text = " ".join(context.args) if context.args else ""
    if not query_text.strip():
        await update.message.reply_text(
            "Please provide an exam name, e.g. <code>/exam SI</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        match = exam_service.resolve_exam(query_text)
    except Exception as exc:
        log.exception("resolve_exam failed for %r", query_text)
        await update.message.reply_text("⚠️ Something went wrong while searching. Please try again.")
        return

    if not match.matched_exam_id:
        spec = exam_commands.build_exam_not_found_message(query_text)
        await _send_spec(update.message, spec)
        return

    try:
        spec = exam_commands.build_exam_card(match.matched_exam_id)
    except Exception:
        log.exception("build_exam_card failed for %s", match.matched_exam_id)
        spec = None

    if spec is None:
        await update.message.reply_text("⚠️ Exam information could not be verified right now.")
        return

    await _send_spec(update.message, spec)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    try:
        parts = data.split(":")
        kind = parts[0]

        if kind == "dt" and len(parts) == 3:
            _, exam_id, doc_type = parts
            spec = exam_commands.build_years_menu(exam_id, doc_type)
        elif kind == "yr" and len(parts) == 4:
            _, exam_id, doc_type, year = parts
            spec = exam_commands.build_documents_for_year(exam_id, doc_type, year)
        else:
            spec = {"text": "⚠️ Unknown action.", "buttons": [], "parse_mode": "HTML"}
    except Exception:
        log.exception("on_callback failed for data=%r", data)
        spec = {"text": "⚠️ Something went wrong. Please try /exam again.", "buttons": [], "parse_mode": "HTML"}

    await _send_spec(query, spec, edit=True)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Unhandled exception while processing update %s: %s", update, context.error)


def build_application() -> Application:
    if not settings.BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set. Set it in your "
            "environment (or Render's Environment tab) before starting the bot."
        )

    application = Application.builder().token(settings.BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("exam", cmd_exam))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    # Initialize DB schema + seed the authority registry before polling.
    db.get_connection()
    seeded = authority_registry.seed_authorities()
    log.info("Seeded %d authorities into the database.", seeded)

    application = build_application()
    log.info("Starting Rajasthan Exam Information Bot (polling mode)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        log.error(str(exc))
        sys.exit(1)
