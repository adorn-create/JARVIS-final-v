"""Lightweight JARVIS diagnostics; does not start models, cameras, or microphones."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def _available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def collect_report() -> dict:
    adb_env = os.getenv("JARVIS_ADB_PATH", "").strip()
    adb_env_path = Path(adb_env).expanduser() if adb_env else None
    adb_path = shutil.which("adb") or (str(adb_env_path) if adb_env_path and adb_env_path.is_file() else None)
    report = {
        "python": {
            "version": platform.python_version(),
            "supported": (3, 11) <= sys.version_info[:2] < (3, 13),
            "executable": sys.executable,
        },
        "dependencies": {
            "psutil": _available("psutil"),
            "requests": _available("requests"),
            "dotenv": _available("dotenv"),
            "Pillow": _available("PIL"),
            "Whisper": _available("faster_whisper"),
            "sounddevice": _available("sounddevice"),
            "pyttsx3": _available("pyttsx3"),
            "OpenCV": _available("cv2"),
            "MediaPipe": _available("mediapipe"),
            "llama_cpp": _available("llama_cpp"),
        },
        "devices": {
            "adb": adb_path,
        },
        "face_auth": {
            "profiles_file_present": False,
            "samples_file_present": False,
        },
        "model": {
            "requested_backend": os.getenv("JARVIS_LLM_BACKEND", "auto"),
            "gguf_file_present": False,
            "ollama_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            "note": "This check does not load a model or contact Ollama.",
        },
        "memory": {"process_rss_mb": None},
    }

    user_data_root = os.getenv("LOCALAPPDATA") or os.getenv("USERPROFILE") or os.getenv("HOME") or str(ROOT)
    local_data = Path(user_data_root) / "JARVIS" / "face_auth"
    report["face_auth"]["profiles_file_present"] = (local_data / "users.json").is_file()
    report["face_auth"]["samples_file_present"] = (local_data / "face_samples.npz").is_file()

    model_path = os.getenv("JARVIS_GGUF_MODEL", "").strip()
    if model_path:
        report["model"]["gguf_file_present"] = Path(model_path).expanduser().is_file()

    try:
        import psutil
        report["memory"]["process_rss_mb"] = round(
            psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1
        )
    except Exception as exc:
        report["memory"]["error"] = str(exc)

    try:
        from llm_client import _backend
        report["model"]["selected_backend"] = _backend()
    except Exception as exc:
        report["model"]["configuration_error"] = str(exc)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only JARVIS health and configuration check")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()
    report = collect_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("J.A.R.V.I.S. • READ-ONLY SYSTEM CHECK")
        print(f"Python: {report['python']['version']} ({'supported' if report['python']['supported'] else 'unsupported'})")
        print(f"Process memory: {report['memory']['process_rss_mb']} MB (doctor process only)")
        print(f"ADB: {report['devices']['adb'] or 'not found'}")
        print(f"Model backend: {report['model'].get('selected_backend', 'unavailable')}")
        if report["model"].get("configuration_error"):
            print(f"Model config: {report['model']['configuration_error']}")
        print("\nOptional dependencies:")
        for name, present in report["dependencies"].items():
            print(f"  {'OK' if present else '--'}  {name}")
        print("\nFace enrollment files:")
        for name, present in report["face_auth"].items():
            print(f"  {'present' if present else 'missing'}  {name}")
        print("\nNo model, camera, microphone, or network service was started.")
    return 0 if report["python"]["supported"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
