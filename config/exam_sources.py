"""
Seed data for the Authority Registry.

IMPORTANT / HONESTY NOTE
------------------------
This is *seed* data only. It exists so the bot has a correct starting
point instead of guessing domains. Every URL below was checked with a
live web search on 2026-09-15 (see final report for details) — this is
NOT a claim that the PDF links on these pages were verified; only that
the authority home/section URLs themselves are real, currently-online
government pages.

The system's PRIMARY behaviour is NOT "look up this dict and stop" — it
is "start from this authority's official domain, then run discovery +
PDF verification (see services/document_discovery.py and
services/pdf_validator.py) at request time." This file only answers
the question "which domains are we even allowed to look at."

Two authorities called out in the original brief were checked and one
of them turned out to be an *unofficial* URL — that is exactly the
kind of mistake this bot exists to avoid, so it is recorded here
deliberately rather than silently fixed:

- REET (Rajasthan Eligibility Examination for Teachers) is NOT hosted
  at "reet2024.co.in" (a commercial-looking, non-government domain).
  It is conducted by the Board of Secondary Education, Rajasthan
  (BSER) at rajeduboard.rajasthan.gov.in. reet2024.co.in is therefore
  intentionally excluded from ALLOWED_DOMAINS and from this registry.
- "rpsc.rajasthansarkar.in" is an unofficial news/aggregator look-alike
  site, not RPSC's own domain (rpsc.rajasthan.gov.in). Excluded.
"""

# Each authority: id, display name, official domain(s), category,
# a short note on what it conducts, and verification metadata.
AUTHORITIES = [
    {
        "id": "rssb",
        "name": "Rajasthan Staff Selection Board (RSSB)",
        "official_domain": "rssb.rajasthan.gov.in",
        "official_pages": {
            "home": "https://rssb.rajasthan.gov.in/",
            "results": "https://rssb.rajasthan.gov.in/results",
            "news": "https://rssb.rajasthan.gov.in/news",
        },
        "conducts": [
            "Patwar", "VDO", "LDC", "Junior Assistant", "Lab Assistant",
            "Agriculture Supervisor", "Animal Attendant", "Junior Instructor",
            "Primary Teacher Level-1 / 3rd Grade Teacher",
            "Upper Primary Teacher Level-2 / 2nd Grade Teacher (contractual streams)",
        ],
        "verification_status": "WEB_VERIFIED_ONLINE_2026-09-15",
        "notes": (
            "Confirmed live via web search on 2026-09-15: an active RSSB news "
            "feed with January 2026 recruitment notices was found at this domain."
        ),
    },
    {
        "id": "rsmssb",
        "name": "Rajasthan Subordinate and Ministerial Services Selection Board (RSMSSB)",
        "official_domain": "rsmssb.rajasthan.gov.in",
        "official_pages": {
            "home": "https://rsmssb.rajasthan.gov.in/",
        },
        "conducts": [
            "Many of the same subordinate-service exams as RSSB — RSSB and "
            "RSMSSB are related/successor bodies for Rajasthan subordinate "
            "recruitment and, depending on the year, a given exam may be "
            "listed under either domain. The discovery layer checks both.",
        ],
        "verification_status": "WEB_VERIFIED_ONLINE_2026-09-15",
        "notes": "Confirmed live via web search on 2026-09-15.",
    },
    {
        "id": "rpsc",
        "name": "Rajasthan Public Service Commission (RPSC)",
        "official_domain": "rpsc.rajasthan.gov.in",
        "official_pages": {
            "home": "https://rpsc.rajasthan.gov.in/",
            "official_material": "https://rpsc.rajasthan.gov.in/officialmaterial",
            "exam_dashboard": "https://rpsc.rajasthan.gov.in/examdashboard",
        },
        "conducts": [
            "RAS", "School Lecturer / 1st Grade Teacher",
            "Senior Teacher / 2nd Grade Teacher", "Sub Inspector (SI)",
            "Various gazetted/state service exams",
        ],
        "verification_status": "WEB_VERIFIED_ONLINE_2026-09-15",
        "notes": (
            "Confirmed live. RPSC's own site explicitly warns candidates "
            "that misleading information circulates on social media and to "
            "rely only on rpsc.rajasthan.gov.in — reinforcing why this bot "
            "restricts itself to the official domain."
        ),
    },
    {
        "id": "rajeduboard",
        "name": "Board of Secondary Education, Rajasthan (BSER / RBSE)",
        "official_domain": "rajeduboard.rajasthan.gov.in",
        "official_pages": {
            "home": "https://rajeduboard.rajasthan.gov.in/",
        },
        "conducts": ["REET (both Level 1 and Level 2)", "RTET (historical name)"],
        "verification_status": "WEB_VERIFIED_ONLINE_2026-09-15",
        "notes": (
            "Confirmed as the official REET conducting authority via multiple "
            "independent web sources on 2026-09-15. The domain "
            "'reet2024.co.in' suggested in early project notes is NOT an "
            "official government domain and has been deliberately excluded."
        ),
    },
    {
        "id": "hcraj",
        "name": "Rajasthan High Court",
        "official_domain": "hcraj.nic.in",
        "official_pages": {"home": "https://hcraj.nic.in/"},
        "conducts": ["Rajasthan High Court recruitment (various staff cadres)"],
        "verification_status": "NOT_WEB_VERIFIED_THIS_SESSION",
        "notes": (
            "Carried over from project brief; a .nic.in domain is a "
            "standard Indian government domain pattern, but this specific "
            "URL was not independently re-checked in this session. The "
            "PDF validator will still reject it at request time if it is "
            "ever dead or non-official."
        ),
    },
    {
        "id": "recruitment_rajasthan",
        "name": "Rajasthan Recruitment Portal (whole-of-government)",
        "official_domain": "recruitment.rajasthan.gov.in",
        "official_pages": {"home": "https://recruitment.rajasthan.gov.in/"},
        "conducts": [
            "Shared admit-card/payment portal used by multiple Rajasthan "
            "government recruiting departments",
        ],
        "verification_status": "WEB_VERIFIED_ONLINE_2026-09-15",
        "notes": "Confirmed live via web search on 2026-09-15.",
    },
]

# Authorities we know exist in principle (per the original brief) but whose
# exact current official domain was NOT confirmed in this session. They are
# intentionally left OUT of ALLOWED_DOMAINS / AUTHORITIES until a human or a
# future discovery run confirms a real .rajasthan.gov.in / .nic.in / .gov.in
# URL. This list exists so the discovery system has documented leads to
# chase, without the bot ever presenting a guess as verified.
UNCONFIRMED_AUTHORITY_LEADS = [
    "Rajasthan Police recruitment (police.rajasthan.gov.in is plausible by "
    "naming convention but was not independently confirmed this session)",
    "Rajasthan Cooperative Recruitment Board",
    "Rajasthan Housing Board",
    "Rajasthan DISCOM / electricity board recruitment authorities",
    "Rajasthan medical/health recruitment authorities (e.g. RUHS, NHM Rajasthan)",
    "Rajasthan state universities and teacher recruitment bodies",
]

# Domains explicitly identified as UNOFFICIAL / to be rejected even if a
# user or a search result surfaces them. Kept here so both humans and the
# discovery/verifier code have one shared blocklist.
KNOWN_UNOFFICIAL_DOMAINS = [
    "reet2024.co.in",
    "rpsc.rajasthansarkar.in",
    "testbook.com",
    "adda247.com",
    "careers360.com",
    "easyshiksha.com",
    "nokricourse.com",
    "sarkariresult.com",
]
