#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from typing import Any, Callable, Dict

from gateway.retry_backoff import MAX_ATTEMPTS, backoff_delay, circuit_open, should_retry


def diagnose_failure(event: Dict[str, Any]) -> Dict[str, Any]:
    status_code = int(event.get("status_code", 0) or 0)
    error_type = str(event.get("error_type") or "unknown")
    message = str(event.get("error") or event.get("message") or "")

    diagnosis = {
        "status_code": status_code,
        "error_type": error_type,
        "cause": "unknown",
        "heal_action": "fallback_provider",
    }

    low = f"{error_type} {message}".lower()
    if status_code == 429 or "rate" in low:
        diagnosis["cause"] = "rate_limit"
        diagnosis["heal_action"] = "reduce_load"
    elif status_code in {500, 502, 503, 504}:
        diagnosis["cause"] = "transient_upstream"
        diagnosis["heal_action"] = "retry_with_backoff"
    elif "schema" in low or "validation" in low:
        diagnosis["cause"] = "schema_error"
        diagnosis["heal_action"] = "repair_schema"
    return diagnosis


def heal_request(request: Dict[str, Any], diagnosis: Dict[str, Any], attempt: int) -> Dict[str, Any]:
    healed = copy.deepcopy(request)
    action = diagnosis.get("heal_action")

    if action == "reduce_load":
        healed["max_tokens"] = max(128, int(healed.get("max_tokens", 1024) * 0.7))
    elif action == "repair_schema":
        healed["strict_schema"] = True
        healed.setdefault("metadata", {})["schema_repair_attempted"] = True
    else:
        healed.setdefault("metadata", {})["fallback_attempt"] = attempt

    healed.setdefault("metadata", {})["healed"] = True
    healed["attempt"] = attempt
    return healed


def try_heal_retry(
    executor: Callable[[Dict[str, Any]], Dict[str, Any]],
    request: Dict[str, Any],
    max_attempts: int = MAX_ATTEMPTS,
) -> Dict[str, Any]:
    state = {
        "attempt": 0,
        "failures": 0,
        "trace": [],
        "final": None,
    }

    current = copy.deepcopy(request)
    max_attempts = max(1, min(int(max_attempts), MAX_ATTEMPTS))

    for attempt in range(1, max_attempts + 1):
        state["attempt"] = attempt
        result = executor(current)
        status_code = int(result.get("status_code", 200) or 200)
        error_type = str(result.get("error_type") or "")

        state["trace"].append({"step": "execute", "attempt": attempt, "status_code": status_code, "error_type": error_type})

        if status_code < 400:
            state["final"] = result
            return {"ok": True, **state}

        state["failures"] += 1
        diagnosis = diagnose_failure(result)
        state["trace"].append({"step": "doctor", "attempt": attempt, "diagnosis": diagnosis})

        if circuit_open(state["failures"]):
            state["final"] = {"status": "circuit_open", "status_code": status_code, "error_type": error_type}
            return {"ok": False, **state}

        if not should_retry(status_code, error_type):
            state["final"] = result
            return {"ok": False, **state}

        delay = backoff_delay(attempt - 1)
        state["trace"].append({"step": "backoff", "attempt": attempt, "delay_seconds": round(delay, 3)})
        time.sleep(min(delay, 0.05))
        current = heal_request(current, diagnosis, attempt)
        state["trace"].append({"step": "heal", "attempt": attempt, "request": {k: current.get(k) for k in ["max_tokens", "strict_schema", "attempt", "metadata"]}})

    state["final"] = {"status": "max_attempts_exhausted", "status_code": 599, "error_type": "retry_exhausted"}
    return {"ok": False, **state}


if __name__ == "__main__":
    def _fake(req: Dict[str, Any]) -> Dict[str, Any]:
        if req.get("attempt", 0) >= 2:
            return {"status_code": 200, "data": "ok"}
        return {"status_code": 503, "error_type": "upstream"}

    print(json.dumps(try_heal_retry(_fake, {"max_tokens": 800}), ensure_ascii=True))
