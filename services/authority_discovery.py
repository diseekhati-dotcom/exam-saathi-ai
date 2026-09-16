"""
authority_discovery.py
-----------------------
Given free text (a command argument or a natural-language message), work
out:
  1. which known exam it refers to (if any) — via EXAM_REGISTRY
  2. which authority conducts it — either from the matched exam, or, for
     an exam not in the registry, via a keyword-based best guess

This module never invents an authority. If nothing matches, it says so
(`authority=None`) instead of picking one arbitrarily.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from config.exam_sources import AUTHORITIES, EXAM_REGISTRY


@dataclass
class IdentifyResult:
    exam: Optional[dict]        # entry from EXAM_REGISTRY, or None
    authority: Optional[dict]   # entry from AUTHORITIES, or None
    confidence: float           # 0.0 - 1.0
    method: str                 # "registry" | "keyword_guess" | "none"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _contains_alias(cand_norm: str, norm_text: str) -> bool:
    """Word-boundary-safe substring check — see exam_engine._contains_alias
    for why short aliases (e.g. "si") can't use plain `in` containment."""
    if not cand_norm:
        return False
    if len(cand_norm) >= 5:
        return cand_norm in norm_text
    return re.search(rf"\b{re.escape(cand_norm)}\b", norm_text) is not None


def _get_authority(authority_id: str) -> Optional[dict]:
    return AUTHORITIES.get(authority_id)


def match_registry_exam(text: str) -> tuple[Optional[dict], float]:
    """Best-effort match against the curated EXAM_REGISTRY fast path."""
    norm_text = _norm(text)
    best_entry, best_score = None, 0.0

    for entry in EXAM_REGISTRY:
        candidates = [entry["name"]] + entry.get("aliases", [])
        for cand in candidates:
            cand_norm = _norm(cand)
            if not cand_norm:
                continue
            if _contains_alias(cand_norm, norm_text):
                # substring match — favour longer, more specific aliases
                score = 0.85 + 0.15 * min(len(cand_norm) / max(len(norm_text), 1), 1.0)
                score = min(score, 1.0)
            elif len(cand_norm) >= 4:
                # Fuzzy fallback only for longer aliases — see exam_engine.py
                # for why short aliases are excluded from fuzzy scoring
                # (false positives against unrelated long text).
                raw = _similarity(cand_norm, norm_text)
                length_ratio = min(len(cand_norm), len(norm_text)) / max(len(cand_norm), len(norm_text))
                score = raw * length_ratio * 0.75
            else:
                score = 0.0
            if score > best_score:
                best_entry, best_score = entry, score

    return best_entry, best_score


def guess_authority_by_keyword(text: str) -> tuple[Optional[dict], float]:
    """
    Fallback for exams NOT in EXAM_REGISTRY: scan authority keyword_hints
    to guess who conducts it. This only identifies the AUTHORITY, never a
    specific exam — it's the honest middle ground between "found it
    exactly" and "no idea at all".
    """
    norm_text = f" {_norm(text)} "
    best_authority, best_score = None, 0.0

    for authority in AUTHORITIES.values():
        for hint in authority.get("keyword_hints", []):
            hint_norm = f" {_norm(hint)} "
            if hint_norm.strip() and hint_norm in norm_text:
                score = 0.6 + 0.1 * min(len(hint_norm) / 20, 1.0)
                if score > best_score:
                    best_authority, best_score = authority, score

    return best_authority, best_score


def identify_exam(text: str) -> IdentifyResult:
    """
    Main entry point. Order of operations:
      1. Try the curated registry (fast, precise, covers common exams).
      2. If that's weak/empty, fall back to keyword-based authority
         guessing (covers exams outside the registry, e.g. a brand new
         RSSB recruitment not yet added to EXAM_REGISTRY by name).
      3. Otherwise, honestly report nothing was identified.
    """
    exam_entry, exam_score = match_registry_exam(text)

    if exam_entry and exam_score >= 0.55:
        authority = _get_authority(exam_entry["authority"])
        return IdentifyResult(exam=exam_entry, authority=authority,
                               confidence=exam_score, method="registry")

    authority, auth_score = guess_authority_by_keyword(text)
    if authority and auth_score >= 0.5:
        return IdentifyResult(exam=None, authority=authority,
                               confidence=auth_score, method="keyword_guess")

    return IdentifyResult(exam=None, authority=None, confidence=0.0, method="none")
