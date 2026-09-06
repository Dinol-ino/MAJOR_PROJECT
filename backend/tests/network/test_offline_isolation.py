import unittest
from app.network.mode_enforcer import (
    mode_enforcer,
    NetworkIsolationViolation,
    DisallowedDomainError,
    SSRFBlockedError,
)


class TestOfflineNetworkIsolation(unittest.TestCase):

    def setUp(self):
        # Guarantee initial offline mode
        mode_enforcer.set_mode("OFFLINE", reason="Test setup")

    def tearDown(self):
        # Reset to OFFLINE after test
        mode_enforcer.set_mode("OFFLINE", reason="Test teardown")

    def test_offline_mode_blocks_any_outbound_request(self):
        self.assertTrue(mode_enforcer.is_offline())
        with self.assertRaises(NetworkIsolationViolation):
            mode_enforcer.validate_outbound_url("https://indiacode.nic.in/handle/12345")

    def test_online_mode_allows_allowlisted_domain(self):
        mode_enforcer.set_mode("ONLINE", reason="Testing online allowlist")
        self.assertTrue(mode_enforcer.is_online())
        # Indian Kanoon and IndiaCode are in legal_sources.yaml
        self.assertTrue(mode_enforcer.validate_outbound_url("https://indiankanoon.org/doc/12345/"))
        self.assertTrue(mode_enforcer.validate_outbound_url("https://indiacode.nic.in/bitstream/12345"))
        self.assertTrue(mode_enforcer.validate_outbound_url("https://sci.gov.in/judgments"))

    def test_online_mode_rejects_unallowlisted_domain(self):
        mode_enforcer.set_mode("ONLINE", reason="Testing unauthorized domain block")
        with self.assertRaises(DisallowedDomainError):
            mode_enforcer.validate_outbound_url("https://example.com/unauthorized")
        with self.assertRaises(DisallowedDomainError):
            mode_enforcer.validate_outbound_url("https://reddit.com/r/legaladvice")

    def test_ssrf_attacks_blocked(self):
        mode_enforcer.set_mode("ONLINE", reason="Testing SSRF security gate")
        # Loopback
        with self.assertRaises(SSRFBlockedError):
            mode_enforcer.validate_outbound_url("http://127.0.0.1:8000/internal-secrets")
        # AWS metadata service IP
        with self.assertRaises(SSRFBlockedError):
            mode_enforcer.validate_outbound_url("http://169.254.169.254/latest/meta-data")
        # RFC1918 Private subnet
        with self.assertRaises(SSRFBlockedError):
            mode_enforcer.validate_outbound_url("http://192.168.1.1/admin")


if __name__ == "__main__":
    unittest.main()
