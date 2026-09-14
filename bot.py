import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = "/telegram/webhook"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

if not WEBHOOK_URL:
    raise RuntimeError(
        "WEBHOOK_URL environment variable is missing. "
        "Set it to your Render service URL, e.g. https://your-service.onrender.com"
    )

telegram_app = Application.builder().token(BOT_TOKEN).build()


SYLLABI = {
    "reet": {
        "name": "REET",
        "source": "BSER / Rajasthan Board",
        "url": "https://rajeduboard.rajasthan.gov.in/reet2024final121224.PDF",
    },
    "patwari": {
        "name": "Patwari",
        "source": "RSSB",
        "url": "https://rssb.rajasthan.gov.in/storage/advertisement_item/1740055908.pdf",
    },
    "ras": {
        "name": "RAS",
        "source": "RPSC",
        "url": "https://rpsc.rajasthan.gov.in/",
    },
    "si": {
        "name": "Rajasthan SI",
        "source": "RPSC",
        "url": "https://rpsc.rajasthan.gov.in/",
    },
}

ALIASES = {
    "reet": "reet",
    "reet level 1": "reet",
    "reet level 2": "reet",
    "patwar": "patwari",
    "patwari": "patwari",
    "ras": "ras",
    "ras pre": "ras",
    "ras prelims": "ras",
    "rpsc ras": "ras",
    "si": "si",
    "sub inspector": "si",
    "rajasthan si": "si",
    "rpsc si": "si",
}


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Syllabus", callback_data="syllabus"),
            InlineKeyboardButton("📝 PYQ", callback_data="pyq"),
        ],
        [
            InlineKeyboardButton("🧠 Mock Test", callback_data="mock"),
            InlineKeyboardButton("📝 Notes", callback_data="notes"),
        ],
        [
            InlineKeyboardButton("🤖 Ask AI", callback_data="ai"),
            InlineKeyboardButton("⏰ Reminder", callback_data="reminder"),
        ],
    ])


def syllabus_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("REET", callback_data="syllabus:reet"),
            InlineKeyboardButton("Patwari", callback_data="syllabus:patwari"),
        ],
        [
            InlineKeyboardButton("RAS", callback_data="syllabus:ras"),
            InlineKeyboardButton("Rajasthan SI", callback_data="syllabus:si"),
        ],
        [InlineKeyboardButton("🔎 Other Exam", callback_data="syllabus:other")],
        [InlineKeyboardButton("◀️ Back", callback_data="back")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("waiting_for_exam", None)
    await update.message.reply_text(
        "🎓 EXAM SAATHI AI\n\n"
        "Exam या अपना सवाल सीधे लिखें।\n\n"
        "नीचे से कोई option चुनें 👇",
        reply_markup=main_menu(),
    )


async def show_syllabus_menu(query):
    await query.edit_message_text(
        "📋 Syllabus\n\n"
        "अपना Exam चुनें 👇\n\n"
        "अगर list में exam नहीं है तो 🔎 Other Exam चुनकर उसका नाम लिखें।",
        reply_markup=syllabus_menu(),
    )


async def show_known_syllabus(query, key):
    item = SYLLABI[key]
    await query.edit_message_text(
        f"📋 {item['name']} — Syllabus\n\n"
        f"🏢 Source: {item['source']}\n\n"
        "नीचे official source खोलें 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Open Official Syllabus", url=item["url"])],
            [InlineKeyboardButton("◀️ Back", callback_data="syllabus")],
        ]),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "syllabus":
        context.user_data.pop("waiting_for_exam", None)
        await show_syllabus_menu(query)
        return

    if data.startswith("syllabus:"):
        key = data.split(":", 1)[1]

        if key == "other":
            context.user_data["waiting_for_exam"] = True
            await query.edit_message_text(
                "🔎 Other Exam\n\n"
                "जिस exam का syllabus चाहिए, उसका नाम लिखें 👇\n\n"
                "उदाहरण:\n"
                "• SSC CGL\n"
                "• SSC CHSL\n"
                "• CTET\n"
                "• Railway NTPC\n"
                "• UPSC\n"
                "• Rajasthan Cooperative Bank",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="syllabus")]
                ]),
            )
            return

        if key in SYLLABI:
            await show_known_syllabus(query, key)
            return

    if data == "back":
        context.user_data.pop("waiting_for_exam", None)
        await query.edit_message_text(
            "🎓 EXAM SAATHI AI\n\n"
            "Exam या अपना सवाल सीधे लिखें 👇",
            reply_markup=main_menu(),
        )
        return

    messages = {
        "pyq": "📝 PYQ\n\nPYQ system अगले step में जोड़ा जाएगा।",
        "mock": "🧠 Mock Test\n\nAI Mock Test अगले step में जोड़ा जाएगा।",
        "notes": "📝 Notes\n\nAI Notes अगले step में जोड़े जाएँगे।",
        "ai": "🤖 Ask AI\n\nAI system अगले step में जोड़ा जाएगा।",
        "reminder": "⏰ Reminder\n\nReminder system अगले step में जोड़ा जाएगा।",
    }

    await query.edit_message_text(
        messages.get(data, "❌ Unknown option."),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back", callback_data="back")]
        ]),
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if context.user_data.get("waiting_for_exam"):
        key = ALIASES.get(text.lower())

        if key:
            item = SYLLABI[key]
            await update.message.reply_text(
                f"📋 {item['name']} — Syllabus\n\n"
                f"🏢 Source: {item['source']}\n\n"
                "नीचे official source खोलें 👇",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📄 Open Official Syllabus", url=item["url"])],
                    [InlineKeyboardButton("◀️ Back", callback_data="syllabus")],
                ]),
            )
        else:
            await update.message.reply_text(
                f"🔎 Exam: {text}\n\n"
                "Automatic official-source search अगले step में जोड़ा जाएगा।",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Syllabus Menu", callback_data="syllabus")]
                ]),
            )

        context.user_data.pop("waiting_for_exam", None)
        return

    await update.message.reply_text(
        "🤖 आपका सवाल मिल गया।\n\n"
        "AI + natural-language exam detection अगले चरण में जोड़ा जाएगा।"
    )


telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await telegram_app.initialize()
    await telegram_app.start()

    webhook_endpoint = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await telegram_app.bot.set_webhook(
        url=webhook_endpoint,
        drop_pending_updates=True,
    )

    print(f"🤖 Exam Saathi AI running on 0.0.0.0:{PORT}")
    print(f"🔗 Telegram webhook: {webhook_endpoint}")

    yield

    await telegram_app.bot.delete_webhook()
    await telegram_app.stop()
    await telegram_app.shutdown()


api = FastAPI(title="Exam Saathi AI", lifespan=lifespan)


@api.get("/")
async def home():
    return {"status": "ok", "service": "Exam Saathi AI"}


@api.get("/health")
async def health():
    return {"status": "healthy"}


@api.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
