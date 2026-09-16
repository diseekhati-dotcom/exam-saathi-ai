# Exam Saathi AI

**Telegram display name:** Study Saathi AI

A Hindi-first AI exam study assistant for competitive and government exams.
**Phase 1 focus:** Rajasthan exams (REET, RAS, Rajasthan SI, Patwari, Rajasthan CET).
Architecture is built to expand to any Indian exam in later phases.

---

## 🆕 General Rajasthan Exam Discovery System

On top of the original curated Syllabus/PYQ flow, the bot now has a
**generic, authority-driven discovery engine** that isn't limited to a
short hardcoded exam list:

- **`/exam <name>`** — e.g. `/exam CET 12`, `/exam Patwar`, `/exam Lab Assistant`,
  `/exam 1st Grade` — identifies the exam, works out which authority
  conducts it (RSSB / RPSC / RBSE, extensible to others), crawls that
  authority's official archive pages, and returns verified Syllabus /
  Question Paper / Answer Key PDFs with **Final/Revised Final answer keys
  and Master Question Papers prioritised** over provisional/regular ones.
- **Free text also works** for exams outside the original 6 — typing
  `"Lab Assistant"`, `"VDO"`, `"1st Grade"` etc. routes here automatically.
  The original 6 exams (REET, RAS, SI, Patwari, CET Senior Secondary, CET
  Graduation) keep using the existing nicer button-based flow, unchanged.
- **Nothing is ever shown unless verified** — every candidate PDF link is
  checked (HTTPS-only, SSRF-safe, content-type/magic-byte verified,
  size-capped, timeout-protected) before it's offered as a button. Broken
  or fake-looking links are silently dropped, not shown as "maybe".
- **Extensible by data, not code** — new exams go in
  `config/exam_sources.py`'s `EXAM_REGISTRY`; new authorities go in its
  `AUTHORITIES` dict. No Python changes needed for either.

### New files

```
config/
├── __init__.py
└── exam_sources.py          # AUTHORITIES (official base URLs/archive pages)
                              # + EXAM_REGISTRY (fast-path known exams)
handlers/
├── __init__.py
└── exam_commands.py         # /exam command + report rendering
services/
├── authority_discovery.py   # exam name -> (exam, authority) identification
├── document_discovery.py    # crawl + classify + tier-rank + dedupe documents
├── pdf_validator.py         # HTTPS/SSRF/content-type/size verification
└── exam_cache.py            # TTL cache + per-domain rate limiter
```

### Supported authorities (extensible)

| Authority | Conducts (examples) | Archive pages configured? |
|---|---|---|
| **RSSB** (`rsmssb.rajasthan.gov.in`) | CET Senior Secondary, CET Graduation, Patwari, VDO, LDC, Clerk, Lab Assistant, Agriculture Supervisor, Animal Attendant, Junior Instructor, Supervisor, Stenographer, Informatics Assistant, Hostel Superintendent | ✅ Syllabus, Question Paper, Answer Key |
| **RPSC** (`rpsc.rajasthan.gov.in`) | RAS, SI/Platoon Commander, School Lecturer (1st Grade), Senior Teacher (2nd Grade), Assistant Professor, Junior Legal Officer, Assistant Engineer, Statistical Officer, Agriculture Officer | ✅ Syllabus, Question Paper, Answer Key |
| **RBSE/REET** (`rajeduboard.rajasthan.gov.in`) | REET Level 1, REET Level 2, RTET | ✅ Syllabus, Question Paper, Answer Key |
| **Rajasthan High Court** (`hcraj.nic.in`) | Civil Judge, LDC, Junior Judicial Assistant, etc. | Authority identified only — archive pages not yet configured |
| **Rajasthan Police** (`police.rajasthan.gov.in`) | Constable, Home Guard | Authority identified only — archive pages not yet configured |

For an authority with no archive pages configured, the bot correctly
names the authority and links to its homepage, but honestly says
document discovery isn't set up for it yet — it never guesses.

### How exam identification works

1. **Registry match** (`authority_discovery.match_registry_exam`) — checks
   the free text against `EXAM_REGISTRY`'s names/aliases first (exact
   substring for common phrasing, dampened fuzzy match for typos on
   longer names only — short aliases like `"si"` are excluded from fuzzy
   matching specifically because they're accidental substrings of
   unrelated words, e.g. "as-**si**stant").
2. **Keyword authority guess** — if no exact exam matches, authority
   `keyword_hints` are checked so an exam outside the registry can still
   be routed to the right conducting body.
3. **Honest "not found"** — if neither matches, the bot says so instead
   of guessing.

### How document discovery + priority works

For each configured archive page (`document_discovery.py`):
1. Fetch (cached, rate-limited per domain) → extract every PDF link.
2. Keep only links whose text/href mentions the exam's aliases (this is
   what prevents Patwari PDFs from ever appearing under a CET search).
3. Classify by keyword: syllabus / question paper (**Master Question
   Paper** tier > regular) / answer key (**Revised Final** > **Final** >
   **Primary** > **Provisional**).
4. Detect year and paper number from the link text.
5. For each (year, paper) group, keep only the **highest-tier** document
   — so a Final Answer Key silently replaces the Provisional one that
   preceded it, without deleting other years.
6. Verify each surviving candidate via `pdf_validator.verify_pdf_url`
   (HTTPS + SSRF-safe + real PDF content-type/magic-bytes + size cap).
   Only verified links reach the user.

### Caching, rate limiting & security

- `services/exam_cache.py` caches both raw archive-page scrapes and
  fully classified/verified document lists (6-hour TTL — good enough for
  official pages that don't change every minute), keyed by
  `exam + authority + document_type`.
- A `DomainRateLimiter` enforces a minimum interval between requests to
  the same domain, so the bot is a well-behaved crawler even under load.
- `services/pdf_validator.py` blocks non-HTTP(S) schemes, resolves and
  rejects private/loopback/link-local IPs (SSRF), re-validates the host
  after every redirect, caps response size, and times out every request
  — a slow or hostile official site can never hang or crash the bot.

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
│   └── exams.json            # curated syllabus/UI data for the original 6 exams
├── config/
│   ├── __init__.py
│   └── exam_sources.py       # authority + exam registry (see "General Discovery System")
├── handlers/
│   ├── __init__.py
│   └── exam_commands.py      # /exam command + generic report rendering
└── services/
    ├── __init__.py
    ├── exam_engine.py        # syllabus lookups, keyboards, NL matching (original 6 exams)
    ├── pyq_engine.py         # PYQ year discovery + formatting (original 6 exams)
    ├── official_search.py    # low-level fetch/extract/classify primitives (shared)
    ├── authority_discovery.py# exam name -> (exam, authority) identification
    ├── document_discovery.py # generic multi-authority document discovery + tiering
    ├── pdf_validator.py      # PDF link verification (HTTPS/SSRF/content-type/size)
    └── exam_cache.py         # TTL cache + per-domain rate limiter
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

## Extending the general discovery system

- **New exam under an existing authority** (RSSB/RPSC/RBSE): add one
  entry to `EXAM_REGISTRY` in `config/exam_sources.py` — name, aliases,
  `authority` id. That's it; `document_discovery.py` already knows how to
  crawl that authority's configured archive pages for it.
- **New authority entirely** (e.g. a board not yet listed): add an entry
  to `AUTHORITIES` with its **verified** `base_url`. If you don't yet have
  its archive-page URLs, leave `doc_pages` empty — the bot will still
  correctly name the authority and link to its homepage rather than
  guessing.
- **Never** add a `base_url` or archive-page URL you haven't personally
  verified — an unverified guess is worse than an honest "not configured
  yet".

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
