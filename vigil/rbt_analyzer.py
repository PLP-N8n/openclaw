#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List


def _pattern_of(event: Dict[str, Any]) -> str:
    if "task" in event:
        return f"task:{event.get('task')}"
    if "event" in event:
        return f"event:{event.get('event')}"
    if "status_code" in event:
        return f"status_code:{event.get('status_code')}"
    return "unknown"


def extract_patterns(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counter = Counter()
    sev = {}
    for e in events:
        p = _pattern_of(e)
        counter[p] += 1
        status = str(e.get("status", "")).upper()
        exit_code = int(e.get("exit_code", 0) or 0)
        if status in {"FAIL", "ERROR"} or exit_code != 0:
            sev[p] = "high" if counter[p] >= 5 else "med"
        elif status == "WARN":
            sev[p] = "med"
        else:
            sev.setdefault(p, "low")

    out = []
    for p, n in counter.most_common():
        out.append({"pattern": p, "count": n, "severity": sev.get(p, "low")})
    return out


def classify_rbt(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    patterns = extract_patterns(events)

    roses: List[Dict[str, Any]] = []
    buds: List[Dict[str, Any]] = []
    thorns: List[Dict[str, Any]] = []

    for p in patterns:
        pattern = p["pattern"]
        count = int(p["count"])
        severity = p.get("severity", "low")

        if severity == "low" and count >= 2:
            roses.append({"pattern": pattern, "count": count})
        elif severity == "high":
            thorns.append({"pattern": pattern, "count": count, "severity": "high"})
        else:
            buds.append({"pattern": pattern, "count": count})

    return {"roses": roses[:10], "buds": buds[:10], "thorns": thorns[:10]}
