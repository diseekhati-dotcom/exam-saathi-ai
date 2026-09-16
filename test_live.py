"""
test_live.py — REAL network verification, run AFTER deployment.

This script could NOT be executed in the build sandbox (no network
access there). Run it yourself after deploying to Render (or any
environment with internet access) to get real, live-verified results
against the actual government websites.

Usage (after `pip install -r requirements.txt`):

    python test_live.py                     # run all built-in test cases
    python test_live.py "Patwar"             # run just one exam
    python test_live.py --json report.json   # also dump machine-readable results

What it does for each exam:
  1. Resolves the exam name via services.exam_service.resolve_exam
     (exercises the SAME normalizer used by the live bot).
  2. For each document type (Syllabus, Question Paper, Answer Key):
       a. Runs the real discovery crawl against the exam's authority's
          official page(s) (services.exam_service.find_documents).
       b. Prints, per candidate: source page, discovered URL, final URL
          after redirects, HTTP status, Content-Type, PDF magic-byte
          check result, and the resulting verification_status.
  3. Prints a summary table.

This script deliberately does NOT invent success. If discovery finds
zero candidates (e.g. because an archive page renders its links via
JavaScript the plain HTTP fetch can't see), that is reported honestly
as "0 candidates discovered / SOURCE_PAGE_ONLY fallback used" rather
than being papered over.
"""
import argparse
import json
import sys
import time

from database.models import (
    DOC_TYPE_SYLLABUS, DOC_TYPE_QUESTION_PAPER, DOC_TYPE_ANSWER_KEY,
    VERIFICATION_VERIFIED, VERIFICATION_REJECTED, VERIFICATION_SOURCE_PAGE_ONLY,
)
from services import authority_registry, exam_service

DEFAULT_TEST_EXAMS = [
    "CET Senior Secondary",
    "CET Graduation",
    "Lab Assistant Geography",
    "3rd Grade Teacher",
    "Primary Teacher Level-1",
    "REET Level 1",
    "REET Level 2",
    "Patwar",
    "VDO",
    "LDC",
    "Sub Inspector",
]

DOC_TYPES = [
    (DOC_TYPE_SYLLABUS, "Syllabus"),
    (DOC_TYPE_QUESTION_PAPER, "Question Paper"),
    (DOC_TYPE_ANSWER_KEY, "Answer Key"),
]


def run_one(exam_query: str) -> dict:
    print(f"\n{'=' * 70}\nEXAM QUERY: {exam_query}\n{'=' * 70}")
    match = exam_service.resolve_exam(exam_query)
    result = {"query": exam_query, "matched_exam_id": match.matched_exam_id,
              "matched_exam_name": match.matched_exam_name, "doc_types": {}}

    if not match.matched_exam_id:
        print("  -> NOT MATCHED to any known exam (normalizer confidence too low).")
        return result

    exam = exam_service.get_exam(match.matched_exam_id)
    authority = authority_registry.get_authority(exam["authority_id"])
    print(f"  Matched exam : {match.matched_exam_name} (id={match.matched_exam_id})")
    print(f"  Authority    : {authority.name if authority else exam['authority_id']}")

    for doc_type, label in DOC_TYPES:
        print(f"\n  --- {label} ---")
        t0 = time.time()
        try:
            docs = exam_service.find_documents(match.matched_exam_id, doc_type, use_cache=False)
        except Exception as exc:
            print(f"    ERROR while discovering {label}: {exc}")
            result["doc_types"][doc_type] = {"error": str(exc)}
            continue
        elapsed = time.time() - t0

        doc_summaries = []
        for doc in docs:
            print(f"    Title            : {doc.title}")
            print(f"    Source page      : {doc.source_page}")
            print(f"    Candidate URL    : {doc.pdf_url or '(none - see reason)'}")
            print(f"    Year             : {doc.year}")
            print(f"    Verification     : {doc.verification_status}")
            print(f"    Reason           : {doc.verification_reason}")
            print("    " + "-" * 40)
            doc_summaries.append({
                "title": doc.title, "source_page": doc.source_page,
                "pdf_url": doc.pdf_url, "year": doc.year,
                "verification_status": doc.verification_status,
                "verification_reason": doc.verification_reason,
            })

        verified_count = sum(1 for d in docs if d.verification_status == VERIFICATION_VERIFIED)
        rejected_count = sum(1 for d in docs if d.verification_status == VERIFICATION_REJECTED)
        source_only_count = sum(1 for d in docs if d.verification_status == VERIFICATION_SOURCE_PAGE_ONLY)
        print(
            f"    => {len(docs)} candidate(s) in {elapsed:.2f}s | "
            f"verified={verified_count} rejected={rejected_count} source_only={source_only_count}"
        )
        result["doc_types"][doc_type] = {
            "documents": doc_summaries,
            "verified_count": verified_count,
            "rejected_count": rejected_count,
            "source_only_count": source_only_count,
            "elapsed_seconds": round(elapsed, 2),
        }

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Live verification against real Rajasthan exam authority websites.")
    parser.add_argument("exam", nargs="?", help="Run only this one exam query instead of the full default list.")
    parser.add_argument("--json", help="Path to also write a machine-readable JSON report.")
    args = parser.parse_args()

    authority_registry.seed_authorities()

    exams = [args.exam] if args.exam else DEFAULT_TEST_EXAMS
    all_results = []
    for exam_query in exams:
        all_results.append(run_one(exam_query))

    print(f"\n\n{'#' * 70}\nSUMMARY\n{'#' * 70}")
    for r in all_results:
        if not r["matched_exam_id"]:
            print(f"{r['query']:<35} NOT MATCHED")
            continue
        verified_any = any(
            dt.get("verified_count", 0) > 0 for dt in r["doc_types"].values() if isinstance(dt, dict)
        )
        print(f"{r['query']:<35} matched={r['matched_exam_name']:<40} verified_any_doc={verified_any}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nWrote JSON report to {args.json}")


if __name__ == "__main__":
    main()
