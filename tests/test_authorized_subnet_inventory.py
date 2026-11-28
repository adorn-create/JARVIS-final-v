import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from security_engine import scan_authorized_subnet


class AuthorizedSubnetInventoryTests(unittest.TestCase):
    def test_rejects_public_and_large_networks(self):
        for cidr in ("8.8.8.0/28", "192.168.1.0/24", "2001:db8::/64"):
            with self.subTest(cidr=cidr), self.assertRaises(ValueError):
                scan_authorized_subnet(cidr, ports=[80])

    def test_rejects_non_allowlisted_ports(self):
        with self.assertRaises(ValueError):
            scan_authorized_subnet("192.168.1.0/28", ports=[4444])

    @patch("security_engine.socket.create_connection", side_effect=OSError("closed"))
    def test_checks_at_most_fourteen_private_hosts(self, _connect):
        result = scan_authorized_subnet("192.168.1.0/28", ports=[80])
        self.assertTrue(result["ok"])
        self.assertEqual(result["hosts_checked"], 14)
        self.assertEqual(result["ports_per_host"], 1)
        self.assertEqual(result["devices_with_open_ports"], [])
        self.assertEqual(_connect.call_count, 14)


if __name__ == "__main__":
    unittest.main()
