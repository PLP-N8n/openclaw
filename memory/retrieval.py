#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path
from typing import Any, Dict, List

import yaml

from vector_store import get_store


def _load_policy() -> Dict[str, Any]:
    path = Path(__file__).with_name("retrieval-policy.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _fingerprint(row: Dict[str, Any]) -> str:
    base = f"{row.get('source','')}::{row.get('chunk_id','')}::{row.get('text','')}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _decay_weight(ts: float, half_life_days: int, min_weight: float) -> float:
    age_days = max(0.0, (time.time() - float(ts or 0.0)) / 86400.0)
    weight = 0.5 ** (age_days / max(1.0, float(half_life_days)))
    return max(min_weight, weight)


def retrieve_context(query: str, task_type: str = "decision") -> List[Dict[str, Any]]:
    policy = _load_policy().get("retrieval", {})
    top_k = int(policy.get("top_k", 12))
    dedupe = bool((policy.get("dedupe") or {}).get("enabled", True))
    decay_cfg = policy.get("decay") or {}
    decay_on = bool(decay_cfg.get("enabled", True))
    half_life = int(decay_cfg.get("half_life_days", 14))
    min_weight = float(decay_cfg.get("min_weight", 0.2))

    store = get_store()
    rows = store.search(query, top_k=top_k)

    scored: List[Dict[str, Any]] = []
    seen = set()
    for r in rows:
        if task_type and r.get("task_type") and r.get("task_type") != task_type:
            continue
        fp = r.get("fingerprint") or _fingerprint(r)
        if dedupe and fp in seen:
            continue
        seen.add(fp)

        score = float(r.get("score", 0.0))
        if decay_on:
            score = score * _decay_weight(float(r.get("ts", 0.0)), half_life, min_weight)
        r["final_score"] = round(score, 6)
        r["fingerprint"] = fp
        scored.append(r)

    scored.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
    return scored


if __name__ == "__main__":
    out = retrieve_context("what failed in maintenance and why", task_type="ops")
    for row in out[:5]:
        print(row)
