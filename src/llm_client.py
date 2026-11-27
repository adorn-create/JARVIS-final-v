"""JARVIS local language-model router.

Preferred backend: in-process GGUF inference through llama-cpp-python.
Ollama is retained only as an optional compatibility fallback.
"""
import os
from pathlib import Path

_LOCAL = None
_LOCAL_PATH = None


def _backend():
    requested = os.getenv("JARVIS_LLM_BACKEND", "auto").strip().lower()
    if requested not in {"auto", "llama_cpp", "ollama"}:
        raise ValueError("JARVIS_LLM_BACKEND must be auto, llama_cpp, or ollama.")
    path = os.getenv("JARVIS_GGUF_MODEL", "").strip()
    exists = bool(path and Path(path).expanduser().is_file())
    if requested == "auto":
        return "llama_cpp" if exists else "ollama"
    if requested == "llama_cpp" and not exists:
        raise RuntimeError("JARVIS_GGUF_MODEL must point to an existing JARVIS GGUF model file.")
    return requested


def _local_model():
    global _LOCAL, _LOCAL_PATH
    path = str(Path(os.environ["JARVIS_GGUF_MODEL"]).expanduser().resolve())
    if _LOCAL is not None and _LOCAL_PATH == path:
        return _LOCAL
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise RuntimeError("Install the optional direct runtime with: pip install -r requirements-llm.txt") from exc
    try:
        n_ctx = int(os.getenv("JARVIS_CONTEXT_LENGTH", "4096"))
        n_threads = int(os.getenv("JARVIS_CPU_THREADS", str(max(1, (os.cpu_count() or 4) - 1))))
        n_gpu_layers = int(os.getenv("JARVIS_GPU_LAYERS", "0"))
    except ValueError as exc:
        raise ValueError("JARVIS model resource settings must be integers.") from exc
    if not 512 <= n_ctx <= 32768 or not 1 <= n_threads <= 256 or not 0 <= n_gpu_layers <= 999:
        raise ValueError("Invalid JARVIS model resource settings.")
    _LOCAL = Llama(model_path=path, n_ctx=n_ctx, n_threads=n_threads, n_gpu_layers=n_gpu_layers, verbose=False)
    _LOCAL_PATH = path
    return _LOCAL


def chat_completion(payload):
    if _backend() == "ollama":
        from ollama_client import chat_completion as ollama_chat
        return ollama_chat(payload)
    kwargs = {
        "messages": payload.get("messages", []),
        "temperature": payload.get("temperature", 0.35),
        "max_tokens": int(os.getenv("JARVIS_MAX_TOKENS", "1024")),
    }
    if payload.get("tools"):
        kwargs["tools"] = payload["tools"]
        kwargs["tool_choice"] = payload.get("tool_choice", "auto")
    try:
        return _local_model().create_chat_completion(**kwargs)
    except Exception as exc:
        raise RuntimeError("JARVIS local inference failed. Verify the GGUF chat template and tool-calling support. " + str(exc)) from exc
