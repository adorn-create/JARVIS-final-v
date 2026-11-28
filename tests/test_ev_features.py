import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ev_features import (
    _resolve_project_data_path,
    analyze_project_file,
    read_biometrics,
)


class EVFeatureTests(unittest.TestCase):
    def test_analysis_rejects_paths_outside_data_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "logs").mkdir()
            with self.assertRaises(ValueError):
                _resolve_project_data_path("../outside.txt", root=root)

    def test_csv_summary_is_aggregate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "logs").mkdir()
            (root / "data" / "metrics.csv").write_text("cpu,ram\n10,20\n30,40\n", encoding="utf-8")
            result = analyze_project_file("data/metrics.csv", root=root)
            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["numeric_summary"]["cpu"]["mean"], 20.0)

    def test_biometrics_reports_missing_sensor_without_inventing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = read_biometrics(Path(tmp) / "missing.json")
            self.assertFalse(result["available"])
            self.assertNotIn("readings", result)

    def test_biometrics_rejects_naive_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sensor.json"
            path.write_text(json.dumps({"timestamp": "2026-11-28T10:00:00", "heart_rate_bpm": 70}), encoding="utf-8")
            result = read_biometrics(path)
            self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
