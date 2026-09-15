import os
import re
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
        "WEBHOOK_URL environment variable is missing. Set it to your Render service URL."
    )

telegram_app = Application.builder().token(BOT_TOKEN).build()

# Official-source-first data. We deliberately use official archive pages where
# a stable year-specific PDF is not known, so the bot never invents a paper.
EXAMS = {
    "reet": {
        "name": "REET",
        "aliases": ["reet", "reet level 1", "reet level 2", "rtet"],
        "syllabus_url": "https://rajeduboard.rajasthan.gov.in/reet2024final121224.PDF",
        "syllabus_source": "BSER / REET",
        "pyq_url": "https://rajeduboard.rajasthan.gov.in/RTET-REET/RTET-REET.htm",
        "pyq_source": "BSER / RTET-REET archive",
    },
    "patwari": {
        "name": "Patwari",
        "aliases": ["patwari", "patwar", "rssb patwari", "patwar 2025"],
        "syllabus_url": "https://rssb.rajasthan.gov.in/storage/advertisement_item/1740055908.pdf",
        "syllabus_source": "RSSB",
        "pyq_url": "https://rssb.rajasthan.gov.in/",
        "pyq_source": "RSSB official portal",
    },
    "ras": {
        "name": "RAS",
        "aliases": ["ras", "ras pre", "ras prelims", "rpsc ras", "ras 2026"],
        "syllabus_url": "https://rpsc.rajasthan.gov.in/Static/Syllabus/7D943B35-2D9E-4E50-BC3E-3726268AE18B.pdf",
        "syllabus_source": "RPSC",
        "pyq_url": "https://rpsc.rajasthan.gov.in/previousquestionpapers.aspx",
        "pyq_source": "RPSC Previous Question Papers",
    },
    "si": {
        "name": "Rajasthan SI",
        "aliases": ["si", "sub inspector", "sub-inspector", "rajasthan si", "rpsc si", "si 2025"],
        "syllabus_url": "https://rpsc.rajasthan.gov.in/Static/Syllabus/A1E1781F-8C6F-44BD-9DF2-E75D3D258617.pdf",
        "syllabus_source": "RPSC",
        "pyq_url": "https://rpsc.rajasthan.gov.in/previousquestionpapers.aspx",
        "pyq_source": "RPSC Previous Question Papers",
    },
}

# Extra official portals for users who type an exam not in the quick menu.
OFFICIAL_PORTALS = [
    ("Rajasthan Recruitment Portal", "https://recruitment.rajasthan.gov.in/"),
    ("RSSB", "https://rssb.rajasthan.gov.in/"),
    ("RPSC", "https://rpsc.rajasthan.gov.in/"),
    ("RBSE / BSER", "https://rajeduboard.rajasthan.gov.in/"),
]


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", text)
    return re.sub(r"\s+", " ", text)


def detect_exam(text: str):
    q = normalize(text)
    # Longest alias first so "REET Level 1" wins over "REET".
    choices = []
    for key, item in EXAMS.items():
        for alias in item["aliases"]:
            choices.append((len(normalize(alias)), alias, key))
    for _, alias, key in sorted(choices, reverse=True):
        if normalize(alias) in q:
            return key
    return None


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


def back_menu(callback="back"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data=callback)]])


def exam_menu(prefix: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("REET", callback_data=f"{prefix}:reet"),
            InlineKeyboardButton("Patwari", callback_data=f"{prefix}:patwari"),
        ],
        [
            InlineKeyboardButton("RAS", callback_data=f"{prefix}:ras"),
            InlineKeyboardButton("Rajasthan SI", callback_data=f"{prefix}:si"),
        ],
        [InlineKeyboardButton("🔎 Other Exam", callback_data=f"{prefix}:other")],
        [InlineKeyboardButton("◀️ Back", callback_data="back")],
    ])


def exam_result_keyboard(key: str, mode: str):
    item = EXAMS[key]
    if mode == "syllabus":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Open Official Syllabus", url=item["syllabus_url"])],
            [InlineKeyboardButton("📝 PYQ", callback_data=f"pyq:{key}")],
            [InlineKeyboardButton("◀️ Back", callback_data="syllabus")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Open Official PYQ Archive", url=item["pyq_url"])],
        [InlineKeyboardButton("📋 Syllabus", callback_data=f"syllabus:{key}")],
        [InlineKeyboardButton("◀️ Back", callback_data="pyq")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎓 EXAM SAATHI AI\n\n"
        "Exam या अपना सवाल सीधे लिखें।\n\n"
        "नीचे से कोई option चुनें 👇",
        reply_markup=main_menu(),
    )


async def show_syllabus_menu(query):
    await query.edit_message_text(
        "📋 Syllabus\n\nअपना Exam चुनें 👇",
        reply_markup=exam_menu("syllabus"),
    )


async def show_pyq_menu(query):
    await query.edit_message_text(
        "📝 PYQ\n\nअपना Exam चुनें 👇\n\n"
        "मैं official/publicly available source ही दिखाऊँगा। जिस साल का verified paper उपलब्ध नहीं है, उसे खुद से नहीं बनाऊँगा।",
        reply_markup=exam_menu("pyq"),
    )


async def show_known_syllabus(query, key):
    item = EXAMS[key]
    await query.edit_message_text(
        f"📋 {item['name']} — Syllabus\n\n"
        f"🏢 Source: {item['syllabus_source']}\n\n"
        "यह official source है। PDF खोलने के लिए नीचे दबाएँ 👇",
        reply_markup=exam_result_keyboard(key, "syllabus"),
    )


async def show_known_pyq(query, key):
    item = EXAMS[key]
    await query.edit_message_text(
        f"📝 {item['name']} — PYQ\n\n"
        f"🏢 Source: {item['pyq_source']}\n\n"
        "नीचे official archive खोलें। वहाँ उपलब्ध exam/year के papers दिए जाते हैं।\n\n"
        "ℹ️ Bot केवल verified/public source को सूची में रखेगा; missing year को invent नहीं करेगा।",
        reply_markup=exam_result_keyboard(key, "pyq"),
    )


async def other_exam_prompt(query, mode: str):
    context = query._bot_data  # not used; kept out of user state
    await query.edit_message_text(
        f"🔎 Other Exam — {('Syllabus' if mode == 'syllabus' else 'PYQ')}\n\n"
        "Exam का नाम लिखें 👇\n\n"
        "उदाहरण:\n"
        "• CET 12th\n"
        "• LDC\n"
        "• Grade 4\n"
        "• SSC CGL\n"
        "• CTET\n\n"
        "नाम मिलने पर bot पहले known official source check करेगा।",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=mode)]
        ]),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "syllabus":
        context.user_data.pop("waiting_mode", None)
        await show_syllabus_menu(query)
        return
    if data == "pyq":
        context.user_data.pop("waiting_mode", None)
        await show_pyq_menu(query)
        return
    if data == "back":
        context.user_data.clear()
        await query.edit_message_text(
            "🎓 EXAM SAATHI AI\n\nExam या अपना सवाल सीधे लिखें 👇",
            reply_markup=main_menu(),
        )
        return

    for mode in ("syllabus", "pyq"):
        if data.startswith(mode + ":"):
            key = data.split(":", 1)[1]
            if key == "other":
                context.user_data["waiting_mode"] = mode
                await other_exam_prompt(query, mode)
                return
            if key in EXAMS:
                if mode == "syllabus":
                    await show_known_syllabus(query, key)
                else:
                    await show_known_pyq(query, key)
                return

    messages = {
        "mock": "🧠 Mock Test\n\nMock Test module अगला step है। इसमें answers test के दौरान hidden रहेंगे और result के बाद Show Answers मिलेगा।",
        "notes": "📝 Notes\n\nNotes module अगला step है। Notes verified syllabus के अनुसार बनाए जाएँगे।",
        "ai": "🤖 Ask AI\n\nAI module अगला step है। आप सीधे exam question लिख सकेंगे।",
        "reminder": "⏰ Reminder\n\nReminder module अगला step है।",
    }
    await query.edit_message_text(
        messages.get(data, "❌ Unknown option."),
        reply_markup=back_menu(),
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    waiting_mode = context.user_data.get("waiting_mode")
    if waiting_mode in ("syllabus", "pyq"):
        key = detect_exam(text)
        if key:
            if waiting_mode == "syllabus":
                await update.message.reply_text(
                    f"📋 {EXAMS[key]['name']} — Syllabus",
                    reply_markup=exam_result_keyboard(key, "syllabus"),
                )
            else:
                await update.message.reply_text(
                    f"📝 {EXAMS[key]['name']} — PYQ",
                    reply_markup=exam_result_keyboard(key, "pyq"),
                )
        else:
            await update.message.reply_text(
                f"🔎 {text}\n\n"
                "यह exam अभी quick database में नहीं है। नीचे official portals से check कर सकते हैं।\n\n"
                "मैं बिना verification के syllabus/PYQ link नहीं बनाऊँगा।",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(name, url=url)] for name, url in OFFICIAL_PORTALS
                ] + [[InlineKeyboardButton("◀️ Back", callback_data=waiting_mode)]]),
            )
        context.user_data.pop("waiting_mode", None)
        return

    # Natural-language detection for common direct requests.
    key = detect_exam(text)
    q = normalize(text)
    if key and any(word in q for word in ["syllabus", "पाठ्यक्रम"]):
        await update.message.reply_text(
            f"📋 {EXAMS[key]['name']} — Syllabus",
            reply_markup=exam_result_keyboard(key, "syllabus"),
        )
        return
    if key and any(word in q for word in ["pyq", "previous", "question paper", "previous year", "प्रश्न पत्र"]):
        await update.message.reply_text(
            f"📝 {EXAMS[key]['name']} — PYQ",
            reply_markup=exam_result_keyboard(key, "pyq"),
        )
        return

    await update.message.reply_text(
        "🤖 सवाल मिल गया।\n\n"
        "Natural-language AI answer system अगले module में जुड़ेगा।\n\n"
        "अभी आप 📋 Syllabus या 📝 PYQ button से शुरू कर सकते हैं।",
        reply_markup=main_menu(),
    )


telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await telegram_app.initialize()
    await telegram_app.start()
    webhook_endpoint = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await telegram_app.bot.set_webhook(url=webhook_endpoint, drop_pending_updates=True)
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
