import os
import tempfile
import unittest
from unittest.mock import patch

from database.models import (
    Document, DOC_TYPE_QUESTION_PAPER, DOC_TYPE_ANSWER_KEY,
    VERIFICATION_VERIFIED, VERIFICATION_REJECTED, VERIFICATION_SOURCE_PAGE_ONLY,
)
from handlers import exam_commands, start as start_handlers
from services import authority_registry


class HandlerTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_handlers.sqlite3")
        import config.settings as settings_module
        self._old_path = settings_module.settings.DATABASE_PATH
        settings_module.settings.DATABASE_PATH = self.db_path
        authority_registry.seed_authorities()

    def tearDown(self):
        import config.settings as settings_module
        settings_module.settings.DATABASE_PATH = self._old_path


class TestStartMessage(unittest.TestCase):
    def test_start_message_has_no_phase2_features(self):
        spec = start_handlers.build_start_message()
        lowered = spec["text"].lower()
        for banned in ["mock test", "current affairs", "ranking", "subscription", "ai tutor"]:
            self.assertNotIn(banned, lowered)

    def test_start_message_mentions_exam_command(self):
        spec = start_handlers.build_start_message()
        self.assertIn("/exam", spec["text"])


class TestExamNotFound(unittest.TestCase):
    def test_not_found_message_has_no_buttons(self):
        spec = exam_commands.build_exam_not_found_message("xyzrandom123")
        self.assertEqual(spec["buttons"], [])
        self.assertIn("could not be verified", spec["text"])


class TestBuildExamCard(HandlerTestBase):
    def test_known_exam_produces_three_doc_type_buttons_plus_source(self):
        spec = exam_commands.build_exam_card("police_si")
        self.assertIsNotNone(spec)
        flat_buttons = [b for row in spec["buttons"] for b in row]
        callback_buttons = [b for b in flat_buttons if "callback_data" in b]
        self.assertEqual(len(callback_buttons), 3)
        callback_data = {b["callback_data"] for b in callback_buttons}
        self.assertIn("dt:police_si:SYLLABUS", callback_data)
        self.assertIn("dt:police_si:QUESTION_PAPER", callback_data)
        self.assertIn("dt:police_si:ANSWER_KEY", callback_data)

    def test_unknown_exam_returns_none(self):
        spec = exam_commands.build_exam_card("does_not_exist")
        self.assertIsNone(spec)

    def test_exam_card_includes_authority_name(self):
        spec = exam_commands.build_exam_card("police_si")
        self.assertIn("Rajasthan Public Service Commission", spec["text"])


class TestDocumentButtons(unittest.TestCase):
    def test_verified_document_gets_url_button_to_pdf_url_not_source_page(self):
        doc = Document(
            id="d1", exam_id="patwar", authority_id="rssb",
            doc_type=DOC_TYPE_QUESTION_PAPER, title="Patwar QP 2026",
            source_page="https://rssb.rajasthan.gov.in/results",
            pdf_url="https://rssb.rajasthan.gov.in/files/patwar-qp-2026.pdf",
            year="2026",
        )
        doc.mark_verified("PDF verified")
        buttons = exam_commands._document_buttons([doc])
        self.assertEqual(len(buttons), 1)
        btn = buttons[0][0]
        self.assertEqual(btn["url"], doc.pdf_url)
        self.assertNotEqual(btn["url"], doc.source_page)

    def test_rejected_document_produces_no_button(self):
        doc = Document(
            id="d2", exam_id="patwar", authority_id="rssb",
            doc_type=DOC_TYPE_QUESTION_PAPER, title="Broken link",
            source_page="https://rssb.rajasthan.gov.in/results",
        )
        doc.mark_rejected("HTTP 404")
        buttons = exam_commands._document_buttons([doc])
        self.assertEqual(buttons, [])

    def test_source_page_only_document_gets_official_source_button(self):
        doc = Document(
            id="d3", exam_id="patwar", authority_id="rssb",
            doc_type=DOC_TYPE_ANSWER_KEY, title="Official Answer Key Source",
            source_page="https://rssb.rajasthan.gov.in/results",
        )
        doc.mark_source_page_only("No direct PDF found")
        buttons = exam_commands._document_buttons([doc])
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0][0]["text"], "🌐 Official Source")
        self.assertEqual(buttons[0][0]["url"], doc.source_page)

    def test_no_empty_buttons_for_mixed_results(self):
        verified = Document(
            id="d4", exam_id="patwar", authority_id="rssb",
            doc_type=DOC_TYPE_QUESTION_PAPER, title="Good",
            source_page="https://rssb.rajasthan.gov.in/results",
            pdf_url="https://rssb.rajasthan.gov.in/files/good.pdf", year="2026",
        )
        verified.mark_verified("ok")
        rejected = Document(
            id="d5", exam_id="patwar", authority_id="rssb",
            doc_type=DOC_TYPE_QUESTION_PAPER, title="Bad",
            source_page="https://rssb.rajasthan.gov.in/results",
        )
        rejected.mark_rejected("404")
        buttons = exam_commands._document_buttons([verified, rejected])
        self.assertEqual(len(buttons), 1)


class TestYearsMenu(HandlerTestBase):
    @patch("services.exam_service.available_years")
    def test_years_menu_lists_years_as_callback_buttons(self, mock_years):
        mock_years.return_value = ["2026", "2025", "2021"]
        spec = exam_commands.build_years_menu("patwar", DOC_TYPE_QUESTION_PAPER)
        flat = [b for row in spec["buttons"] for b in row]
        self.assertEqual([b["text"] for b in flat], ["2026", "2025", "2021"])
        self.assertEqual(flat[0]["callback_data"], "yr:patwar:QUESTION_PAPER:2026")

    @patch("services.exam_service.find_documents")
    @patch("services.exam_service.available_years")
    def test_no_years_falls_back_without_fake_buttons(self, mock_years, mock_find):
        mock_years.return_value = []
        mock_find.return_value = []
        spec = exam_commands.build_years_menu("patwar", DOC_TYPE_QUESTION_PAPER)
        self.assertEqual(spec["buttons"], [])
        self.assertIn("unavailable", spec["text"].lower())


if __name__ == "__main__":
    unittest.main()
