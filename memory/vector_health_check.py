#!/usr/bin/env python3
import json
import os
import time

from vector_store import MemoryItem, get_store

backend = os.environ.get("BHAIRAV_VECTOR_BACKEND", "qdrant")
status = {"backend": backend, "ok": False, "error": "", "search_hits": 0}

try:
    store = get_store()
    item = MemoryItem(
        id=f"health-{int(time.time())}",
        text="vector backend health check",
        source="healthcheck",
        task_type="ops",
        ts=time.time(),
        meta={"fingerprint": "vector-healthcheck"},
    )
    store.upsert(item)
    hits = store.search("health check", top_k=2)
    status["search_hits"] = len(hits)
    status["ok"] = len(hits) > 0
except Exception as exc:
    status["error"] = str(exc)

print(json.dumps(status, ensure_ascii=True))
raise SystemExit(0 if status["ok"] else 1)
