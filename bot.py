import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")


def main_menu():
    keyboard = [
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
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 EXAM SAATHI AI\n\n"
        "Exam या अपना सवाल सीधे लिखें।\n\n"
        "नीचे से कोई option चुनें 👇",
        reply_markup=main_menu(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    messages = {
        "syllabus": "📋 Syllabus\n\nSyllabus system अगले step में जोड़ा जाएगा।",
        "pyq": "📝 PYQ\n\nPYQ system अगले step में जोड़ा जाएगा।",
        "mock": "🧠 Mock Test\n\nAI Mock Test अगले step में जोड़ा जाएगा।",
        "notes": "📝 Notes\n\nAI Notes अगले step में जोड़े जाएँगे।",
        "ai": "🤖 Ask AI\n\nAI system अगले step में जोड़ा जाएगा।",
        "reminder": "⏰ Reminder\n\nReminder system अगले step में जोड़ा जाएगा।",
    }

    text = messages.get(query.data, "❌ Unknown option.")
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Back", callback_data="back")]]
        ),
    )


async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎓 EXAM SAATHI AI\n\n"
        "Exam या अपना सवाल सीधे लिखें 👇",
        reply_markup=main_menu(),
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(back_handler, pattern="^back$"))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Exam Saathi AI is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
