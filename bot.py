import os, re, asyncio, json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from services.exam_engine import CATALOG, find_exam, detect_stage, detect_paper
from services.official_search import search_exam

BOT_TOKEN=os.getenv('BOT_TOKEN')
WEBHOOK_URL=os.getenv('WEBHOOK_URL','').rstrip('/')
PORT=int(os.getenv('PORT','10000'))
WEBHOOK_PATH='/telegram/webhook'
if not BOT_TOKEN: raise RuntimeError('BOT_TOKEN environment variable is missing.')
if not WEBHOOK_URL: raise RuntimeError('WEBHOOK_URL environment variable is missing.')

telegram_app=Application.builder().token(BOT_TOKEN).build()


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📋 Syllabus',callback_data='sy'),InlineKeyboardButton('📝 PYQ / Old Paper',callback_data='pq')],
        [InlineKeyboardButton('🧠 Mock Test',callback_data='mock'),InlineKeyboardButton('📝 Notes',callback_data='notes')],
        [InlineKeyboardButton('🤖 Ask AI',callback_data='ai'),InlineKeyboardButton('⏰ Reminder',callback_data='reminder')]
    ])

def section_menu(section):
    keys=list(CATALOG)
    rows=[]
    for i in range(0,len(keys),2):
        rows.append([InlineKeyboardButton(CATALOG[k]['name'],callback_data=f'{section}:e:{k}') for k in keys[i:i+2]])
    rows.append([InlineKeyboardButton('🔎 Other Exam',callback_data=f'{section}:other')])
    rows.append([InlineKeyboardButton('🏠 Main Menu',callback_data='home')])
    return InlineKeyboardMarkup(rows)

def stage_menu(section,key):
    e=CATALOG[key]; rows=[]
    for sk,stage in e['stages'].items():
        rows.append([InlineKeyboardButton('📚 '+stage['label'],callback_data=f'{section}:s:{key}:{sk}')])
    if e.get('syllabus_pdf'):
        rows.append([InlineKeyboardButton('📄 Official Syllabus PDF',url=e['syllabus_pdf'])])
    elif e.get('notice_pdf'):
        rows.append([InlineKeyboardButton('📄 Official Notice / Source',url=e['notice_pdf'])])
    rows += [[InlineKeyboardButton('◀️ Back',callback_data=section)]]
    return InlineKeyboardMarkup(rows)

def paper_menu(section,key,stage):
    e=CATALOG[key]['stages'][stage]; rows=[]
    for pk,p in e['papers'].items(): rows.append([InlineKeyboardButton('📄 '+p['label'],callback_data=f'{section}:p:{key}:{stage}:{pk}')])
    rows.append([InlineKeyboardButton('◀️ Back',callback_data=f'{section}:e:{key}')])
    return InlineKeyboardMarkup(rows)

def detail_text(key,stage,pk):
    e=CATALOG[key]; st=e['stages'][stage]; p=st['papers'][pk]
    lines=[f"📋 {e['name']}",f"📚 {st['label']}",f"📄 {p['label']}"]
    if p.get('marks') is not None: lines.append(f"💯 Marks: {p['marks']}")
    if p.get('questions') is not None: lines.append(f"❓ Questions: {p['questions']}")
    if p.get('time'): lines.append(f"⏱ Time: {p['time']}")
    if p.get('negative'): lines.append(f"➖ Negative: {p['negative']}")
    if p.get('subjects'):
        lines.append(''); lines.append('📚 Subjects / Topics:')
        for s in p['subjects']:
            if isinstance(s,dict):
                line='• '+s['name']+(f" — {s['marks']} marks" if s.get('marks') is not None else '')
                lines.append(line)
                for t in s.get('topics',[]): lines.append('  └ '+t)
    if p.get('units'):
        lines.append(''); lines.append('📚 Units:')
        lines.extend('• '+u for u in p['units'])
    lines.append(''); lines.append('ℹ️ Full official syllabus PDF is the final source for complete wording.')
    return '\n'.join(lines)

def paper_source(key,stage):
    e=CATALOG[key]
    if stage in e['stages'] and e['stages'][stage].get('syllabus_pdf'): return e['stages'][stage]['syllabus_pdf']
    return e.get('syllabus_pdf') or e.get('notice_pdf') or e.get('official_page')

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text('🎓 EXAM SAATHI AI\n\nExam या अपना सवाल सीधे लिखें।\n\n📚 Preparation ke liye option choose karein 👇',reply_markup=main_menu())

async def show_section(q,section):
    title='📋 Syllabus' if section=='sy' else '📝 PYQ / Old Paper'
    await q.edit_message_text(f'{title}\n\nअपनी परीक्षा चुनें 👇',reply_markup=section_menu(section))

async def show_other(q,context,section):
    context.user_data['waiting']=section
    await q.edit_message_text('🔎 Other Exam\n\nकिसी भी exam का नाम लिखें।\n\nExample: SSC CGL, UPSC, CTET, Railway NTPC, Rajasthan JEN, Jail Prahari',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('◀️ Back',callback_data=section)]]))

async def show_pyq_known(q,key):
    e=CATALOG[key]
    rows=[]
    rows.append([InlineKeyboardButton('📄 Find Official PYQ PDF',callback_data=f'findpq:{key}')])
    rows.append([InlineKeyboardButton('📋 Syllabus',callback_data=f'sy:e:{key}')])
    rows.append([InlineKeyboardButton('◀️ Back',callback_data='pq')])
    await q.edit_message_text(f"📝 {e['name']}\n\nOfficial question-paper PDF खोज रहा हूँ.\n\nPDF मिलने पर bot सीधे PDF link देगा — generic website/archive link नहीं. 👇",reply_markup=InlineKeyboardMarkup(rows))

async def do_dynamic(update,context,exam,kind,edit_message=None):
    target=edit_message
    if target:
        await target.edit_text(f'🔎 {exam}\n\nOfficial {"syllabus" if kind=="sy" else "PYQ / old paper"} PDF खोज रहा हूँ…')
    else:
        target=await update.message.reply_text(f'🔎 {exam}\n\nOfficial source खोज रहा हूँ…')
    results=await search_exam(exam,'syllabus' if kind=='sy' else 'pyq')
    if not results:
        await target.edit_text(f'⚠️ {exam}\n\nVerified official source नहीं मिला.\n\nBot ने कोई unverified PDF invent नहीं की.',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('◀️ Back',callback_data=kind)]]))
        return
    rows=[]
    for r in results[:8]:
        icon='📄' if r['pdf'] else '🌐'
        rows.append([InlineKeyboardButton(icon+' '+('PDF: ' if r['pdf'] else '')+r['title'][:45],url=r['url'])])
    rows.append([InlineKeyboardButton('◀️ Back',callback_data=kind)])
    await target.edit_text(f'🔎 {exam}\n\nOfficial source से actual PDF links मिले हैं. सीधे PDF खोलने के लिए चुनें 👇',reply_markup=InlineKeyboardMarkup(rows))

async def button(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); d=q.data
    if d=='home':
        context.user_data.clear(); await q.edit_message_text('🎓 EXAM SAATHI AI\n\nExam या अपना सवाल सीधे लिखें 👇',reply_markup=main_menu()); return
    if d in ('sy','pq'):
        await show_section(q,d); return
    if d in ('mock','notes','ai','reminder'):
        text={'mock':'🧠 Mock Test\n\nPhase 1 में syllabus/PYQ engine तैयार किया जा रहा है. Mock Test next phase में इसी verified syllabus से बनेगा.', 'notes':'📝 Notes\n\nNotes engine next phase में इसी verified syllabus से जुड़ेगा.', 'ai':'🤖 Ask AI\n\nआप सवाल अभी सीधे लिख सकते हैं. Full exam-context AI next phase में जुड़ेगा.', 'reminder':'⏰ Reminder\n\nReminder scheduler next phase में जुड़ेगा.'}[d]
        await q.edit_message_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 Main Menu',callback_data='home')]])); return
    if d in ('sy','pq'): return
    if d in ('sy:other','pq:other'):
        await show_other(q,context,d.split(':')[0]); return
    if d.startswith('findpq:'):
        key=d.split(':',1)[1]; await do_dynamic(None,context,CATALOG[key]['name'],'pq',q); return
    if d.startswith('findsy:'):
        key=d.split(':',1)[1]; await do_dynamic(None,context,CATALOG[key]['name'],'sy',q); return
    p=d.split(':')
    if len(p)==3 and p[1]=='e':
        section,key=p[0],p[2]
        if section=='sy': await q.edit_message_text(f"📋 {CATALOG[key]['name']}\n\nLevel / Stage चुनें 👇",reply_markup=stage_menu(section,key))
        else: await show_pyq_known(q,key)
        return
    if len(p)==4 and p[1]=='s':
        section,key,stage=p[0],p[2],p[3]
        await q.edit_message_text(f"📚 {CATALOG[key]['name']}\n\n{CATALOG[key]['stages'][stage]['label']}\n\nPaper चुनें 👇",reply_markup=paper_menu(section,key,stage)); return
    if len(p)==5 and p[1]=='p':
        section,key,stage,pk=p
        rows=[]
        src=paper_source(key,stage)
        if src and src.lower().split('?')[0].endswith('.pdf'):
            rows.append([InlineKeyboardButton('📄 Official Syllabus PDF',url=src)])
        else:
            rows.append([InlineKeyboardButton('🔎 Find Official Syllabus PDF',callback_data=f'findsy:{key}')])
        if section=='sy': rows.append([InlineKeyboardButton('📝 PYQ / Old Papers',callback_data=f'pq:e:{key}')])
        rows.append([InlineKeyboardButton('◀️ Back',callback_data=f'{section}:s:{key}:{stage}')])
        await q.edit_message_text(detail_text(key,stage,pk),reply_markup=InlineKeyboardMarkup(rows)); return

async def text_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    text=(update.message.text or '').strip()
    waiting=context.user_data.get('waiting')
    if waiting:
        context.user_data.pop('waiting',None)
        key=find_exam(text)
        if key:
            if waiting=='sy': await update.message.reply_text(f"📋 {CATALOG[key]['name']}\n\nLevel / Stage चुनें 👇",reply_markup=stage_menu('sy',key))
            else: await show_pyq_message(update,key)
        else:
            await do_dynamic(update,context,text,waiting)
        return
    key=find_exam(text)
    if key:
        stage=detect_stage(key,text); pk=detect_paper(key,stage,text)
        wants_pyq=any(x in text.lower() for x in ('pyq','old paper','previous paper','question paper'))
        wants_syl=any(x in text.lower() for x in ('syllabus','scheme'))
        if wants_pyq:
            await show_pyq_message(update,key); return
        if wants_syl:
            await update.message.reply_text(detail_text(key,stage,pk),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📄 Official Syllabus PDF',url=paper_source(key,stage)) if paper_source(key,stage).lower().split('?')[0].endswith('.pdf') else InlineKeyboardButton('🔎 Find Official Syllabus PDF',callback_data=f'findsy:{key}')],[InlineKeyboardButton('📝 PYQ',callback_data=f'pq:e:{key}')]])); return
        await update.message.reply_text(f"🔎 {CATALOG[key]['name']}\n\nक्या चाहिए?",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📋 Syllabus',callback_data=f'sy:e:{key}'),InlineKeyboardButton('📝 PYQ',callback_data=f'pq:e:{key}')],[InlineKeyboardButton('🏠 Main Menu',callback_data='home')]])); return
    await update.message.reply_text('🤖 Exam name या अपना सवाल लिखें.\n\nSyllabus/PYQ के लिए main menu से option भी चुन सकते हैं.',reply_markup=main_menu())

async def show_pyq_message(update,key):
    e=CATALOG[key]
    await update.message.reply_text(f"📝 {e['name']} — PYQ / Old Papers\n\nBot official source से actual PDF खोजेगा. Generic website link नहीं दिया जाएगा. 👇",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📄 Find Official PYQ PDF',callback_data=f'findpq:{key}')],[InlineKeyboardButton('📋 Syllabus',callback_data=f'sy:e:{key}')]]))

telegram_app.add_handler(CommandHandler('start',start))
telegram_app.add_handler(CallbackQueryHandler(button))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))

@asynccontextmanager
async def lifespan(api):
    await telegram_app.initialize(); await telegram_app.start()
    endpoint=f'{WEBHOOK_URL}{WEBHOOK_PATH}'
    await telegram_app.bot.set_webhook(url=endpoint,drop_pending_updates=True)
    me=await telegram_app.bot.get_me(); info=await telegram_app.bot.get_webhook_info()
    print(f'🤖 EXAM SAATHI AI | phase=1 | bot=@{me.username} | id={me.id}')
    print(f'🔗 Configured webhook: {endpoint}')
    print(f'📡 Telegram webhook: {info.url or "NOT REGISTERED"}')
    print(f'📥 Pending updates: {info.pending_update_count}')
    print(f'⚠️ Last webhook error: {info.last_error_message or "None"}')
    yield
    # IMPORTANT: do not delete webhook on shutdown; Render restarts must not erase the new webhook.
    await telegram_app.stop(); await telegram_app.shutdown()

api=FastAPI(title='EXAM SAATHI AI — Phase 1',version='1.0.0',lifespan=lifespan)

@api.get('/')
async def home():
    return {'status':'ok','service':'EXAM SAATHI AI','phase':'1','build':'structured-syllabus-pyq-v1'}

@api.get('/health')
async def health(): return {'status':'healthy','phase':1}

@api.post(WEBHOOK_PATH)
async def webhook(request:Request):
    data=await request.json(); print('📨 Telegram update received')
    await telegram_app.process_update(Update.de_json(data,telegram_app.bot))
    return {'ok':True}
