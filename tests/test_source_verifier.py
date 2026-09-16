import unittest

from services import source_verifier
from database.models import DOC_TYPE_ANSWER_KEY, DOC_TYPE_QUESTION_PAPER, DOC_TYPE_SYLLABUS


class TestExtractIdentity(unittest.TestCase):
    def test_extracts_year(self):
        ident = source_verifier.extract_identity("Patwar Question Paper 2026")
        self.assertEqual(ident.year, "2026")

    def test_extracts_shift_and_doc_type(self):
        ident = source_verifier.extract_identity("Lab Assistant Question Paper 2026 Shift 1")
        self.assertEqual(ident.doc_type_guess, DOC_TYPE_QUESTION_PAPER)
        self.assertEqual(ident.shift, "1")

    def test_extracts_answer_key_and_status_final(self):
        ident = source_verifier.extract_identity("VDO Final Answer Key 2025")
        self.assertEqual(ident.doc_type_guess, DOC_TYPE_ANSWER_KEY)
        self.assertEqual(ident.answer_key_status, "FINAL")

    def test_extracts_answer_key_status_provisional(self):
        ident = source_verifier.extract_identity("VDO Provisional Answer Key 2025")
        self.assertEqual(ident.answer_key_status, "PROVISIONAL")

    def test_extracts_answer_key_status_final_revised(self):
        ident = source_verifier.extract_identity("VDO Final Revised Answer Key 2025")
        self.assertEqual(ident.answer_key_status, "FINAL_REVISED")

    def test_extracts_syllabus_doc_type(self):
        ident = source_verifier.extract_identity("Patwar Syllabus and Exam Pattern")
        self.assertEqual(ident.doc_type_guess, DOC_TYPE_SYLLABUS)

    def test_extracts_set_and_paper(self):
        ident = source_verifier.extract_identity("LDC Question Paper 2024 Paper 2 Set B")
        self.assertEqual(ident.paper, "2")
        self.assertEqual(ident.doc_set, "B")

    def test_no_year_returns_none(self):
        ident = source_verifier.extract_identity("General notification about the exam")
        self.assertIsNone(ident.year)


class TestMatchesRequested(unittest.TestCase):
    def test_matching_year_and_type_passes(self):
        ident = source_verifier.extract_identity("Patwar Question Paper 2026")
        self.assertTrue(
            source_verifier.matches_requested(ident, requested_year="2026", requested_doc_type=DOC_TYPE_QUESTION_PAPER)
        )

    def test_wrong_year_rejected(self):
        ident = source_verifier.extract_identity("Patwar Question Paper 2022")
        self.assertFalse(
            source_verifier.matches_requested(ident, requested_year="2026")
        )

    def test_wrong_doc_type_rejected(self):
        ident = source_verifier.extract_identity("Patwar Answer Key 2026")
        self.assertFalse(
            source_verifier.matches_requested(ident, requested_doc_type=DOC_TYPE_QUESTION_PAPER)
        )

    def test_unspecified_identity_fields_do_not_block(self):
        # A link with no discoverable year at all should not be auto-rejected
        # just because the user asked for a specific year — it falls through
        # to PDF-level identity checks instead of being excluded here.
        ident = source_verifier.extract_identity("Patwar Question Paper")
        self.assertTrue(
            source_verifier.matches_requested(ident, requested_year="2026")
        )


if __name__ == "__main__":
    unittest.main()
