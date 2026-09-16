"""
Caching layer.

Cache key is composed from the dimensions called out in the project
brief: authority + exam + document_type + year + paper + subject +
shift + set. Values are JSON-serialized. Expiry uses settings.CACHE_TTL_SECONDS
unless a caller overrides it. Verification timestamps are stored inside
the cached value (documents already carry verified_at), satisfying the
"store verification timestamp" requirement.
"""
import json
import time
from typing import Any, Optional

from database import db
from config.settings import settings


def build_cache_key(
    authority: str = "",
    exam: str = "",
    document_type: str = "",
    year: str = "",
    paper: str = "",
    subject: str = "",
    shift: str = "",
    doc_set: str = "",
) -> str:
    parts = [authority, exam, document_type, year, paper, subject, shift, doc_set]
    normalized = [str(p or "").strip().lower().replace(" ", "_") for p in parts]
    return "doc:" + "|".join(normalized)


def get(key: str) -> Optional[Any]:
    conn = db.get_connection()
    raw = db.cache_get(conn, key, now=time.time())
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    ttl = settings.CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    conn = db.get_connection()
    with_expiry = time.time() + ttl
    db.cache_set(conn, key, json.dumps(value), with_expiry)
    conn.commit()


def delete(key: str) -> None:
    conn = db.get_connection()
    db.cache_delete(conn, key)
    conn.commit()


def get_or_compute(key: str, compute_fn, ttl_seconds: Optional[int] = None) -> Any:
    """Return the cached value for `key`, or call compute_fn() and cache it."""
    cached = get(key)
    if cached is not None:
        return cached
    value = compute_fn()
    set(key, value, ttl_seconds=ttl_seconds)
    return value
