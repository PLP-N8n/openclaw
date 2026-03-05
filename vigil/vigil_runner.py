#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

CORE_DIR = Path(__file__).resolve().parents[1]
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from learning.raise_loop import load_recent_events
from vigil.guarded_patch import generate_patch_suggestion, mark_patch_readiness, run_sandbox_check
from vigil.rbt_analyzer import classify_rbt


def run_vigil_cycle(since_hours: int = 24) -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    paths = [
        str(logs_dir / "maintenance-runs.jsonl"),
        str(logs_dir / "maintenance-failures.jsonl"),
        str(logs_dir / "config-drift.jsonl"),
        str(logs_dir / "msv-runs.jsonl"),
    ]

    state_trace = []
    events = load_recent_events(paths, since_hours)
    state_trace.append({"step": "load_events", "ok": True, "count": len(events)})
    rbt = classify_rbt(events)
    state_trace.append({"step": "classify_rbt", "ok": True, "thorns": len(rbt.get("thorns", []))})
    top_thorn = (rbt.get("thorns") or [None])[0]
    state_trace.append({"step": "pick_top_thorn", "ok": bool(top_thorn), "top_thorn": top_thorn})

    patch = None
    sandbox = None
    guarded_patch = None
    if top_thorn:
        patch = generate_patch_suggestion(top_thorn)
        state_trace.append({"step": "generate_patch", "ok": True, "patch_id": patch.get("id")})
        sandbox = run_sandbox_check(patch)
        state_trace.append({"step": "sandbox_check", "ok": bool(sandbox.get("ok")), "checks": sandbox.get("checks", {})})
        guarded_patch = mark_patch_readiness(patch, sandbox)
        state_trace.append({"step": "mark_readiness", "ok": bool(guarded_patch.get("ready")), "risk": guarded_patch.get("risk")})

    cycle = {
        "event": "vigil_cycle",
        "ts": datetime.now(timezone.utc).isoformat(),
        "since_hours": since_hours,
        "event_count": len(events),
        "rbt": rbt,
        "top_thorn": top_thorn,
        "patch": guarded_patch,
        "state_trace": state_trace,
    }

    out = logs_dir / "vigil-cycles.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(cycle, ensure_ascii=True) + "\n")

    return cycle


if __name__ == "__main__":
    print(json.dumps(run_vigil_cycle(), ensure_ascii=True))
