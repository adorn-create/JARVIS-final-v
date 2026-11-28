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

    def test_cpu_model_uses_conservative_resource_defaults(self):
        captured = {}

        class FakeLlama:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def create_chat_completion(self, **kwargs):
                captured["request"] = kwargs
                return {"choices": [{"message": {"content": "local"}}]}

        fake = types.ModuleType("llama_cpp")
        fake.Llama = FakeLlama
        with tempfile.NamedTemporaryFile(suffix=".gguf") as model:
            with patch.dict(os.environ, {
                "JARVIS_LLM_BACKEND": "llama_cpp",
                "JARVIS_GGUF_MODEL": model.name,
            }, clear=True):
                with patch.dict(sys.modules, {"llama_cpp": fake}):
                    with patch.object(llm_client, "_LOCAL", None), patch.object(llm_client, "_LOCAL_PATH", None):
                        result = llm_client.chat_completion({"messages": [{"role": "user", "content": "hi"}]})

        self.assertEqual(result["choices"][0]["message"]["content"], "local")
        self.assertEqual(captured["n_ctx"], 3072)
        self.assertEqual(captured["n_threads"], 4)
        self.assertEqual(captured["n_batch"], 256)
        self.assertEqual(captured["n_gpu_layers"], 0)
        self.assertEqual(captured["request"]["max_tokens"], 768)

    def test_ollama_backend_is_delegated_without_loading_llama_cpp(self):
        fake = types.ModuleType("ollama_client")
        fake.chat_completion = lambda payload: {"choices": [{"message": {"content": "ok"}}]}
        with patch.dict(os.environ, {"JARVIS_LLM_BACKEND": "ollama"}, clear=True):
            with patch.dict(sys.modules, {"ollama_client": fake}):
                result = llm_client.chat_completion({"messages": []})
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")


if __name__ == "__main__":
    unittest.main()
