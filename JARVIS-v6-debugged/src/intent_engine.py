"""Tiny, trainable JARVIS intent model using only the Python standard library.

This is a specialized intent router, not a general-purpose language model.
It never executes actions; it adds a routing hint to the main assistant.
"""
import math
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jarvis_memory.sqlite3"
SEED = {
    "system": ["show system status", "how much ram is being used", "check cpu usage", "what processes are running", "is my pc slow"],
    "automation": ["open notepad", "open calculator", "click the save button", "type this into the text field", "control my desktop"],
    "vision": ["look at my screen", "what is on my display", "analyze this window", "inspect the screen"],
    "voice": ["listen to me", "start voice input", "hey jarvis", "speak your answer"],
    "security": ["check for suspicious activity", "scan my computer for threats", "help secure my pc", "cybersecurity status"],
    "memory": ["remember this preference", "what did i ask yesterday", "recall my previous task", "forget that saved preference"],
    "general": ["explain this concept", "help me plan a project", "write a message", "hello jarvis"],
}


def _tokens(text):
    return re.findall(r"[a-z0-9_]+", str(text).casefold())


def _training_data():
    samples = [(label, phrase) for label, phrases in SEED.items() for phrase in phrases]
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as con:
        con.execute("CREATE TABLE IF NOT EXISTS intent_feedback (id INTEGER PRIMARY KEY, phrase TEXT NOT NULL, label TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        samples.extend((label, phrase) for phrase, label in con.execute("SELECT phrase,label FROM intent_feedback"))
    return samples


def classify(text):
    samples = _training_data()
    vocabulary = set()
    counts = defaultdict(Counter)
    totals = Counter()
    docs = Counter()
    for label, phrase in samples:
        tokens = _tokens(phrase)
        docs[label] += 1
        totals[label] += len(tokens)
        counts[label].update(tokens)
        vocabulary.update(tokens)
    words = _tokens(text)
    if not words:
        return {"intent": "general", "confidence": 0.0, "hint": "General conversation"}
    scores = {}
    total_docs = sum(docs.values())
    for label in docs:
        score = math.log(docs[label] / total_docs)
        for word in words:
            score += math.log((counts[label][word] + 1) / (totals[label] + max(1, len(vocabulary))))
        scores[label] = score
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    margin = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else 0
    confidence = 1 / (1 + math.exp(-max(-30, min(30, margin))))
    label = ranked[0][0] if confidence >= 0.55 else "general"
    return {"intent": label, "confidence": round(confidence, 3), "hint": f"Likely request category: {label}. Treat this as a weak hint; follow the user's actual request."}


def learn(phrase, label):
    phrase = str(phrase).strip()[:500]
    label = str(label).strip().lower()
    if not phrase or label not in SEED:
        raise ValueError(f"Provide a phrase and one label from: {', '.join(SEED)}")
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as con:
        con.execute("CREATE TABLE IF NOT EXISTS intent_feedback (id INTEGER PRIMARY KEY, phrase TEXT NOT NULL, label TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        con.execute("INSERT INTO intent_feedback(phrase,label) VALUES(?,?)", (phrase, label))
    return {"ok": True, "learned": phrase, "intent": label}
