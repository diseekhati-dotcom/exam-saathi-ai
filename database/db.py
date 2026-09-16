"""
Thin SQLite persistence layer.

Uses only the stdlib `sqlite3` module — no ORM dependency. Provides:
  - authority / exam / document tables mirroring database/models.py
  - a generic key/value cache table used by services/exam_cache.py

All functions are safe to call repeatedly (CREATE TABLE IF NOT EXISTS).
"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from config.settings import settings

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS authorities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    official_domain TEXT NOT NULL,
    official_pages TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS exams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL,
    authority_id TEXT,
    category TEXT,
    levels TEXT,
    official_source TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL,
    authority_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    title TEXT,
    source_page TEXT,
    pdf_url TEXT,
    year TEXT,
    subject TEXT,
    paper TEXT,
    shift TEXT,
    doc_set TEXT,
    level TEXT,
    answer_key_status TEXT,
    verification_status TEXT NOT NULL,
    verification_reason TEXT,
    verified_at REAL
);

CREATE TABLE IF NOT EXISTS cache (
    cache_key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at REAL NOT NULL
);
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating schema on first use."""
    path = db_path or settings.DATABASE_PATH
    cache_attr = f"_conn_{path}"
    conn = getattr(_local, cache_attr, None)
    if conn is not None:
        return conn

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    setattr(_local, cache_attr, conn)
    return conn


@contextmanager
def transaction(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def upsert_authority(conn: sqlite3.Connection, authority) -> None:
    conn.execute(
        """
        INSERT INTO authorities (id, name, official_domain, official_pages,
                                  verification_status, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            official_domain=excluded.official_domain,
            official_pages=excluded.official_pages,
            verification_status=excluded.verification_status,
            notes=excluded.notes
        """,
        (
            authority.id,
            authority.name,
            authority.official_domain,
            json.dumps(authority.official_pages),
            authority.verification_status,
            authority.notes,
        ),
    )


def upsert_exam(conn: sqlite3.Connection, exam) -> None:
    conn.execute(
        """
        INSERT INTO exams (id, name, aliases, authority_id, category, levels,
                            official_source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            aliases=excluded.aliases,
            authority_id=excluded.authority_id,
            category=excluded.category,
            levels=excluded.levels,
            official_source=excluded.official_source
        """,
        (
            exam.id,
            exam.name,
            json.dumps(exam.aliases),
            exam.authority_id,
            exam.category,
            json.dumps(exam.levels),
            exam.official_source,
        ),
    )


def upsert_document(conn: sqlite3.Connection, doc) -> None:
    conn.execute(
        """
        INSERT INTO documents (id, exam_id, authority_id, doc_type, title,
                                source_page, pdf_url, year, subject, paper,
                                shift, doc_set, level, answer_key_status,
                                verification_status, verification_reason,
                                verified_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            exam_id=excluded.exam_id,
            authority_id=excluded.authority_id,
            doc_type=excluded.doc_type,
            title=excluded.title,
            source_page=excluded.source_page,
            pdf_url=excluded.pdf_url,
            year=excluded.year,
            subject=excluded.subject,
            paper=excluded.paper,
            shift=excluded.shift,
            doc_set=excluded.doc_set,
            level=excluded.level,
            answer_key_status=excluded.answer_key_status,
            verification_status=excluded.verification_status,
            verification_reason=excluded.verification_reason,
            verified_at=excluded.verified_at
        """,
        (
            doc.id, doc.exam_id, doc.authority_id, doc.doc_type, doc.title,
            doc.source_page, doc.pdf_url, doc.year, doc.subject, doc.paper,
            doc.shift, doc.doc_set, doc.level, doc.answer_key_status,
            doc.verification_status, doc.verification_reason, doc.verified_at,
        ),
    )


def cache_get(conn: sqlite3.Connection, key: str, now: float) -> Optional[str]:
    row = conn.execute(
        "SELECT value, expires_at FROM cache WHERE cache_key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    if row["expires_at"] < now:
        return None
    return row["value"]


def cache_set(conn: sqlite3.Connection, key: str, value: str, expires_at: float) -> None:
    conn.execute(
        """
        INSERT INTO cache (cache_key, value, expires_at) VALUES (?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET value=excluded.value,
                                              expires_at=excluded.expires_at
        """,
        (key, value, expires_at),
    )


def cache_delete(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
