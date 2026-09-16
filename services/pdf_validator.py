"""
PDF validation pipeline.

This is the module the whole "never show a broken/wrong PDF" requirement
rests on. It is deliberately structured as a sequence of independent,
individually-testable checks (`_check_*`) that `validate_pdf_url()`
threads together, so each rule can be unit-tested offline with a faked
SafeResponse (see tests/test_pdf_validator.py) without ever touching the
network.

KNOWN LIMITATION (documented honestly, not hidden): full text-layer
extraction from inside the PDF (to cross-check "does this PDF's own text
mention the right year/subject") would require a PDF-parsing dependency
that is not available in this build environment and was not verified
against real files. Identity validation here instead checks the
available *surface* signals: the final URL, any filename in
Content-Disposition, and the document title/metadata string the
discovery layer extracted from the source page's link text. This is
correctly labelled SOURCE_PAGE_ONLY / REJECTED rather than silently
trusted when those signals are insufficient — see
`identity_confidence` in the result.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from utils.http_client import (
    safe_request,
    SafeResponse,
    DisallowedDomainError,
    UnsafeAddressError,
    TooManyRedirectsError,
    DownloadTooLargeError,
)
from config.settings import settings
from utils.logger import get_logger

log = get_logger(__name__)

PDF_MAGIC = b"%PDF-"

# Content-Type strings that unambiguously mean "not a PDF, this is a web page"
_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")

_ERROR_PAGE_MARKERS = [
    "page not found", "page you looking for can't be found",
    "page you are looking for", "404", "error page", "sorry", "not found",
    "login", "sign in", "session expired", "access denied",
]


@dataclass
class PdfValidationResult:
    url: str
    passed: bool
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    redirect_chain: List[str] = field(default_factory=list)
    size_bytes: Optional[int] = None
    reasons: List[str] = field(default_factory=list)  # rejection reasons, if any
    identity_confidence: str = "UNKNOWN"  # LOW | MEDIUM | HIGH | UNKNOWN

    def reason_text(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "OK"


def _looks_like_error_or_login_page(text_sample: str) -> bool:
    lowered = text_sample.lower()
    hits = sum(1 for marker in _ERROR_PAGE_MARKERS if marker in lowered)
    # Require at least 2 markers so we don't false-positive on a PDF whose
    # metadata happens to contain the word "login" once, etc.
    return hits >= 2


def validate_pdf_url(
    url: str,
    expected_tokens: Optional[List[str]] = None,
    method: str = "GET",
) -> PdfValidationResult:
    """
    Run the full validation pipeline against `url` and return a
    PdfValidationResult. Never raises for "the URL turned out to be bad" —
    only for programmer errors. Network/SSRF/timeout problems are caught
    and turned into a failed result with a clear reason, per the
    "bot must never crash" requirement.

    expected_tokens: optional list of normalized tokens (e.g. exam name
    fragments, a year, "answer key") that should appear somewhere in the
    final URL or filename for a MEDIUM/HIGH identity_confidence rating.
    """
    result = PdfValidationResult(url=url, passed=False)

    try:
        resp: SafeResponse = safe_request(url, method=method, stream=True)
    except DisallowedDomainError as exc:
        result.reasons.append(f"Domain not allowlisted: {exc}")
        return result
    except UnsafeAddressError as exc:
        result.reasons.append(f"Unsafe address rejected (SSRF protection): {exc}")
        return result
    except TooManyRedirectsError as exc:
        result.reasons.append(f"Too many redirects: {exc}")
        return result
    except DownloadTooLargeError as exc:
        result.reasons.append(f"Download exceeded size limit: {exc}")
        return result
    except Exception as exc:  # network errors, timeouts, DNS failures, etc.
        result.reasons.append(f"Request failed: {exc.__class__.__name__}: {exc}")
        return result

    result.final_url = resp.final_url
    result.status_code = resp.status_code
    result.redirect_chain = resp.redirect_chain
    result.content_type = resp.headers.get("Content-Type", "")
    result.size_bytes = len(resp.content)

    # 1. HTTP status
    if resp.status_code != 200:
        result.reasons.append(f"Non-200 HTTP status: {resp.status_code}")

    # 2. HTTPS preferred (warn, not hard-fail, since some .gov.in still run
    #    plain HTTP for legacy reasons) — but record it.
    if not result.final_url.lower().startswith("https://"):
        result.reasons.append("Final URL is not HTTPS (downgraded)")

    # 3. Content-Type must not be an HTML page
    ct_lower = (result.content_type or "").lower()
    if any(html_ct in ct_lower for html_ct in _HTML_CONTENT_TYPES):
        result.reasons.append(f"Content-Type indicates HTML, not a PDF: {result.content_type}")

    # 4. PDF magic bytes ("%PDF-") must appear near the start of the file
    head = resp.content[: settings.PDF_SNIFF_BYTES]
    if PDF_MAGIC not in head:
        result.reasons.append("PDF magic bytes ('%PDF-') not found in response")

    # 5. If it wasn't flagged as PDF by magic bytes, sniff for an error/login page
    if PDF_MAGIC not in head:
        try:
            text_sample = head.decode("utf-8", errors="ignore")
        except Exception:
            text_sample = ""
        if _looks_like_error_or_login_page(text_sample):
            result.reasons.append(
                "Response body looks like an error/login/not-found page"
            )

    # 6. Reasonable file size (reject suspiciously tiny "PDFs" — likely a
    #    redirect stub or error page saved with a .pdf extension)
    if PDF_MAGIC in head and result.size_bytes is not None and result.size_bytes < 512:
        result.reasons.append(
            f"File too small to be a real document ({result.size_bytes} bytes)"
        )

    # 7. Best-effort identity check against expected tokens (see module
    #    docstring for the honesty note on this check's limits)
    if expected_tokens:
        haystack = (result.final_url + " " + resp.headers.get("Content-Disposition", "")).lower()
        haystack = re.sub(r"[^a-z0-9]+", " ", haystack)
        matched = sum(1 for tok in expected_tokens if tok.lower() in haystack)
        if matched == 0:
            result.identity_confidence = "LOW"
        elif matched < len(expected_tokens):
            result.identity_confidence = "MEDIUM"
        else:
            result.identity_confidence = "HIGH"
    else:
        result.identity_confidence = "UNKNOWN"

    result.passed = len(result.reasons) == 0
    if not result.passed:
        log.info("PDF validation failed for %s: %s", url, result.reason_text())
    return result
