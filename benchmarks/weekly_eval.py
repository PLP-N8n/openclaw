#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
results_file = root / "results.jsonl"
out_file = root / "weekly-summary.json"

rows = []
if results_file.exists():
    for line in results_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue

by_task = defaultdict(list)
for r in rows:
    tid = str(r.get("task_id", ""))
    if tid:
        by_task[tid].append(r)

if not by_task:
    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tasks_evaluated": 0,
        "pass_at_2": 0.0,
        "hallucination_rate": 0.0,
        "abstain_rate": 0.0,
        "mttr_hours": None,
        "note": "No benchmark results yet. Append rows to benchmarks/results.jsonl.",
    }
else:
    pass2 = 0
    hallucinations = 0
    abstains = 0
    total = len(by_task)
    for task_rows in by_task.values():
        task_rows = sorted(task_rows, key=lambda x: int(x.get("attempt", 99)))[:2]
        if any(bool(x.get("success")) for x in task_rows):
            pass2 += 1
        hallucinations += sum(1 for x in task_rows if bool(x.get("hallucinated")))
        abstains += sum(1 for x in task_rows if bool(x.get("abstained")))
    denom = max(1, sum(min(2, len(v)) for v in by_task.values()))
    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tasks_evaluated": total,
        "pass_at_2": round(pass2 / total, 4),
        "hallucination_rate": round(hallucinations / denom, 4),
        "abstain_rate": round(abstains / denom, 4),
        "mttr_hours": None,
    }

out_file.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
print(json.dumps(out, ensure_ascii=True))
