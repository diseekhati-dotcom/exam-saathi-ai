# EXAM SAATHI AI — Phase 1

Structured **Syllabus + PYQ / Old Paper** Telegram bot foundation.

## Phase 1 includes
- Button-first Telegram UI
- REET Level 1 / Level 2
- Rajasthan Patwari
- RAS Prelims / Mains Paper I–IV
- Rajasthan SI Paper I / II
- CET Senior Secondary / Graduation
- Official syllabus PDF/source buttons
- Official PYQ/archive buttons
- Official-domain PDF discovery for Other Exam
- Direct text queries such as `REET Level 1 syllabus`, `RAS mains paper 2 syllabus`, `SI paper 2 syllabus`, `REET PYQ`
- No fake years and no invented official PDFs
- Webhook shutdown fix: the bot does **not** delete its webhook when Render restarts

## Deploy on Render
Build command:
`pip install -r requirements.txt`

Start command:
`uvicorn bot:api --host 0.0.0.0 --port $PORT`

Environment variables:
- `BOT_TOKEN` = your Telegram bot token
- `WEBHOOK_URL` = `https://exam-saathi-ai-rffr.onrender.com`

Do not add `/telegram/webhook` to `WEBHOOK_URL`; the code adds that path itself.

## Important upload layout
Upload these files/folders to the **repository root**:

```text
bot.py
requirements.txt
render.yaml
README.md
data/exams.json
services/exam_engine.py
services/official_search.py
services/pyq_engine.py
```

Do NOT upload the ZIP as a nested `src/` folder.

## Next phases
Phase 2: real Mock Test engine.
Phase 3: Notes + Ask AI.
Phase 4: Reminder + broader exam database/caching.
