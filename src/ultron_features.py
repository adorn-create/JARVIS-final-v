"""Safe Ultron-inspired planning, resilience and simulated fleet utilities.

This module deliberately has no network client, shell execution, self-replication,
code rewriting, device driver, or physical actuator.
"""
import re
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psutil


CAPABILITIES = {
    "superintelligence": "Use the configured local LLM for reasoning, planning and research; results remain fallible.",
    "self_improvement": "Generate reviewable improvement proposals; no automatic source-code edits.",
    "digital_infiltration": "Use MORPHEUS defensive checks only on explicitly authorized lab/private targets.",
    "robotics": "Simulate robotics commands; physical actuators require a separately reviewed, safety-rated integration.",
    "robot_army": "Simulate a fleet of virtual units; no self-replicating agents or weapon functions.",
    "distributed_presence": "Prepare a model for authenticated, owner-enrolled nodes; no remote agent deployment is included.",
    "strategic_analysis": "Break a stated goal into bounded steps, risks and approval points.",
    "adaptation": "Turn user feedback into reviewable rule/model-training suggestions.",
    "durability": "Monitor local system health and recommend recovery; no hardware repair or destructive changes.",
    "autonomous_operation": "Prepare bounded task plans; execution remains subject to existing approvals and user control.",
}


def capability_report():
    return {
        "system": "ULTRON-inspired safe subsystem",
        "capabilities": CAPABILITIES,
        "implemented_now": [
            "local reasoning through existing JARVIS model",
            "bounded strategic planning",
            "review-only improvement proposals",
            "feedback-to-training suggestions",
            "virtual robotics/fleet simulation",
            "read-only host resilience diagnostics",
            "approval-gated task autonomy design",
            "authorized defensive security through MORPHEUS",
        ],
        "not_enabled": [
            "self-replicating code or agents",
            "unauthorized access or exploit execution",
            "weapon control or targeting",
            "unattended physical robot actuation",
            "automatic source-code rewriting",
            "remote deployment to unverified devices",
        ],
        "note": "These are safe software analogues, not Marvel-level superintelligence or physical robotics.",
    }


def strategic_plan(goal):
    goal = re.sub(r"\\s+", " ", str(goal or "")).strip()
    if not goal or len(goal) > 500:
        raise ValueError("Goal must contain 1 to 500 characters.")
    return {
        "goal": goal,
        "plan": [
            {"step": "Clarify success criteria and authorized scope", "approval": "user confirmation"},
            {"step": "Collect only the minimum required local or public information", "approval": "before external access"},
            {"step": "Analyze options, dependencies and failure modes", "approval": "none for read-only analysis"},
            {"step": "Prepare a reversible implementation or action plan", "approval": "review required"},
            {"step": "Execute only allowlisted actions with per-action approval", "approval": "required"},
            {"step": "Verify outcomes and report unresolved risks", "approval": "none for read-only verification"},
        ],
        "safety": "Planning only; this function does not execute commands, access devices, or contact external systems.",
    }


def _plan_store_path():
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "ultron_plans.json"


def _load_saved_plans():
    path = _plan_store_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read ULTRON plan store: {exc}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("ULTRON plan store has an invalid format.")
    return payload[-50:]


def _write_saved_plans(plans):
    path = _plan_store_path()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(plans[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def save_strategy_plan(goal):
    """Persist an explicitly requested advisory plan; no steps are executed."""
    result = strategic_plan(goal)
    plans = _load_saved_plans()
    item = {
        "plan_id": uuid.uuid4().hex[:12],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "goal": result["goal"],
        "status": "proposed",
        "steps": [
            {**step, "status": "pending"}
            for step in result["plan"]
        ],
        "safety": result["safety"],
    }
    plans.append(item)
    _write_saved_plans(plans)
    return {
        "ok": True,
        "saved_plan": item,
        "storage": "local project data/ultron_plans.json",
        "note": "Saved for review only. ULTRON does not execute plan steps automatically.",
    }


def list_saved_plans():
    plans = _load_saved_plans()
    return {
        "ok": True,
        "count": len(plans),
        "plans": [
            {
                "plan_id": item.get("plan_id"),
                "created_at": item.get("created_at"),
                "goal": item.get("goal"),
                "status": item.get("status"),
                "completed_steps": sum(1 for step in item.get("steps", []) if step.get("status") == "completed"),
                "total_steps": len(item.get("steps", [])),
            }
            for item in plans
        ],
        "note": "Local advisory plan history only; no background execution.",
    }


def update_saved_plan_step(plan_id, step_index, status):
    """Manually update review progress; this does not execute the selected step."""
    plan_id = str(plan_id or "").strip()
    try:
        step_index = int(step_index)
    except (TypeError, ValueError) as exc:
        raise ValueError("step_index must be an integer.") from exc
    status = str(status or "").strip().lower()
    if status not in {"pending", "in_progress", "completed", "blocked"}:
        raise ValueError("status must be pending, in_progress, completed, or blocked.")
    plans = _load_saved_plans()
    item = next((entry for entry in plans if entry.get("plan_id") == plan_id), None)
    if item is None:
        raise ValueError("Saved ULTRON plan was not found.")
    if not 0 <= step_index < len(item.get("steps", [])):
        raise ValueError("step_index is outside the saved plan.")
    item["steps"][step_index]["status"] = status
    statuses = [step.get("status") for step in item.get("steps", [])]
    item["status"] = "completed" if statuses and all(value == "completed" for value in statuses) else "in_progress"
    if "blocked" in statuses:
        item["status"] = "blocked"
    _write_saved_plans(plans)
    return {
        "ok": True, "plan_id": plan_id, "step_index": step_index,
        "step_status": status, "plan_status": item["status"],
        "note": "Progress metadata updated only; no task or command was executed.",
    }


def review_improvement(area, feedback):
    area = str(area or "").strip()[:100]
    feedback = str(feedback or "").strip()[:1000]
    if not area or not feedback:
        raise ValueError("Provide a subsystem area and feedback.")
    return {
        "proposal": {
            "area": area,
            "observation": feedback,
            "suggested_change": "Create a small, testable change behind the existing interface; add regression tests and preserve current features.",
            "validation": ["review diff", "run unit tests", "measure RAM/CPU", "verify rollback"],
        },
        "status": "PROPOSAL ONLY — no source files or model weights were modified.",
    }


def simulate_fleet(command, unit_count=3):
    command = str(command or "").strip().lower()
    allowed = {"status", "standby", "return_to_base", "formation_demo", "sensor_check"}
    if command not in allowed:
        raise ValueError("Simulation command must be one of: " + ", ".join(sorted(allowed)))
    try:
        unit_count = int(unit_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("unit_count must be an integer from 1 to 20.") from exc
    if not 1 <= unit_count <= 20:
        raise ValueError("unit_count must be an integer from 1 to 20.")
    return {
        "simulation": True,
        "command": command,
        "units": [{"id": f"SIM-{i:02d}", "result": "simulated"} for i in range(1, unit_count + 1)],
        "physical_devices_contacted": False,
        "note": "Virtual demonstration only; no network connections or physical actuators.",
    }


def resilience_check():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(psutil.disk_partitions(all=False)[0].mountpoint)
    battery = psutil.sensors_battery()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "ram_percent": memory.percent,
        "ram_available_gb": round(memory.available / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "battery": None if battery is None else {
            "percent": battery.percent, "plugged_in": battery.power_plugged
        },
        "recommendations": [
            "Keep at least one tested backup before changing project files.",
            "Prefer reversible updates and retain the previous working version.",
            "Stop optional camera, microphone and vision tasks when not needed.",
        ],
        "read_only": True,
    }
