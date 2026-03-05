#!/usr/bin/env python3
from __future__ import annotations

import random

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
NON_RETRYABLE_ERROR_TYPES = {"auth_error", "schema_error", "validation_error", "permission_denied"}
MAX_ATTEMPTS = 5


def should_retry(status_code: int, error_type: str) -> bool:
    if int(status_code) not in RETRYABLE_STATUS_CODES:
        return False
    return str(error_type or "").lower() not in NON_RETRYABLE_ERROR_TYPES


def backoff_delay(attempt: int, base: float = 1.0, jitter: float = 0.3) -> float:
    attempt = max(0, int(attempt))
    raw = float(base) * (2 ** attempt)
    spread = raw * max(0.0, float(jitter))
    return max(0.0, raw + random.uniform(-spread, spread))


def circuit_open(failures: int, threshold: int = 5) -> bool:
    return int(failures) >= int(threshold)
