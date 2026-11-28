"""Read-only local Windows threat triage helpers.

These checks produce investigation leads, not malware verdicts. They do not
execute, modify, quarantine, delete, or upload inspected files.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time

MAX_FILE_BYTES = 512 * 1024 * 1024
RISKY_SUFFIXES = {
    ".exe", ".dll", ".scr", ".com", ".bat", ".cmd", ".ps1",
    ".vbs", ".vbe", ".js", ".jse", ".hta", ".msi", ".msp",
    ".lnk", ".iso", ".img", ".reg",
}
USER_WRITABLE_MARKERS = (
    "\\appdata\\local\\temp\\",
    "\\windows\\temp\\",
    "\\downloads\\",
    "\\desktop\\",
)


def _file_signature(path: Path) -> dict:
    if os.name != "nt":
        return {"status": "not_checked", "reason": "Authenticode check requires Windows"}
    import subprocess

    script = (
        "$s = Get-AuthenticodeSignature -LiteralPath $env:JARVIS_TRIAGE_PATH; "
        "[pscustomobject]@{Status=[string]$s.Status; "
        "StatusMessage=[string]$s.StatusMessage; "
        "Signer=$(if($s.SignerCertificate){$s.SignerCertificate.Subject}else{$null})} "
        "| ConvertTo-Json -Compress"
    )
    env = os.environ.copy()
    env["JARVIS_TRIAGE_PATH"] = str(path)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=12, check=False, env=env,
        )
        if result.returncode != 0:
            return {"status": "check_failed", "reason": result.stderr.strip()[:240]}
        import json
        data = json.loads(result.stdout)
        return {
            "status": str(data.get("Status", "Unknown")),
            "message": str(data.get("StatusMessage", ""))[:240],
            "signer": data.get("Signer"),
        }
    except Exception as exc:
        return {"status": "check_failed", "reason": str(exc)[:240]}


def triage_file(file_path: str) -> dict:
    """Hash and inspect metadata/signature of one user-selected local file."""
    raw = str(file_path or "").strip()
    if not raw or len(raw) > 2048:
        raise ValueError("Provide a local file path of 1 to 2048 characters.")
    path = Path(raw).expanduser()
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"File could not be resolved: {exc}") from exc
    if not path.is_file():
        raise ValueError("The selected path is not a regular file.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File triage is limited to 512 MB.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    with path.open("rb") as stream:
        header = stream.read(16)
    suffix = path.suffix.casefold()
    lower_path = str(path).casefold().replace("/", "\\")
    indicators = []
    score = 0
    if suffix in RISKY_SUFFIXES:
        indicators.append({"kind": "executable_or_script_type", "detail": f"File type {suffix} can contain executable code."})
        score += 1
    if any(lower_path.find(marker) >= 0 for marker in USER_WRITABLE_MARKERS):
        indicators.append({"kind": "user_writable_location", "detail": "File is in a commonly user-writable location."})
        score += 1
    if suffix in {".exe", ".dll", ".scr", ".com"} and header[:2] != b"MZ":
        indicators.append({"kind": "extension_header_mismatch", "detail": "Executable extension does not have a normal MZ header."})
        score += 2
    if suffix in {".bat", ".cmd", ".ps1", ".vbs", ".js", ".hta"}:
        indicators.append({"kind": "script_file", "detail": "Script files can run commands; inspect contents before opening."})
    zone_path = Path(str(path) + ":Zone.Identifier") if os.name == "nt" else None
    zone_present = bool(zone_path and zone_path.exists())
    signature = _file_signature(path)
    if signature.get("status") == "NotSigned":
        indicators.append({"kind": "unsigned_file", "detail": "No Authenticode signature was found; many legitimate files are unsigned."})
        score += 1
    elif signature.get("status") not in {"Valid", "NotSigned", "not_checked"}:
        indicators.append({"kind": "signature_not_valid", "detail": f"Authenticode status: {signature.get('status')}."})
        score += 2
    if zone_present:
        indicators.append({"kind": "download_zone_metadata", "detail": "Windows marks this file as originating from another zone."})
    return {
        "ok": True,
        "mode": "read-only static triage",
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "modified_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime)),
        "sha256": digest.hexdigest(),
        "extension": suffix,
        "header_hex": header.hex(),
        "authenticode": signature,
        "download_zone_present": zone_present,
        "heuristic_score": score,
        "indicators": indicators,
        "verdict": "needs_review" if indicators else "no_static_indicator_found",
        "limitations": "Not an antivirus scan or proof of safety. File was not executed, uploaded, modified, or quarantined.",
    }


def scan_with_windows_defender(file_path: str, timeout: int = 300) -> dict:
    """Run a user-approved Microsoft Defender custom scan on one local file.

    Defender's configured remediation policy may quarantine or remove a detected
    threat. This function never disables Defender or changes its policy.
    """
    import subprocess

    if os.name != "nt":
        return {"ok": False, "error": "Microsoft Defender custom file scans require Windows."}
    raw = str(file_path or "").strip()
    if not raw or len(raw) > 2048:
        raise ValueError("Provide a local file path of 1 to 2048 characters.")
    try:
        path = Path(raw).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"File could not be resolved: {exc}") from exc
    if not path.is_file():
        raise ValueError("The selected path is not a regular file.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Defender single-file scan is limited to 512 MB.")
    script = (
        "$ErrorActionPreference='Stop'; "
        "Import-Module Defender -ErrorAction Stop; "
        "Start-MpScan -ScanType CustomScan -ScanPath $env:JARVIS_DEFENDER_SCAN_PATH; "
        "'DEFENDER_SCAN_COMMAND_COMPLETED'"
    )
    env = os.environ.copy()
    env["JARVIS_DEFENDER_SCAN_PATH"] = str(path)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True,
            timeout=max(30, min(int(timeout), 600)),
            check=False, env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False, "timed_out": True, "path": str(path),
            "error": "Microsoft Defender scan exceeded the time limit. Check Windows Security Protection History.",
        }
    except OSError as exc:
        return {"ok": False, "error": f"Could not start Microsoft Defender scan: {exc}"}
    if result.returncode != 0:
        return {
            "ok": False, "path": str(path),
            "error": "Microsoft Defender scan command failed. Check Defender availability and permissions.",
            "details": result.stderr.strip()[:500],
        }
    return {
        "ok": True, "path": str(path),
        "engine": "Microsoft Defender",
        "command_completed": "DEFENDER_SCAN_COMMAND_COMPLETED" in result.stdout,
        "stdout": result.stdout.strip()[-1200:],
        "next_step": "Review Windows Security > Virus & threat protection > Protection history for detections and remediation.",
        "side_effect_notice": "Microsoft Defender's existing policy may quarantine or remove a detected file. JARVIS does not change that policy.",
    }


def process_snapshot(limit: int = 100) -> dict:
    """Summarize running processes using path-based heuristics only."""
    import psutil

    limit = max(1, min(int(limit), 200))
    observations = []
    for proc in psutil.process_iter(["pid", "name", "exe", "memory_info"]):
        try:
            info = proc.info
            executable = info.get("exe") or ""
            normalized = executable.casefold().replace("/", "\\")
            indicators = []
            if executable and any(marker in normalized for marker in USER_WRITABLE_MARKERS):
                indicators.append("process_image_in_user_writable_location")
            if executable and Path(executable).suffix.casefold() in {".ps1", ".vbs", ".js", ".bat", ".cmd"}:
                indicators.append("script_host_or_script_path")
            if indicators:
                memory = info.get("memory_info")
                observations.append({
                    "pid": info.get("pid"),
                    "name": info.get("name"),
                    "image_path": executable[:500],
                    "memory_mb": round(memory.rss / (1024 * 1024), 1) if memory else None,
                    "indicators": indicators,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    observations.sort(key=lambda item: len(item["indicators"]), reverse=True)
    return {
        "ok": True,
        "mode": "read-only process snapshot",
        "processes_examined": "current accessible process list",
        "observations": observations[:limit],
        "limitations": "Path heuristics only. No process is classified as malware, terminated, suspended, or modified.",
    }
