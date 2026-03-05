#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml


def load_policy(path: str | None = None) -> Dict[str, Any]:
    p = Path(path) if path else Path(__file__).with_name("spend-governor.yaml")
    if not p.exists():
        return {
            "policy": {
                "daily_cap_usd": 5.0,
                "near_limit_ratio": 0.85,
                "cloud_only_for_high_stakes": True,
                "downgrade_lane_when_near": "local-strong",
                "downgrade_lane_when_capped": "local-fast",
            },
            "batch_mode": {"heavy_token_threshold": 12000, "heavy_task_types": []},
        }
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _parse_ts(raw: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def load_daily_spend(log_path: str, now: datetime | None = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    p = Path(log_path)
    if not p.exists():
        return {"daily_spend_usd": 0.0, "entries": 0, "status": "NO_DATA"}

    spend = 0.0
    entries = 0
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        ts = _parse_ts(row.get("ts"))
        if ts is None:
            continue
        if ts.date() != now.date():
            continue
        entries += 1
        spend += float(row.get("cost_usd", 0.0) or 0.0)

    return {"daily_spend_usd": round(spend, 4), "entries": entries, "status": "OK" if entries > 0 else "NO_DATA"}


def spend_state(spend_info: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    p = policy.get("policy", {})
    cap = float(p.get("daily_cap_usd", 5.0) or 5.0)
    near_ratio = float(p.get("near_limit_ratio", 0.85) or 0.85)
    spend = float(spend_info.get("daily_spend_usd", 0.0) or 0.0)

    near_threshold = cap * near_ratio
    status = "OK"
    if spend >= cap:
        status = "CAPPED"
    elif spend >= near_threshold:
        status = "NEAR_LIMIT"

    return {
        "status": status,
        "daily_spend_usd": round(spend, 4),
        "daily_cap_usd": cap,
        "near_limit_threshold_usd": round(near_threshold, 4),
        "utilization": round((spend / cap) if cap > 0 else 0.0, 4),
        "entries": int(spend_info.get("entries", 0) or 0),
    }


def should_force_batch(task_type: str, estimated_tokens: int, policy: Dict[str, Any]) -> bool:
    b = policy.get("batch_mode", {})
    threshold = int(b.get("heavy_token_threshold", 12000) or 12000)
    heavy_types = set(str(x) for x in (b.get("heavy_task_types", []) or []))
    return int(estimated_tokens or 0) >= threshold or str(task_type or "") in heavy_types


def cloud_allowed(risk: str, state: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    p = policy.get("policy", {})
    cloud_high_only = bool(p.get("cloud_only_for_high_stakes", True))
    if state.get("status") == "CAPPED":
        return False
    if cloud_high_only and str(risk).lower() != "high":
        return False
    return True


def apply_spend_governor(
    lane: Dict[str, Any],
    risk: str,
    task_type: str,
    estimated_tokens: int,
    spend_state_obj: Dict[str, Any],
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(lane)
    p = policy.get("policy", {})

    provider = str(out.get("provider", "")).lower()
    is_cloud = provider not in {"ollama", "local"}

    if is_cloud and not cloud_allowed(risk, spend_state_obj, policy):
        if spend_state_obj.get("status") == "CAPPED":
            out["name"] = p.get("downgrade_lane_when_capped", "local-fast")
        else:
            out["name"] = p.get("downgrade_lane_when_near", "local-strong")
        out["provider"] = "ollama"
        out["model"] = "llama3.1:8b" if out["name"] == "local-strong" else "qwen2.5:3b"
        out["downgraded_by_spend_governor"] = True

    if should_force_batch(task_type, estimated_tokens, policy):
        out["execution_mode"] = "batch"
        out["forced_batch_mode"] = True
    else:
        out["execution_mode"] = "online"
        out["forced_batch_mode"] = False

    out["spend_state"] = spend_state_obj
    out["risk"] = risk
    out["task_type"] = task_type
    out["estimated_tokens"] = int(estimated_tokens or 0)
    return out


def daily_governor_impact(log_path: str, now: datetime | None = None) -> Dict[str, int]:
    now = now or datetime.now(timezone.utc)
    p = Path(log_path)
    if not p.exists():
        return {"downgrades_triggered": 0, "cloud_calls_blocked": 0}

    downgrades = 0
    cloud_blocked = 0
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        ts = _parse_ts(row.get("ts"))
        if ts is None or ts.date() != now.date():
            continue
        if bool(row.get("downgraded_by_spend_governor")):
            downgrades += 1
        if bool(row.get("cloud_call_blocked")):
            cloud_blocked += 1

    return {"downgrades_triggered": downgrades, "cloud_calls_blocked": cloud_blocked}
