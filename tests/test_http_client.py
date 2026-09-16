import socket
import unittest
from unittest.mock import patch

from utils.http_client import (
    is_domain_allowed,
    _resolve_and_check_ip,
    _validate_url_or_raise,
    DisallowedDomainError,
    UnsafeAddressError,
)


class TestDomainAllowlist(unittest.TestCase):
    def test_exact_allowed_domain(self):
        self.assertTrue(is_domain_allowed("rajasthan.gov.in"))

    def test_subdomain_of_allowed_domain(self):
        self.assertTrue(is_domain_allowed("rssb.rajasthan.gov.in"))
        self.assertTrue(is_domain_allowed("rsmssb.rajasthan.gov.in"))
        self.assertTrue(is_domain_allowed("rpsc.rajasthan.gov.in"))

    def test_unofficial_lookalike_domain_rejected(self):
        self.assertFalse(is_domain_allowed("rpsc.rajasthansarkar.in"))
        self.assertFalse(is_domain_allowed("reet2024.co.in"))

    def test_random_domain_rejected(self):
        self.assertFalse(is_domain_allowed("evil.example.com"))
        self.assertFalse(is_domain_allowed("testbook.com"))

    def test_empty_hostname_rejected(self):
        self.assertFalse(is_domain_allowed(""))

    def test_similar_but_not_subdomain_rejected(self):
        # "notrajasthan.gov.in" must NOT match "rajasthan.gov.in" just
        # because it ends with a similar-looking substring.
        self.assertFalse(is_domain_allowed("notrajasthan.gov.in"))
        self.assertFalse(is_domain_allowed("rajasthan.gov.in.evil.com"))


class TestIpSafety(unittest.TestCase):
    @patch("utils.http_client.socket.getaddrinfo")
    def test_private_ip_rejected(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(None, None, None, None, ("10.0.0.5", 0))]
        with self.assertRaises(UnsafeAddressError):
            _resolve_and_check_ip("rssb.rajasthan.gov.in")

    @patch("utils.http_client.socket.getaddrinfo")
    def test_loopback_ip_rejected(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
        with self.assertRaises(UnsafeAddressError):
            _resolve_and_check_ip("rssb.rajasthan.gov.in")

    @patch("utils.http_client.socket.getaddrinfo")
    def test_link_local_ip_rejected(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(None, None, None, None, ("169.254.1.1", 0))]
        with self.assertRaises(UnsafeAddressError):
            _resolve_and_check_ip("rssb.rajasthan.gov.in")

    @patch("utils.http_client.socket.getaddrinfo")
    def test_public_ip_allowed(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(None, None, None, None, ("103.21.58.10", 0))]
        try:
            _resolve_and_check_ip("rssb.rajasthan.gov.in")
        except UnsafeAddressError:
            self.fail("A public IP address should not raise UnsafeAddressError")

    @patch("utils.http_client.socket.getaddrinfo")
    def test_dns_failure_raises_unsafe_address_error_not_crash(self, mock_getaddrinfo):
        mock_getaddrinfo.side_effect = socket.gaierror("name resolution failed")
        with self.assertRaises(UnsafeAddressError):
            _resolve_and_check_ip("nonexistent.rajasthan.gov.in")


class TestUrlValidation(unittest.TestCase):
    def test_disallowed_scheme_rejected(self):
        with self.assertRaises(DisallowedDomainError):
            _validate_url_or_raise("ftp://rssb.rajasthan.gov.in/file.pdf")

    def test_disallowed_domain_rejected(self):
        with self.assertRaises(DisallowedDomainError):
            _validate_url_or_raise("https://evil.example.com/file.pdf")

    @patch("utils.http_client.socket.getaddrinfo")
    def test_allowed_domain_and_public_ip_passes(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(None, None, None, None, ("103.21.58.10", 0))]
        url = _validate_url_or_raise("https://rssb.rajasthan.gov.in/file.pdf")
        self.assertEqual(url, "https://rssb.rajasthan.gov.in/file.pdf")


if __name__ == "__main__":
    unittest.main()
