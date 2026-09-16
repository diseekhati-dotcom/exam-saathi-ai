import unittest
from unittest.mock import patch

from services import pdf_validator
from utils.http_client import (
    SafeResponse,
    DisallowedDomainError,
    UnsafeAddressError,
    TooManyRedirectsError,
    DownloadTooLargeError,
)

REAL_LOOKING_PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"0" * 2000 + b"\n%%EOF"


def _fake_pdf_response(url="https://rssb.rajasthan.gov.in/files/paper.pdf"):
    return SafeResponse(
        final_url=url,
        status_code=200,
        headers={"Content-Type": "application/pdf"},
        content=REAL_LOOKING_PDF_BYTES,
        redirect_chain=[url],
    )


def _fake_html_response(url="https://rssb.rajasthan.gov.in/files/paper.pdf"):
    html = b"<html><head><title>Error</title></head><body>Sorry, the Page you looking for can't be Found. 404 Not Found</body></html>"
    return SafeResponse(
        final_url=url,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=html,
        redirect_chain=[url],
    )


class TestPdfValidatorHappyPath(unittest.TestCase):
    @patch("services.pdf_validator.safe_request")
    def test_valid_pdf_passes(self, mock_request):
        mock_request.return_value = _fake_pdf_response()
        result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/files/paper.pdf")
        self.assertTrue(result.passed)
        self.assertEqual(result.reasons, [])
        self.assertEqual(result.status_code, 200)

    @patch("services.pdf_validator.safe_request")
    def test_identity_tokens_high_confidence(self, mock_request):
        mock_request.return_value = _fake_pdf_response(
            url="https://rssb.rajasthan.gov.in/files/paper-2026-shift1.pdf"
        )
        result = pdf_validator.validate_pdf_url(
            "https://rssb.rajasthan.gov.in/files/paper-2026-shift1.pdf",
            expected_tokens=["2026", "shift1"],
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.identity_confidence, "HIGH")

    @patch("services.pdf_validator.safe_request")
    def test_identity_tokens_low_confidence_when_missing(self, mock_request):
        mock_request.return_value = _fake_pdf_response(
            url="https://rssb.rajasthan.gov.in/files/paper.pdf"
        )
        result = pdf_validator.validate_pdf_url(
            "https://rssb.rajasthan.gov.in/files/paper.pdf",
            expected_tokens=["2026", "shift1"],
        )
        self.assertTrue(result.passed)  # still a real PDF
        self.assertEqual(result.identity_confidence, "LOW")


class TestPdfValidatorRejections(unittest.TestCase):
    @patch("services.pdf_validator.safe_request")
    def test_html_error_page_rejected(self, mock_request):
        mock_request.return_value = _fake_html_response()
        result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/files/paper.pdf")
        self.assertFalse(result.passed)
        joined = result.reason_text().lower()
        self.assertTrue("html" in joined or "error" in joined)

    @patch("services.pdf_validator.safe_request")
    def test_non_200_status_rejected(self, mock_request):
        mock_request.return_value = SafeResponse(
            final_url="https://rssb.rajasthan.gov.in/files/missing.pdf",
            status_code=404,
            headers={"Content-Type": "text/html"},
            content=b"<html>not found</html>",
            redirect_chain=["https://rssb.rajasthan.gov.in/files/missing.pdf"],
        )
        result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/files/missing.pdf")
        self.assertFalse(result.passed)
        self.assertIn("404", result.reason_text())

    @patch("services.pdf_validator.safe_request")
    def test_tiny_fake_pdf_rejected(self, mock_request):
        mock_request.return_value = SafeResponse(
            final_url="https://rssb.rajasthan.gov.in/files/tiny.pdf",
            status_code=200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.4\n",  # tiny, suspicious
            redirect_chain=["https://rssb.rajasthan.gov.in/files/tiny.pdf"],
        )
        result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/files/tiny.pdf")
        self.assertFalse(result.passed)
        self.assertIn("too small", result.reason_text().lower())

    @patch("services.pdf_validator.safe_request")
    def test_missing_magic_bytes_rejected_even_with_pdf_content_type(self, mock_request):
        mock_request.return_value = SafeResponse(
            final_url="https://rssb.rajasthan.gov.in/files/fake.pdf",
            status_code=200,
            headers={"Content-Type": "application/pdf"},
            content=b"not actually a pdf" * 50,
            redirect_chain=["https://rssb.rajasthan.gov.in/files/fake.pdf"],
        )
        result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/files/fake.pdf")
        self.assertFalse(result.passed)
        self.assertIn("magic bytes", result.reason_text().lower())

    @patch("services.pdf_validator.safe_request")
    def test_disallowed_domain_exception_handled_gracefully(self, mock_request):
        mock_request.side_effect = DisallowedDomainError("evil.example.com not allowed")
        result = pdf_validator.validate_pdf_url("https://evil.example.com/paper.pdf")
        self.assertFalse(result.passed)
        self.assertIn("not allowlisted", result.reason_text())

    @patch("services.pdf_validator.safe_request")
    def test_ssrf_unsafe_address_handled_gracefully(self, mock_request):
        mock_request.side_effect = UnsafeAddressError("resolves to 127.0.0.1")
        result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/paper.pdf")
        self.assertFalse(result.passed)
        self.assertIn("SSRF", result.reason_text())

    @patch("services.pdf_validator.safe_request")
    def test_too_many_redirects_handled_gracefully(self, mock_request):
        mock_request.side_effect = TooManyRedirectsError("exceeded 5 hops")
        result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/paper.pdf")
        self.assertFalse(result.passed)
        self.assertIn("redirect", result.reason_text().lower())

    @patch("services.pdf_validator.safe_request")
    def test_download_too_large_handled_gracefully(self, mock_request):
        mock_request.side_effect = DownloadTooLargeError("exceeded 25MB")
        result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/paper.pdf")
        self.assertFalse(result.passed)
        self.assertIn("size limit", result.reason_text().lower())

    @patch("services.pdf_validator.safe_request")
    def test_generic_network_exception_never_crashes(self, mock_request):
        mock_request.side_effect = TimeoutError("connection timed out")
        try:
            result = pdf_validator.validate_pdf_url("https://rssb.rajasthan.gov.in/paper.pdf")
        except Exception as exc:  # pragma: no cover - the whole point of this test
            self.fail(f"validate_pdf_url raised instead of returning a failed result: {exc}")
        self.assertFalse(result.passed)

    @patch("services.pdf_validator.safe_request")
    def test_non_https_flagged(self, mock_request):
        mock_request.return_value = _fake_pdf_response(url="http://rssb.rajasthan.gov.in/files/paper.pdf")
        result = pdf_validator.validate_pdf_url("http://rssb.rajasthan.gov.in/files/paper.pdf")
        self.assertFalse(result.passed)
        self.assertIn("https", result.reason_text().lower())


if __name__ == "__main__":
    unittest.main()
