"""Safe Ultron-inspired planning, resilience and simulated fleet utilities.

This module deliberately has no network client, shell execution, self-replication,
code rewriting, device driver, or physical actuator.
"""
import re
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
