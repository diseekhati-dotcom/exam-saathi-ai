"""
Hardened HTTP client used by every scraper/validator in this project.

Security properties (per project requirements):
  - Domain allowlist enforced BEFORE any request is made (SSRF mitigation).
  - Private / loopback / link-local IP literals are rejected outright, even
    if somehow allowlisted by hostname (defence in depth against DNS
    rebinding and "http://127.0.0.1/" style tricks).
  - Redirects are followed manually (not via requests' built-in
    allow_redirects) so each hop can be re-validated against the same
    domain allowlist and a hard hop-count limit — this prevents an
    allowlisted page from redirecting somewhere unsafe.
  - Response bodies are streamed and capped at MAX_DOWNLOAD_BYTES so a
    huge/hostile response cannot exhaust memory or disk.
  - A single connect+read timeout is enforced on every request.
  - No downloaded content is ever executed/imported/eval'd anywhere in
    this project.

This module intentionally has no network calls performed at import time.
"""
import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

from config.settings import settings


class DisallowedDomainError(Exception):
    pass


class UnsafeAddressError(Exception):
    pass


class TooManyRedirectsError(Exception):
    pass


class DownloadTooLargeError(Exception):
    pass


@dataclass
class SafeResponse:
    final_url: str
    status_code: int
    headers: dict
    content: bytes
    redirect_chain: list  # list[str] of every URL hop, including the first


def is_domain_allowed(hostname: str) -> bool:
    if not hostname:
        return False
    hostname = hostname.lower().strip(".")
    for allowed in settings.ALLOWED_DOMAINS:
        allowed = allowed.lower()
        if hostname == allowed or hostname.endswith("." + allowed):
            return True
    return False


def _resolve_and_check_ip(hostname: str) -> None:
    """Reject requests that resolve to private/loopback/link-local ranges."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeAddressError(f"Could not resolve host: {hostname} ({exc})")

    for info in infos:
        addr = info[4][0]
        ip = ipaddress.ip_address(addr)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeAddressError(
                f"Host {hostname} resolves to a disallowed address range: {addr}"
            )


def _validate_url_or_raise(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise DisallowedDomainError(f"Disallowed URL scheme: {parsed.scheme!r}")
    if not is_domain_allowed(parsed.hostname or ""):
        raise DisallowedDomainError(
            f"Domain not in allowlist: {parsed.hostname!r}"
        )
    _resolve_and_check_ip(parsed.hostname)
    return url


def safe_request(
    url: str,
    method: str = "GET",
    max_redirects: Optional[int] = None,
    stream: bool = True,
    max_bytes: Optional[int] = None,
    timeout: Optional[float] = None,
) -> SafeResponse:
    """
    Perform an SSRF-hardened HTTP request, following redirects manually so
    every hop is re-validated against the domain allowlist.
    """
    max_redirects = settings.HTTP_MAX_REDIRECTS if max_redirects is None else max_redirects
    max_bytes = settings.MAX_DOWNLOAD_BYTES if max_bytes is None else max_bytes
    timeout = settings.HTTP_TIMEOUT_SECONDS if timeout is None else timeout

    headers = {"User-Agent": settings.HTTP_USER_AGENT}
    chain = []
    current_url = url

    session = requests.Session()
    try:
        for hop in range(max_redirects + 1):
            _validate_url_or_raise(current_url)
            chain.append(current_url)

            resp = session.request(
                method,
                current_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                stream=stream,
            )

            if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                resp.close()
                if not location:
                    raise TooManyRedirectsError(
                        "Redirect status with no Location header"
                    )
                # Resolve relative redirects
                current_url = requests.compat.urljoin(current_url, location)
                continue

            # Not a redirect: this is the final response. Read it capped.
            content = b""
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                content += chunk
                if len(content) > max_bytes:
                    resp.close()
                    raise DownloadTooLargeError(
                        f"Response exceeded {max_bytes} bytes"
                    )
            final = SafeResponse(
                final_url=current_url,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                content=content,
                redirect_chain=chain,
            )
            resp.close()
            return final
        raise TooManyRedirectsError(
            f"Exceeded max redirect hops ({max_redirects})"
        )
    finally:
        session.close()
