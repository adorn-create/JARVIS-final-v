"""Measure JARVIS and Ollama memory while the user runs the app.

This is a passive sampler. It does not start, stop, or modify any process.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import psutil


def _is_jarvis_process(info: dict) -> bool:
    name = str(info.get("name") or "").casefold()
    exe = str(info.get("exe") or "").casefold().replace("/", "\\")
    cmdline = " ".join(str(part) for part in (info.get("cmdline") or [])).casefold().replace("/", "\\")
    if name in {"jarvis.exe", "jarvis"}:
        return True
    return "main.py" in cmdline and "src\\" in cmdline or "\\jarvis" in exe


def _is_ollama_process(info: dict) -> bool:
    name = str(info.get("name") or "").casefold()
    return name in {"ollama.exe", "ollama app.exe", "ollama"}


def sample_once():
    jarvis = []
    ollama = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "memory_info"]):
        try:
            info = proc.info
            memory = info.get("memory_info")
            if not memory:
                continue
            item = {
                "pid": info.get("pid"),
                "name": info.get("name"),
                "rss_mb": round(memory.rss / (1024 * 1024), 1),
            }
            if _is_jarvis_process(info):
                jarvis.append(item)
            elif _is_ollama_process(info):
                ollama.append(item)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    system = psutil.virtual_memory()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "jarvis_processes": jarvis,
        "jarvis_rss_mb": round(sum(item["rss_mb"] for item in jarvis), 1),
        "ollama_processes": ollama,
        "ollama_rss_mb": round(sum(item["rss_mb"] for item in ollama), 1),
        "system_ram_used_percent": system.percent,
        "system_ram_available_mb": round(system.available / (1024 * 1024), 1),
    }


def run_benchmark(duration_seconds=60, interval_seconds=1):
    duration = max(5, min(int(duration_seconds), 600))
    interval = max(0.5, min(float(interval_seconds), 10))
    samples = []
    deadline = time.monotonic() + duration
    while True:
        samples.append(sample_once())
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
    return {
        "ok": True,
        "duration_seconds": duration,
        "sample_count": len(samples),
        "jarvis_peak_rss_mb": max((item["jarvis_rss_mb"] for item in samples), default=0),
        "ollama_peak_rss_mb": max((item["ollama_rss_mb"] for item in samples), default=0),
        "combined_peak_rss_mb": max((item["jarvis_rss_mb"] + item["ollama_rss_mb"] for item in samples), default=0),
        "samples": samples,
        "interpretation": "JARVIS RSS includes an in-process GGUF model. With Ollama, model memory is reported separately. Run while exercising idle, voice, face, gestures, vision, and chat. This does not claim a 2 GB limit.",
    }


def main():
    parser = argparse.ArgumentParser(description="Passively measure JARVIS/Ollama RAM use")
    parser.add_argument("--duration", type=int, default=60, help="sample duration in seconds (5-600)")
    parser.add_argument("--interval", type=float, default=1, help="sample interval in seconds (0.5-10)")
    parser.add_argument("--json", action="store_true", help="print full JSON samples")
    args = parser.parse_args()
    result = run_benchmark(args.duration, args.interval)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("JARVIS RESOURCE BENCHMARK • PASSIVE SAMPLING")
        print(f"Samples: {result['sample_count']} over {result['duration_seconds']} seconds")
        print(f"JARVIS peak RSS: {result['jarvis_peak_rss_mb']} MB")
        print(f"Ollama peak RSS: {result['ollama_peak_rss_mb']} MB")
        print(f"Combined peak RSS: {result['combined_peak_rss_mb']} MB")
        print(result["interpretation"])
        print("Run again while testing voice, face, gestures, screen analysis and chat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
