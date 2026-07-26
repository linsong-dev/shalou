"""mindol.tools.track_rule - Rule execution tracker & pattern decay

Records rule/pattern match results into memory spaces.
Supports pattern confidence decay (7-day rule) and health reporting.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..core import Mindol


def _default_core() -> Mindol:
    """Get a Mindol instance with default Codex path."""
    return Mindol()


def track_rule_match(rule_id: str, rule_text: str,
                     matched: bool,
                     context: str = "",
                     decision: str = "",
                     outcome: str = "",
                     severity: str = "medium") -> str:
    """Record a rule match result into memory.

    Args:
        rule_id: rule identifier
        rule_text: rule description
        matched: whether the rule triggered
        context: context at match time
        decision: decision made
        outcome: result of the decision
        severity: rule severity (high/medium/low)

    Returns:
        uid of the saved memory unit
    """
    date = datetime.now().strftime("%Y%m%d")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    if matched:
        text = (
            f"[Rule Triggered] {rule_id}\n"
            f"Rule: {rule_text[:200]}\n"
            f"Context: {context[:200]}\n"
            f"Decision: {decision[:200]}\n"
            f"Outcome: {outcome}\n"
            f"Time: {ts}"
        )
        uid = f"rule_match_{date}_{rule_id[:20]}"
        meta_type = "rule_match"
    else:
        text = (
            f"[Rule Not Triggered] {rule_id}\n"
            f"Rule: {rule_text[:200]}\n"
            f"Context: {context[:200]}\n"
            f"Time: {ts}"
        )
        uid = f"rule_nomatch_{date}_{rule_id[:20]}"
        meta_type = "rule_nomatch"

    core = _default_core()
    core.add_unit(
        text=text, source="rule", uid=uid,
        metadata={"type": meta_type, "rule_id": rule_id,
                  "matched": matched, "date": date, "outcome": outcome}
    )
    _update_rule_health(rule_id, matched, outcome, severity)
    core.save()
    core.close()
    return uid


def track_pattern_match(pattern_id: str, pattern_text: str,
                        matched: bool, context: str = "",
                        confidence_delta: float = 0) -> str:
    """Record pattern match with confidence calibration and decay.

    Decay rules:
    - 7 days no match: start decay (-0.1/day)
    - confidence <= 1.5: status -> decaying
    - confidence <= 1.0: status -> archived
    - re-match: restore to active
    """
    date = datetime.now().strftime("%Y%m%d")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    health_path = _pattern_health_path()
    try:
        with open(health_path, "r", encoding="utf-8") as f:
            phealth = json.load(f)
    except Exception:
        phealth = {}

    if pattern_id not in phealth:
        phealth[pattern_id] = {
            "confidence": 3.0, "match_count": 0,
            "last_matched": today if matched else "",
            "total_decay": 0.0, "status": "active",
        }
    ph = phealth[pattern_id]

    if matched:
        ph["confidence"] = min(5.0, ph["confidence"] + confidence_delta)
        ph["match_count"] += 1
        ph["last_matched"] = today
        ph["total_decay"] = 0.0
        if ph.get("status") in ("decaying",):
            ph["status"] = "active"
        text = (
            f"[Pattern Match] {pattern_id}\n"
            f"Pattern: {pattern_text[:200]}\n"
            f"Context: {context[:200]}\n"
            f"Confidence: {ph['confidence']:.1f}\n"
            f"Status: {ph['status']}\n"
            f"Time: {ts}"
        )
        uid = f"pat_match_{date}_{pattern_id[:20]}"
        meta_type = "pattern_match"
    else:
        if ph.get("last_matched"):
            days_since = (datetime.now() - datetime.strptime(ph["last_matched"], "%Y-%m-%d")).days
            if days_since > 7:
                decay = -0.1 * min(days_since - 7, 30)
                ph["confidence"] = max(1.0, ph["confidence"] + decay)
                ph["total_decay"] = ph.get("total_decay", 0) + abs(decay)
                if ph["confidence"] <= 1.5 and ph.get("status") == "active":
                    ph["status"] = "decaying"
                if ph["confidence"] <= 1.0:
                    ph["status"] = "archived"
        text = (
            f"[Pattern Decay] {pattern_id}\n"
            f"Pattern: {pattern_text[:200]}\n"
            f"Confidence: {ph['confidence']:.1f} | Status: {ph['status']}\n"
            f"Time: {ts}"
        )
        uid = f"pat_decay_{date}_{pattern_id[:20]}"
        meta_type = "pattern_decay"

    os.makedirs(os.path.dirname(health_path), exist_ok=True)
    with open(health_path, "w", encoding="utf-8") as f:
        json.dump(phealth, f, ensure_ascii=False, indent=2)

    core = _default_core()
    core.add_unit(
        text=text, source="pattern", uid=uid,
        metadata={"type": meta_type, "pattern_id": pattern_id,
                  "matched": matched, "date": date,
                  "confidence": ph["confidence"], "status": ph["status"]}
    )
    core.save()
    core.close()
    return uid


def _update_rule_health(rule_id: str, matched: bool, outcome: str, severity: str):
    """Update rule_health.json"""
    health_path = _rule_health_path()
    try:
        with open(health_path, "r", encoding="utf-8") as f:
            health = json.load(f)
    except Exception:
        health = {}

    today = datetime.now().strftime("%Y-%m-%d")
    if rule_id not in health:
        health[rule_id] = {
            "total_matches": 0, "correct": 0, "wrong": 0, "unknown": 0,
            "severity": severity, "daily": {},
        }
    h = health[rule_id]
    h["total_matches"] = h.get("total_matches", 0) + 1
    if outcome == "correct":
        h["correct"] = h.get("correct", 0) + 1
    elif outcome == "wrong":
        h["wrong"] = h.get("wrong", 0) + 1
    else:
        h["unknown"] = h.get("unknown", 0) + 1
    h["last_matched"] = today

    if today not in h["daily"]:
        h["daily"][today] = {"matched": 0, "correct": 0, "wrong": 0}
    h["daily"][today]["matched"] += 1
    if outcome == "correct":
        h["daily"][today]["correct"] += 1
    elif outcome == "wrong":
        h["daily"][today]["wrong"] += 1

    total_decided = h["correct"] + h["wrong"]
    h["accuracy"] = round(h["correct"] / total_decided, 2) if total_decided > 0 else None

    os.makedirs(os.path.dirname(health_path), exist_ok=True)
    with open(health_path, "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)


def _rule_health_path() -> str:
    from ..codex_adapter import _default_storage_path
    return os.path.join(_default_storage_path(), "rule_health.json")


def _pattern_health_path() -> str:
    from ..codex_adapter import _default_storage_path
    return os.path.join(_default_storage_path(), "pattern_health.json")


def generate_health_report() -> str:
    """Generate rule + pattern health report."""
    lines = []
    lines.append(f"## Diegin Health Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    health_path = _rule_health_path()
    try:
        with open(health_path, "r", encoding="utf-8") as f:
            health = json.load(f)
    except Exception:
        health = {}

    if health:
        lines.append("### Rule Health")
        for rid, h in sorted(health.items(), key=lambda x: -x[1].get("total_matches", 0)):
            acc = h.get("accuracy", "N/A")
            days = h.get("days_since_last_match", 0)
            tag = " [PRUNE]" if days > 14 and h.get("total_matches", 0) > 0 else ""
            lines.append(f"- {rid}: {h['total_matches']}x, acc={acc}, idle={days}d{tag}")
        lines.append("")

    phealth_path = _pattern_health_path()
    try:
        with open(phealth_path, "r", encoding="utf-8") as f:
            phealth = json.load(f)
    except Exception:
        phealth = {}

    if phealth:
        lines.append("### Pattern Health")
        for pid, ph in sorted(phealth.items(), key=lambda x: -x[1].get("confidence", 0)):
            s = ph.get("status", "active")
            mark = " [DECAYING]" if s == "decaying" else " [ARCHIVED]" if s == "archived" else ""
            lines.append(f"- {pid}: conf={ph.get('confidence', 0):.1f}, {ph.get('match_count', 0)}x, status={s}{mark}")
        lines.append("")

    lines.append(f"---")
    lines.append(f"Rules: {len(health)}, Patterns: {len(phealth)}")
    return "\n".join(lines)
