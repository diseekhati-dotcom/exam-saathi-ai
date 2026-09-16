# Rajasthan Exam Information Bot (Phase 1)

A Telegram bot that finds **official** syllabus, previous question papers,
and answer keys for Rajasthan government/competitive exams, verified
directly from the conducting authority's own website — never a coaching
site, never a guessed URL.

## Honesty notice (read this first)

This project was built in a sandboxed environment **with no outbound
network access**. That means:

- All Python code (scraper, PDF validator, Telegram bot, cache, security
  layer) is real and functional — nothing here is a stub or a mock.
- **Live scraping/verification against rssb.rajasthan.gov.in,
  rsmssb.rajasthan.gov.in, rpsc.rajasthan.gov.in, etc. could not be run
  during the build.** The pipeline was instead proven correct with an
  extensive **offline** test suite (106 tests, all passing — see below)
  that feeds it realistic fake HTTP responses (real PDFs, HTML error
  pages, 404s, redirects, tiny fake PDFs, SSRF attempts, etc.) and checks
  it does the right thing with each.
- A small number of official authority URLs were checked with live web
  search during the build (see "Web-verified seeds" below) to make sure
  the registry starts from real domains, not guesses.
- Run `test_live.py` after deploying (see below) to get real, live
  verification results.

## What Phase 1 actually does

1. `/exam <name>` — normalizes the exam name (handles aliases like "SI" /
   "Sub Inspector", "CET 12" / "CET Senior Secondary", "3rd Grade" /
   "Primary Teacher Level 1", etc.) and matches it against a seed exam
   registry.
2. Shows an exam card with the conducting authority and three buttons:
   Syllabus / Question Papers / Answer Keys.
3. Each button triggers **live discovery**: the bot fetches the
   authority's real official page(s), parses every link, and keeps only
   the ones whose text matches the exam + document type + year.
4. Every candidate URL is run through a real PDF validator before it is
   ever shown: HTTP status, redirect-chain resolution, final URL,
   Content-Type, `%PDF-` magic bytes, minimum file size, HTML/login/error
   page detection, and a best-effort identity check (year/shift/set/paper
   tokens).
5. Only URLs that pass become a "📄 Download ... (PDF)" button, using the
   **final verified PDF URL** — never the archive/listing page. If
   nothing verifies, the bot shows a clearly separate "🌐 Official
   Source" button to the real listing page, or an honest
   "⚠️ Official document is currently unavailable" message. It never
   fabricates a link.
6. Results are cached (SQLite) for `CACHE_TTL_SECONDS` (default 6h) keyed
   by authority+exam+doc_type+year+paper+subject+shift+set, so the bot
   doesn't re-scrape on every Telegram tap.

## Project structure

```
raj_exam_bot/
├── main.py                     # Telegram bot entrypoint (python-telegram-bot wiring)
├── test_live.py                # Real network verification — run AFTER deployment
├── requirements.txt
├── render.yaml                 # Render Background Worker config
├── runtime.txt                 # Pinned Python version
├── .env.example
├── config/
│   ├── settings.py             # Env-var driven settings, domain allowlist
│   └── exam_sources.py         # Seed authority registry (web-verified 2026-09-15)
├── database/
│   ├── models.py                # Authority / Exam / Document dataclasses
│   └── db.py                    # SQLite persistence (schema, upserts, cache table)
├── services/
│   ├── exam_normalizer.py       # Reusable alias + fuzzy-match name normalizer
│   ├── exam_registry_data.py    # Seed canonical exam list
│   ├── authority_registry.py    # Loads/queries authorities
│   ├── document_discovery.py    # Generic link-crawler + filter
│   ├── rssb_parser.py           # RSSB/RSMSSB-specific source pages
│   ├── rpsc_parser.py           # RPSC-specific source pages
│   ├── source_verifier.py       # Extracts year/shift/set/paper/doc-type from link text
│   ├── pdf_validator.py         # The real PDF verification pipeline
│   └── exam_cache.py            # SQLite-backed cache
├── handlers/
│   ├── start.py                 # /start (pure message builder, no telegram import)
│   └── exam_commands.py         # /exam + callback logic (pure message/button builders)
├── utils/
│   ├── http_client.py           # SSRF-hardened HTTP client (domain allowlist, IP checks,
│   │                             #   manual redirect validation, size cap, timeout)
│   └── logger.py
└── tests/                       # 106 offline unit tests (see below)
```

Handlers are split into a **pure logic layer** (plain dicts describing
text + buttons — testable without the `telegram` package) and a thin
adapter in `main.py` that converts those into real
`InlineKeyboardMarkup`/`InlineKeyboardButton` objects. This is why the
offline test suite can verify 100% of the bot's decision logic even
though `python-telegram-bot` itself isn't installed in this build
environment.

## Supported authorities (seed registry)

| Authority | Official domain | Web-verified 2026-09-15? |
|---|---|---|
| RSSB | rssb.rajasthan.gov.in | ✅ yes |
| RSMSSB | rsmssb.rajasthan.gov.in | ✅ yes |
| RPSC | rpsc.rajasthan.gov.in | ✅ yes |
| BSER / RBSE (REET) | rajeduboard.rajasthan.gov.in | ✅ yes |
| Rajasthan Recruitment Portal | recruitment.rajasthan.gov.in | ✅ yes |
| Rajasthan High Court | hcraj.nic.in | ⚠️ carried over from brief, not re-checked live |

**Two corrections made during the build**, exactly the kind of mistake
this bot exists to prevent:
- The brief's suggested REET URL `reet2024.co.in` is **not** an official
  government domain. REET is conducted by BSER at
  `rajeduboard.rajasthan.gov.in`. `reet2024.co.in` is excluded from the
  domain allowlist.
- `rpsc.rajasthansarkar.in` (which surfaced in search results) is an
  unofficial look-alike site, not RPSC's own domain. Also excluded.

Both exclusions are enforced in code via `KNOWN_UNOFFICIAL_DOMAINS` in
`config/exam_sources.py` and the `ALLOWED_DOMAINS` allowlist in
`config/settings.py` — the HTTP client refuses to even connect to a
non-allowlisted domain (SSRF protection doubles as an official-source
guarantee).

Rajasthan Police, Cooperative Recruitment Board, Housing Board, DISCOMs,
health/medical recruitment bodies, and university recruitment bodies were
**not** independently confirmed this session (see
`UNCONFIRMED_AUTHORITY_LEADS` in `config/exam_sources.py`) and are
intentionally left out of the allowlist rather than guessed.

## Security protections

- Domain allowlist checked **before** any request (SSRF mitigation).
- DNS resolution result checked against private/loopback/link-local/
  reserved IP ranges — rejects DNS-rebinding style attacks even against
  an allowlisted hostname.
- Redirects followed **manually**, one hop at a time, re-validating the
  allowlist and IP-safety on every hop (an allowlisted page can't redirect
  you somewhere unsafe), with a hard hop-count limit.
- Response bodies streamed and capped at `MAX_DOWNLOAD_BYTES` (default
  25MB) to prevent memory/disk exhaustion.
- Single connect+read timeout enforced on every request.
- Downloaded content is **never executed**, imported, or eval'd anywhere.
- `BOT_TOKEN` is read only from an environment variable; it is never
  hardcoded and `.env` is gitignored.

## Cache

SQLite-backed, key = `authority|exam|document_type|year|paper|subject|
shift|doc_set`, default TTL 6 hours (`CACHE_TTL_SECONDS`). Verification
timestamp is stored on each `Document.verified_at`.

## Offline tests actually executed (106/106 passing)

Run in this exact build environment:

```
$ python3 -m unittest discover -s tests -p "test_*.py"
...
Ran 106 tests in 0.13s

OK
```

Covered without any network access:
- `test_normalizer.py` (23 tests) — every alias example from the brief
  (SI/Sub Inspector, CET 12/CET Senior, 3rd Grade/Primary Teacher Level 1,
  REET L1/REET Level 1, ...) plus gibberish/empty-string rejection.
- `test_http_client.py` (13 tests) — domain allowlist incl. the two
  unofficial look-alikes, private/loopback/link-local IP rejection
  (mocked DNS), DNS-failure handling, disallowed-scheme rejection.
- `test_pdf_validator.py` (14 tests) — real PDF passes; HTML/error page,
  404, tiny fake PDF, missing magic bytes, non-HTTPS, and every
  SSRF/redirect/size exception type are all correctly turned into a
  failed result instead of a crash; identity-token confidence scoring.
- `test_document_discovery.py` (9 tests) — link parsing, relative-URL
  resolution, filtering by exam name / doc type / year, and that a
  disallowed domain or a broken page never raises.
- `test_source_verifier.py` (12 tests) — year/shift/set/paper/doc-type/
  answer-key-status extraction from realistic link text.
- `test_exam_service.py` (6 tests) — the full orchestration: a verified
  PDF flows through to a VERIFIED document with the final URL; a broken
  PDF correctly falls back to SOURCE_PAGE_ONLY with `pdf_url=None`
  (never the broken link); zero candidates never crashes.
- `test_handlers.py` (13 tests) — `/start` has no Phase 2 features;
  unknown exam gets no buttons; exam card gets exactly the right 3
  callback buttons + an official-source URL button; REJECTED documents
  produce **zero** buttons (no empty/fake buttons); VERIFIED documents
  point at `pdf_url`, never `source_page`.
- `test_db.py` (5 tests), `test_cache.py` (6 tests) — SQLite schema,
  upsert idempotency, cache expiry.

Plus, separately: `python3 -m py_compile` on every `.py` file in the
project (syntax check) and an import check of every module except
`main.py` (which needs `python-telegram-bot`, not installed in this
sandbox — see next section).

## What could NOT be run in this sandbox

- **`main.py` was not import-tested or run**, because
  `python-telegram-bot` is not installed here and the sandbox has no
  network access to `pip install` it. Every function `main.py` calls
  (`exam_service.*`, `handlers.exam_commands.*`, `handlers.start.*`) IS
  covered by the offline suite above; `main.py` itself is a thin,
  manually-reviewed adapter (dict → `InlineKeyboardMarkup`).
- **No live HTTP requests to any `.rajasthan.gov.in` / `.nic.in` site**
  were made by the test suite — the sandbox has no outbound network
  access at all. All such tests use mocked responses.
- Consequently, **no claim is made that any specific 2026 exam PDF is
  currently live and verified.** That can only be established by running
  `test_live.py` for real, after deployment.

## Running `test_live.py` after deployment

Once deployed (Render or any machine with internet access):

```bash
pip install -r requirements.txt
python test_live.py                       # runs the 11 default test-case exams
python test_live.py "Patwar"              # run just one
python test_live.py --json live_report.json
```

For each exam it will print, per document type: every candidate URL
discovered, the source page it came from, the final URL after redirects,
HTTP status, Content-Type, PDF magic-byte result, and whether it ended up
VERIFIED / REJECTED / SOURCE_PAGE_ONLY — plus a summary table at the end.
If an archive page turns out to render its links via JavaScript (a known
possibility flagged in `services/document_discovery.py`'s docstring),
this will show up honestly as 0 candidates discovered, not a false
success.

## Render deployment

This bot uses long-polling (`Application.run_polling`), so it should be
deployed as a **Background Worker**, not a Web Service (no HTTP port is
opened). `render.yaml` is provided:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py`
- **Required env var:** `BOT_TOKEN` (set in Render's Environment tab —
  get it from [@BotFather](https://t.me/BotFather); never commit it)

## Known limitations (stated honestly)

- Some Rajasthan government archive pages may render document links via
  client-side JavaScript; this build's discovery layer only sees
  server-rendered HTML (no headless browser dependency was available/
  installable in the build sandbox). Where that happens, the bot will
  correctly fall back to an "🌐 Official Source" link rather than a fake
  PDF button — but will not surface a direct-download button either,
  until a JS-rendering discovery backend is added (candidate Phase 2
  item).
- PDF identity verification checks the final URL, filename, and
  discovered link text for expected tokens (year/shift/set/paper) — it
  does not parse the PDF's own internal text layer (no PDF-text-extraction
  dependency was available/installable in the build sandbox). This is a
  deliberately honest "MEDIUM/LOW confidence" signal rather than a
  fabricated "HIGH confidence" one when those tokens aren't present in
  the surface metadata.
- Coverage claim: **maximum possible coverage through authority + exam +
  document discovery architecture; coverage depends on official sources
  being publicly accessible and not requiring JavaScript rendering or a
  login.** This is not a claim that "all Rajasthan exams are supported."

## Phase 2 (not built — waiting for explicit instruction)

Mock tests, current affairs, user rankings/progress, notifications, paid
features/subscriptions, and an AI tutor are explicitly out of scope for
this Phase 1 delivery.
