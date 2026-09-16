"""
Exam-name normalization and matching.

Design goal (per project brief): this must be a REUSABLE, general
normalizer — not a lookup table with two or three special cases bolted
on. It works in three layers:

  1. Text normalization (case, punctuation, ordinal words, common
     Hindi-English tokens, spacing) — applies to EVERY exam, not a
     hardcoded few.
  2. A token-alias map (many-to-one) — e.g. "SI" / "Sub Inspector" /
     "Police SI" / "Rajasthan SI" all normalize to the same alias
     tokens, and "1st" / "first" / "I" all normalize to the same
     ordinal token. This map is data, not branching logic, so adding
     a new exam/alias does not require new code.
  3. Fuzzy scoring fallback (difflib) for typos / partial matches
     against every registered exam's canonical name + aliases, so
     exams that were never given an explicit alias can still be found.

canonical exam registry lives in services/exam_registry_data.py.
"""
import difflib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# --- Layer 1: generic text normalization -----------------------------

_ORDINAL_WORDS = {
    "first": "1st", "one": "1st", "i": "1st",
    "second": "2nd", "two": "2nd", "ii": "2nd",
    "third": "3rd", "three": "3rd", "iii": "3rd",
    "fourth": "4th", "four": "4th", "iv": "4th",
}

_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_MULTISPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, expand ordinals."""
    text = text.strip().lower()
    text = _PUNCTUATION_RE.sub(" ", text)
    text = _MULTISPACE_RE.sub(" ", text).strip()
    tokens = text.split(" ")
    tokens = [_ORDINAL_WORDS.get(tok, tok) for tok in tokens]
    return " ".join(tokens)


# --- Layer 2: token/phrase alias map (data-driven, reusable) ---------
# Each entry: a tuple of phrases that should all resolve to the same
# "normalized alias phrase". This is intentionally generic infrastructure:
# to support a brand-new exam's synonyms, add a tuple here — no new
# matching code is required.
ALIAS_GROUPS: List[Tuple[str, ...]] = [
    ("si", "sub inspector", "police si", "rajasthan si", "sub inspector si"),
    ("cet 12", "cet 12th", "cet senior", "cet senior secondary", "senior cet",
     "cet sr secondary", "cet sr sec"),
    ("cet graduation", "cet grad", "cet graduate"),
    ("3rd grade", "third grade", "3rd grade teacher", "third grade teacher",
     "primary teacher", "primary school teacher", "primary teacher level 1",
     "reet level 1 teacher recruitment", "level 1 teacher"),
    ("2nd grade", "second grade", "2nd grade teacher", "second grade teacher",
     "senior teacher", "upper primary teacher", "upper primary school teacher",
     "level 2 teacher"),
    ("1st grade", "first grade", "1st grade teacher", "school lecturer",
     "lecturer"),
    ("reet", "reet exam", "rajasthan eligibility examination for teachers",
     "rtet"),
    ("reet level 1", "reet l1", "reet lvl 1"),
    ("reet level 2", "reet l2", "reet lvl 2"),
    ("vdo", "village development officer"),
    ("ldc", "lower division clerk"),
    ("patwar", "patwari"),
    ("junior assistant", "jr assistant", "jr asst"),
    ("lab assistant", "laboratory assistant"),
    ("agriculture supervisor", "agri supervisor"),
    ("animal attendant", "pashu parichar"),
    ("junior instructor", "jr instructor"),
    ("ras", "rajasthan administrative service"),
    ("high court", "rajasthan high court", "hcraj"),
]

_ALIAS_LOOKUP = {}
for group in ALIAS_GROUPS:
    canonical = group[0]
    for phrase in group:
        _ALIAS_LOOKUP[normalize_text(phrase)] = canonical


def apply_alias_layer(normalized_text: str) -> str:
    """
    Replace any known alias phrase found inside normalized_text with its
    canonical phrase. Longest phrases are matched first so e.g. "cet 12"
    doesn't get chewed up by a shorter, unrelated alias.
    """
    result = normalized_text
    phrases_by_len = sorted(_ALIAS_LOOKUP.keys(), key=len, reverse=True)
    for phrase in phrases_by_len:
        if phrase in result:
            result = result.replace(phrase, _ALIAS_LOOKUP[phrase])
    return result


@dataclass
class MatchResult:
    query: str
    normalized_query: str
    matched_exam_id: Optional[str]
    matched_exam_name: Optional[str]
    score: float  # 0..1
    method: str  # "alias" | "fuzzy" | "none"


def normalize_and_match(query: str, exam_registry: List[dict]) -> MatchResult:
    """
    exam_registry: list of dicts with at least {"id", "name", "aliases": [...]}
    Returns the best match, or a MatchResult with matched_exam_id=None if
    nothing crosses the confidence threshold.
    """
    norm = normalize_text(query)
    aliased = apply_alias_layer(norm)

    # Build a flat searchable index: normalized(name/alias) -> exam
    best_id, best_name, best_score, best_method = None, None, 0.0, "none"

    for exam in exam_registry:
        candidates = [exam["name"]] + list(exam.get("aliases", []))
        for cand in candidates:
            cand_norm = apply_alias_layer(normalize_text(cand))
            if cand_norm == aliased:
                return MatchResult(query, norm, exam["id"], exam["name"], 1.0, "alias")
            score = difflib.SequenceMatcher(None, aliased, cand_norm).ratio()
            # Bonus for substring containment (helps "cet 12 exam 2026" match "cet 12")
            if cand_norm and cand_norm in aliased:
                score = max(score, 0.9)
            if score > best_score:
                best_id, best_name, best_score, best_method = (
                    exam["id"], exam["name"], score, "fuzzy",
                )

    if best_score >= 0.55:
        return MatchResult(query, norm, best_id, best_name, round(best_score, 3), best_method)
    return MatchResult(query, norm, None, None, round(best_score, 3), "none")
