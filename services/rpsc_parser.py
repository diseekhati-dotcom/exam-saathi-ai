"""
RPSC-specific source page resolver.

RPSC's site structure (per project brief + web verification on
2026-09-15) exposes an "Official Material" listing page and an "Exam
Dashboard" rather than a single predictable archive URL per document
type, so this module points the generic discovery crawler at those
listing pages; the crawler + source_verifier then filter by exam name
and document-type keywords found in each link's text.
"""
from typing import List, Optional

RPSC_HOME = "https://rpsc.rajasthan.gov.in/"
RPSC_OFFICIAL_MATERIAL = "https://rpsc.rajasthan.gov.in/officialmaterial"
RPSC_EXAM_DASHBOARD = "https://rpsc.rajasthan.gov.in/examdashboard"


def get_source_pages(doc_type: Optional[str] = None) -> List[str]:
    # RPSC does not split its official-material listing by document type in
    # a predictable URL pattern, so the same listing pages are used for all
    # document types; filtering happens in document_discovery/source_verifier.
    return [RPSC_OFFICIAL_MATERIAL, RPSC_EXAM_DASHBOARD, RPSC_HOME]


def get_official_source_page(doc_type: Optional[str] = None) -> str:
    return RPSC_OFFICIAL_MATERIAL
