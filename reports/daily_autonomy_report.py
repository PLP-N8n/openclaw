#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
CORE = ROOT / "bhairav-core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from gateway.spend_governor import daily_governor_impact, load_daily_spend, load_policy, spend_state


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    return rows


def _parse_ts(raw: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _mttr_minutes() -> float | None:
    failures = _read_jsonl(LOGS / "maintenance-failures.jsonl")
    runs = _read_jsonl(LOGS / "maintenance-runs.jsonl")
    if not failures:
        return None

    deltas: List[float] = []
    for f in failures[-30:]:
        task = f.get("task")
        f_ts = _parse_ts(f.get("ts"))
        if not task or f_ts is None:
            continue
        for r in runs:
            if r.get("task") == task and str(r.get("status")) == "OK":
                r_ts = _parse_ts(r.get("ts"))
                if r_ts and r_ts > f_ts:
                    deltas.append((r_ts - f_ts) / 60.0)
                    break

    if not deltas:
        return None
    return round(sum(deltas) / len(deltas), 2)


def _pass_at_2() -> float:
    path = CORE / "benchmarks" / "weekly-summary.json"
    if not path.exists():
        return 0.0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return float(payload.get("pass_at_2", 0.0) or 0.0)
    except Exception:
        return 0.0


def _msv_hold_rate() -> float:
    rows = _read_jsonl(LOGS / "msv-runs.jsonl")
    if not rows:
        return 0.0
    holds = sum(1 for r in rows if r.get("needs_clarification") is True)
    return round(holds / len(rows), 4)


def _token_usage() -> Dict[str, float]:
    rows = _read_jsonl(LOGS / "model-usage.jsonl")
    prompt = sum(int(r.get("prompt_tokens", 0) or 0) for r in rows)
    completion = sum(int(r.get("completion_tokens", 0) or 0) for r in rows)
    cost = sum(float(r.get("cost_usd", 0.0) or 0.0) for r in rows)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cost_usd": round(cost, 4),
    }


def _pending_clarifications() -> int:
    path = ROOT / "knowledge" / "shared-mental-model.yaml"
    if not path.exists():
        return 0
    try:
        model = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = model.get("pending_clarifications", [])
        return len(entries) if isinstance(entries, list) else 0
    except Exception:
        return 0


def _top_failures() -> List[Dict[str, Any]]:
    fails = _read_jsonl(LOGS / "maintenance-failures.jsonl")[-200:]
    c = Counter(str(r.get("task") or "unknown") for r in fails)
    return [{"pattern": k, "count": v} for k, v in c.most_common(5)]


def _top_improvements() -> List[Dict[str, Any]]:
    proposals_dir = CORE / "learning" / "proposals"
    if not proposals_dir.exists():
        return []
    files = sorted(proposals_dir.glob("raise-proposals-*.jsonl"))
    if not files:
        return []
    rows = _read_jsonl(files[-1])
    out = []
    for r in rows[:5]:
        out.append({"pattern": str(r.get("category", "unknown")), "count": 1})
    return out


def _spend_governor_summary() -> Dict[str, Any]:
    policy = load_policy(str(CORE / "gateway" / "spend-governor.yaml"))
    spend = load_daily_spend(str(LOGS / "model-usage.jsonl"))
    state = spend_state(spend, policy)
    impact = daily_governor_impact(str(LOGS / "spend-governor-routing.jsonl"))
    return {
        "spend_used_today": state.get("daily_spend_usd", 0.0),
        "cap": state.get("daily_cap_usd", 0.0),
        "downgrades_triggered": impact.get("downgrades_triggered", 0),
        "cloud_calls_blocked": impact.get("cloud_calls_blocked", 0),
    }


def collect_kpis() -> Dict[str, Any]:
    return {
        "pass_at_2": _pass_at_2(),
        "mttr_minutes": _mttr_minutes(),
        "msv_hold_rate": _msv_hold_rate(),
        "token_usage": _token_usage(),
        "pending_clarifications": _pending_clarifications(),
        "top_failures": _top_failures(),
        "top_improvements": _top_improvements(),
        "spend_governor_summary": _spend_governor_summary(),
    }


def render_text_report(kpis: Dict[str, Any]) -> str:
    lines = [
        "# Daily Autonomy Report",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        f"- pass_at_2: {kpis.get('pass_at_2')}",
        f"- mttr_minutes: {kpis.get('mttr_minutes')}",
        f"- msv_hold_rate: {kpis.get('msv_hold_rate')}",
        f"- token_usage: {json.dumps(kpis.get('token_usage', {}), ensure_ascii=True)}",
        f"- pending_clarifications: {kpis.get('pending_clarifications')}",
        f"- top_failures: {json.dumps(kpis.get('top_failures', []), ensure_ascii=True)}",
        f"- top_improvements: {json.dumps(kpis.get('top_improvements', []), ensure_ascii=True)}",
        f"- spend_governor: {json.dumps(kpis.get('spend_governor_summary', {}), ensure_ascii=True)}",
        "",
    ]
    return "\n".join(lines)


def write_daily_report(kpis: Dict[str, Any], out_dir: str) -> str:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = d / f"daily-autonomy-{stamp}.md"
    path.write_text(render_text_report(kpis), encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    k = collect_kpis()
    out = write_daily_report(k, str(CORE / "reports" / "out"))
    print(json.dumps({"kpis": k, "report": out}, ensure_ascii=True))
