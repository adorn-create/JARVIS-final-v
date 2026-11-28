"""Lightweight F.R.I.D.A.Y.-inspired analysis helpers for JARVIS.

These are advisory desktop/sensor utilities, not weapon, suit, or remote-control
systems. They use the standard library and do not load another AI model.
"""
import math
import statistics


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")
    return float(value)


def analyze_movement(samples, horizon_seconds=1.0):
    """Analyze user-provided 2D observations and extrapolate a short trajectory."""
    if not isinstance(samples, list) or not 2 <= len(samples) <= 60:
        raise ValueError("Provide 2 to 60 movement samples.")
    points = []
    for index, item in enumerate(samples):
        if not isinstance(item, dict):
            raise ValueError("Each movement sample must be an object with x, y, and t.")
        x, y, t = (_number(item.get(k), k) for k in ("x", "y", "t"))
        if points and t <= points[-1][2]:
            raise ValueError("Sample timestamps must be strictly increasing.")
        points.append((x, y, t))
    horizon = max(0.1, min(_number(horizon_seconds, "horizon_seconds"), 3.0))
    first, last = points[0], points[-1]
    elapsed = last[2] - first[2]
    if elapsed <= 0:
        raise ValueError("Movement samples must span a positive time interval.")
    dx, dy = last[0] - first[0], last[1] - first[1]
    speed = math.hypot(dx, dy) / elapsed
    direction = "stationary"
    if math.hypot(dx, dy) >= 2:
        direction = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
    recent = points[-min(5, len(points)):]
    vx = (recent[-1][0] - recent[0][0]) / (recent[-1][2] - recent[0][2])
    vy = (recent[-1][1] - recent[0][1]) / (recent[-1][2] - recent[0][2])
    predicted = {"x": round(last[0] + vx * horizon, 2), "y": round(last[1] + vy * horizon, 2)}
    step_speeds = [
        math.hypot(b[0] - a[0], b[1] - a[1]) / (b[2] - a[2])
        for a, b in zip(points, points[1:])
    ]
    variation = statistics.pstdev(step_speeds) if len(step_speeds) > 1 else 0.0
    pattern = "steady" if variation <= max(1.0, speed * 0.25) else "variable"
    if speed < 1:
        pattern = "mostly stationary"
    return {
        "ok": True, "observations": len(points), "duration_seconds": round(elapsed, 3),
        "average_speed_pixels_per_second": round(speed, 2), "direction": direction,
        "movement_pattern": pattern, "predicted_position_after_seconds": horizon,
        "predicted_position": predicted,
        "warning": "Short linear extrapolation only; this is not identity tracking, combat prediction, or a reliable forecast."
    }


def assess_safety_signals(signals):
    """Score user-reported environmental hazards; never scores or labels people."""
    allowed = {
        "smoke": (4, "Move away from the area; avoid inhaling smoke."),
        "fire": (5, "Evacuate if safe and contact local emergency services."),
        "gas_smell": (5, "Leave the area, avoid switches/flames, and contact emergency services or the gas provider."),
        "vehicle_approaching": (3, "Move to a protected safe location and keep clear of the vehicle path."),
        "fall_or_injury": (3, "Check scene safety and seek medical help if needed."),
        "loud_impact": (2, "Check for immediate hazards from a safe position."),
        "power_outage": (2, "Use a safe light source and avoid exposed electrical equipment."),
    }
    if not isinstance(signals, list) or len(signals) > 10:
        raise ValueError("Provide up to 10 recognized environmental safety signals.")
    normalized = []
    for signal in signals:
        key = str(signal).strip().lower()
        if key not in allowed:
            raise ValueError(f"Unsupported signal: {key}")
        normalized.append(key)
    score = min(10, sum(allowed[key][0] for key in set(normalized)))
    level = "low" if score <= 2 else "moderate" if score <= 5 else "high"
    actions = list(dict.fromkeys(allowed[key][1] for key in normalized))
    return {
        "ok": True, "signals": sorted(set(normalized)), "advisory_score_0_to_10": score,
        "level": level, "suggested_actions": actions,
        "notice": "This is a rule-based advisory from supplied signals, not an automated detector or verified emergency assessment."
    }


def fuse_environmental_observations(
    camera_motion_detected=False,
    acoustic_classification="not_sampled",
    reported_signals=None,
):
    """Combine opt-in E.V. observations into a conservative F.R.I.D.A.Y. advisory.

    Sensor observations are weak contextual clues. Only explicitly supplied
    safety signals produce scenario guidance; no person is classified and no
    emergency is automatically declared or contacted.
    """
    if not isinstance(camera_motion_detected, bool):
        raise ValueError("camera_motion_detected must be true or false.")
    allowed_acoustics = {
        "not_sampled", "quiet", "moderate ambient sound",
        "loud or sustained ambient sound", "strong transient or very loud sound",
    }
    acoustic = str(acoustic_classification or "not_sampled").strip().lower()
    if acoustic not in allowed_acoustics:
        raise ValueError("Unsupported acoustic classification.")
    signals = reported_signals or []
    if not isinstance(signals, list):
        raise ValueError("reported_signals must be a list.")
    advisory = assess_safety_signals(signals)
    evidence = []
    if camera_motion_detected:
        evidence.append({"source": "camera_motion", "observation": "moving regions detected; object identity and cause unknown"})
    if acoustic not in {"not_sampled", "quiet"}:
        evidence.append({"source": "microphone_level", "observation": acoustic})
    if advisory["signals"]:
        evidence.append({"source": "user_report", "observation": "user-supplied safety signals", "signals": advisory["signals"]})
    independent_sources = len({item["source"] for item in evidence})
    corroboration = (
        "multiple_sources_observed" if independent_sources >= 2
        else "single_source_observed" if independent_sources == 1
        else "no_indicators_supplied"
    )
    return {
        "ok": True,
        "system": "E.V. + F.R.I.D.A.Y. advisory fusion",
        "evidence": evidence,
        "independent_sources": independent_sources,
        "corroboration": corroboration,
        "reported_signal_advisory": {
            "score_0_to_10": advisory["advisory_score_0_to_10"],
            "level": advisory["level"],
            "suggested_actions": advisory["suggested_actions"],
        },
        "decision": "review_observations" if evidence else "insufficient_observations",
        "limitations": "Motion and sound do not identify a hazard or person. Sensor samples may be noisy or unrelated. Follow official emergency guidance; this function does not contact responders or trigger automated actions.",
    }


def system_diagnostics():
    """Read-only host health summary."""
    import psutil
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(psutil.disk_partitions(all=False)[0].mountpoint if psutil.disk_partitions(all=False) else "/")
    battery = psutil.sensors_battery()
    try:
        temperature = psutil.sensors_temperatures()
        temp_names = list(temperature)[:5] if temperature else []
    except Exception:
        temp_names = []
    return {
        "ok": True, "cpu_percent": psutil.cpu_percent(interval=0.2),
        "ram_percent": memory.percent, "ram_available_gb": round(memory.available / 1024**3, 2),
        "disk_percent": disk.percent, "disk_free_gb": round(disk.free / 1024**3, 2),
        "battery": None if battery is None else {"percent": battery.percent, "plugged_in": battery.power_plugged},
        "temperature_sensor_groups": temp_names,
        "notice": "Read-only diagnostics; no settings or processes were changed."
    }


def power_advice():
    """Return energy recommendations without changing Windows power settings."""
    import psutil
    battery = psutil.sensors_battery()
    if battery is None:
        return {"ok": True, "available": False, "message": "No battery telemetry is available; this may be a desktop PC."}
    suggestions = []
    if not battery.power_plugged and battery.percent <= 25:
        suggestions.extend(["Enable Windows Battery Saver if appropriate.", "Reduce screen brightness and close unnecessary high-CPU apps."])
    elif battery.power_plugged:
        suggestions.append("AC power is connected; keep ventilation clear during sustained workloads.")
    else:
        suggestions.append("Battery level is healthy; use Windows power mode appropriate to your workload.")
    return {"ok": True, "battery_percent": battery.percent, "plugged_in": battery.power_plugged,
            "suggestions": suggestions, "changed_settings": False}


def navigation_guidance(current_heading_deg, target_bearing_deg, distance_m=None, speed_mps=None):
    """Give basic compass-relative navigation cues from supplied telemetry."""
    heading = _number(current_heading_deg, "current_heading_deg") % 360
    bearing = _number(target_bearing_deg, "target_bearing_deg") % 360
    delta = (bearing - heading + 540) % 360 - 180
    turn = "continue straight" if abs(delta) < 12 else ("turn right" if delta > 0 else "turn left")
    result = {"ok": True, "current_heading_deg": round(heading, 1),
              "target_bearing_deg": round(bearing, 1), "relative_turn_deg": round(delta, 1),
              "guidance": turn,
              "notice": "Compass guidance only; it does not access GPS, control a vehicle, or replace road/aviation navigation."}
    if distance_m is not None:
        distance = _number(distance_m, "distance_m")
        if distance < 0:
            raise ValueError("distance_m cannot be negative.")
        result["distance_m"] = round(distance, 1)
        if speed_mps is not None:
            speed = _number(speed_mps, "speed_mps")
            if speed <= 0:
                raise ValueError("speed_mps must be positive.")
            result["estimated_travel_seconds"] = round(distance / speed, 1)
    return result


def emergency_guidance(scenario):
    """Provide conservative first-response reminders; never contacts anyone."""
    key = str(scenario).strip().lower()
    guides = {
        "fire": ["Alert people nearby and evacuate using a safe exit.", "Do not use elevators.", "Call the local fire/emergency number from a safe location."],
        "medical": ["Check scene safety and responsiveness.", "Call local emergency services.", "Follow dispatcher instructions; do not move a seriously injured person unless in immediate danger."],
        "road_accident": ["Move to a safe place away from traffic.", "Call local emergency services.", "Do not approach fuel leaks, fire, or unstable vehicles."],
        "intrusion": ["Move to a secure location; do not confront the intruder.", "Contact local police/emergency services when safe.", "Preserve your own safety over property."],
        "severe_weather": ["Move indoors to a sturdy shelter.", "Stay away from windows and floodwater.", "Follow official local weather and emergency alerts."],
        "power_outage": ["Use a flashlight rather than open flames.", "Unplug sensitive equipment if safe.", "Avoid downed wires and report electrical hazards."],
    }
    if key not in guides:
        raise ValueError("Scenario must be one of: " + ", ".join(sorted(guides)))
    return {"ok": True, "scenario": key, "recommended_steps": guides[key],
            "notice": "General safety information only. JARVIS does not call emergency services or verify the scene. Follow local authorities."}
