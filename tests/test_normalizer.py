import unittest

from services.exam_normalizer import normalize_and_match, normalize_text, apply_alias_layer
from services.exam_registry_data import EXAM_REGISTRY


class TestNormalizeText(unittest.TestCase):
    def test_lowercases_and_strips_punctuation(self):
        self.assertEqual(normalize_text("CET-12th!!"), "cet 12th")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_text("  Sub   Inspector  "), "sub inspector")

    def test_expands_ordinal_words(self):
        self.assertEqual(normalize_text("Third Grade"), "3rd grade")
        self.assertEqual(normalize_text("First Grade"), "1st grade")


class TestAliasLayer(unittest.TestCase):
    def test_si_aliases_collapse(self):
        for phrase in ["si", "sub inspector", "police si", "rajasthan si"]:
            self.assertEqual(apply_alias_layer(normalize_text(phrase)), "si")

    def test_cet_12_aliases_collapse(self):
        for phrase in ["CET 12", "CET 12th", "CET Senior", "CET Senior Secondary", "Senior CET"]:
            self.assertEqual(apply_alias_layer(normalize_text(phrase)), "cet 12")

    def test_third_grade_aliases_collapse(self):
        for phrase in ["3rd Grade", "Third Grade", "3rd Grade Teacher", "Primary Teacher"]:
            self.assertEqual(apply_alias_layer(normalize_text(phrase)), "3rd grade")


class TestNormalizeAndMatch(unittest.TestCase):
    def test_cet_12_matches_cet_senior_secondary(self):
        result = normalize_and_match("CET 12", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "cet_senior_secondary")

    def test_cet_senior_matches_cet_senior_secondary(self):
        result = normalize_and_match("CET Senior", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "cet_senior_secondary")

    def test_si_matches_police_si(self):
        result = normalize_and_match("SI", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "police_si")

    def test_sub_inspector_matches_police_si(self):
        result = normalize_and_match("Sub Inspector", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "police_si")

    def test_third_grade_matches_primary_teacher_l1(self):
        result = normalize_and_match("3rd Grade", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "primary_teacher_l1")

    def test_level_1_matches_primary_teacher_l1_in_context(self):
        result = normalize_and_match("Primary Teacher Level 1", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "primary_teacher_l1")

    def test_reet_l1_matches_reet_level_1(self):
        result = normalize_and_match("REET L1", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "reet_level_1")

    def test_reet_level_2_matches(self):
        result = normalize_and_match("REET Level 2", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "reet_level_2")

    def test_lab_assistant_matches(self):
        result = normalize_and_match("Lab Assistant", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "lab_assistant")

    def test_lab_assistant_geography_still_matches_lab_assistant(self):
        # "Geography" is a subject qualifier, not a different exam — the
        # exam-level match should still resolve to lab_assistant; the
        # subject distinction is handled later by source_verifier when
        # filtering discovered documents, not by the exam matcher.
        result = normalize_and_match("Lab Assistant Geography", EXAM_REGISTRY)
        self.assertEqual(result.matched_exam_id, "lab_assistant")

    def test_patwar_and_patwari_both_match(self):
        self.assertEqual(normalize_and_match("Patwar", EXAM_REGISTRY).matched_exam_id, "patwar")
        self.assertEqual(normalize_and_match("Patwari", EXAM_REGISTRY).matched_exam_id, "patwar")

    def test_vdo_matches(self):
        self.assertEqual(normalize_and_match("VDO", EXAM_REGISTRY).matched_exam_id, "vdo")

    def test_ldc_matches(self):
        self.assertEqual(normalize_and_match("LDC", EXAM_REGISTRY).matched_exam_id, "ldc")

    def test_junior_assistant_matches(self):
        self.assertEqual(
            normalize_and_match("Junior Assistant", EXAM_REGISTRY).matched_exam_id,
            "junior_assistant",
        )

    def test_agriculture_supervisor_matches(self):
        self.assertEqual(
            normalize_and_match("Agriculture Supervisor", EXAM_REGISTRY).matched_exam_id,
            "agriculture_supervisor",
        )

    def test_animal_attendant_matches(self):
        self.assertEqual(
            normalize_and_match("Animal Attendant", EXAM_REGISTRY).matched_exam_id,
            "animal_attendant",
        )

    def test_junior_instructor_matches(self):
        self.assertEqual(
            normalize_and_match("Junior Instructor", EXAM_REGISTRY).matched_exam_id,
            "junior_instructor",
        )

    def test_ras_matches(self):
        self.assertEqual(normalize_and_match("RAS", EXAM_REGISTRY).matched_exam_id, "ras")

    def test_school_lecturer_matches_first_grade(self):
        self.assertEqual(
            normalize_and_match("School Lecturer", EXAM_REGISTRY).matched_exam_id,
            "school_lecturer",
        )
        self.assertEqual(
            normalize_and_match("1st Grade", EXAM_REGISTRY).matched_exam_id,
            "school_lecturer",
        )

    def test_senior_teacher_matches_second_grade(self):
        self.assertEqual(
            normalize_and_match("Senior Teacher", EXAM_REGISTRY).matched_exam_id,
            "senior_teacher",
        )
        self.assertEqual(
            normalize_and_match("2nd Grade", EXAM_REGISTRY).matched_exam_id,
            "senior_teacher",
        )

    def test_high_court_matches(self):
        self.assertEqual(
            normalize_and_match("Rajasthan High Court", EXAM_REGISTRY).matched_exam_id,
            "rajasthan_high_court",
        )

    def test_gibberish_does_not_match(self):
        result = normalize_and_match("xyzrandom123", EXAM_REGISTRY)
        self.assertIsNone(result.matched_exam_id)

    def test_empty_string_does_not_match(self):
        result = normalize_and_match("", EXAM_REGISTRY)
        self.assertIsNone(result.matched_exam_id)


if __name__ == "__main__":
    unittest.main()
