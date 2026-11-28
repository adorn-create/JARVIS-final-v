"""Safe local ADB bridge for owner-authorized Android devices.

Only lists ADB devices, wakes displays, and launches an explicit package allowlist.
It never enters PINs, bypasses Android lock screens, reads private device data,
or executes arbitrary shell commands.
"""
import concurrent.futures
import ipaddress
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

LOG = logging.getLogger("jarvis.android")

APP_PACKAGES = {
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "maps": "com.google.android.apps.maps",
    "whatsapp": "com.whatsapp",
    "spotify": "com.spotify.music",
    "gmail": "com.google.android.gm",
    "settings": "com.android.settings",
    "camera": "com.android.camera2",
    "photos": "com.google.android.apps.photos",
}
SERIAL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
HOSTPORT_RE = re.compile(r"^(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]{1,253}):[0-9]{1,5}$")


def _adb_path():
    configured = os.environ.get("JARVIS_ADB_PATH", "").strip().strip('"')
    candidates = [
        configured,
        shutil.which("adb"),
        str(Path(__file__).resolve().parent.parent / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")),
        str(Path(__file__).resolve().parent.parent / "tools" / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError(
        "ADB was not found. Install Android Platform Tools and add adb to PATH, "
        "or set JARVIS_ADB_PATH to the adb executable."
    )


def _run(args, timeout=12):
    command = [_adb_path(), *[str(item) for item in args]]
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout,
        check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "ADB command failed").strip()
        raise RuntimeError(detail[:500])
    return completed.stdout.strip()


def list_android_devices():
    """Read-only list of connected, unauthorized, and offline ADB devices."""
    output = _run(["devices", "-l"])
    devices = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if not SERIAL_RE.fullmatch(serial):
            continue
        details = {}
        for token in parts[2:]:
            if ":" in token:
                key, value = token.split(":", 1)
                if key in {"model", "product", "device", "transport_id"}:
                    details[key] = value
        devices.append({"serial": serial, "state": state, **details})
    return {
        "ok": True,
        "devices": devices,
        "ready_count": sum(item["state"] == "device" for item in devices),
        "note": "Only devices in the 'device' state are controllable. Approve this PC's debugging key on each phone.",
    }


def _validated_targets(serials):
    listed = list_android_devices()["devices"]
    ready = {item["serial"] for item in listed if item["state"] == "device"}
    if not isinstance(serials, list) or not serials or len(serials) > 16:
        raise ValueError("Choose between 1 and 16 device serials from the current device list.")
    chosen = []
    for serial in serials:
        serial = str(serial).strip()
        if not SERIAL_RE.fullmatch(serial) or serial not in ready:
            raise ValueError(f"Device '{serial[:80]}' is not currently authorized and connected.")
        if serial not in chosen:
            chosen.append(serial)
    return chosen


def _per_device(serial, args, timeout=12):
    return _run(["-s", serial, *args], timeout=timeout)


def wake_android_displays(serials):
    """Wake screens only. Does not dismiss keyguard or unlock devices."""
    targets = _validated_targets(serials)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
        futures = {pool.submit(_per_device, serial, ["shell", "input", "keyevent", "224"]): serial for serial in targets}
        for future in concurrent.futures.as_completed(futures):
            serial = futures[future]
            try:
                future.result(timeout=15)
                results.append({"serial": serial, "ok": True, "action": "display_woken"})
            except Exception as exc:
                results.append({"serial": serial, "ok": False, "error": str(exc)[:300]})
    return {"ok": all(item["ok"] for item in results), "results": sorted(results, key=lambda x: targets.index(x["serial"])),
            "note": "The Android lock screen remains in place; JARVIS does not unlock phones or enter PINs."}


def launch_android_app(serials, app):
    """Launch one allowlisted app on selected already-authorized Android devices."""
    app = str(app).strip().lower()
    package = APP_PACKAGES.get(app)
    if not package:
        return {"ok": False, "error": "App is not allowlisted.", "allowed_apps": sorted(APP_PACKAGES)}
    targets = _validated_targets(serials)
    results = []
    args = ["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
        futures = {pool.submit(_per_device, serial, args, 15): serial for serial in targets}
        for future in concurrent.futures.as_completed(futures):
            serial = futures[future]
            try:
                output = future.result(timeout=18)
                results.append({"serial": serial, "ok": True, "package": package, "output": output[-200:]})
            except Exception as exc:
                results.append({"serial": serial, "ok": False, "error": str(exc)[:300]})
    results.sort(key=lambda item: targets.index(item["serial"]))
    return {"ok": all(item["ok"] for item in results), "app": app, "package": package, "results": results,
            "note": "Apps are launched only on selected, currently authorized ADB devices. A locked phone may require its owner to unlock it first."}


def pair_wireless_android_device(address, pairing_code):
    """Pair with an Android Wireless Debugging pairing endpoint using a one-time code."""
    address = str(address).strip()
    code = str(pairing_code).strip()
    if not HOSTPORT_RE.fullmatch(address):
        raise ValueError("Address must be an Android Wireless Debugging pairing address in host:port form.")
    host_port = int(address.rsplit(":", 1)[1])
    if not 1 <= host_port <= 65535:
        raise ValueError("Pairing port must be between 1 and 65535.")
    if not re.fullmatch(r"[0-9]{6}", code):
        raise ValueError("Enter the six-digit pairing code shown by Android Wireless Debugging.")
    # Pairing code is used only for this call and is never logged or persisted by JARVIS.
    host = address.rsplit(":", 1)[0].strip("[]")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Use the phone private LAN IP shown in Wireless Debugging.") from exc
    if not ip.is_private or ip.is_loopback or ip.is_unspecified:
        raise ValueError("Wireless pairing is limited to a private LAN address.")
    output = _run(["pair", address, code], timeout=30)
    return {"ok": "successfully paired" in output.lower(), "output": output[:300],
            "note": "Pairing establishes ADB trust; use the phone's separate connect endpoint if Android reports one."}


def connect_wireless_android_device(address):
    """Connect to the separate ADB endpoint shown on Android Wireless Debugging."""
    address = str(address).strip()
    if not HOSTPORT_RE.fullmatch(address):
        raise ValueError("Address must be the Android Wireless Debugging connect endpoint in host:port form.")
    host = address.rsplit(":", 1)[0].strip("[]")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Use the phone's private LAN IP address shown in Wireless Debugging.") from exc
    if not ip.is_private or ip.is_loopback or ip.is_unspecified:
        raise ValueError("Wireless ADB connection is limited to a private LAN address.")
    port = int(address.rsplit(":", 1)[1])
    if not 1 <= port <= 65535:
        raise ValueError("Connect port must be between 1 and 65535.")
    output = _run(["connect", address], timeout=20)
    ok = "connected to" in output.lower() or "already connected" in output.lower()
    return {"ok": ok, "output": output[:300],
            "note": "The device must still be authorized in Android Wireless Debugging. Use android_list_devices to verify its state."}
