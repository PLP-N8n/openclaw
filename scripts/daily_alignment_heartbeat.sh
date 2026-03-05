#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

python3 bhairav-core/dashboard/kpi_dashboard.py >/tmp/bhairav-kpi.txt
./cron/scripts/operator-status.sh record \
  --decision "alignment_heartbeat" \
  --why "Daily check: still aligned with Hunny priorities before deep runs" \
  --evidence "bhairav-core/dashboard/latest-kpis.json" \
  --risk low \
  --next "continue if priorities/constraints unchanged" \
  --telegram >/dev/null
