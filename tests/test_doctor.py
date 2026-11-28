import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import doctor


class DoctorTests(unittest.TestCase):
    def test_report_is_read_only_and_has_expected_sections(self):
        with patch.dict(os.environ, {"JARVIS_LLM_BACKEND": "ollama"}, clear=True):
            report = doctor.collect_report()
        self.assertIn("python", report)
        self.assertIn("dependencies", report)
        self.assertIn("devices", report)
        self.assertIn("face_auth", report)
        self.assertEqual(report["model"]["requested_backend"], "ollama")
        self.assertIn("process_rss_mb", report["memory"])

    def test_gguf_presence_is_reported_without_loading_model(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf") as model:
            with patch.dict(os.environ, {
                "JARVIS_LLM_BACKEND": "auto",
                "JARVIS_GGUF_MODEL": model.name,
            }, clear=True):
                report = doctor.collect_report()
        self.assertTrue(report["model"]["gguf_file_present"])
        self.assertEqual(report["model"]["selected_backend"], "llama_cpp")


if __name__ == "__main__":
    unittest.main()
