"""
Authority registry service.

Loads the seed data from config/exam_sources.py into the database (idempotent),
and exposes lookup helpers used by discovery/services. This is the single
place that answers "what authorities do we know about and what are their
official domains" — handlers and discovery never hardcode a domain string
themselves.
"""
from typing import Dict, List, Optional

from config.exam_sources import AUTHORITIES, KNOWN_UNOFFICIAL_DOMAINS
from database import db
from database.models import Authority


def _to_model(raw: dict) -> Authority:
    return Authority(
        id=raw["id"],
        name=raw["name"],
        official_domain=raw["official_domain"],
        official_pages=raw.get("official_pages", {}),
        verification_status=raw.get("verification_status", "UNVERIFIED"),
        notes=raw.get("notes", ""),
    )


def seed_authorities() -> int:
    """Load seed authorities into the DB. Safe to call repeatedly. Returns count."""
    conn = db.get_connection()
    count = 0
    for raw in AUTHORITIES:
        db.upsert_authority(conn, _to_model(raw))
        count += 1
    conn.commit()
    return count


def get_authority(authority_id: str) -> Optional[Authority]:
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM authorities WHERE id = ?", (authority_id,)
    ).fetchone()
    if row is None:
        return None
    import json
    return Authority(
        id=row["id"],
        name=row["name"],
        official_domain=row["official_domain"],
        official_pages=json.loads(row["official_pages"]),
        verification_status=row["verification_status"],
        notes=row["notes"] or "",
    )


def list_authorities() -> List[Authority]:
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM authorities").fetchall()
    import json
    return [
        Authority(
            id=row["id"], name=row["name"], official_domain=row["official_domain"],
            official_pages=json.loads(row["official_pages"]),
            verification_status=row["verification_status"], notes=row["notes"] or "",
        )
        for row in rows
    ]


def is_domain_known_unofficial(domain: str) -> bool:
    domain = domain.lower().strip(".")
    for bad in KNOWN_UNOFFICIAL_DOMAINS:
        if domain == bad.lower() or domain.endswith("." + bad.lower()):
            return True
    return False
