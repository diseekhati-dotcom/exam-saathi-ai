import os
import tempfile
import unittest
from unittest.mock import patch

from database.models import DOC_TYPE_QUESTION_PAPER, VERIFICATION_VERIFIED, VERIFICATION_SOURCE_PAGE_ONLY
from services import exam_service
from services.document_discovery import CandidateLink
from services.source_verifier import extract_identity


class ExamServiceTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_exam_service.sqlite3")
        import config.settings as settings_module
        self._old_path = settings_module.settings.DATABASE_PATH
        settings_module.settings.DATABASE_PATH = self.db_path
        from services import authority_registry
        authority_registry.seed_authorities()

    def tearDown(self):
        import config.settings as settings_module
        settings_module.settings.DATABASE_PATH = self._old_path


class TestResolveExam(unittest.TestCase):
    def test_resolve_known_exam(self):
        match = exam_service.resolve_exam("CET 12")
        self.assertEqual(match.matched_exam_id, "cet_senior_secondary")

    def test_resolve_unknown_exam(self):
        match = exam_service.resolve_exam("xyzrandom123")
        self.assertIsNone(match.matched_exam_id)


class TestFindDocuments(ExamServiceTestBase):
    @patch("services.exam_service.document_discovery.discover_candidates")
    @patch("services.pdf_validator.safe_request")
    def test_verified_pdf_flows_through_to_document(self, mock_http, mock_discover):
        from utils.http_client import SafeResponse

        candidate = CandidateLink(
            url="https://rssb.rajasthan.gov.in/files/patwar-qp-2026.pdf",
            link_text="Patwar Question Paper 2026",
            source_page="https://rssb.rajasthan.gov.in/results",
            identity=extract_identity("Patwar Question Paper 2026"),
        )
        mock_discover.return_value = [candidate]
        mock_http.return_value = SafeResponse(
            final_url=candidate.url, status_code=200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.4\n" + b"0" * 2000, redirect_chain=[candidate.url],
        )

        docs = exam_service.find_documents("patwar", DOC_TYPE_QUESTION_PAPER, use_cache=False)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].verification_status, VERIFICATION_VERIFIED)
        self.assertEqual(docs[0].pdf_url, candidate.url)

    @patch("services.exam_service.document_discovery.discover_candidates")
    @patch("services.pdf_validator.safe_request")
    def test_broken_pdf_falls_back_to_source_page_only(self, mock_http, mock_discover):
        from utils.http_client import SafeResponse

        candidate = CandidateLink(
            url="https://rssb.rajasthan.gov.in/files/patwar-qp-2026.pdf",
            link_text="Patwar Question Paper 2026",
            source_page="https://rssb.rajasthan.gov.in/results",
            identity=extract_identity("Patwar Question Paper 2026"),
        )
        mock_discover.return_value = [candidate]
        # Server returns an HTML error page instead of a PDF
        mock_http.return_value = SafeResponse(
            final_url=candidate.url, status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"<html>Sorry, the Page you looking for can't be Found. 404</html>",
            redirect_chain=[candidate.url],
        )

        docs = exam_service.find_documents("patwar", DOC_TYPE_QUESTION_PAPER, use_cache=False)
        statuses = [d.verification_status for d in docs]
        self.assertIn(VERIFICATION_SOURCE_PAGE_ONLY, statuses)
        self.assertNotIn(VERIFICATION_VERIFIED, statuses)
        # The fallback must never claim the broken URL as its pdf_url
        for d in docs:
            if d.verification_status == VERIFICATION_SOURCE_PAGE_ONLY:
                self.assertIsNone(d.pdf_url)

    @patch("services.exam_service.document_discovery.discover_candidates")
    def test_no_candidates_still_returns_source_fallback_not_crash(self, mock_discover):
        mock_discover.return_value = []
        docs = exam_service.find_documents("patwar", DOC_TYPE_QUESTION_PAPER, use_cache=False)
        # Should not crash, and should not fabricate a verified doc
        self.assertTrue(all(d.verification_status != VERIFICATION_VERIFIED for d in docs))

    def test_unknown_exam_id_returns_empty_list(self):
        docs = exam_service.find_documents("does_not_exist", DOC_TYPE_QUESTION_PAPER, use_cache=False)
        self.assertEqual(docs, [])


if __name__ == "__main__":
    unittest.main()
