import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import morpheus_monitor


class MorpheusMonitorTests(unittest.TestCase):
    def test_triage_hashes_file_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.txt"
            path.write_bytes(b"safe test content")
            before = path.read_bytes()
            with patch.object(morpheus_monitor, "_file_signature", return_value={"status": "Valid", "signer": "Test"}):
                result = morpheus_monitor.triage_file(str(path))
            self.assertEqual(len(result["sha256"]), 64)
            self.assertEqual(result["sha256"], __import__("hashlib").sha256(before).hexdigest())
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(result["mode"], "read-only static triage")

    def test_triage_rejects_missing_and_directory_paths(self):
        with self.assertRaises(ValueError):
            morpheus_monitor.triage_file("Z:/definitely-not-present/file.exe")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                morpheus_monitor.triage_file(folder)

    def test_executable_extension_mismatch_is_flagged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fake.exe"
            path.write_bytes(b"not an executable")
            with patch.object(morpheus_monitor, "_file_signature", return_value={"status": "Valid"}):
                result = morpheus_monitor.triage_file(str(path))
            self.assertIn("extension_header_mismatch", {x["kind"] for x in result["indicators"]})

    def test_defender_scan_is_windows_only(self):
        with patch.object(morpheus_monitor.os, "name", "posix"):
            result = morpheus_monitor.scan_with_windows_defender("sample.exe")
        self.assertFalse(result["ok"])
        self.assertIn("Windows", result["error"])

    def test_process_snapshot_is_read_only_and_bounded(self):
        result = morpheus_monitor.process_snapshot(10000)
        self.assertEqual(result["mode"], "read-only process snapshot")
        self.assertLessEqual(len(result["observations"]), 200)


if __name__ == "__main__":
    unittest.main()
