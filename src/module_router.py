"""Deterministic lightweight routing hints for JARVIS subsystem selection."""
import re

MODULE_RULES = {
    "ULTRON": (r"\\b(ultron|strategic plan|self improvement|self-improvement|fleet simulation|robot fleet|resilience check|adaptive defense|improvement proposal)\\b",),
    "MORPHEUS": (
        r"\b(cve|vulnerabilit|exploit|firewall|defender|malware|security scan|tls|https scan|port scan|cyber|network audit)\b",
    ),
    "E.V.": (
        r"\b(camera|face profile|face recognition|biometric|heart rate|spo2|microphone sample|sound level|public alert|wearable|opencv|vision sensor)\b",
    ),
    "F.R.I.D.A.Y.": (
        r"\b(track|tracking|movement|motion|predict|trajectory|hazard|threat|tactical|navigation|bearing|emergency|safety signal|power advice|diagnostic)\b",
    ),
    "JARVIS": (
        r"\b(open|launch|find file|search file|click|type|desktop|window|screen|screenshot|voice|remember|forget|chat|summari[sz]e|write|explain)\b",
    ),
}


def route_request(text):
    """Return advisory module routing; the LLM still chooses actual available tools."""
    query = str(text or "").strip().lower()
    selected = [
        module for module, patterns in MODULE_RULES.items()
        if any(re.search(pattern, query, re.IGNORECASE) for pattern in patterns)
    ]
    if not selected:
        selected = ["JARVIS"]
    # Main assistant is always the coordinator, not a separate model.
    return {
        "coordinator": "JARVIS",
        "modules": selected,
        "hint": "JARVIS coordinates this request. Delegate relevant work to: "
                + ", ".join(selected)
                + ". Use only registered tools and their existing approval checks.",
    }
