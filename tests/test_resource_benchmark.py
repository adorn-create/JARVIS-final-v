import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from resource_benchmark import _is_jarvis_process, _is_ollama_process


class ResourceBenchmarkTests(unittest.TestCase):
    def test_identifies_jarvis_main_process_without_exposing_command_line(self):
        self.assertTrue(_is_jarvis_process({
            "name": "python.exe",
            "exe": "D:\\AI\\JARVIS-v6\\.venv\\Scripts\\python.exe",
            "cmdline": ["python.exe", "D:\\AI\\JARVIS-v6\\src\\main.py"],
        }))

    def test_identifies_ollama_separately(self):
        self.assertTrue(_is_ollama_process({"name": "ollama.exe"}))
        self.assertFalse(_is_ollama_process({"name": "python.exe"}))


if __name__ == "__main__":
    unittest.main()
