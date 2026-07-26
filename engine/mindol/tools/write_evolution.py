"""mindol.tools.write_evolution - Evolution trajectory logging

Records the evolution process: what changed, why, and the outcome.
Enables cross-session learning by persisting evolutionary steps.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core import Mindol


def _default_core() -> Mindol:
    return Mindol()


def write_evolution(
    change_type: str,
    summary: str,
    detail: str = "",
    before: str = "",
    after: str = "",
    metadata: Dict = None,
) -> str:
    """Record an evolution step to memory.

    Args:
        change_type: type of change (rule_added, pattern_refined, param_tuned, etc.)
        summary: one-line summary of the change
        detail: detailed description
        before: state before the change
        after: state after the change
        metadata: optional metadata

    Returns:
        uid of the saved evolution entry
    """
    core = _default_core()
    ts = datetime.now()
    date = ts.strftime("%Y%m%d")
    timestamp = ts.strftime("%Y-%m-%d %H:%M")

    text = (
        f"[Evolution] {change_type}\n"
        f"Summary: {summary[:200]}\n"
        f"Time: {timestamp}\n"
    )
    if detail:
        text += f"Detail: {detail[:500]}\n"
    if before:
        text += f"Before: {before[:300]}\n"
    if after:
        text += f"After: {after[:300]}\n"

    uid = f"evo_{date}_{hash(text) % 10000:04d}"
    meta = {
        "type": "evolution",
        "change_type": change_type,
        "timestamp": timestamp,
        "date": date,
        **(metadata or {}),
    }

    unit = core.add_unit(
        text=text, source="pattern", uid=uid, space="codex", metadata=meta
    )
    core.save()
    core.close()
    return unit.uid


def get_recent_evolution(days: int = 7) -> List[Dict]:
    """Get recent evolution entries.

    Args:
        days: how many days back

    Returns:
        list of evolution entries sorted by time desc
    """
    core = _default_core()
    results = core.retrieve("evolution", top_k=30, spaces=["codex"])
    core.close()

    entries = []
    for unit, score in results:
        meta = unit.metadata
        if meta.get("type") != "evolution":
            continue
        entries.append({
            "uid": unit.uid,
            "summary": unit.text[:300],
            "change_type": meta.get("change_type", ""),
            "timestamp": meta.get("timestamp", ""),
            "score": round(float(score), 3),
        })

    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return entries
