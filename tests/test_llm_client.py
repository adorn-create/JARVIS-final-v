import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm_client


class LLMRouterTests(unittest.TestCase):
    def test_auto_uses_ollama_when_no_gguf_is_configured(self):
        with patch.dict(os.environ, {"JARVIS_LLM_BACKEND": "auto"}, clear=True):
            self.assertEqual(llm_client._backend(), "ollama")

    def test_auto_uses_gguf_when_model_file_exists(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf") as model:
            with patch.dict(os.environ, {
                "JARVIS_LLM_BACKEND": "auto",
                "JARVIS_GGUF_MODEL": model.name,
            }, clear=True):
                self.assertEqual(llm_client._backend(), "llama_cpp")

    def test_explicit_gguf_backend_fails_clearly_for_missing_file(self):
        with patch.dict(os.environ, {
            "JARVIS_LLM_BACKEND": "llama_cpp",
            "JARVIS_GGUF_MODEL": "missing-model.gguf",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "existing JARVIS GGUF"):
                llm_client._backend()

    def test_invalid_backend_is_rejected(self):
        with patch.dict(os.environ, {"JARVIS_LLM_BACKEND": "remote"}, clear=True):
            with self.assertRaisesRegex(ValueError, "must be auto"):
                llm_client._backend()

    def test_ollama_backend_is_delegated_without_loading_llama_cpp(self):
        fake = types.ModuleType("ollama_client")
        fake.chat_completion = lambda payload: {"choices": [{"message": {"content": "ok"}}]}
        with patch.dict(os.environ, {"JARVIS_LLM_BACKEND": "ollama"}, clear=True):
            with patch.dict(sys.modules, {"ollama_client": fake}):
                result = llm_client.chat_completion({"messages": []})
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")


if __name__ == "__main__":
    unittest.main()
