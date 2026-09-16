import unittest
from unittest.mock import patch

from database.models import DOC_TYPE_QUESTION_PAPER, DOC_TYPE_ANSWER_KEY
from services import document_discovery
from utils.http_client import SafeResponse, DisallowedDomainError

SAMPLE_HTML = b"""
<html><body>
<a href="/files/patwar-qp-2026.pdf">Patwar Question Paper 2026</a>
<a href="/files/patwar-qp-2022.pdf">Patwar Question Paper 2022</a>
<a href="/files/vdo-qp-2026.pdf">VDO Question Paper 2026</a>
<a href="#">Skip me</a>
<a href="javascript:void(0)">Skip me too</a>
<a href="/files/patwar-answerkey-2026.pdf">Patwar Final Answer Key 2026</a>
</body></html>
"""

EXAM_PATWAR = {"id": "patwar", "name": "Patwari / Patwar", "aliases": ["patwar", "patwari"]}


def _fake_html_response(url):
    return SafeResponse(
        final_url=url,
        status_code=200,
        headers={"Content-Type": "text/html"},
        content=SAMPLE_HTML,
        redirect_chain=[url],
    )


class TestFetchLinks(unittest.TestCase):
    @patch("services.document_discovery.safe_request")
    def test_fetch_links_parses_anchor_tags(self, mock_request):
        mock_request.return_value = _fake_html_response("https://rssb.rajasthan.gov.in/results")
        links = document_discovery.fetch_links("https://rssb.rajasthan.gov.in/results")
        texts = [l["text"] for l in links]
        self.assertIn("Patwar Question Paper 2026", texts)
        self.assertIn("VDO Question Paper 2026", texts)
        # javascript:/# links must be skipped
        self.assertNotIn("Skip me", texts)
        self.assertNotIn("Skip me too", texts)

    @patch("services.document_discovery.safe_request")
    def test_fetch_links_resolves_relative_urls_absolute(self, mock_request):
        mock_request.return_value = _fake_html_response("https://rssb.rajasthan.gov.in/results")
        links = document_discovery.fetch_links("https://rssb.rajasthan.gov.in/results")
        hrefs = [l["href"] for l in links]
        self.assertTrue(any(h.startswith("https://rssb.rajasthan.gov.in/files/") for h in hrefs))

    @patch("services.document_discovery.safe_request")
    def test_fetch_links_returns_empty_on_disallowed_domain(self, mock_request):
        mock_request.side_effect = DisallowedDomainError("not allowed")
        links = document_discovery.fetch_links("https://evil.example.com/page")
        self.assertEqual(links, [])

    @patch("services.document_discovery.safe_request")
    def test_fetch_links_returns_empty_on_non_200(self, mock_request):
        mock_request.return_value = SafeResponse(
            final_url="https://rssb.rajasthan.gov.in/missing",
            status_code=404,
            headers={"Content-Type": "text/html"},
            content=b"not found",
            redirect_chain=["https://rssb.rajasthan.gov.in/missing"],
        )
        links = document_discovery.fetch_links("https://rssb.rajasthan.gov.in/missing")
        self.assertEqual(links, [])

    @patch("services.document_discovery.safe_request")
    def test_fetch_links_never_raises_on_unexpected_exception(self, mock_request):
        mock_request.side_effect = RuntimeError("boom")
        try:
            links = document_discovery.fetch_links("https://rssb.rajasthan.gov.in/results")
        except Exception as exc:
            self.fail(f"fetch_links raised instead of returning []: {exc}")
        self.assertEqual(links, [])


class TestDiscoverCandidates(unittest.TestCase):
    @patch("services.document_discovery.safe_request")
    def test_filters_by_exam_name(self, mock_request):
        mock_request.return_value = _fake_html_response("https://rssb.rajasthan.gov.in/results")
        candidates = document_discovery.discover_candidates(
            source_pages=["https://rssb.rajasthan.gov.in/results"],
            exam=EXAM_PATWAR,
        )
        texts = [c.link_text for c in candidates]
        self.assertTrue(all("patwar" in t.lower() or "patwari" in t.lower() for t in texts))
        self.assertFalse(any("vdo" in t.lower() for t in texts))

    @patch("services.document_discovery.safe_request")
    def test_filters_by_doc_type(self, mock_request):
        mock_request.return_value = _fake_html_response("https://rssb.rajasthan.gov.in/results")
        candidates = document_discovery.discover_candidates(
            source_pages=["https://rssb.rajasthan.gov.in/results"],
            exam=EXAM_PATWAR,
            doc_type=DOC_TYPE_ANSWER_KEY,
        )
        self.assertEqual(len(candidates), 1)
        self.assertIn("Answer Key", candidates[0].link_text)

    @patch("services.document_discovery.safe_request")
    def test_filters_by_year_rejects_wrong_year(self, mock_request):
        mock_request.return_value = _fake_html_response("https://rssb.rajasthan.gov.in/results")
        candidates = document_discovery.discover_candidates(
            source_pages=["https://rssb.rajasthan.gov.in/results"],
            exam=EXAM_PATWAR,
            doc_type=DOC_TYPE_QUESTION_PAPER,
            year="2026",
        )
        self.assertEqual(len(candidates), 1)
        self.assertIn("2026", candidates[0].link_text)


if __name__ == "__main__":
    unittest.main()
