"""
config/exam_sources.py
-----------------------
Single source of truth for:
  1. AUTHORITIES  — Rajasthan conducting bodies (RSSB, RPSC, RBSE, ...) with
     their official base URL and, where known, the official archive/listing
     pages for each document type. These base URLs/listing pages are the
     ONLY hardcoded links in the whole discovery system — individual PDFs
     for individual years are never hardcoded here; they are discovered at
     request time from these listing pages (per the "don't hardcode every
     PDF" requirement).
  2. EXAM_REGISTRY — a fast-path list of known exams (name + aliases +
     which authority conducts them). This is for quick, reliable
     recognition of common exams. It is explicitly NOT the ceiling of what
     the bot supports: `services/authority_discovery.py` falls back to
     keyword-based authority guessing for anything not in this list, and
     new exams can be added here at any time without touching any Python
     logic.

Extending this file:
  - New RSSB/RPSC/RBSE exam? Add an entry to EXAM_REGISTRY — no other file
    needs to change; document discovery already knows how to crawl that
    authority's archive pages for it.
  - New conducting authority entirely (a board/commission not yet listed)?
    Add an entry to AUTHORITIES with its verified official base_url. If you
    don't yet have its syllabus/question_paper/answer_key archive page
    URLs, leave `doc_pages` empty — the bot will correctly identify the
    authority and link to its homepage, but will honestly say document
    discovery isn't configured for it yet, rather than guessing.

IMPORTANT: never add a base_url you have not personally verified. An
unverified/guessed government domain is worse than no domain at all.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. AUTHORITIES
# ---------------------------------------------------------------------------

AUTHORITIES: dict[str, dict] = {
    "rssb": {
        "id": "rssb",
        "name": "RSSB",
        "full_name": "Rajasthan Subordinate and Ministerial Services Selection Board (RSMSSB)",
        "base_url": "https://rsmssb.rajasthan.gov.in/",
        "doc_pages": {
            "syllabus": [
                "https://rsmssb.rajasthan.gov.in/show_archived?lang=Hindi&menuName=fEaFReFd6jAdvM%2FXeaDXig%3D%3D&theme=Red",
            ],
            "question_paper": [
                "https://rsmssb.rajasthan.gov.in/show_archived?menuName=Xj4lCb9vGxpQnfLs%2FxlZ2g%3D%3D&theme=Red",
            ],
            "answer_key": [
                "https://rsmssb.rajasthan.gov.in/show_archived?menuName=AGDAnN3xlANlxQ9BZvzaeg%3D%3D",
            ],
        },
        "keyword_hints": [
            "rssb", "rsmssb", "patwar", "patwari", "vdo", "village development officer",
            "ldc", "junior assistant", "clerk", "lab assistant", "laboratory assistant",
            "agriculture supervisor", "animal attendant", "junior instructor",
            "supervisor", "stenographer", "informatics assistant",
            "hostel superintendent", "cet", "common eligibility test",
        ],
    },
    "rpsc": {
        "id": "rpsc",
        "name": "RPSC",
        "full_name": "Rajasthan Public Service Commission",
        "base_url": "https://rpsc.rajasthan.gov.in/",
        "doc_pages": {
            "syllabus": ["https://rpsc.rajasthan.gov.in/syllabus.aspx"],
            "question_paper": ["https://rpsc.rajasthan.gov.in/previousquestionpapers.aspx"],
            "answer_key": ["https://rpsc.rajasthan.gov.in/answerkeys.aspx"],
        },
        "keyword_hints": [
            "rpsc", "ras", "rajasthan administrative service", "sub inspector", " si ",
            "platoon commander", "school lecturer", "1st grade", "first grade",
            "senior teacher", "2nd grade", "second grade", "assistant professor",
            "junior legal officer", "assistant engineer", "statistical officer",
            "agriculture officer",
        ],
    },
    "rbse": {
        "id": "rbse",
        "name": "RBSE / REET",
        "full_name": "Board of Secondary Education, Rajasthan",
        "base_url": "https://rajeduboard.rajasthan.gov.in/",
        "doc_pages": {
            "syllabus": ["https://rajeduboard.rajasthan.gov.in/RTET-REET/RTET-REET.htm"],
            "question_paper": [
                "https://rajeduboard.rajasthan.gov.in/RTET-REET/RTET-REET.htm",
                "https://rajeduboard.rajasthan.gov.in/books/left.htm",
            ],
            "answer_key": ["https://rajeduboard.rajasthan.gov.in/RTET-REET/RTET-REET.htm"],
        },
        "keyword_hints": ["reet", "rtet", "rbse", "board of secondary education"],
    },
    # --- Recognised but not yet crawlable (no confirmed archive-listing
    # pages). The bot will correctly name the authority and link to its
    # homepage, and will say plainly that specific documents can't be
    # auto-discovered yet, instead of guessing.
    "high_court": {
        "id": "high_court",
        "name": "Rajasthan High Court",
        "full_name": "Rajasthan High Court, Jodhpur",
        "base_url": "https://hcraj.nic.in/hcraj/",
        "doc_pages": {},
        "keyword_hints": [
            "high court", "hcraj", "civil judge", "district judge",
            "junior judicial assistant", "jja", "court ldc",
        ],
    },
    "rajasthan_police": {
        "id": "rajasthan_police",
        "name": "Rajasthan Police",
        "full_name": "Rajasthan Police Department",
        "base_url": "https://police.rajasthan.gov.in/",
        "doc_pages": {},
        "keyword_hints": ["police constable", "home guard", "rajasthan police"],
    },
    # Add further authorities here as their official domains are verified —
    # e.g. Rajasthan Cooperative Recruitment Board, Rajasthan Housing Board,
    # Discoms/Electricity Boards, medical/health recruitment boards,
    # university recruitment boards. Leave base_url unset (None) rather
    # than guessing a domain:
    # "some_new_board": {
    #     "id": "some_new_board", "name": "...", "full_name": "...",
    #     "base_url": None, "doc_pages": {}, "keyword_hints": [...],
    # },
}


# ---------------------------------------------------------------------------
# 2. EXAM_REGISTRY — fast-path known exams (extensible, not exhaustive)
# ---------------------------------------------------------------------------

EXAM_REGISTRY: list[dict] = [
    # ---------------- RSSB ----------------
    {"id": "cet_senior_secondary", "name": "CET Senior Secondary Level", "authority": "rssb",
     "aliases": ["cet 12", "cet 12th", "cet senior secondary", "senior cet", "cet ss",
                 "senior secondary cet", "common eligibility test senior secondary"]},
    {"id": "cet_graduation", "name": "CET Graduation Level", "authority": "rssb",
     "aliases": ["cet graduation", "cet grad", "cet graduate", "graduate cet",
                 "common eligibility test graduation"]},
    {"id": "patwari", "name": "Patwari (RSSB)", "authority": "rssb",
     "aliases": ["patwar", "patwari"]},
    {"id": "vdo", "name": "VDO (RSSB)", "authority": "rssb",
     "aliases": ["vdo", "village development officer"]},
    {"id": "ldc", "name": "LDC / Junior Assistant (RSSB)", "authority": "rssb",
     "aliases": ["ldc", "lower division clerk", "junior assistant"]},
    {"id": "clerk", "name": "Clerk (RSSB)", "authority": "rssb",
     "aliases": ["clerk grade ii", "clerk grade 2"]},
    {"id": "lab_assistant", "name": "Lab Assistant (RSSB)", "authority": "rssb",
     "aliases": ["lab assistant", "laboratory assistant"]},
    {"id": "agriculture_supervisor", "name": "Agriculture Supervisor (RSSB)", "authority": "rssb",
     "aliases": ["agriculture supervisor", "krishi paryavekshak"]},
    {"id": "animal_attendant", "name": "Animal Attendant (RSSB)", "authority": "rssb",
     "aliases": ["animal attendant", "pashu parichar"]},
    {"id": "junior_instructor", "name": "Junior Instructor (RSSB)", "authority": "rssb",
     "aliases": ["junior instructor"]},
    {"id": "supervisor_rssb", "name": "Supervisor (RSSB)", "authority": "rssb",
     "aliases": ["rssb supervisor"]},
    {"id": "stenographer", "name": "Stenographer (RSSB)", "authority": "rssb",
     "aliases": ["stenographer", "steno"]},
    {"id": "informatics_assistant", "name": "Informatics Assistant (RSSB)", "authority": "rssb",
     "aliases": ["informatics assistant"]},
    {"id": "hostel_superintendent", "name": "Hostel Superintendent (RSSB)", "authority": "rssb",
     "aliases": ["hostel superintendent"]},

    # ---------------- RPSC ----------------
    {"id": "ras", "name": "RAS", "authority": "rpsc",
     "aliases": ["ras", "rajasthan administrative service", "rpsc ras"]},
    {"id": "si", "name": "Rajasthan Police SI / Platoon Commander", "authority": "rpsc",
     "aliases": ["si", "sub inspector", "platoon commander", "rajasthan si"]},
    {"id": "school_lecturer", "name": "School Lecturer / 1st Grade Teacher (RPSC)", "authority": "rpsc",
     "aliases": ["1st grade", "first grade", "school lecturer", "grade 1 teacher"]},
    {"id": "senior_teacher", "name": "Senior Teacher / 2nd Grade Teacher (RPSC)", "authority": "rpsc",
     "aliases": ["2nd grade", "second grade", "senior teacher", "grade 2 teacher"]},
    {"id": "assistant_professor", "name": "Assistant Professor (RPSC)", "authority": "rpsc",
     "aliases": ["assistant professor"]},
    {"id": "junior_legal_officer", "name": "Junior Legal Officer (RPSC)", "authority": "rpsc",
     "aliases": ["junior legal officer", "jlo"]},
    {"id": "assistant_engineer", "name": "Assistant Engineer (RPSC)", "authority": "rpsc",
     "aliases": ["assistant engineer", "ae rpsc"]},
    {"id": "statistical_officer", "name": "Statistical Officer (RPSC)", "authority": "rpsc",
     "aliases": ["statistical officer"]},
    {"id": "agriculture_officer", "name": "Agriculture Officer (RPSC)", "authority": "rpsc",
     "aliases": ["agriculture officer"]},

    # ---------------- RBSE ----------------
    {"id": "reet_level1", "name": "REET Level 1", "authority": "rbse",
     "aliases": ["reet 1", "reet level 1", "reet l1"]},
    {"id": "reet_level2", "name": "REET Level 2", "authority": "rbse",
     "aliases": ["reet 2", "reet level 2", "reet l2"]},
    {"id": "reet", "name": "REET", "authority": "rbse",
     "aliases": ["reet", "rtet"]},
]
