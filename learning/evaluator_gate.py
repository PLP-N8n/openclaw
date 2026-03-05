#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


def load_constitution(path: str | None = None) -> Dict[str, Any]:
    cfg_path = Path(path) if path else Path(__file__).with_name("constitution.yaml")
    if not cfg_path.exists():
        return {"gate": {"min_total_score": 0.62, "min_evidence_score": 0.55, "min_usefulness_score": 0.5}}
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}


def score_output(candidate: Dict[str, Any], constitution: Dict[str, Any]) -> Dict[str, float]:
    text = json.dumps(candidate, ensure_ascii=True).lower()
    evidence = candidate.get("evidence") or []
    has_evidence = isinstance(evidence, list) and len(evidence) > 0
    has_action = bool(str(candidate.get("recommended_change") or candidate.get("action") or "").strip())
    has_summary = bool(str(candidate.get("summary") or candidate.get("outcome") or "").strip())
    risk = str(candidate.get("risk") or candidate.get("risk_score") or "med").lower()

    evidence_score = 0.85 if has_evidence else 0.2
    usefulness_score = 0.8 if (has_action and has_summary) else 0.35

    invented_penalty = 0.0
    if "unknown" in text and "evidence" not in text:
        invented_penalty += 0.1

    risk_score = 0.75 if risk in {"low", "med", "high"} else 0.3

    total = (0.4 * evidence_score) + (0.35 * usefulness_score) + (0.25 * risk_score) - invented_penalty
    total = max(0.0, min(1.0, round(total, 4)))

    return {
        "total_score": total,
        "evidence_score": round(evidence_score, 4),
        "usefulness_score": round(usefulness_score, 4),
        "risk_score": round(risk_score, 4),
    }


def evaluator_gate(candidate: Dict[str, Any], constitution: Dict[str, Any] | None = None) -> Tuple[bool, str, Dict[str, float]]:
    cfg = constitution or load_constitution()
    gate = cfg.get("gate", {})
    scores = score_output(candidate, cfg)

    min_total = float(gate.get("min_total_score", 0.62))
    min_ev = float(gate.get("min_evidence_score", 0.55))
    min_use = float(gate.get("min_usefulness_score", 0.5))

    if scores["evidence_score"] < min_ev:
        return False, "evidence score below gate", scores
    if scores["usefulness_score"] < min_use:
        return False, "usefulness score below gate", scores
    if scores["total_score"] < min_total:
        return False, "total score below gate", scores

    return True, "approved", scores
