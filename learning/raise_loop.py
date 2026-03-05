#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

CORE_DIR = Path(__file__).resolve().parents[1]
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from learning.evaluator_gate import evaluator_gate, load_constitution


def _parse_ts(raw: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _detect_category(event: Dict[str, Any]) -> str:
    text = json.dumps(event, ensure_ascii=True).lower()
    status = int(event.get("status_code", 0) or 0)
    if status in {429, 500, 502, 503, 504} or "retry" in text:
        return "retry_storm"
    if "schema" in text or "validation" in text:
        return "schema_fail"
    if "routing" in text or "fallback" in text or "provider" in text and "selected" in text:
        return "routing_miss"
    return "provider_error"


def load_recent_events(paths: List[str], since_hours: int) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc).timestamp() - (max(1, since_hours) * 3600)
    rows: List[Dict[str, Any]] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            ts = _parse_ts(row.get("ts") or row.get("timestamp") or row.get("started_at"))
            if ts is None or ts < cutoff:
                continue
            rows.append(row)
    return rows


def cluster_failures(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        status = str(e.get("status", "")).upper()
        exit_code = int(e.get("exit_code", 0) or 0)
        is_failure = status in {"FAIL", "WARN", "ERROR"} or exit_code != 0 or "error" in json.dumps(e).lower()
        if not is_failure:
            continue
        grouped[_detect_category(e)].append(e)

    out: List[Dict[str, Any]] = []
    for cat, rows in grouped.items():
        evidence = []
        for r in rows[:5]:
            ref = str(r.get("task") or r.get("event") or "event")
            ts = str(r.get("ts") or r.get("started_at") or "na")
            evidence.append(f"{ref}@{ts}")
        out.append(
            {
                "category": cat,
                "count": len(rows),
                "events": rows,
                "evidence": evidence,
                "severity_hint": "high" if len(rows) >= 10 else "med" if len(rows) >= 4 else "low",
            }
        )
    out.sort(key=lambda x: x["count"], reverse=True)
    return out


def score_candidate(cluster: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    count = int(cluster.get("count", 0) or 0)
    severity = str(cluster.get("severity_hint", "med"))
    impact_w = float((policy.get("weights") or {}).get("impact", 0.6))
    risk_w = float((policy.get("weights") or {}).get("risk", 0.4))

    impact_base = min(1.0, count / float(policy.get("impact_saturation", 12) or 12))
    sev_bonus = 0.2 if severity == "high" else 0.1 if severity == "med" else 0.0
    impact_score = round(min(1.0, impact_base + sev_bonus), 3)

    risk_map = {"retry_storm": 0.35, "schema_fail": 0.45, "routing_miss": 0.5, "provider_error": 0.55}
    risk_score = round(min(1.0, risk_map.get(cluster.get("category"), 0.5) + sev_bonus / 2), 3)

    confidence = round(max(0.1, min(1.0, 0.4 + (count * 0.05))), 3)
    final_score = round((impact_score * impact_w) + (risk_score * risk_w), 3)

    return {
        **cluster,
        "impact_score": impact_score,
        "risk_score": risk_score,
        "confidence": confidence,
        "final_score": final_score,
    }


def build_proposals(clusters: List[Dict[str, Any]], policy: Dict[str, Any]) -> List[Dict[str, Any]]:
    scored = [score_candidate(c, policy) for c in clusters]
    scored.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
    constitution = load_constitution()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proposals: List[Dict[str, Any]] = []
    for i, c in enumerate(scored, start=1):
        cat = str(c.get("category", "provider_error"))
        recommended_change = {
            "retry_storm": "tighten retry/backoff and open circuit earlier for repeated transient failures",
            "schema_fail": "add strict preflight schema validation before provider call",
            "routing_miss": "adjust model routing thresholds and fallback ordering",
            "provider_error": "add provider-specific error handling and degrade gracefully",
        }.get(cat, "improve failure handling")

        target_file = {
            "retry_storm": "bhairav-core/gateway/retry_backoff.py",
            "schema_fail": "bhairav-core/actions/oap_router.py",
            "routing_miss": "bhairav-core/routing/model-lanes.yaml",
            "provider_error": "bhairav-core/gateway/litellm-config.yaml",
        }.get(cat, "bhairav-core/README.md")

        proposal = {
            "id": f"raise-{ts}-{i}",
            "category": cat,
            "summary": f"{cat} recurring across {c.get('count', 0)} events",
            "evidence": list(c.get("evidence", []))[:5],
            "impact_score": float(c.get("impact_score", 0.0)),
            "risk_score": float(c.get("risk_score", 0.0)),
            "confidence": float(c.get("confidence", 0.0)),
            "recommended_change": recommended_change,
            "target_file": target_file,
            "status": "proposed",
        }
        approved, reason, scores = evaluator_gate(proposal, constitution)
        proposal["evaluator"] = {"approved": approved, "reason": reason, "scores": scores}
        if not approved:
            proposal["status"] = "rejected_by_evaluator"
        proposals.append(proposal)
    return proposals


def write_proposals(proposals: List[Dict[str, Any]], out_dir: str) -> str:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_path = out_path / f"raise-proposals-{ts}.jsonl"

    with file_path.open("w", encoding="utf-8") as f:
        for p in proposals:
            f.write(json.dumps(p, ensure_ascii=True) + "\n")
    return str(file_path)
