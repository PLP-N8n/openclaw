#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

CORE_DIR = Path(__file__).resolve().parents[1]
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from gateway.spend_governor import apply_spend_governor, load_daily_spend, load_policy, spend_state

cfg = yaml.safe_load(Path(__file__).with_name("model-lanes.yaml").read_text(encoding="utf-8"))
risk = (sys.argv[1] if len(sys.argv) > 1 else "low").strip().lower()
task_type = (sys.argv[2] if len(sys.argv) > 2 else "interactive").strip().lower()
estimated_tokens = int(sys.argv[3]) if len(sys.argv) > 3 else 0

if risk == "high":
    lane = cfg["high_stakes_lane"]
elif risk == "med":
    lane = cfg["escalation_lane"]
else:
    lane = cfg["default_lane"]

policy = load_policy(str(CORE_DIR / "gateway" / "spend-governor.yaml"))
spend_info = load_daily_spend(str(Path(__file__).resolve().parents[2] / "logs" / "model-usage.jsonl"))
state = spend_state(spend_info, policy)
requested_lane = lane
final = apply_spend_governor(lane, risk, task_type, estimated_tokens, state, policy)

root = Path(__file__).resolve().parents[2]
logs_dir = root / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
gov_log = logs_dir / "spend-governor-routing.jsonl"

requested_provider = str(requested_lane.get("provider", "")).lower()
final_provider = str(final.get("provider", "")).lower()
requested_is_cloud = requested_provider not in {"ollama", "local"}
final_is_cloud = final_provider not in {"ollama", "local"}

row = {
    "event": "spend_governor_route",
    "ts": datetime.now(timezone.utc).isoformat(),
    "risk": risk,
    "task_type": task_type,
    "estimated_tokens": estimated_tokens,
    "requested_lane": requested_lane.get("name"),
    "requested_provider": requested_lane.get("provider"),
    "final_lane": final.get("name"),
    "final_provider": final.get("provider"),
    "spend_state": state.get("status"),
    "downgraded_by_spend_governor": bool(final.get("downgraded_by_spend_governor")),
    "cloud_call_blocked": bool(requested_is_cloud and not final_is_cloud),
}
with gov_log.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=True) + "\n")

print(json.dumps(final, ensure_ascii=True))
