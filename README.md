# Exam Saathi AI

**Telegram display name:** Study Saathi AI

A Hindi-first AI exam study assistant for competitive and government exams.
**Phase 1 focus:** Rajasthan exams (REET, RAS, Rajasthan SI, Patwari, Rajasthan CET).
Architecture is built to expand to any Indian exam in later phases.

---

## ✅ Phase 1 features (fully working)

- **📋 Syllabus engine** — exam → level/stage → paper (→ subject group where
  applicable) → structured syllabus with an official PDF button.
- **📝 PYQ / Old Paper engine** — exam → level → paper → *dynamically
  discovered* years, each backed by a real PDF link found on the official
  government page at request time (never a hardcoded/guessed year).
- **🔎 Other Exam** — free-text search for exams outside the curated
  Rajasthan list (SSC, UPSC, CTET, NEET, JEE, Railway, etc.), restricted to
  known official domains.
- **Natural language input** — typing `"REET Level 1 syllabus"`,
  `"patwari old paper 2025"`, `"ras mains paper 1"` etc. works without
  touching a single button.
- **Anti-hallucination by design** — the bot never invents exam years, PDF
  URLs, question counts, marks, or syllabus topics. Where data isn't
  verified it says so explicitly instead of guessing.

## 🚧 Placeholder-only (Phase 2+, not implemented yet)

- 🧠 Mock Test
- 📝 Notes
- 🤖 Ask AI
- ⏰ Reminder
- 📊 Student Progress

These buttons exist in the main menu and show a clean "coming soon"
message — they do not fake functionality.

---

## Folder structure

```
exam-saathi-ai/
├── bot.py                    # FastAPI app + all Telegram handlers
├── requirements.txt
├── render.yaml
├── README.md
├── data/
│   └── exams.json            # all exam/syllabus data — no data in bot.py
└── services/
    ├── __init__.py
    ├── exam_engine.py        # syllabus lookups, keyboards, NL matching
    ├── pyq_engine.py         # PYQ year discovery + formatting
    └── official_search.py    # generic official-source crawler/classifier
```

Adding a new exam or a new phase never requires touching `bot.py`'s core
routing — only `data/exams.json` and, for genuinely new behaviour, the
relevant service module.

---

## Environment variables

| Variable      | Required | Description                                                                 |
|---------------|----------|-------------------------------------------------------------------------------|
| `BOT_TOKEN`   | Yes      | Telegram bot token from [@BotFather](https://t.me/BotFather).                |
| `WEBHOOK_URL` | Recommended | Public base URL of your deployment, e.g. `https://exam-saathi-ai.onrender.com`. If set, the app configures the Telegram webhook automatically on startup. |

Never commit these to GitHub. Set them in Render's dashboard (or a local
`.env` file that is **not** committed) instead.

---

## Running locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

export BOT_TOKEN="123456:your-telegram-token"
# Local testing without a public URL: skip WEBHOOK_URL and use a tunnel
# (e.g. ngrok) if you want to test webhooks locally, or temporarily poll
# instead (see "Local polling" note below).

uvicorn bot:api --host 0.0.0.0 --port 8000
```

Then, if you have a tunnel (e.g. `ngrok http 8000`), set:

```bash
export WEBHOOK_URL="https://<your-ngrok-id>.ngrok.io"
```
and restart — the app will call `setWebhook` automatically pointing at
`WEBHOOK_URL + /telegram/webhook`.

**Local polling alternative:** if you don't want to deal with webhooks
while developing, you can temporarily run
`application.run_polling()` in a throwaway script that imports
`bot.application` — the handlers are identical either way.

---

## Deploying to Render

1. Push this project to a GitHub repo (root of the repo = root of this
   project — no extra nesting).
2. On Render: **New → Web Service** → connect the repo. Render will read
   `render.yaml` automatically, or set manually:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn bot:api --host 0.0.0.0 --port $PORT`
3. Add environment variables `BOT_TOKEN` and `WEBHOOK_URL` (the latter is
   your Render service URL, e.g. `https://exam-saathi-ai.onrender.com`)
   in the Render dashboard.
4. Deploy. On startup the app calls Telegram's `setWebhook` pointing to
   `WEBHOOK_URL/telegram/webhook`.

### Webhook behaviour

- Webhook path: **`/telegram/webhook`** (POST).
- The webhook is **(re)configured on every startup** if `WEBHOOK_URL` is
  set — so a Render restart or redeploy re-registers it automatically.
- The webhook is **never deleted on shutdown** — this is intentional so
  routine Render restarts don't cause a window where Telegram has no
  webhook registered.
- `GET /` is a simple health check Render can ping.

---

## How to add a new exam

Edit `data/exams.json` → add a new key under `"exams"`:

```json
"my_new_exam": {
  "id": "my_new_exam",
  "name": "My New Exam",
  "full_name": "Full official name",
  "aliases": ["shortname", "common misspelling"],
  "source_label": "Official <Authority Name>",
  "official_syllabus_pdf": "https://official-domain.gov.in/syllabus.pdf",
  "official_archive": "https://official-domain.gov.in/",
  "levels": {
    "level_id": {
      "id": "level_id",
      "name": "Display Name",
      "aliases": ["alt name"],
      "papers": {
        "paper_id": {
          "id": "paper_id",
          "name": "Paper Display Name",
          "aliases": [],
          "questions": null,
          "marks": null,
          "duration": null,
          "pattern_verified": false,
          "subjects": []
        }
      }
    }
  }
}
```

Also add an entry under `"pyq_sources"` with the official page(s) where
that exam's past papers are published, so the PYQ engine can crawl them.

**Rule:** never fill `questions` / `marks` / `duration` with numbers you
haven't verified against an official source — leave them `null` and set
`"pattern_verified": false`. The bot will render an honest "verify in
official PDF" message instead of a possibly-wrong number.

## How to add an official PDF

- For a **syllabus PDF**, set `official_syllabus_pdf` on the exam (or
  `official_pdf` on a specific paper if different papers have different
  syllabus documents, like RAS/SI).
- For **past-paper PDFs**, you don't hardcode individual years — add the
  official archive/listing page URL to `pyq_sources` for that exam, and
  `services/official_search.py` will discover and classify individual
  year PDFs automatically at request time (cached for 6 hours).

---

## Anti-hallucination rules baked into the code

- `pattern_verified: false` in `exams.json` blocks the bot from ever
  printing questions/marks/duration for that paper.
- The PYQ engine only shows a year button if a PDF link mentioning that
  year was physically present on the fetched official page — it never
  fabricates a URL.
- Question papers and answer keys are classified separately and never
  mislabelled as each other.
- If a page can't be reached (network error, timeout, site down), the
  bot says so plainly instead of pretending nothing is wrong or
  guessing content.

---

## Error handling & resilience

- All callback data is parsed defensively — malformed/unknown
  `callback_data` falls back to the main menu instead of crashing.
- Network calls (`httpx`) are wrapped in try/except for timeouts and
  transport errors.
- A global Telegram error handler logs unhandled exceptions instead of
  letting them crash the process.
- The webhook endpoint always returns HTTP 200 to Telegram (even on
  internal errors) so Telegram doesn't get stuck retrying a bad update.

---

## Verifying the project

```bash
python -m py_compile bot.py services/*.py
python -c "import json; json.load(open('data/exams.json'))"
```

Both commands should complete with no output/errors.

---

## Phase 1 limitations

- Detailed subject → topic → sub-topic breakdowns are only populated for
  REET (well-documented, stable pattern). Other exams currently link
  directly to the official syllabus PDF rather than a fabricated topic
  list.
- Exam pattern numbers (question count / marks / duration) are shown
  only for REET, since the spec forbids inventing unverified figures for
  exams whose pattern wasn't explicitly confirmed against an official
  source in this build.
- `official_syllabus_pdf` / advertisement PDF links (especially for
  Patwari and CET, which live at `.../advertisement_item/<id>.pdf` URLs)
  are tied to a specific recruitment cycle and **will need updating**
  when RSSB publishes a new notification — update
  `data/exams.json`, no code change needed.
- "Other Exam" search only recognises a small curated set of domains
  (`known_official_domains` in `exams.json`); anything else is answered
  honestly as "could not be verified" rather than guessed.
- Mock Test, Notes, Ask AI, Reminder, and Student Progress are UI
  placeholders only (see Future Phases below).

## Future phases (architecture is ready for these)

| Phase | Feature | Notes |
|-------|---------|-------|
| 2 | 🧠 Mock Test | exam → subject → topic → question count → timer → score → explanations → weak-topic tracking |
| 3 | 📝 Notes | short/detailed/revision notes, PDF notes where legally available |
| 4 | 🤖 Ask AI | Hindi doubt-solving, MCQ solving, concept explanation |
| 5 | ⏰ Reminder | daily study reminders, exam countdowns, revision reminders |
| 6 | 📊 Student Progress | mock scores, weak subjects, streaks, analytics |

Each phase should get its own `services/<phase>_engine.py`, following the
same pattern as `exam_engine.py` / `pyq_engine.py`, and its own menu
branch in `bot.py`'s `on_callback` router.
