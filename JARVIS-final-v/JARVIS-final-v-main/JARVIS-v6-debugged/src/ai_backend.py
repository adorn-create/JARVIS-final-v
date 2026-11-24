"""Resource-aware local GGUF inference with optional Ollama fallback.

The local model is a real pretrained language model loaded by llama-cpp-python.
JARVIS's intent classifier remains a separate lightweight router/learner.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

_lock = threading.RLock()
_model = None
_model_path = None


def _setting_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _provider() -> str:
    value = os.getenv("JARVIS_AI_PROVIDER", "auto").strip().lower()
    if value not in {"auto", "local", "ollama"}:
        raise ValueError("JARVIS_AI_PROVIDER must be auto, local, or ollama.")
    return value


def _local_path() -> Path:
    configured = os.getenv(
        "JARVIS_LOCAL_MODEL_PATH",
        "models/jarvis-qwen2.5-1.5b-instruct-q4_k_m.gguf",
    ).strip()
    if not configured:
        raise ValueError("JARVIS_LOCAL_MODEL_PATH cannot be empty.")
    path = Path(configured).expanduser()
    return path if path.is_absolute() else ROOT / path


def _load_local_model():
    global _model, _model_path
    path = _local_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Local GGUF model not found: {path}. Download a compatible GGUF "
            "and set JARVIS_LOCAL_MODEL_PATH in .env."
        )
    with _lock:
        if _model is not None and _model_path == path:
            return _model
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "The local AI runtime is not installed. Run "
                "'.venv\\Scripts\\python.exe -m pip install -r requirements-local-ai.txt'."
            ) from exc
        context = _setting_int("JARVIS_LOCAL_CONTEXT", 4096, 1024, 32768)
        threads = _setting_int("JARVIS_LOCAL_THREADS", 0, 0, 64)
        if threads == 0:
            threads = max(1, (os.cpu_count() or 2) - 1)
        gpu_layers = _setting_int("JARVIS_LOCAL_GPU_LAYERS", 0, 0, 999)
        _model = Llama(
            model_path=str(path),
            n_ctx=context,
            n_threads=threads,
            n_gpu_layers=gpu_layers,
            verbose=False,
        )
        _model_path = path
        return _model


def _local_chat(payload: dict) -> dict:
    model = _load_local_model()
    allowed = {
        "messages", "tools", "tool_choice", "temperature", "top_p",
        "max_tokens", "stop", "presence_penalty", "frequency_penalty",
        "seed", "response_format",
    }
    request = {key: value for key, value in payload.items() if key in allowed}
    # llama.cpp reads the model's embedded chat template, including Qwen tool syntax.
    result = model.create_chat_completion(**request)
    if not isinstance(result, dict) or not result.get("choices"):
        raise RuntimeError("Local model returned an invalid chat response.")
    return result


def _ollama_chat(payload: dict) -> dict:
    from ollama_client import chat_completion as ollama_completion
    return ollama_completion(payload)


def chat_completion(payload: dict) -> dict:
    """OpenAI-compatible chat interface; select local, Ollama, or fallback."""
    if not isinstance(payload, dict):
        raise TypeError("Chat payload must be a dictionary.")
    provider = _provider()
    fallback = os.getenv("JARVIS_OLLAMA_FALLBACK", "1").strip().lower() in {
        "1", "true", "yes", "on"
    }
    if provider == "ollama":
        return _ollama_chat(payload)
    if provider == "local":
        try:
            return _local_chat(payload)
        except Exception:
            if not fallback:
                raise
            return _ollama_chat(payload)
    if _local_path().is_file():
        try:
            return _local_chat(payload)
        except Exception:
            if not fallback:
                raise
            return _ollama_chat(payload)
    return _ollama_chat(payload)


def provider_status() -> dict:
    """Return local readiness without loading the model into RAM."""
    path = _local_path()
    try:
        import importlib.util
        runtime_installed = importlib.util.find_spec("llama_cpp") is not None
    except (ImportError, ValueError):
        runtime_installed = False
    return {
        "configured_provider": _provider(),
        "local_model_path": str(path),
        "local_model_present": path.is_file(),
        "local_runtime_installed": runtime_installed,
        "ollama_fallback": os.getenv("JARVIS_OLLAMA_FALLBACK", "1"),
    }
