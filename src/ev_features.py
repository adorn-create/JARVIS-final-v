"""Lightweight, on-demand E.V.-inspired sensors and analysis for JARVIS.

No extra AI model is loaded. Camera/audio/sensor modules are imported only when
the corresponding tool is explicitly requested.
"""
import csv
import datetime as dt
import ipaddress
import json
import os
import socket
import statistics
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BIOMETRICS_FILE = DATA_DIR / "ev_biometrics.json"
MAX_ANALYSIS_BYTES = 2 * 1024 * 1024


def _resolve_project_data_path(relative_path, root=None):
    root = Path(root or ROOT).resolve()
    raw = Path(str(relative_path))
    if raw.is_absolute():
        raise ValueError("Use a project-relative path under data/ or logs/.")
    candidate = (root / raw).resolve()
    allowed = [(root / "data").resolve(), (root / "logs").resolve()]
    if not any(candidate == base or base in candidate.parents for base in allowed):
        raise ValueError("Data analysis is limited to files inside the project's data/ or logs/ folders.")
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("The selected project data file does not exist or is not a regular file.")
    if candidate.stat().st_size > MAX_ANALYSIS_BYTES:
        raise ValueError("File exceeds the 2 MB analysis limit.")
    if candidate.suffix.lower() not in {".csv", ".json", ".jsonl", ".log", ".txt"}:
        raise ValueError("Supported formats: CSV, JSON, JSONL, LOG, and TXT.")
    return candidate


def analyze_project_file(relative_path, root=None):
    path = _resolve_project_data_path(relative_path, root=root)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            columns = reader.fieldnames or []
        numeric = {}
        for column in columns:
            values = []
            for row in rows:
                try:
                    value = float(row.get(column, ""))
                    if value == value and abs(value) != float("inf"):
                        values.append(value)
                except (TypeError, ValueError):
                    pass
            if values:
                numeric[column] = {
                    "count": len(values),
                    "min": round(min(values), 3),
                    "max": round(max(values), 3),
                    "mean": round(statistics.fmean(values), 3),
                }
        return {"ok": True, "file": str(path.relative_to(Path(root or ROOT).resolve())),
                "format": "csv", "rows": len(rows), "columns": columns,
                "numeric_summary": numeric}
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            shape = {"top_level_keys": list(value)[:40], "key_count": len(value)}
        elif isinstance(value, list):
            shape = {"items": len(value), "first_item_type": type(value[0]).__name__ if value else None}
        else:
            shape = {"value_type": type(value).__name__}
        return {"ok": True, "file": str(path.relative_to(Path(root or ROOT).resolve())),
                "format": "json", **shape}
    if suffix == ".jsonl":
        count = 0
        keys = Counter()
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    item = json.loads(line)
                    count += 1
                    if isinstance(item, dict):
                        keys.update(item.keys())
        return {"ok": True, "file": str(path.relative_to(Path(root or ROOT).resolve())),
                "format": "jsonl", "records": count, "common_keys": keys.most_common(20)}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    levels = Counter()
    for line in lines:
        upper = line.upper()
        for level in ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"):
            if level in upper:
                levels[level] += 1
                break
    return {"ok": True, "file": str(path.relative_to(Path(root or ROOT).resolve())),
            "format": suffix.lstrip("."), "lines": len(lines),
            "log_level_counts": dict(levels)}


def read_biometrics(path=None, now=None, max_age_seconds=180):
    """Read a local wearable bridge JSON; never invent missing sensor values.

    Expected schema: {"timestamp":"ISO-8601 with timezone","heart_rate_bpm":72,
    "spo2_percent":98,"temperature_c":36.7,"source":"device name"}.
    """
    path = Path(path or BIOMETRICS_FILE)
    if not path.is_file():
        return {"ok": True, "available": False,
                "message": "No wearable bridge data found. Connect a compatible sensor bridge and write data/ev_biometrics.json."}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        stamp = dt.datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        current = now or dt.datetime.now(dt.timezone.utc)
        age = max(0.0, (current - stamp.astimezone(dt.timezone.utc)).total_seconds())
        if age > max_age_seconds:
            return {"ok": True, "available": False, "stale": True,
                    "age_seconds": round(age), "message": "Wearable data is stale; no current reading is available."}
        ranges = {
            "heart_rate_bpm": (25, 240),
            "spo2_percent": (50, 100),
            "temperature_c": (30, 43),
        }
        readings = {}
        for key, (low, high) in ranges.items():
            value = data.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f"{key} is outside the accepted data range")
            readings[key] = value
        return {"ok": True, "available": bool(readings), "age_seconds": round(age),
                "source": str(data.get("source", "unspecified"))[:80],
                "readings": readings,
                "notice": "Readings are informational, may be inaccurate, and are not medical advice."}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"ok": False, "available": False, "error": f"Invalid wearable bridge data: {exc}"}


def track_camera_motion(duration_seconds=4, camera_index=0):
    """Short, on-demand motion tracking; frames are not saved."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Camera tracking requires the optional OpenCV package.") from exc
    duration = max(2, min(int(duration_seconds), 8))
    capture = cv2.VideoCapture(int(camera_index), cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(int(camera_index))
    if not capture.isOpened():
        raise RuntimeError("Could not open the camera. Check Windows camera permissions.")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    subtractor = cv2.createBackgroundSubtractorMOG2(history=45, varThreshold=32, detectShadows=False)
    tracks = {}
    next_id = 1
    start = dt.datetime.now().timestamp()
    frames = 0
    try:
        while dt.datetime.now().timestamp() - start < duration:
            ok, frame = capture.read()
            if not ok:
                break
            frames += 1
            if frames % 3:
                continue
            mask = subtractor.apply(frame)
            mask = cv2.medianBlur(mask, 5)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            centers = []
            for contour in contours:
                if cv2.contourArea(contour) < 550:
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                centers.append((x + w // 2, y + h // 2, (x, y, w, h)))
            unmatched = set(tracks)
            for cx, cy, box in centers[:8]:
                best_id, best_dist = None, 48
                for track_id in list(unmatched):
                    old = tracks[track_id]["last"]
                    distance = ((cx - old[0]) ** 2 + (cy - old[1]) ** 2) ** 0.5
                    if distance < best_dist:
                        best_id, best_dist = track_id, distance
                if best_id is None:
                    best_id = next_id
                    next_id += 1
                    tracks[best_id] = {"first": (cx, cy), "last": (cx, cy), "box": box, "hits": 0}
                else:
                    unmatched.discard(best_id)
                item = tracks[best_id]
                item["last"], item["box"] = (cx, cy), box
                item["hits"] += 1
    finally:
        capture.release()
    results = []
    for track_id, item in tracks.items():
        if item["hits"] < 2:
            continue
        dx = item["last"][0] - item["first"][0]
        dy = item["last"][1] - item["first"][1]
        direction = "stationary"
        if abs(dx) + abs(dy) >= 12:
            direction = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
        results.append({"track_id": track_id, "direction": direction,
                        "displacement_pixels": round((dx * dx + dy * dy) ** 0.5, 1),
                        "last_bounding_box": item["box"], "observations": item["hits"]})
    return {"ok": True, "frames_sampled": frames, "duration_seconds": duration,
            "tracks": results[:12], "note": "Tracks represent moving regions, not verified object identities. Frames were processed in memory and not saved."}


def analyze_microphone_sample(duration_seconds=2):
    """Measure only short-term acoustic levels; raw audio is never saved."""
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("Sound analysis requires the optional sounddevice and numpy packages.") from exc
    duration = max(1, min(int(duration_seconds), 3))
    device = sd.query_devices(kind="input")
    audio = sd.rec(int(16000 * duration), samplerate=16000, channels=1, dtype="float32")
    sd.wait()
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    rms = float(np.sqrt(np.mean(np.square(values)) + 1e-12))
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    if peak > 0.8 and rms > 0.12:
        label = "strong transient or very loud sound"
    elif rms > 0.035:
        label = "loud or sustained ambient sound"
    elif rms > 0.008:
        label = "moderate ambient sound"
    else:
        label = "quiet"
    return {"ok": True, "microphone": str(device.get("name", "default"))[:100],
            "duration_seconds": duration, "rms_level": round(rms, 5),
            "peak_level": round(peak, 5), "classification": label,
            "note": "This is acoustic-level analysis, not speech recognition or a diagnosis. Audio was not saved."}


def _public_feed_url(url):
    parsed = urllib.parse.urlparse(str(url).strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Public alert feeds must be HTTPS URLs without embedded credentials.")
    if parsed.port not in (None, 443):
        raise ValueError("Only standard HTTPS port 443 is allowed for public alert feeds.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        ips = {ipaddress.ip_address(item[4][0]) for item in addresses}
    except OSError as exc:
        raise ValueError(f"Could not resolve feed host: {exc}") from exc
    if not ips or any(not ip.is_global for ip in ips):
        raise ValueError("Feed host must resolve only to public IP addresses.")
    return parsed.geturl()


def fetch_public_safety_alerts(max_items=10):
    """Fetch configured public RSS/Atom bulletins; no radio interception."""
    import requests
    raw = os.getenv("JARVIS_PUBLIC_ALERT_FEEDS", "").strip()
    if not raw:
        return {"ok": True, "configured": False, "alerts": [],
                "message": "No public alert feeds configured. Set JARVIS_PUBLIC_ALERT_FEEDS to one or more official HTTPS RSS/Atom feed URLs separated by semicolons."}
    urls = [part.strip() for part in raw.split(";") if part.strip()][:5]
    alerts, errors = [], []
    for url in urls:
        try:
            safe_url = _public_feed_url(url)
            response = requests.get(safe_url, timeout=(3, 6), allow_redirects=False,
                                    headers={"User-Agent": "JARVIS-PublicAlertReader/1.0"})
            if response.status_code != 200:
                raise ValueError(f"HTTP status {response.status_code}")
            if len(response.content) > 1024 * 1024:
                raise ValueError("Feed exceeds 1 MB limit")
            root = ET.fromstring(response.content)
            for node in root.iter():
                tag = node.tag.rsplit("}", 1)[-1].lower()
                if tag not in {"item", "entry"}:
                    continue
                fields = {}
                for child in list(node):
                    key = child.tag.rsplit("}", 1)[-1].lower()
                    value = "".join(child.itertext()).strip()
                    if key in {"title", "summary", "description", "published", "pubdate", "updated", "link"} and value:
                        fields[key] = value
                    if key == "link" and not value:
                        fields[key] = child.attrib.get("href", "")
                title = fields.get("title", "")
                if title:
                    alerts.append({"title": title[:240],
                                   "summary": fields.get("summary", fields.get("description", ""))[:500],
                                   "published": fields.get("published", fields.get("pubdate", fields.get("updated", "")))[:80],
                                   "source": urllib.parse.urlparse(safe_url).hostname})
                if len(alerts) >= max_items:
                    break
        except Exception as exc:
            errors.append({"feed": url[:180], "error": str(exc)[:240]})
        if len(alerts) >= max_items:
            break
    return {"ok": True, "configured": True, "alerts": alerts[:max(1, min(int(max_items), 20))],
            "feed_errors": errors,
            "note": "Only configured public RSS/Atom bulletins are read. This does not receive, decode, or intercept police radio."}


def enrolled_face_profiles():
    """Expose only the local enrolled-profile roster; matching remains face_auth's job."""
    try:
        from face_auth import _load_profiles
        profiles = _load_profiles()
        return {"ok": True, "enrolled_profiles": [
            {"name": str(item.get("name", "")), "role": str(item.get("role", "user"))}
            for item in profiles
        ], "count": len(profiles),
            "scope": "Existing local JARVIS face-unlock profiles only; no public-person identification."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}
