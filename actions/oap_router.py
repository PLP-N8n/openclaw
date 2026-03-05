#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _priority_from_risk(risk: str) -> str:
    r = str(risk).lower()
    if r == "high":
        return "P1"
    if r == "med":
        return "P2"
    return "P3"


def to_oap(insight: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    deadline = (now + timedelta(days=1)).replace(microsecond=0).isoformat()

    risk = str(insight.get("risk") or insight.get("risk_level") or "med").lower()
    priority = str(insight.get("priority") or _priority_from_risk(risk)).upper()

    evidence = insight.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = [str(evidence)]

    return {
        "outcome": str(insight.get("outcome") or insight.get("summary") or "improve runtime reliability"),
        "action": str(insight.get("action") or insight.get("recommended_change") or "investigate and patch"),
        "owner": str(insight.get("owner") or "bhairav"),
        "deadline": str(insight.get("deadline") or deadline),
        "evidence": [str(x) for x in evidence if str(x).strip()],
        "priority": priority if priority in {"P1", "P2", "P3"} else "P2",
        "status": str(insight.get("status") or "open"),
    }


def validate_oap(oap: Dict[str, Any], schema_path: str) -> Tuple[bool, str]:
    required = ["outcome", "action", "owner", "deadline", "evidence", "priority", "status"]
    for key in required:
        if key not in oap:
            return False, f"missing field: {key}"

    if oap.get("owner") not in {"bhairav", "gayatri", "hunny"}:
        return False, "owner must be bhairav|gayatri|hunny"
    if oap.get("priority") not in {"P1", "P2", "P3"}:
        return False, "priority must be P1|P2|P3"
    if not isinstance(oap.get("evidence"), list) or not oap.get("evidence"):
        return False, "evidence must be a non-empty list"

    try:
        datetime.fromisoformat(str(oap.get("deadline")).replace("Z", "+00:00"))
    except Exception:
        return False, "deadline must be ISO-8601"

    p = Path(schema_path)
    if p.exists():
        try:
            schema = json.loads(p.read_text(encoding="utf-8"))
            req = schema.get("required", []) if isinstance(schema, dict) else []
            for key in req:
                if key not in oap:
                    return False, f"schema required missing: {key}"
        except Exception as exc:
            return False, f"schema load error: {exc}"

    return True, "ok"


def reject_non_actionable(insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ins in insights:
        action = str(ins.get("action") or ins.get("recommended_change") or "").strip()
        outcome = str(ins.get("outcome") or ins.get("summary") or "").strip()
        evidence = ins.get("evidence") or []
        confidence = float(ins.get("confidence", 0.0) or 0.0)
        if not action or not outcome:
            continue
        if not isinstance(evidence, list) or len(evidence) == 0:
            continue
        if confidence < 0.35:
            continue
        out.append(ins)
    return out
