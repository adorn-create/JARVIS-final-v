import logging
import os
import re
import subprocess
import webbrowser
from pathlib import Path

import psutil

from memory import forget, recall, remember
from intent_engine import learn

LOG = logging.getLogger("jarvis.actions")
APP_ALLOWLIST = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "explorer": ["explorer.exe"],
    "task manager": ["taskmgr.exe"],
}
CLICKABLE_TYPES = {"Button", "Hyperlink", "MenuItem", "CheckBox", "RadioButton", "TabItem"}
SENSITIVE_FIELD_TERMS = (
    "password",
    "passcode",
    "secret",
    "credential",
    "token",
    "api key",
    "api_key",
)


def system_status():
    disk = psutil.disk_usage(os.environ.get("SystemDrive", "C:"))
    battery = psutil.sensors_battery()
    processes = []
    for process in psutil.process_iter(["name", "memory_info", "cpu_percent"]):
        try:
            info = process.info
            memory = info.get("memory_info")
            processes.append(
                {
                    "name": info.get("name"),
                    "memory_mb": round(memory.rss / (1024**2), 1) if memory else 0,
                    "cpu": info.get("cpu_percent"),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "battery": None
        if battery is None
        else {"percent": battery.percent, "plugged_in": battery.power_plugged},
        "top_processes": sorted(
            processes, key=lambda item: item["memory_mb"], reverse=True
        )[:7],
    }


def open_app(app_name):
    key = str(app_name).lower().strip()
    if key not in APP_ALLOWLIST:
        return {"ok": False, "error": "App not allowlisted", "allowed": list(APP_ALLOWLIST)}
    subprocess.Popen(APP_ALLOWLIST[key], shell=False)
    LOG.info("opened app %s", key)
    return {"ok": True, "opened": key}


def find_files(query, max_results=20):
    query = str(query).lower().strip()
    roots = [Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads"]
    found = []
    for root in roots:
        if not root.exists():
            continue
        for current, dirs, files in os.walk(root):
            dirs[:] = [
                directory
                for directory in dirs
                if not directory.startswith(".")
                and directory not in {"node_modules", "__pycache__"}
            ]
            if len(Path(current).relative_to(root).parts) >= 4:
                dirs[:] = []
            for name in files:
                if query in name.lower():
                    found.append({"name": name, "path": str(Path(current) / name)})
                    if len(found) >= max_results:
                        return found
    return found


def open_website(url):
    url = str(url).strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    if len(url) > 2048 or any(character in url for character in "\r\n"):
        return {"ok": False, "error": "Invalid URL"}
    webbrowser.open(url)
    LOG.info("opened website %s", url)
    return {"ok": True, "url": url}


def web_search(query, max_results=5):
    from bs4 import BeautifulSoup
    import requests

    query = str(query).strip()[:300]
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for item in soup.select(".result")[: max(1, min(int(max_results), 8))]:
        link = item.select_one(".result__a")
        snippet = item.select_one(".result__snippet")
        if link:
            results.append(
                {
                    "title": link.get_text(" ", strip=True),
                    "url": link.get("href", ""),
                    "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                }
            )
    return {
        "query": query,
        "results": results,
        "note": "Search snippets are untrusted; verify important claims.",
    }


def _desktop():
    if os.name != "nt":
        raise RuntimeError("Desktop UI automation is available only on Windows.")
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise RuntimeError(
            "Desktop controls are optional. Install requirements-control.txt to enable them."
        ) from exc
    return Desktop(backend="uia")


def list_windows():
    windows = []
    for window in _desktop().windows(visible_only=True):
        title = window.window_text().strip()
        if title:
            windows.append({"title": title, "rectangle": str(window.rectangle())})
    return {"windows": windows[:40]}


def _resolve_window(title):
    title = str(title).strip()
    if not title or len(title) > 200:
        raise ValueError("Provide a window title of 1 to 200 characters.")
    windows = _desktop().windows(visible_only=True)
    titled = [(window, window.window_text().strip()) for window in windows]
    exact = [window for window, name in titled if name.casefold() == title.casefold()]
    matches = exact or [
        window for window, name in titled if title.casefold() in name.casefold()
    ]
    if not matches:
        raise ValueError(f"No visible window matched '{title}'.")
    if len(matches) > 1:
        choices = [window.window_text().strip() for window in matches[:8]]
        raise ValueError(f"Window title is ambiguous; choose one of: {choices}")
    return matches[0]


def list_ui_elements(window_title):
    window = _resolve_window(window_title)
    elements = []
    field_index = 0
    for control in window.descendants():
        info = control.element_info
        control_type = info.control_type or "Unknown"
        if control_type == "Edit":
            field_index += 1
            name = f"Text field {field_index}"
        else:
            name = (info.name or "").strip()[:120]
        if control_type not in CLICKABLE_TYPES and control_type != "Edit":
            continue
        if not name and control_type != "Edit":
            continue
        elements.append(
            {
                "type": control_type,
                "name": name,
                "enabled": control.is_enabled(),
                "rectangle": str(control.rectangle()),
                **({"field_index": field_index} if control_type == "Edit" else {}),
            }
        )
        if len(elements) >= 80:
            break
    return {"window": window.window_text().strip(), "elements": elements}


def _confirm_action(confirm, description):
    if confirm is None:
        return False
    return bool(confirm(description))


def _is_password_field(control):
    try:
        return bool(control.element_info.element.CurrentIsPassword)
    except Exception as exc:
        raise RuntimeError(
            "JARVIS could not verify whether this text field is a password field; refusing text entry."
        ) from exc


def _is_sensitive_field(control):
    info = control.element_info
    metadata = f"{info.name or ''} {info.automation_id or ''}".casefold()
    return any(term in metadata for term in SENSITIVE_FIELD_TERMS)


def click_ui_element(window_title, element_name, confirm=None):
    window = _resolve_window(window_title)
    name = str(element_name).strip()
    if not name or len(name) > 120:
        raise ValueError("Provide a UI element name of 1 to 120 characters.")
    matches = [
        control
        for control in window.descendants()
        if control.element_info.control_type in CLICKABLE_TYPES
        and (control.element_info.name or "").strip().casefold() == name.casefold()
        and control.is_enabled()
    ]
    if not matches:
        raise ValueError(f"No enabled button or link named '{name}' was found.")
    if len(matches) > 1:
        raise ValueError(f"More than one enabled element is named '{name}'.")
    description = f"Click '{name}' in the window '{window.window_text().strip()}'?"
    if not _confirm_action(confirm, description):
        return {"ok": False, "error": "User did not approve this UI action."}
    matches[0].click_input()
    LOG.info("clicked UI element %r in window %r", name, window.window_text().strip())
    return {
        "ok": True,
        "action": "click dispatched",
        "target": name,
        "verify_with_screen": True,
    }


def type_into_field(window_title, field_index, text, confirm=None):
    window = _resolve_window(window_title)
    try:
        field_index = int(field_index)
    except (TypeError, ValueError) as exc:
        raise ValueError("field_index must be the number shown by list_ui_elements.") from exc
    if field_index < 1:
        raise ValueError("field_index must be a positive number.")
    fields = [
        control
        for control in window.descendants()
        if control.element_info.control_type == "Edit"
    ]
    if field_index > len(fields):
        raise ValueError("That text field is no longer available; inspect the window again.")
    field = fields[field_index - 1]
    if not field.is_enabled():
        raise ValueError("The selected text field is disabled.")
    if _is_password_field(field):
        raise ValueError("JARVIS will not type into password fields.")
    if _is_sensitive_field(field):
        raise ValueError("JARVIS will not type into fields identified as credential-related.")
    text = str(text)
    if not text or len(text) > 1000:
        raise ValueError("Text must contain 1 to 1000 characters.")
    description = (
        f"Type the following text into field {field_index} in "
        f"'{window.window_text().strip()}':\n\n{text}"
    )
    if not _confirm_action(confirm, description):
        return {"ok": False, "error": "User did not approve this UI action."}
    field.set_edit_text(text)
    verified = field.get_value() == text
    if not verified:
        raise RuntimeError("Text entry was not verified by the target UI control.")
    LOG.info(
        "entered text into field %s in window %r",
        field_index,
        window.window_text().strip(),
    )
    return {"ok": True, "action": "text entered and verified", "field_index": field_index}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "security_triage_file",
            "description": "Perform read-only local triage of one user-selected file: SHA-256, file header, extension indicators, Windows download-zone marker, and Authenticode signature where available. Never executes, uploads, modifies, deletes, or quarantines the file. This is not a malware verdict and requires user approval.",
            "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_process_snapshot",
            "description": "Read-only snapshot of running processes using conservative path-based indicators for processes launched from common user-writable folders. Reports leads only; does not terminate, suspend, or modify processes. Requires user approval.",
            "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_host_audit",
            "description": "Read the local Windows Defender and Windows Firewall status. Read-only; does not change security settings.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_scan_private_host",
            "description": "Perform a conservative TCP connect-only check against ONE explicitly authorized private, loopback, or link-local IPv4 address. Only allowlisted ports are accepted; no payloads or exploit attempts are sent. Always obtain user approval before invoking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "One literal private IPv4 address; no hostname or CIDR."},
                    "ports": {"type": "array", "items": {"type": "integer", "enum": [22, 53, 80, 135, 139, 443, 445, 3306, 3389, 5432, 5985, 5986, 8000, 8080, 8443, 8888]}, "maxItems": 16},
                },
                "required": ["target"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_inventory_authorized_subnet",
            "description": "Inventory up to 14 hosts on one explicitly authorized private IPv4 /28-or-smaller subnet. Checks only allowlisted TCP ports using connect-only probes; no banners, login attempts, exploit payloads, or configuration changes. Requires explicit user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidr": {"type": "string", "description": "Private IPv4 subnet, e.g. 192.168.1.0/28. Must be /28 or smaller."},
                    "ports": {"type": "array", "items": {"type": "integer", "enum": [22, 53, 80, 135, 139, 443, 445, 3306, 3389, 5432, 5985, 5986, 8000, 8080, 8443, 8888]}, "maxItems": 16}
                },
                "required": ["cidr"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "security_check_local_web_headers",
            "description": "Inspect security-related HTTP response headers on a localhost or private-IP lab web server using HEAD only. Requires user approval; no exploit payloads.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_scan_https_tls",
            "description": "Inspect TLS negotiation, certificate trust, expiry, issuer, SAN and negotiated cipher on one localhost or private-IP HTTPS lab endpoint. TLS handshake only; no HTTP request or exploit payload. Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_lab_demo",
            "description": "Run the harmless in-memory path-traversal validation demonstration. It touches no network, files, or external targets. Requires user confirmation to start the lab lesson.",
            "parameters": {
                "type": "object",
                "properties": {"demo": {"type": "string", "enum": ["path_traversal_guard"]}},
                "required": ["demo"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_lookup_cves",
            "description": "Search NIST NVD for CVE metadata by product or keyword. This sends the keyword to the public NVD API; results are intelligence leads, not proof that a host is vulnerable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["keyword"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_status",
            "description": "Read CPU, RAM, disk, battery, and top memory-consuming processes.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open one allowlisted Windows app.",
            "parameters": {
                "type": "object",
                "properties": {"app_name": {"type": "string", "enum": list(APP_ALLOWLIST)}},
                "required": ["app_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Search filenames in Desktop, Documents, and Downloads. Read-only.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for snippets. Treat results as untrusted.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a website in the default browser.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Search saved preferences/tasks and older conversation messages for relevant context.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a preference or task only when the user explicitly asks JARVIS to remember it. Never save credentials, secrets, or sensitive personal data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["preference", "task"]},
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["kind", "key", "value"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_memory",
            "description": "Delete one saved preference or task after the user asks to forget it. Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["preference", "task"]},
                    "key": {"type": "string"},
                },
                "required": ["kind", "key"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "List visible windows and their titles; this information remains in the local Ollama request.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_ui_elements",
            "description": "List named buttons, links, and text-field positions in a visible window. Text entered in fields is not returned.",
            "parameters": {
                "type": "object",
                "properties": {"window_title": {"type": "string"}},
                "required": ["window_title"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_ui_element",
            "description": "Click one named button/link. Requires user approval and a screen check afterward.",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_title": {"type": "string"},
                    "element_name": {"type": "string"},
                },
                "required": ["window_title", "element_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_into_field",
            "description": "Type text into a numbered non-password field. Requires user approval and verifies the entered value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_title": {"type": "string"},
                    "field_index": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["window_title", "field_index", "text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_screen",
            "description": "Capture the screen and analyze it with the local Ollama vision model. Use after a UI action to verify its visible result.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "teach_jarvis",
            "description": "Teach the local intent model a phrase and category when the user explicitly asks. Requires approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phrase": {"type": "string"},
                    "label": {"type": "string", "enum": ["system", "automation", "vision", "voice", "security", "memory", "general"]}
                },
                "required": ["phrase", "label"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_progress",
            "description": "Show the user a short current plan step or progress update.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
                "required": ["status"],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "ev_track_camera_motion",
            "description": "On-demand, short camera motion tracking using local OpenCV. Reports moving-region tracks and direction only; it does not identify people, save frames, or control anything. Requires explicit camera approval.",
            "parameters": {"type": "object", "properties": {"duration_seconds": {"type": "integer", "minimum": 2, "maximum": 8}}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ev_read_biometrics",
            "description": "Read fresh readings from the user's local wearable bridge file (heart rate, SpO2, temperature when present). No sensor values are fabricated; informational only. Requires approval.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ev_analyze_senses",
            "description": "Capture a very short microphone sample and classify acoustic level/transients locally. Raw audio is not saved and this is not speech recognition. Requires microphone approval.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ev_public_safety_alerts",
            "description": "Read configured official public HTTPS RSS/Atom emergency bulletins. No radio interception, private dispatch feeds, or non-public channels. Requires approval before network access.",
            "parameters": {"type": "object", "properties": {"max_items": {"type": "integer", "minimum": 1, "maximum": 20}}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ev_face_profiles",
            "description": "List locally enrolled JARVIS face-unlock profiles. Does not identify unknown or public people. Requires approval to read the local profile roster.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ev_analyze_project_data",
            "description": "Produce aggregate summaries of one project-relative CSV/JSON/JSONL/LOG/TXT file under data/ or logs/ (max 2 MB). Does not read arbitrary paths or return full file contents. Requires approval.",
            "parameters": {"type": "object", "properties": {"relative_path": {"type": "string"}}, "required": ["relative_path"], "additionalProperties": False},
        },
    },


    {
        "type": "function",
        "function": {
            "name": "friday_track_target_motion",
            "description": "Analyze 2D position samples for one anonymous moving object, estimate direction/speed, and extrapolate its near-term position. No identity recognition, weapon targeting, or action control.",
            "parameters": {"type": "object", "properties": {
                "samples": {"type": "array", "minItems": 2, "maxItems": 60, "items": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "t": {"type": "number"}}, "required": ["x", "y", "t"], "additionalProperties": False}},
                "horizon_seconds": {"type": "number", "minimum": 0.1, "maximum": 3}
            }, "required": ["samples"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "friday_assess_safety_signals",
            "description": "Score user-reported environmental hazards such as smoke, fire, gas smell, approaching vehicle, injury, loud impact, or power outage. Does not score people or automatically detect threats.",
            "parameters": {"type": "object", "properties": {"signals": {"type": "array", "items": {"type": "string", "enum": ["smoke", "fire", "gas_smell", "vehicle_approaching", "fall_or_injury", "loud_impact", "power_outage"]}, "maxItems": 10}}, "required": ["signals"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "friday_system_diagnostics",
            "description": "Run read-only CPU, RAM, disk, battery and available temperature-sensor diagnostics on this PC.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "friday_power_advice",
            "description": "Read battery state and suggest energy-saving actions. Never changes Windows power settings.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "friday_navigation_guidance",
            "description": "Convert supplied compass heading and target bearing into a simple turn cue. Optional distance/speed gives a rough ETA. No GPS, autopilot, vehicle control, or aviation navigation.",
            "parameters": {"type": "object", "properties": {
                "current_heading_deg": {"type": "number"}, "target_bearing_deg": {"type": "number"},
                "distance_m": {"type": "number"}, "speed_mps": {"type": "number"}
            }, "required": ["current_heading_deg", "target_bearing_deg"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "friday_intelligence_search",
            "description": "Search public web snippets for an intelligence brief. Requires user approval before external network access; results are untrusted and must be verified.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "friday_emergency_guidance",
            "description": "Provide conservative first-response reminders for fire, medical emergency, road accident, intrusion, severe weather, or power outage. Does not contact emergency services.",
            "parameters": {"type": "object", "properties": {"scenario": {"type": "string", "enum": ["fire", "medical", "road_accident", "intrusion", "severe_weather", "power_outage"]}}, "required": ["scenario"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "friday_local_alert",
            "description": "Show a local F.R.I.D.A.Y. alert in the JARVIS HUD. This does not send email, SMS, calls, or external messages.",
            "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "message": {"type": "string"}}, "required": ["title", "message"], "additionalProperties": False}
        }
    },

    {
        "type": "function",
        "function": {
            "name": "ultron_capability_report",
            "description": "Describe the safe Ultron-inspired subsystem, its capabilities and limitations.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ultron_strategic_plan",
            "description": "Create a bounded advisory plan for a goal. Planning only; it does not execute commands or access devices.",
            "parameters": {"type": "object", "properties": {"goal": {"type": "string", "maxLength": 500}}, "required": ["goal"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ultron_review_improvement",
            "description": "Turn user feedback into a review-only improvement proposal. Does not modify source code or model weights.",
            "parameters": {"type": "object", "properties": {"area": {"type": "string", "maxLength": 100}, "feedback": {"type": "string", "maxLength": 1000}}, "required": ["area", "feedback"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ultron_simulate_fleet",
            "description": "Simulate a small virtual robotics fleet. No network access or physical device control. Allowed commands: status, standby, return_to_base, formation_demo, sensor_check.",
            "parameters": {"type": "object", "properties": {"command": {"type": "string", "enum": ["status", "standby", "return_to_base", "formation_demo", "sensor_check"]}, "unit_count": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["command"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ultron_resilience_check",
            "description": "Read-only local CPU, memory, disk and battery health check with backup and recovery recommendations.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },

    {
        "type": "function",
        "function": {
            "name": "android_list_devices",
            "description": "List Android phones/tablets currently visible to this PC through ADB, including authorized, unauthorized, and offline states. Read-only; does not access phone contents.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "android_set_device_alias",
            "description": "Give a friendly local name to one Android device currently visible to ADB. Stores only the serial-to-label mapping on this PC; never stores credentials. Requires explicit user approval.",
            "parameters": {"type": "object", "properties": {"serial": {"type": "string"}, "alias": {"type": "string", "minLength": 1, "maxLength": 32}}, "required": ["serial", "alias"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "android_wake_devices",
            "description": "Wake the displays of selected, currently authorized Android devices in parallel. Does not unlock them, dismiss the lock screen, or enter a PIN. Requires explicit user approval.",
            "parameters": {"type": "object", "properties": {"serials": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}}, "required": ["serials"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "android_launch_app",
            "description": "Launch one allowlisted Android app on selected, currently authorized ADB devices in parallel. Supported apps: YouTube, Chrome, Maps, WhatsApp, Spotify, Gmail, Settings, Camera, Photos. Requires explicit user approval. A locked phone may require its owner to unlock it first.",
            "parameters": {"type": "object", "properties": {"serials": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "app": {"type": "string", "enum": ["youtube", "chrome", "maps", "whatsapp", "spotify", "gmail", "settings", "camera", "photos"]}}, "required": ["serials", "app"], "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "android_pair_wireless_device",
            "description": "Pair one owner-controlled Android phone using its Android Wireless Debugging pairing address and temporary six-digit pairing code. The code is used once and not saved. Requires explicit user approval; never bypasses the phone lock screen.",
            "parameters": {"type": "object", "properties": {"address": {"type": "string"}, "pairing_code": {"type": "string", "pattern": "^[0-9]{6}$"}}, "required": ["address", "pairing_code"], "additionalProperties": False}
        }
    },

    {
        "type": "function",
        "function": {
            "name": "android_connect_wireless_device",
            "description": "Connect to the separate private-LAN ADB endpoint shown on an owner-controlled Android phone's Wireless Debugging screen after pairing. Requires explicit user approval.",
            "parameters": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"], "additionalProperties": False}
        }
    },
]


def execute(name, args, confirm=None, progress=None):

    if name == "android_list_devices":
        from android_bridge import list_android_devices
        return list_android_devices()
    if name == "android_set_device_alias":
        from android_bridge import set_android_device_alias
        serial = str(args.get("serial", "")).strip()
        alias = str(args.get("alias", "")).strip()
        if not _confirm_action(confirm, f"Save the local device name '{alias}' for Android device {serial}? No passwords or pairing codes are stored."):
            return {"ok": False, "error": "User did not approve saving the Android device name."}
        return set_android_device_alias(serial, alias)
    if name == "android_wake_devices":
        from android_bridge import wake_android_displays
        serials = args.get("serials", [])
        if not _confirm_action(confirm, "Wake the displays on these selected Android devices? This does not unlock them or enter PINs.\\n\\n" + ", ".join(map(str, serials))):
            return {"ok": False, "error": "User did not approve waking the Android devices."}
        return wake_android_displays(serials)
    if name == "android_launch_app":
        from android_bridge import launch_android_app
        serials = args.get("serials", [])
        app = str(args.get("app", "")).strip().lower()
        if not _confirm_action(confirm, f"Launch {app} on these selected, authorized Android devices?\\n\\n" + ", ".join(map(str, serials))):
            return {"ok": False, "error": "User did not approve the Android app launch."}
        return launch_android_app(serials, app)
    if name == "android_pair_wireless_device":
        from android_bridge import pair_wireless_android_device
        address = str(args.get("address", "")).strip()
        code = str(args.get("pairing_code", "")).strip()
        if not _confirm_action(confirm, "Pair JARVIS with this owner-controlled Android Wireless Debugging endpoint? The six-digit pairing code is used once and is not stored.\\n\\n" + address):
            return {"ok": False, "error": "User did not approve Android wireless pairing."}
        return pair_wireless_android_device(address, code)


    if name == "android_connect_wireless_device":
        from android_bridge import connect_wireless_android_device
        address = str(args.get("address", "")).strip()
        if not _confirm_action(confirm, "Connect to this private-LAN Android Wireless Debugging endpoint?\\n\\n" + address):
            return {"ok": False, "error": "User did not approve the wireless ADB connection."}
        return connect_wireless_android_device(address)

    if name == "system_status":
        return system_status()
    if name == "open_app":
        return open_app(args.get("app_name", ""))
    if name == "find_files":
        return find_files(args.get("query", ""))
    if name == "web_search":
        return web_search(args.get("query", ""))
    if name == "open_website":
        return open_website(args.get("url", ""))
    if name == "recall_memory":
        return recall(args.get("query", ""))
    if name == "remember":
        kind = args.get("kind", "")
        key = args.get("key", "")
        value = args.get("value", "")
        description = f"Save this {kind} for future chats?\n\n{key}: {value}"
        if not _confirm_action(confirm, description):
            return {"ok": False, "error": "User did not approve saving this memory."}
        return remember(kind, key, value)
    if name == "forget_memory":
        kind = args.get("kind", "")
        key = args.get("key", "")
        if not _confirm_action(
            confirm, f"Forget the saved {kind} '{key}' for future chats?"
        ):
            return {"ok": False, "error": "User did not approve deleting this memory."}
        return forget(kind, key)
    if name == "list_windows":
        return list_windows()
    if name == "list_ui_elements":
        return list_ui_elements(args.get("window_title", ""))
    if name == "click_ui_element":
        return click_ui_element(
            args.get("window_title", ""),
            args.get("element_name", ""),
            confirm=confirm,
        )
    if name == "type_into_field":
        return type_into_field(
            args.get("window_title", ""),
            args.get("field_index", 0),
            args.get("text", ""),
            confirm=confirm,
        )
    if name == "inspect_screen":
        from vision import analyze_screen

        return analyze_screen(str(args.get("question", ""))[:1000])
    if name == "teach_jarvis":
        phrase = str(args.get("phrase", "")).strip()
        label = str(args.get("label", "")).strip().lower()
        if not _confirm_action(confirm, f"Add this training example to JARVIS's local intent model?\\n\\nCategory: {label}\\nPhrase: {phrase}"):
            return {"ok": False, "error": "User did not approve model training."}
        return learn(phrase, label)
    if name == "security_triage_file":
        from morpheus_monitor import triage_file
        file_path = str(args.get("file_path", "")).strip()
        if not _confirm_action(
            confirm,
            "Inspect this selected local file using read-only hashing, metadata and signature checks?\n\n"
            + file_path
            + "\nThe file will not be executed, uploaded, modified, deleted, or quarantined."
        ):
            return {"ok": False, "error": "User did not approve file triage."}
        return triage_file(file_path)
    if name == "security_process_snapshot":
        from morpheus_monitor import process_snapshot
        limit = args.get("limit", 100)
        if not _confirm_action(
            confirm,
            "Read a local snapshot of running process paths and report basic heuristic indicators? "
            "No process will be stopped or modified."
        ):
            return {"ok": False, "error": "User did not approve process snapshot."}
        return process_snapshot(limit=limit)
    if name == "security_host_audit":
        from security_engine import audit_windows_security
        return audit_windows_security()
    if name == "security_scan_private_host":
        from security_engine import scan_private_host
        target = str(args.get("target", "")).strip()
        ports = args.get("ports")
        if not _confirm_action(
            confirm,
            "Run a limited TCP connect-only scan against this single authorized private host?\n\n"
            f"Target: {target}\nPorts: {ports if ports else 'JARVIS default safe port list'}\n"
            "No exploit payloads will be sent."
        ):
            return {"ok": False, "error": "User did not approve the network check."}
        return scan_private_host(target, ports=ports)
    if name == "security_inventory_authorized_subnet":
        from security_engine import scan_authorized_subnet
        cidr = str(args.get("cidr", "")).strip()
        ports = args.get("ports")
        if not _confirm_action(
            confirm,
            "Inventory this explicitly authorized private subnet?\n\n"
            f"Network: {cidr}\nPorts: {ports if ports else 'JARVIS default safe port list'}\n"
            "Maximum 14 hosts. TCP connect-only checks; no exploit payloads, logins, or changes."
        ):
            return {"ok": False, "error": "User did not approve subnet inventory."}
        return scan_authorized_subnet(cidr, ports=ports)
    if name == "security_check_local_web_headers":
        from security_engine import check_local_web_headers
        url = str(args.get("url", "")).strip()
        if not _confirm_action(
            confirm,
            "Inspect HTTP security headers on this localhost/private lab endpoint?\n\n" + url
        ):
            return {"ok": False, "error": "User did not approve the web-header check."}
        return check_local_web_headers(url)
    if name == "security_scan_https_tls":
        from security_engine import scan_private_https_tls
        url = str(args.get("url", "")).strip()
        if not _confirm_action(
            confirm,
            "Run a TLS handshake and certificate inspection against this authorized localhost/private HTTPS lab endpoint?\n\n"
            + url + "\nNo HTTP request or exploit payload will be sent."
        ):
            return {"ok": False, "error": "User did not approve the HTTPS/TLS scan."}
        return scan_private_https_tls(url)
    if name == "security_lab_demo":
        from security_engine import run_safe_lab_demo
        demo = str(args.get("demo", "")).strip()
        if not _confirm_action(
            confirm,
            "Run the harmless in-memory security lab demonstration?\n\n"
            "It will not access the network or read/write files."
        ):
            return {"ok": False, "error": "User did not approve the lab demonstration."}
        return run_safe_lab_demo(demo)
    if name == "security_lookup_cves":
        from security_engine import lookup_cves
        return lookup_cves(args.get("keyword", ""), args.get("limit", 5))

    if name == "ev_track_camera_motion":
        from ev_features import track_camera_motion
        duration = args.get("duration_seconds", 4)
        if not _confirm_action(confirm, "Enable the camera for a short local motion-tracking sample? Frames are processed in memory and not saved; no people are identified."):
            return {"ok": False, "error": "User did not approve camera tracking."}
        return track_camera_motion(duration_seconds=duration)
    if name == "ev_read_biometrics":
        from ev_features import read_biometrics
        if not _confirm_action(confirm, "Read the current local wearable sensor readings (if available)? This may include health-related measurements."):
            return {"ok": False, "error": "User did not approve reading biometric data."}
        return read_biometrics()
    if name == "ev_analyze_senses":
        from ev_features import analyze_microphone_sample
        if not _confirm_action(confirm, "Use the microphone for a 2-second acoustic-level sample? Audio will not be saved."):
            return {"ok": False, "error": "User did not approve microphone analysis."}
        return analyze_microphone_sample()
    if name == "ev_public_safety_alerts":
        from ev_features import fetch_public_safety_alerts
        if not _confirm_action(confirm, "Fetch configured public HTTPS emergency bulletins? This connects only to feeds configured in JARVIS settings; no radio is intercepted."):
            return {"ok": False, "error": "User did not approve public alert feed access."}
        return fetch_public_safety_alerts(args.get("max_items", 10))
    if name == "ev_face_profiles":
        from ev_features import enrolled_face_profiles
        if not _confirm_action(confirm, "Read the names and roles of locally enrolled JARVIS face-unlock profiles?"):
            return {"ok": False, "error": "User did not approve reading face profile metadata."}
        return enrolled_face_profiles()
    if name == "ev_analyze_project_data":
        from ev_features import analyze_project_file
        relative_path = str(args.get("relative_path", "")).strip()
        if not _confirm_action(confirm, "Analyze this project-local data file and return aggregate statistics only?\n\n" + relative_path):
            return {"ok": False, "error": "User did not approve local data analysis."}
        return analyze_project_file(relative_path)


    if name == "friday_track_target_motion":
        from friday_features import analyze_movement
        return analyze_movement(args.get("samples", []), args.get("horizon_seconds", 1.0))
    if name == "friday_assess_safety_signals":
        from friday_features import assess_safety_signals
        return assess_safety_signals(args.get("signals", []))
    if name == "friday_system_diagnostics":
        from friday_features import system_diagnostics
        return system_diagnostics()
    if name == "friday_power_advice":
        from friday_features import power_advice
        return power_advice()
    if name == "friday_navigation_guidance":
        from friday_features import navigation_guidance
        return navigation_guidance(
            args.get("current_heading_deg"), args.get("target_bearing_deg"),
            args.get("distance_m"), args.get("speed_mps")
        )
    if name == "friday_intelligence_search":
        query = str(args.get("query", "")).strip()[:300]
        if not _confirm_action(confirm, "Search public websites for this F.R.I.D.A.Y. intelligence brief?\n\n" + query):
            return {"ok": False, "error": "User did not approve external intelligence search."}
        return web_search(query)
    if name == "friday_emergency_guidance":
        from friday_features import emergency_guidance
        return emergency_guidance(args.get("scenario", ""))
    if name == "friday_local_alert":
        title = str(args.get("title", "")).strip()[:100]
        message = str(args.get("message", "")).strip()[:500]
        if not title or not message:
            return {"ok": False, "error": "A non-empty alert title and message are required."}
        if progress:
            progress("ALERT • " + title + ": " + message[:90])
        return {"ok": True, "displayed_in_local_hud": bool(progress), "title": title, "message": message,
                "note": "Local JARVIS HUD only; no external communication was sent."}

    if name == "ultron_capability_report":
        from ultron_features import capability_report
        return capability_report()
    if name == "ultron_strategic_plan":
        from ultron_features import strategic_plan
        return strategic_plan(args.get("goal", ""))
    if name == "ultron_review_improvement":
        from ultron_features import review_improvement
        return review_improvement(args.get("area", ""), args.get("feedback", ""))
    if name == "ultron_simulate_fleet":
        from ultron_features import simulate_fleet
        command = args.get("command", "")
        count = args.get("unit_count", 3)
        if not _confirm_action(
            confirm,
            "Run a virtual-only fleet simulation? No physical devices or networks will be contacted.\\n\\n"
            f"Command: {command}\\nUnits: {count}"
        ):
            return {"ok": False, "error": "User did not approve the fleet simulation."}
        return simulate_fleet(command, count)
    if name == "ultron_resilience_check":
        from ultron_features import resilience_check
        return resilience_check()

    if name == "report_progress":
        status = str(args.get("status", "")).strip()[:120]
        if progress and status:
            progress(status)
        return {"ok": True, "status": status}
    return {"error": "Unknown tool"}
