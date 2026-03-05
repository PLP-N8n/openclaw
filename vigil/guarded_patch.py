#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _target_for_pattern(pattern: str) -> str:
    p = pattern.lower()
    if "retry" in p or "status_code:429" in p or "status_code:50" in p:
        return "bhairav-core/gateway/retry_backoff.py"
    if "schema" in p:
        return "bhairav-core/actions/oap_router.py"
    if "routing" in p:
        return "bhairav-core/routing/model-lanes.yaml"
    return "bhairav-core/learning/raise_loop.py"


def generate_patch_suggestion(pattern: Dict[str, Any]) -> Dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_file = _target_for_pattern(str(pattern.get("pattern", "")))
    count = int(pattern.get("count", 1) or 1)
    risk = "high" if count >= 10 else "med" if count >= 4 else "low"

    diff_preview = "\n".join(
        [
            f"*** target: {target_file}",
            "@@ suggested change @@",
            "+ add guard condition for recurring failure pattern",
            "+ add structured logging with evidence reference",
            "+ add test case for this failure mode",
        ]
    )

    return {
        "id": f"patch-{ts}-1",
        "target_file": target_file,
        "diff_preview": diff_preview,
        "reason": f"pattern {pattern.get('pattern')} occurred {count} times",
        "risk": risk,
        "ready": False,
    }


def run_sandbox_check(patch: Dict[str, Any]) -> Dict[str, Any]:
    target_file = str(patch.get("target_file", "")).strip()
    root = Path(__file__).resolve().parents[2]
    target_exists = (root / target_file).exists() if target_file else False
    risk = str(patch.get("risk", "low"))

    checks = {
        "has_target_file": bool(target_file),
        "target_exists": target_exists,
        "target_in_core_repo": target_file.startswith("bhairav-core/"),
        "has_diff_preview": bool(str(patch.get("diff_preview", "")).strip()),
        "reason_present": bool(str(patch.get("reason", "")).strip()),
        "risk_allowed": risk in {"low", "med", "high"},
        "high_risk_requires_explicit_review": (risk != "high") or bool(patch.get("explicit_review")),
    }
    ok = all(checks.values())
    return {"ok": ok, "checks": checks, "notes": "static sandbox checks only"}


def mark_patch_readiness(patch: Dict[str, Any], sandbox: Dict[str, Any]) -> Dict[str, Any]:
    ready = bool(sandbox.get("ok")) and str(patch.get("risk", "low")) != "high"
    out = dict(patch)
    out["ready"] = ready
    out["sandbox"] = sandbox
    return out
