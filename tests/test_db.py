import os
import tempfile
import time
import unittest

from database import db
from database.models import Authority, Exam, Document, DOC_TYPE_QUESTION_PAPER


class TestDbRoundtrips(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_db.sqlite3")

    def test_schema_created_on_first_connect(self):
        conn = db.get_connection(self.db_path)
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertTrue({"authorities", "exams", "documents", "cache"}.issubset(tables))

    def test_upsert_authority_roundtrip(self):
        conn = db.get_connection(self.db_path)
        authority = Authority(
            id="rssb", name="Rajasthan Staff Selection Board",
            official_domain="rssb.rajasthan.gov.in",
            official_pages={"home": "https://rssb.rajasthan.gov.in/"},
            verification_status="WEB_VERIFIED", notes="test",
        )
        db.upsert_authority(conn, authority)
        conn.commit()
        row = conn.execute("SELECT * FROM authorities WHERE id='rssb'").fetchone()
        self.assertEqual(row["name"], "Rajasthan Staff Selection Board")

    def test_upsert_authority_is_idempotent_update(self):
        conn = db.get_connection(self.db_path)
        a1 = Authority(id="x", name="Old Name", official_domain="x.gov.in")
        db.upsert_authority(conn, a1)
        a2 = Authority(id="x", name="New Name", official_domain="x.gov.in")
        db.upsert_authority(conn, a2)
        conn.commit()
        rows = conn.execute("SELECT * FROM authorities WHERE id='x'").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "New Name")

    def test_upsert_document_roundtrip(self):
        conn = db.get_connection(self.db_path)
        doc = Document(
            id="doc1", exam_id="patwar", authority_id="rssb",
            doc_type=DOC_TYPE_QUESTION_PAPER, title="Patwar QP 2026",
            source_page="https://rssb.rajasthan.gov.in/results",
            pdf_url="https://rssb.rajasthan.gov.in/files/qp.pdf", year="2026",
        )
        doc.mark_verified("ok")
        db.upsert_document(conn, doc)
        conn.commit()
        row = conn.execute("SELECT * FROM documents WHERE id='doc1'").fetchone()
        self.assertEqual(row["verification_status"], "VERIFIED")
        self.assertEqual(row["pdf_url"], "https://rssb.rajasthan.gov.in/files/qp.pdf")

    def test_cache_get_set_delete(self):
        conn = db.get_connection(self.db_path)
        now = time.time()
        db.cache_set(conn, "k1", "v1", now + 100)
        conn.commit()
        self.assertEqual(db.cache_get(conn, "k1", now), "v1")
        self.assertIsNone(db.cache_get(conn, "k1", now + 200))  # expired
        db.cache_delete(conn, "k1")
        conn.commit()
        self.assertIsNone(db.cache_get(conn, "k1", now))


if __name__ == "__main__":
    unittest.main()
