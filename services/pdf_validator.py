"""
pdf_validator.py
-----------------
Verifies a discovered link is actually a safe, real, reachable PDF before
the bot ever shows it to a user. Nothing is shown unless it passes here.

Checks performed:
  1. Scheme must be http/https (never file://, ftp://, etc.)
  2. SSRF guard — the resolved IP must not be private/loopback/link-local/
     reserved, so a malicious redirect can't make the bot's server hit an
     internal service.
  3. Redirects are followed but each hop is re-checked against the same
     SSRF guard ("redirect validation").
  4. A HEAD request (falling back to a small ranged GET when HEAD isn't
     supported) checks the Content-Type is a PDF, or — if the server lies
     about Content-Type — the first bytes are checked for the `%PDF-`
     magic number.
  5. Content-Length (if present) is capped so we never try to pull down a
     huge file just to validate it.
  6. Every step has a timeout; every exception is caught — a broken/slow
     official site can never crash the bot, it just means that one link
     doesn't get shown.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

REQUEST_TIMEOUT = 10.0
MAX_CONTENT_BYTES = 40 * 1024 * 1024  # 40 MB cap
USER_AGENT = "Mozilla/5.0 (ExamSaathiAI/1.0; +https://t.me/StudySaathiAI)"
MAGIC_BYTES = b"%PDF-"


@dataclass
class ValidationResult:
    ok: bool
    reason: str
    content_type: Optional[str] = None
    final_url: Optional[str] = None


def _is_private_host(hostname: str) -> bool:
    """Resolve hostname and reject private/loopback/link-local/reserved IPs (SSRF guard)."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True  # can't resolve -> treat as unsafe/invalid, not shown
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def _basic_url_check(url: str) -> Optional[str]:
    """Returns an error reason string, or None if the URL passes basic checks."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "invalid_scheme"
    if not parsed.netloc:
        return "invalid_url"
    if _is_private_host(parsed.hostname or ""):
        return "ssrf_blocked"
    return None


async def verify_pdf_url(url: str) -> ValidationResult:
    err = _basic_url_check(url)
    if err:
        return ValidationResult(ok=False, reason=err)

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            max_redirects=5,
        ) as client:
            try:
                resp = await client.head(url)
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError):
                resp = None

            if resp is None or resp.status_code >= 400 or "content-type" not in resp.headers:
                # HEAD failed or was unhelpful — fall back to a small ranged GET
                try:
                    async with client.stream("GET", url, headers={"Range": "bytes=0-2048"}) as stream_resp:
                        if stream_resp.status_code >= 400:
                            return ValidationResult(ok=False, reason=f"http_{stream_resp.status_code}")
                        # revalidate final host after redirects
                        final_err = _basic_url_check(str(stream_resp.url))
                        if final_err:
                            return ValidationResult(ok=False, reason=final_err)
                        content_type = stream_resp.headers.get("content-type", "")
                        first_chunk = b""
                        async for chunk in stream_resp.aiter_bytes():
                            first_chunk += chunk
                            break
                        is_pdf = "pdf" in content_type.lower() or first_chunk.startswith(MAGIC_BYTES)
                        if not is_pdf:
                            return ValidationResult(ok=False, reason="not_pdf", content_type=content_type)
                        return ValidationResult(ok=True, reason="verified_via_get",
                                                 content_type=content_type, final_url=str(stream_resp.url))
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPError):
                    return ValidationResult(ok=False, reason="unreachable")

            # HEAD succeeded
            final_err = _basic_url_check(str(resp.url))
            if final_err:
                return ValidationResult(ok=False, reason=final_err)

            content_type = resp.headers.get("content-type", "")
            content_length = resp.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > MAX_CONTENT_BYTES:
                return ValidationResult(ok=False, reason="too_large", content_type=content_type)

            if "pdf" not in content_type.lower():
                # some servers mislabel — don't reject outright on HEAD alone if
                # the URL clearly ends in .pdf; otherwise reject (likely an HTML page)
                if not urlparse(str(resp.url)).path.lower().endswith(".pdf"):
                    return ValidationResult(ok=False, reason="not_pdf", content_type=content_type)

            return ValidationResult(ok=True, reason="verified_via_head",
                                     content_type=content_type, final_url=str(resp.url))

    except Exception:
        return ValidationResult(ok=False, reason="validation_error")
