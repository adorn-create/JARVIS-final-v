import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_backend


class BackendSelectionTests(unittest.TestCase):
    def test_auto_uses_ollama_when_local_model_missing(self):
        with patch.dict(os.environ, {"JARVIS_AI_PROVIDER": "auto"}):
            with patch.object(ai_backend, "_local_path", return_value=Path("/missing/model.gguf")):
                with patch.object(ai_backend, "_ollama_chat", return_value={"source": "ollama"}) as ollama:
                    self.assertEqual(ai_backend.chat_completion({"messages": []}), {"source": "ollama"})
                    ollama.assert_called_once()

    def test_auto_prefers_local_model_when_present(self):
        with tempfile.NamedTemporaryFile() as model_file:
            with patch.dict(os.environ, {"JARVIS_AI_PROVIDER": "auto"}):
                with patch.object(ai_backend, "_local_path", return_value=Path(model_file.name)):
                    with patch.object(ai_backend, "_local_chat", return_value={"source": "local"}) as local:
                        with patch.object(ai_backend, "_ollama_chat") as ollama:
                            self.assertEqual(ai_backend.chat_completion({"messages": []}), {"source": "local"})
                            local.assert_called_once()
                            ollama.assert_not_called()

    def test_local_error_falls_back_when_enabled(self):
        with patch.dict(os.environ, {"JARVIS_AI_PROVIDER": "local", "JARVIS_OLLAMA_FALLBACK": "1"}):
            with patch.object(ai_backend, "_local_chat", side_effect=RuntimeError("load failed")):
                with patch.object(ai_backend, "_ollama_chat", return_value={"source": "ollama"}):
                    self.assertEqual(ai_backend.chat_completion({"messages": []}), {"source": "ollama"})

    def test_local_error_surfaces_when_fallback_disabled(self):
        with patch.dict(os.environ, {"JARVIS_AI_PROVIDER": "local", "JARVIS_OLLAMA_FALLBACK": "0"}):
            with patch.object(ai_backend, "_local_chat", side_effect=RuntimeError("load failed")):
                with self.assertRaisesRegex(RuntimeError, "load failed"):
                    ai_backend.chat_completion({"messages": []})


if __name__ == "__main__":
    unittest.main()
