"""mindol.tools.diegin_search - Auto search & parameter evolution

Genetic algorithm based search for optimizing memory system parameters.
Generates candidates, evaluates, cross-validates, and persists results.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..core import Mindol


SEARCHABLE_PARAMS = {
    "stop_loss_pct": {"type": "float", "range": (0.03, 0.10), "default": 0.07},
    "position_limit_pct": {"type": "float", "range": (0.20, 0.50), "default": 0.30},
    "space_weight_trade": {"type": "float", "range": (1.0, 1.5), "default": 1.3},
    "space_weight_rule": {"type": "float", "range": (1.0, 1.3), "default": 1.15},
    "retrieve_top_k": {"type": "int", "range": (3, 10), "default": 3},
    "keyword_boost_per_hit": {"type": "float", "range": (0.05, 0.20), "default": 0.1},
    "pattern_decay_days": {"type": "int", "range": (5, 14), "default": 7},
    "pattern_decay_per_day": {"type": "float", "range": (0.05, 0.20), "default": 0.1},
}


def load_current_params() -> dict:
    """Get current parameter defaults as starting point."""
    return {k: v["default"] for k, v in SEARCHABLE_PARAMS.items()}


def mutate_params(current: dict, mutation_rate: float = 0.3) -> dict:
    """Mutate current params to generate a candidate."""
    candidate = deepcopy(current)
    for key, spec in SEARCHABLE_PARAMS.items():
        if random.random() < mutation_rate:
            low, high = spec["range"]
            if spec["type"] == "float":
                val = low + random.random() * (high - low)
                candidate[key] = round(val, 2)
            elif spec["type"] == "int":
                candidate[key] = random.randint(int(low), int(high))
    return candidate


def crossover_params(parent_a: dict, parent_b: dict) -> dict:
    """Crossover two candidates."""
    child = {}
    for key in SEARCHABLE_PARAMS:
        child[key] = parent_a[key] if random.random() < 0.5 else parent_b[key]
    return child


def evaluate_candidate(params: dict) -> Tuple[float, List[str]]:
    """Evaluate a candidate parameter set. Higher is better (0-100)."""
    score = 50.0
    reasons = []

    sl = params["stop_loss_pct"]
    if 0.05 <= sl <= 0.08:
        score += 15; reasons.append("stop_loss in optimal range")
    elif sl < 0.05:
        score -= 10; reasons.append("stop_loss too tight")
    else:
        score -= 5; reasons.append("stop_loss too wide")

    pl = params["position_limit_pct"]
    if 0.25 <= pl <= 0.40:
        score += 10; reasons.append("position limit balanced")
    elif pl < 0.25:
        score -= 5; reasons.append("position limit too conservative")
    else:
        score -= 10; reasons.append("position limit too aggressive")

    tw = params["space_weight_trade"]
    rw = params["space_weight_rule"]
    if tw >= rw:
        score += 5; reasons.append("trade weight > rule weight")
    if tw - rw <= 0.3:
        score += 5; reasons.append("trade/rule delta reasonable")

    kw = params["keyword_boost_per_hit"]
    if 0.08 <= kw <= 0.15:
        score += 5; reasons.append("keyword boost reasonable")
    elif kw > 0.15:
        score -= 5; reasons.append("keyword boost too high")

    dd = params["pattern_decay_days"]
    if 5 <= dd <= 10:
        score += 5; reasons.append("decay days reasonable")
    dp = params["pattern_decay_per_day"]
    if 0.08 <= dp <= 0.15:
        score += 5; reasons.append("decay rate reasonable")

    return max(0, min(100, score)), reasons


def run_search(population_size: int = 5, generations: int = 3) -> List[Dict]:
    """Run genetic search for optimal parameters.

    Args:
        population_size: number of candidates per generation
        generations: number of evolution generations

    Returns:
        top-3 candidates with scores and params
    """
    current = load_current_params()
    population = [current] + [mutate_params(current) for _ in range(population_size)]

    for gen in range(generations):
        evaluated = [(evaluate_candidate(p), p) for p in population]
        evaluated.sort(key=lambda x: -x[0][0])
        top3 = [p for _, p in evaluated[:3]]

        next_gen = list(top3)
        while len(next_gen) < population_size + 1:
            pa = random.choice(top3)
            pb = random.choice(top3)
            child = crossover_params(pa, pb)
            child = mutate_params(child, mutation_rate=0.2)
            next_gen.append(child)
        population = next_gen

    final = sorted(
        [(evaluate_candidate(p), p) for p in population],
        key=lambda x: -x[0][0]
    )
    return [
        {"score": score, "params": p, "reasons": reasons}
        for (score, reasons), p in final[:3]
    ]


def write_search_results(results: List[Dict]) -> str:
    """Write search results to memory."""
    core = Mindol()
    date = datetime.now().strftime("%Y%m%d")
    text_lines = [
        f"## Diegin Auto Search Results - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    for i, r in enumerate(results):
        text_lines.append(f"### Candidate {i+1}: Score {r['score']:.0f}/100")
        for k, v in r["params"].items():
            text_lines.append(f"- {k}: {v}")
        if r["reasons"]:
            text_lines.append(f"  Reasons: {', '.join(r['reasons'])}")
        text_lines.append("")

    text = "\n".join(text_lines)
    uid = f"search_result_{date}_{hashlib.md5(text.encode()).hexdigest()[:6]}"
    core.add_unit(
        text=text, source="chat", uid=uid,
        metadata={"type": "search_result", "date": date, "score": results[0]["score"]}
    )
    core.save()
    core.close()
    return uid


if __name__ == "__main__":
    print("=== Diegin Auto Search ===")
    results = run_search(population_size=5, generations=3)
    for i, r in enumerate(results):
        print(f"\nCandidate {i+1}: Score {r['score']:.0f}/100")
        for k, v in r["params"].items():
            print(f"  {k}: {v}")
    uid = write_search_results(results)
    print(f"\nSaved to memory: {uid}")
