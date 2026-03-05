#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
CORE = ROOT / "bhairav-core"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except Exception:
            continue
    return out


def _parse_ts(raw: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def mttr_hours() -> float | None:
    fails = _read_jsonl(LOGS / "maintenance-failures.jsonl")
    runs = _read_jsonl(LOGS / "maintenance-runs.jsonl")
    if not fails:
        return None

    recovered_deltas = []
    for f in fails[-30:]:
        f_task = f.get("task")
        f_ts = _parse_ts(f.get("ts"))
        if f_ts is None:
            continue
        for r in runs:
            if r.get("task") == f_task and str(r.get("status")) == "OK":
                r_ts = _parse_ts(r.get("ts"))
                if r_ts is not None and r_ts > f_ts:
                    recovered_deltas.append((r_ts - f_ts) / 3600.0)
                    break
    if not recovered_deltas:
        return None
    return round(sum(recovered_deltas) / len(recovered_deltas), 3)


def pass_at_2() -> float:
    summary = CORE / "benchmarks" / "weekly-summary.json"
    if summary.exists():
        try:
            return float(json.loads(summary.read_text(encoding="utf-8")).get("pass_at_2", 0.0))
        except Exception:
            return 0.0
    return 0.0


def msv_hold_rate() -> float:
    rows = _read_jsonl(LOGS / "msv-runs.jsonl")
    if not rows:
        return 0.0
    holds = sum(1 for r in rows if r.get("needs_clarification") is True)
    return round(holds / len(rows), 4)


def token_usage() -> Dict[str, float]:
    rows = _read_jsonl(LOGS / "model-usage.jsonl")
    prompt = 0
    completion = 0
    cost = 0.0
    for r in rows[-500:]:
        prompt += int(r.get("prompt_tokens", 0) or 0)
        completion += int(r.get("completion_tokens", 0) or 0)
        cost += float(r.get("cost_usd", 0.0) or 0.0)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "cost_usd": round(cost, 4)}


def pending_clarifications() -> int:
    path = ROOT / "knowledge" / "shared-mental-model.yaml"
    if not path.exists():
        return 0
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = payload.get("pending_clarifications", [])
        return len(entries) if isinstance(entries, list) else 0
    except Exception:
        return 0


def main() -> None:
    snapshot = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mttr_hours": mttr_hours(),
        "pass_at_2": pass_at_2(),
        "msv_hold_rate": msv_hold_rate(),
        "token_usage": token_usage(),
        "pending_clarifications": pending_clarifications(),
    }

    out = CORE / "dashboard" / "latest-kpis.json"
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print("Bhairav KPI Dashboard")
    print(f"MTTR (h): {snapshot['mttr_hours']}")
    print(f"pass@2: {snapshot['pass_at_2']}")
    print(f"msv_hold_rate: {snapshot['msv_hold_rate']}")
    print(f"token_usage: {snapshot['token_usage']}")
    print(f"pending_clarifications: {snapshot['pending_clarifications']}")
    print(f"artifact: {out}")


if __name__ == "__main__":
    main()
