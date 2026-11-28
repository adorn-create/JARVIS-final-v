"""Windows-native, conservative security assessment helpers for JARVIS.

All network assessment is limited to one explicitly supplied private/loopback IPv4
address and a small allowlist of TCP ports. No exploit payloads are sent.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import PurePosixPath

PORT_LABELS = {
    22: "SSH",
    53: "DNS",
    80: "HTTP",
    135: "MS RPC",
    139: "NetBIOS",
    443: "HTTPS",
    445: "SMB",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5985: "WinRM HTTP",
    5986: "WinRM HTTPS",
    8000: "HTTP alternate",
    8080: "HTTP proxy/alternate",
    8443: "HTTPS alternate",
    8888: "HTTP alternate",
}
DEFAULT_PORTS = (22, 80, 135, 139, 443, 445, 3389, 5985, 5986, 8080, 8443)


def _private_ipv4(value: str) -> ipaddress.IPv4Address:
    raw = str(value).strip()
    try:
        address = ipaddress.ip_address(raw)
    except ValueError as exc:
        raise ValueError("Target must be one literal IPv4 address; hostnames and CIDRs are not accepted.") from exc
    if not isinstance(address, ipaddress.IPv4Address):
        raise ValueError("Only IPv4 targets are supported in this first Windows-native release.")
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError("Only private, loopback, or link-local IPv4 targets are allowed.")
    if address.is_multicast or address.is_unspecified or address.is_reserved:
        raise ValueError("This target address range is not allowed.")
    return address


def normalize_ports(ports=None) -> list[int]:
    if ports is None:
        return list(DEFAULT_PORTS)
    if not isinstance(ports, (list, tuple)) or not ports:
        raise ValueError("Provide a non-empty list of allowed TCP ports.")
    if len(ports) > 16:
        raise ValueError("A scan is limited to 16 ports per request.")
    normalized = []
    for item in ports:
        if isinstance(item, bool):
            raise ValueError("Ports must be integers.")
        try:
            port = int(item)
        except (TypeError, ValueError) as exc:
            raise ValueError("Ports must be integers.") from exc
        if port not in PORT_LABELS:
            raise ValueError(f"Port {port} is not in JARVIS's conservative scan allowlist.")
        if port not in normalized:
            normalized.append(port)
    return normalized


def audit_windows_security() -> dict:
    """Read Defender and Windows Firewall posture; never changes settings."""
    import os

    if os.name != "nt":
        return {"ok": False, "error": "Windows security posture checks require Windows."}
    script = (
        "$d = Get-MpComputerStatus | Select-Object AMServiceEnabled,AntivirusEnabled,"
        "RealTimeProtectionEnabled,BehaviorMonitorEnabled,IoavProtectionEnabled,"
        "AntivirusSignatureLastUpdated;"
        "$f = Get-NetFirewallProfile | Select-Object Name,Enabled,"
        "DefaultInboundAction,DefaultOutboundAction;"
        "[pscustomobject]@{ Defender=$d; Firewall=$f } | ConvertTo-Json -Depth 4"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"Could not query Windows security status: {exc}"}
    if result.returncode != 0:
        return {
            "ok": False,
            "error": "Windows security query failed. Check Defender/PowerShell availability.",
            "details": result.stderr.strip()[:500],
        }
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "Windows returned an unreadable security-status response."}
    return {"ok": True, "read_only": True, "platform": "Windows", "status": data}


def scan_private_host(target: str, ports=None, timeout: float = 0.35) -> dict:
    """Perform connect-only checks against one private IPv4 host; sends no payload."""
    address = _private_ipv4(target)
    selected = normalize_ports(ports)
    timeout = max(0.15, min(float(timeout), 0.8))
    results = []
    for port in selected:
        started = time.monotonic()
        state = "closed_or_filtered"
        try:
            with socket.create_connection((str(address), port), timeout=timeout):
                state = "open"
        except (OSError, TimeoutError):
            pass
        results.append({
            "port": port,
            "service_hint": PORT_LABELS[port],
            "state": state,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        })
        time.sleep(0.025)
    return {
        "ok": True,
        "target": str(address),
        "scope": "single private/loopback IPv4 address",
        "method": "TCP connect-only; no banner grab or exploit payload",
        "ports_checked": len(selected),
        "results": results,
    }


def check_local_web_headers(url: str) -> dict:
    """Inspect response headers on a local/private HTTP(S) lab endpoint only."""
    parsed = urllib.parse.urlsplit(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Use a complete http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not accepted.")
    host = parsed.hostname.casefold()
    if host != "localhost":
        _private_ipv4(host)
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid destination port.")
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "JARVIS-Security-Audit/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            headers = {key.casefold(): value for key, value in response.headers.items()}
            status = getattr(response, "status", None)
    except Exception as exc:
        return {"ok": False, "url": url[:300], "error": f"Header check failed: {exc}"}
    expected = (
        "content-security-policy",
        "strict-transport-security",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "permissions-policy",
    )
    return {
        "ok": True,
        "url": url[:300],
        "http_status": status,
        "checks": [
            {"header": name, "present": name in headers, "value": headers.get(name, "")[:240]}
            for name in expected
        ],
        "note": "Header presence is a basic signal, not a complete web security assessment.",
    }


def run_safe_lab_demo(name: str) -> dict:
    """Demonstrate path traversal in memory, then show the fixed containment check."""
    import posixpath

    if name != "path_traversal_guard":
        raise ValueError("Available lab demo: path_traversal_guard.")
    root = "/jarvis-lab/safe-data"
    samples = ("report.txt", "../outside.txt", "images/../../outside.txt", "/etc/passwd")
    checks = []
    for sample in samples:
        naive_result = posixpath.normpath(posixpath.join(root, sample.replace("\\", "/")))
        naive_escaped = not (
            naive_result == root or naive_result.startswith(root.rstrip("/") + "/")
        )
        path = PurePosixPath(sample.replace("\\", "/"))
        blocked = path.is_absolute() or ".." in path.parts
        checks.append({
            "input": sample,
            "vulnerable_demo": "ESCAPES LAB ROOT" if naive_escaped else "STAYS IN LAB ROOT",
            "fixed_guard": "BLOCK" if blocked else "ALLOW",
        })
    return {
        "ok": True,
        "demo": name,
        "mode": "in-memory isolated simulation",
        "lab_root": root,
        "targets_touched": 0,
        "files_written": 0,
        "network_connections": 0,
        "checks": checks,
        "lesson": "The vulnerable join can escape the trusted directory; the fixed guard rejects absolute paths and parent-directory traversal before access.",
    }

def lookup_cves(keyword: str, limit: int = 5) -> dict:
    """Query public NVD CVE metadata by keyword; returns identifiers and severity only."""
    term = str(keyword).strip()
    if not term or len(term) > 100:
        raise ValueError("CVE search keyword must contain 1 to 100 characters.")
    limit = max(1, min(int(limit), 10))
    query = urllib.parse.urlencode({"keywordSearch": term, "resultsPerPage": limit})
    request = urllib.request.Request(
        "https://services.nvd.nist.gov/rest/json/cves/2.0?" + query,
        headers={"User-Agent": "JARVIS-Defensive-Security/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read(1_500_000).decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"NVD lookup failed: {exc}"}
    items = []
    for entry in payload.get("vulnerabilities", []):
        cve = entry.get("cve", {})
        descriptions = cve.get("descriptions", [])
        description = next(
            (item.get("value", "") for item in descriptions if item.get("lang") == "en"),
            "",
        )
        metrics = cve.get("metrics", {})
        score = None
        severity = None
        for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            metric_list = metrics.get(key) or []
            if metric_list:
                data = metric_list[0].get("cvssData", {})
                score = data.get("baseScore")
                severity = data.get("baseSeverity")
                break
        items.append({
            "cve_id": cve.get("id"),
            "published": cve.get("published"),
            "cvss_base_score": score,
            "severity": severity,
            "description": description[:500],
        })
    return {"ok": True, "source": "NIST NVD", "keyword": term, "results": items}
