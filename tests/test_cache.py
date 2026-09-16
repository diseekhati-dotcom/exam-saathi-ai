import os
import tempfile
import unittest

from database import db
from services import exam_cache


class TestCacheKeyBuilding(unittest.TestCase):
    def test_build_cache_key_normalizes_and_orders_fields(self):
        key = exam_cache.build_cache_key(
            authority="RSSB", exam="Patwar", document_type="Question Paper",
            year="2026",
        )
        self.assertEqual(key, "doc:rssb|patwar|question_paper|2026||||")

    def test_build_cache_key_handles_missing_fields(self):
        key = exam_cache.build_cache_key(authority="rpsc", exam="si")
        self.assertTrue(key.startswith("doc:rpsc|si|"))


class TestCacheStorage(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_cache.sqlite3")
        # Point the db module's thread-local connection at a fresh temp file
        import config.settings as settings_module
        self._old_path = settings_module.settings.DATABASE_PATH
        settings_module.settings.DATABASE_PATH = self.db_path

    def tearDown(self):
        import config.settings as settings_module
        settings_module.settings.DATABASE_PATH = self._old_path

    def test_set_then_get_roundtrips(self):
        key = "doc:rssb|patwar|question_paper|2026|||"
        exam_cache.set(key, {"pdf_url": "https://rssb.rajasthan.gov.in/paper.pdf"})
        value = exam_cache.get(key)
        self.assertEqual(value, {"pdf_url": "https://rssb.rajasthan.gov.in/paper.pdf"})

    def test_get_missing_key_returns_none(self):
        self.assertIsNone(exam_cache.get("doc:does|not|exist|||||"))

    def test_expired_entry_returns_none(self):
        key = "doc:expired|key|||||"
        exam_cache.set(key, {"a": 1}, ttl_seconds=-1)  # already expired
        self.assertIsNone(exam_cache.get(key))

    def test_get_or_compute_calls_compute_only_once(self):
        key = "doc:computed|key|||||"
        calls = {"count": 0}

        def compute():
            calls["count"] += 1
            return {"value": 42}

        first = exam_cache.get_or_compute(key, compute)
        second = exam_cache.get_or_compute(key, compute)
        self.assertEqual(first, {"value": 42})
        self.assertEqual(second, {"value": 42})
        self.assertEqual(calls["count"], 1)

    def test_delete_removes_entry(self):
        key = "doc:to|delete|||||"
        exam_cache.set(key, {"a": 1})
        exam_cache.delete(key)
        self.assertIsNone(exam_cache.get(key))


if __name__ == "__main__":
    unittest.main()
