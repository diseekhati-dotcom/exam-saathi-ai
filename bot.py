import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from services.exam_engine import CATALOG, find_exam, detect_stage, detect_paper
from services.official_search import search_exam

BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '').rstrip('/')
PORT = int(os.getenv('PORT', '10000'))
WEBHOOK_PATH = '/telegram/webhook'

if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN environment variable is missing.')
if not WEBHOOK_URL:
    raise RuntimeError('WEBHOOK_URL environment variable is missing.')

telegram_app = Application.builder().token(BOT_TOKEN).build()


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📋 Syllabus', callback_data='sy'),
         InlineKeyboardButton('📝 PYQ / Old Paper', callback_data='pq')],
        [InlineKeyboardButton('🧠 Mock Test', callback_data='mock'),
         InlineKeyboardButton('📝 Notes', callback_data='notes')],
        [InlineKeyboardButton('🤖 Ask AI', callback_data='ai'),
         InlineKeyboardButton('⏰ Reminder', callback_data='reminder')],
    ])


def section_menu(section):
    rows = []
    keys = list(CATALOG)
    for i in range(0, len(keys), 2):
        rows.append([
            InlineKeyboardButton(CATALOG[k]['name'], callback_data=f'{section}:e:{k}')
            for k in keys[i:i + 2]
        ])
    rows.append([InlineKeyboardButton('🔎 Other Exam', callback_data=f'{section}:other')])
    rows.append([InlineKeyboardButton('🏠 Main Menu', callback_data='home')])
    return InlineKeyboardMarkup(rows)


def stage_menu(section, key):
    e = CATALOG[key]
    rows = []
    for sk, stage in e['stages'].items():
        rows.append([InlineKeyboardButton(
            '📚 ' + stage['label'], callback_data=f'{section}:s:{key}:{sk}'
        )])
    # A direct exam-level PDF is useful, but never replace the actual PDF with a homepage.
    pdf = e.get('syllabus_pdf')
    if pdf and pdf.lower().split('?')[0].endswith('.pdf'):
        rows.append([InlineKeyboardButton('📄 Official Syllabus PDF', url=pdf)])
    rows.append([InlineKeyboardButton('◀️ Back', callback_data=section)])
    return InlineKeyboardMarkup(rows)


def paper_menu(section, key, stage):
    st = CATALOG[key]['stages'][stage]
    rows = []
    for pk, p in st['papers'].items():
        rows.append([InlineKeyboardButton(
            '📄 ' + p['label'], callback_data=f'{section}:p:{key}:{stage}:{pk}'
        )])
    if section == 'pq':
        rows.append([InlineKeyboardButton(
            '🔎 Find Official PYQ PDFs', callback_data=f'pqfind:{key}:{stage}'
        )])
    rows.append([InlineKeyboardButton('◀️ Back', callback_data=f'{section}:e:{key}')])
    return InlineKeyboardMarkup(rows)


def detail_text(key, stage, pk):
    e = CATALOG[key]
    st = e['stages'][stage]
    p = st['papers'][pk]
    lines = [f"📋 {e['name']}", f"📚 {st['label']}", f"📄 {p['label']}"]
    if p.get('marks') is not None:
        lines.append(f"💯 Marks: {p['marks']}")
    if p.get('questions') is not None:
        lines.append(f"❓ Questions: {p['questions']}")
    if p.get('time'):
        lines.append(f"⏱ Time: {p['time']}")
    if p.get('negative'):
        lines.append(f"➖ Negative: {p['negative']}")
    if p.get('subjects'):
        lines += ['', '📚 Subjects / Topics:']
        for s in p['subjects']:
            if isinstance(s, dict):
                line = '• ' + s['name']
                if s.get('marks') is not None:
                    line += f" — {s['marks']} marks"
                lines.append(line)
                for t in s.get('topics', []):
                    lines.append('  └ ' + t)
    if p.get('units'):
        lines += ['', '📚 Units:']
        lines.extend('• ' + u for u in p['units'])
    lines += ['', 'ℹ️ Complete official wording is in the official PDF.']
    return '\n'.join(lines)


def paper_source(key, stage, pk=None):
    e = CATALOG[key]
    if pk:
        p = e['stages'][stage]['papers'][pk]
        if p.get('syllabus_pdf') and p['syllabus_pdf'].lower().split('?')[0].endswith('.pdf'):
            return p['syllabus_pdf']
    st = e['stages'][stage]
    if st.get('syllabus_pdf') and st['syllabus_pdf'].lower().split('?')[0].endswith('.pdf'):
        return st['syllabus_pdf']
    if e.get('syllabus_pdf') and e['syllabus_pdf'].lower().split('?')[0].endswith('.pdf'):
        return e['syllabus_pdf']
    return None


def back_button(section):
    return InlineKeyboardButton('◀️ Back', callback_data=section)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        '🎓 EXAM SAATHI AI\n\nExam या अपना सवाल सीधे लिखें।\n\n📚 Preparation ke liye option choose karein 👇',
        reply_markup=main_menu(),
    )


async def show_section(q, section):
    title = '📋 Syllabus' if section == 'sy' else '📝 PYQ / Old Paper'
    await q.edit_message_text(f'{title}\n\nअपनी परीक्षा चुनें 👇', reply_markup=section_menu(section))


async def show_other(q, context, section):
    context.user_data['waiting'] = section
    await q.edit_message_text(
        '🔎 Other Exam\n\nकिसी भी exam का नाम लिखें।\n\n'
        'Example: SSC CGL, UPSC, CTET, Railway NTPC, Rajasthan JEN, Jail Prahari',
        reply_markup=InlineKeyboardMarkup([[back_button(section)]]),
    )


async def show_pyq_known(q, key):
    e = CATALOG[key]
    rows = []
    for sk, stage in e['stages'].items():
        rows.append([InlineKeyboardButton(
            '📚 ' + stage['label'], callback_data=f'pq:s:{key}:{sk}'
        )])
    rows.append([back_button('pq')])
    await q.edit_message_text(
        f"📝 {e['name']}\n\nLevel / Stage चुनें 👇",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def do_dynamic(update, context, exam, kind, edit_message=None, stage_label=None):
    target = edit_message
    label = 'syllabus' if kind == 'sy' else 'PYQ / old paper'
    extra = f' — {stage_label}' if stage_label else ''
    if target:
        await target.edit_text(f'🔎 {exam}{extra}\n\nOfficial {label} PDF खोज रहा हूँ…')
    else:
        target = await update.message.reply_text(f'🔎 {exam}{extra}\n\nOfficial {label} PDF खोज रहा हूँ…')

    query_exam = exam if not stage_label else f'{exam} {stage_label}'
    results = await search_exam(query_exam, 'syllabus' if kind == 'sy' else 'pyq')
    # Strict rule: user asked for direct PDF links, not official home/archive pages.
    pdf_results = [r for r in results if r.get('pdf') and str(r.get('url', '')).lower().split('?')[0].endswith('.pdf')]

    if not pdf_results:
        await target.edit_text(
            f'⚠️ {exam}{extra}\n\nVerified official PDF नहीं मिला.\n\n'
            'Bot ने generic website/archive link को PDF की जगह नहीं दिखाया।',
            reply_markup=InlineKeyboardMarkup([[back_button(kind)]]),
        )
        return

    rows = []
    for r in pdf_results[:10]:
        title = (r.get('title') or 'Official PDF').strip()[:52]
        rows.append([InlineKeyboardButton('📄 ' + title, url=r['url'])])
    rows.append([back_button(kind)])
    await target.edit_text(
        f'🔎 {exam}{extra}\n\nOfficial source से direct PDF मिले हैं. खोलने के लिए चुनें 👇',
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data or ''

    if d == 'home':
        context.user_data.clear()
        await q.edit_message_text('🎓 EXAM SAATHI AI\n\nExam या अपना सवाल सीधे लिखें 👇', reply_markup=main_menu())
        return

    if d in ('sy', 'pq'):
        await show_section(q, d)
        return

    if d in ('mock', 'notes', 'ai', 'reminder'):
        text = {
            'mock': '🧠 Mock Test\n\nPhase 1 में syllabus/PYQ engine तैयार है. Mock Test next phase में इसी verified syllabus से बनेगा.',
            'notes': '📝 Notes\n\nNotes engine next phase में इसी verified syllabus से जुड़ेगा.',
            'ai': '🤖 Ask AI\n\nआप सवाल अभी सीधे लिख सकते हैं. Full exam-context AI next phase में जुड़ेगा.',
            'reminder': '⏰ Reminder\n\nReminder scheduler next phase में जुड़ेगा.',
        }[d]
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 Main Menu', callback_data='home')]]))
        return

    if d in ('sy:other', 'pq:other'):
        await show_other(q, context, d.split(':')[0])
        return

    if d.startswith('findpq:'):
        key = d.split(':', 1)[1]
        await do_dynamic(None, context, CATALOG[key]['name'], 'pq', q)
        return

    if d.startswith('findsy:'):
        key = d.split(':', 1)[1]
        await do_dynamic(None, context, CATALOG[key]['name'], 'sy', q)
        return

    if d.startswith('pqfind:'):
        parts = d.split(':')
        if len(parts) == 3:
            _, key, stage = parts
            await do_dynamic(None, context, CATALOG[key]['name'], 'pq', q, CATALOG[key]['stages'][stage]['label'])
        return

    parts = d.split(':')

    # section:e:key
    if len(parts) == 3 and parts[1] == 'e':
        section, key = parts[0], parts[2]
        if section == 'sy':
            await q.edit_message_text(
                f"📋 {CATALOG[key]['name']}\n\nLevel / Stage चुनें 👇",
                reply_markup=stage_menu(section, key),
            )
        else:
            await show_pyq_known(q, key)
        return

    # section:s:key:stage
    if len(parts) == 4 and parts[1] == 's':
        section, key, stage = parts[0], parts[2], parts[3]
        await q.edit_message_text(
            f"📚 {CATALOG[key]['name']}\n\n{CATALOG[key]['stages'][stage]['label']}\n\nPaper चुनें 👇",
            reply_markup=paper_menu(section, key, stage),
        )
        return

    # section:p:key:stage:paper  <-- fixed: 5 parts, not 4
    if len(parts) == 5 and parts[1] == 'p':
        section, _, key, stage, pk = parts
        rows = []
        src = paper_source(key, stage, pk)
        if src:
            rows.append([InlineKeyboardButton('📄 Official Syllabus PDF', url=src)])
        else:
            rows.append([InlineKeyboardButton('🔎 Find Official Syllabus PDF', callback_data=f'findsy:{key}')])
        if section == 'sy':
            rows.append([InlineKeyboardButton('📝 PYQ / Old Papers', callback_data=f'pq:e:{key}')])
        else:
            rows.append([InlineKeyboardButton('🔎 Find Official PYQ PDFs', callback_data=f'pqfind:{key}:{stage}')])
        rows.append([InlineKeyboardButton('◀️ Back', callback_data=f'{section}:s:{key}:{stage}')])
        await q.edit_message_text(detail_text(key, stage, pk), reply_markup=InlineKeyboardMarkup(rows))
        return


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    waiting = context.user_data.get('waiting')

    if waiting:
        context.user_data.pop('waiting', None)
        key = find_exam(text)
        if key:
            if waiting == 'sy':
                await update.message.reply_text(
                    f"📋 {CATALOG[key]['name']}\n\nLevel / Stage चुनें 👇",
                    reply_markup=stage_menu('sy', key),
                )
            else:
                await show_pyq_message(update, key)
        else:
            await do_dynamic(update, context, text, waiting)
        return

    key = find_exam(text)
    if key:
        stage = detect_stage(key, text)
        pk = detect_paper(key, stage, text)
        low = text.lower()
        wants_pyq = any(x in low for x in ('pyq', 'old paper', 'previous paper', 'question paper'))
        wants_syl = any(x in low for x in ('syllabus', 'scheme'))
        if wants_pyq:
            await show_pyq_message(update, key)
            return
        if wants_syl:
            src = paper_source(key, stage, pk)
            rows = []
            if src:
                rows.append([InlineKeyboardButton('📄 Official Syllabus PDF', url=src)])
            else:
                rows.append([InlineKeyboardButton('🔎 Find Official Syllabus PDF', callback_data=f'findsy:{key}')])
            rows.append([InlineKeyboardButton('📝 PYQ', callback_data=f'pq:e:{key}')])
            await update.message.reply_text(detail_text(key, stage, pk), reply_markup=InlineKeyboardMarkup(rows))
            return
        await update.message.reply_text(
            f"🔎 {CATALOG[key]['name']}\n\nक्या चाहिए?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('📋 Syllabus', callback_data=f'sy:e:{key}'), InlineKeyboardButton('📝 PYQ', callback_data=f'pq:e:{key}')],
                [InlineKeyboardButton('🏠 Main Menu', callback_data='home')],
            ]),
        )
        return

    await update.message.reply_text(
        '🤖 Exam name या अपना सवाल लिखें.\n\nSyllabus/PYQ के लिए main menu से option भी चुन सकते हैं.',
        reply_markup=main_menu(),
    )


async def show_pyq_message(update, key):
    e = CATALOG[key]
    rows = []
    for sk, stage in e['stages'].items():
        rows.append([InlineKeyboardButton('📚 ' + stage['label'], callback_data=f'pq:s:{key}:{sk}')])
    rows.append([InlineKeyboardButton('📋 Syllabus', callback_data=f'sy:e:{key}')])
    await update.message.reply_text(
        f"📝 {e['name']} — PYQ / Old Papers\n\nLevel / Stage चुनें 👇",
        reply_markup=InlineKeyboardMarkup(rows),
    )


telegram_app.add_handler(CommandHandler('start', start))
telegram_app.add_handler(CallbackQueryHandler(button))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))


@asynccontextmanager
async def lifespan(api):
    await telegram_app.initialize()
    await telegram_app.start()
    endpoint = f'{WEBHOOK_URL}{WEBHOOK_PATH}'
    await telegram_app.bot.set_webhook(url=endpoint, drop_pending_updates=True)
    me = await telegram_app.bot.get_me()
    info = await telegram_app.bot.get_webhook_info()
    print(f'🤖 EXAM SAATHI AI | phase=1 | bot=@{me.username} | id={me.id}')
    print(f'🔗 Configured webhook: {endpoint}')
    print(f'📡 Telegram webhook: {info.url or "NOT REGISTERED"}')
    print(f'📥 Pending updates: {info.pending_update_count}')
    print(f'⚠️ Last webhook error: {info.last_error_message or "None"}')
    yield
    # Do not delete webhook on shutdown; Render restarts must not erase the new webhook.
    await telegram_app.stop()
    await telegram_app.shutdown()


api = FastAPI(title='EXAM SAATHI AI — Phase 1', version='1.1.0', lifespan=lifespan)


@api.get('/')
async def home():
    return {'status': 'ok', 'service': 'EXAM SAATHI AI', 'phase': '1', 'build': 'phase1-callback-pdf-fix-v2'}


@api.get('/health')
async def health():
    return {'status': 'healthy', 'phase': 1}


@api.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    print('📨 Telegram update received')
    await telegram_app.process_update(Update.de_json(data, telegram_app.bot))
    return {'ok': True}
