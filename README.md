# Exam Saathi AI — Syllabus + PYQ

This build is based on the working FastAPI + Telegram webhook version.

## Render
Environment variables:
- `BOT_TOKEN` = Telegram BotFather token
- `WEBHOOK_URL` = your Render public URL, e.g. `https://exam-saathi-ai-rffr.onrender.com`

Start command:
`uvicorn bot:api --host 0.0.0.0 --port $PORT`

The bot now includes:
- Main menu
- Official-source-first Syllabus menu
- Official/public PYQ archive menu
- REET, Patwari, RAS and Rajasthan SI quick detection
- Natural-language detection for common Syllabus/PYQ requests
- No invented missing years/papers
- Existing webhook/FastAPI setup preserved
