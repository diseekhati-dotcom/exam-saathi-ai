"""
RSSB / RSMSSB source-specific parser.

These two boards share closely related infrastructure. This module's job
is narrow and honest: it knows WHICH official pages to hand to the
generic discovery crawler (services/document_discovery.py) for each
document type, because RSMSSB's archive pages use a document-type-specific
menuName query parameter rather than a predictable path.

The three archive URLs below were supplied directly in the project brief
as the official RSMSSB archive endpoints for question papers, answer keys
and syllabus respectively. They are treated as *source pages to crawl
for links*, never as direct PDF URLs themselves — this module never
returns one of these URLs as a final "download PDF" button target.
"""
from typing import List, Optional

from database.models import DOC_TYPE_SYLLABUS, DOC_TYPE_QUESTION_PAPER, DOC_TYPE_ANSWER_KEY

RSSB_HOME = "https://rssb.rajasthan.gov.in/"
RSSB_RESULTS = "https://rssb.rajasthan.gov.in/results"
RSSB_NEWS = "https://rssb.rajasthan.gov.in/news"

RSMSSB_HOME = "https://rsmssb.rajasthan.gov.in/"
RSMSSB_QUESTION_PAPER_ARCHIVE = (
    "https://rsmssb.rajasthan.gov.in/show_archived?"
    "menuName=Xj4lCb9vGxpQnfLs%2FxlZ2g%3D%3D&theme=Red"
)
RSMSSB_ANSWER_KEY_ARCHIVE = (
    "https://rsmssb.rajasthan.gov.in/show_archived?"
    "menuName=AGDAnN3xlANlxQ9BZvzaeg%3D%3D"
)
RSMSSB_SYLLABUS_ARCHIVE = (
    "https://rsmssb.rajasthan.gov.in/show_archived?"
    "menuName=fEaFReFd6jAdvM%2FXeaDXig%3D%3D&theme=Default"
)


def get_source_pages(doc_type: Optional[str] = None) -> List[str]:
    """Return the official page(s) to crawl for the given document type.
    If doc_type is None, returns all known pages (home pages included as a
    fallback discovery root)."""
    if doc_type == DOC_TYPE_QUESTION_PAPER:
        return [RSMSSB_QUESTION_PAPER_ARCHIVE, RSSB_RESULTS, RSSB_NEWS]
    if doc_type == DOC_TYPE_ANSWER_KEY:
        return [RSMSSB_ANSWER_KEY_ARCHIVE, RSSB_RESULTS, RSSB_NEWS]
    if doc_type == DOC_TYPE_SYLLABUS:
        return [RSMSSB_SYLLABUS_ARCHIVE, RSSB_HOME]
    return [
        RSMSSB_QUESTION_PAPER_ARCHIVE,
        RSMSSB_ANSWER_KEY_ARCHIVE,
        RSMSSB_SYLLABUS_ARCHIVE,
        RSSB_HOME,
        RSSB_RESULTS,
        RSSB_NEWS,
    ]


def get_official_source_page(doc_type: Optional[str] = None) -> str:
    """A single human-shareable 'Official Source' page (not a PDF) to use
    as the fallback button when no direct verified PDF can be found."""
    pages = get_source_pages(doc_type)
    return pages[0] if pages else RSSB_HOME
