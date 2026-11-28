"""Low-overhead, local PC awareness. No screenshots, keystrokes, audio, or camera access."""
import threading
import time

import psutil


class AwarenessMonitor:
    """Poll basic system/process telemetry and report meaningful changes."""

    def __init__(self, on_event=None, interval=None):
        import os
        self.on_event = on_event or (lambda _event: None)
        try:
            self.interval = max(3, int(interval or os.getenv("JARVIS_AWARENESS_INTERVAL", "8")))
        except (TypeError, ValueError):
            self.interval = 8
        self._stop = threading.Event()
        self._thread = None
        self._known = set()
        self._last_alert = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="JARVIS-Awareness", daemon=True)
        self._thread.start()
        self.on_event({"type": "status", "message": "PC AWARENESS ACTIVE • LOCAL TELEMETRY ONLY"})

    def stop(self, wait=True, timeout=4):
        self._stop.set()
        if wait and self._thread:
            self._thread.join(timeout)
        return not self._thread or not self._thread.is_alive()

    def _emit_limited(self, key, message, cooldown=60):
        now = time.monotonic()
        if now - self._last_alert.get(key, 0) >= cooldown:
            self._last_alert[key] = now
            self.on_event({"type": "alert", "message": message})

    def _run(self):
        psutil.cpu_percent(interval=None)
        while not self._stop.wait(self.interval):
            try:
                cpu = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                if cpu >= 92:
                    self._emit_limited("cpu", f"High CPU usage detected: {cpu:.0f}%")
                if memory.percent >= 92:
                    self._emit_limited("memory", f"High memory usage detected: {memory.percent:.0f}%")
                current = set()
                for proc in psutil.process_iter(["pid", "name", "exe"]):
                    try:
                        info = proc.info
                        name = (info.get("name") or "unknown").strip()
                        executable = (info.get("exe") or "").casefold().replace("/", "\\")
                        current.add((info.get("pid"), name, executable))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                if self._known:
                    started = current - self._known
                    # Process paths are weak indicators, not malware verdicts.
                    for pid, name, executable in list(started)[:5]:
                        self.on_event({"type": "process", "message": f"New process observed: {name} (PID {pid})"})
                        if any(marker in executable for marker in (
                            "\\appdata\\local\\temp\\",
                            "\\windows\\temp\\",
                            "\\downloads\\",
                        )):
                            self._emit_limited(
                                f"user-writable-process-{pid}",
                                f"MORPHEUS REVIEW: {name} (PID {pid}) launched from a user-writable folder. This is not a malware verdict; inspect its file and signature.",
                                cooldown=300,
                            )
                self._known = current
            except Exception as exc:
                self._emit_limited("monitor", f"PC awareness check failed: {exc}", cooldown=120)
