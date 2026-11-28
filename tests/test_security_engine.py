import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from security_engine import _private_ipv4, normalize_ports, run_safe_lab_demo, scan_private_https_tls


class SecurityEngineTests(unittest.TestCase):
    def test_private_target_allowed(self):
        self.assertEqual(str(_private_ipv4("192.168.1.10")), "192.168.1.10")
        self.assertEqual(str(_private_ipv4("127.0.0.1")), "127.0.0.1")

    def test_public_target_rejected(self):
        for target in ("8.8.8.8", "example.com", "192.168.1.0/24", "::1"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                _private_ipv4(target)

    def test_ports_are_allowlisted(self):
        self.assertEqual(normalize_ports([80, 443]), [80, 443])
        with self.assertRaises(ValueError):
            normalize_ports([4444])

    def test_https_scanner_requires_https(self):
        with self.assertRaises(ValueError):
            scan_private_https_tls("http://127.0.0.1")
        with self.assertRaises(ValueError):
            scan_private_https_tls("https://8.8.8.8")

    def test_lab_demo_is_non_destructive(self):
        result = run_safe_lab_demo("path_traversal_guard")
        self.assertEqual(result["targets_touched"], 0)
        self.assertEqual(result["files_written"], 0)
        self.assertEqual(result["network_connections"], 0)
        self.assertEqual(result["checks"][1]["fixed_guard"], "BLOCK")
        self.assertEqual(result["checks"][1]["vulnerable_demo"], "ESCAPES LAB ROOT")


if __name__ == "__main__":
    unittest.main()
