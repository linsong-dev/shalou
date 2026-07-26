"""mindol.tools.update_decision_log - Decision logging

Records decision outcomes to memory for later review and pattern analysis.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core import Mindol


def _default_core() -> Mindol:
    return Mindol()


def write_decision_log(
    task_type: str,
    query: str,
    decision: str,
    outcome: str = "",
    context: str = "",
    metadata: Dict = None,
) -> str:
    """Write a decision log entry to memory.

    Args:
        task_type: type of task (e.g. "trade", "analysis", "code_review")
        query: original query or trigger
        decision: what was decided
        outcome: result of the decision
        context: additional context
        metadata: optional metadata dict

    Returns:
        uid of the saved log entry
    """
    core = _default_core()
    ts = datetime.now()
    date = ts.strftime("%Y%m%d")
    timestamp = ts.strftime("%Y-%m-%d %H:%M:%S")

    text = (
        f"[Decision Log] {task_type}\n"
        f"Time: {timestamp}\n"
        f"Query: {query[:300]}\n"
        f"Decision: {decision[:500]}\n"
        f"Outcome: {outcome[:200]}\n"
        f"Context: {context[:300]}"
    )

    uid = f"decision_{date}_{hash(text) % 10000:04d}"
    meta = {
        "type": "decision_log",
        "task_type": task_type,
        "timestamp": timestamp,
        "date": date,
        **(metadata or {}),
    }

    unit = core.add_unit(
        text=text,
        source="chat",
        uid=uid,
        space="codex",
        metadata=meta,
    )
    core.save()
    core.close()
    return unit.uid


def get_recent_decisions(days: int = 7, task_type: str = None) -> List[Dict]:
    """Retrieve recent decision logs.

    Args:
        days: how many days back to search
        task_type: optional filter by task type

    Returns:
        list of decision log entries
    """
    core = _default_core()
    query = "decision log"
    if task_type:
        query = f"{task_type} decision log"

    results = core.retrieve(query, top_k=20, spaces=["codex"])
    core.close()

    entries = []
    for unit, score in results:
        meta = unit.metadata
        if meta.get("type") != "decision_log":
            continue
        if task_type and meta.get("task_type") != task_type:
            continue
        entries.append({
            "uid": unit.uid,
            "text": unit.text[:500],
            "timestamp": meta.get("timestamp", ""),
            "task_type": meta.get("task_type", ""),
            "score": round(float(score), 3),
        })
    return entries


def get_decision_stats() -> Dict[str, Any]:
    """Get summary statistics of all decision logs."""
    core = _default_core()
    results = core.retrieve("decision log", top_k=100, spaces=["codex"])
    core.close()

    total = 0
    by_type: Dict[str, int] = {}

    for unit, _ in results:
        meta = unit.metadata
        if meta.get("type") == "decision_log":
            total += 1
            tt = meta.get("task_type", "unknown")
            by_type[tt] = by_type.get(tt, 0) + 1

    return {"total_entries": total, "by_task_type": by_type}
