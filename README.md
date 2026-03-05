# Bhairav Core

Runtime policy, prompts, guardrails, memory logic, gateway routing, evaluation, and KPI command-center in one clean repo.

## Scope
- Runtime doctrine: `policy/`, `guardrails/`, `prompts/`
- Long-term memory: `memory/` (Qdrant or pgvector)
- Provider gateway: `gateway/`
- Benchmarks: `benchmarks/`
- KPI dashboard: `dashboard/`
- Model lane policy: `routing/`
- Learning loops: `learning/` (RAISE + evaluator gate)
- Vigil loops: `vigil/` (RBT + guarded patch readiness)
- MCP expansion roadmap: `mcp/`

## Quick Start
1. `cd bhairav-core`
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. Generate dashboard:
   - `python dashboard/kpi_dashboard.py`

## Vector DB
- Default: Qdrant local persistent mode (`memory/qdrant_data/`)
- Alternative: pgvector (PostgreSQL + `vector` extension)
- Backend selected via env:
  - `BHAIRAV_VECTOR_BACKEND=qdrant|pgvector`

## Gateway
- `gateway/litellm-config.yaml` provides unified routing + retries + fallback lanes.
- `gateway/try_heal_retry.py` adds deterministic fail -> doctor -> heal -> retry loop.

## Weekly Eval
- Dataset: `benchmarks/tasks.jsonl` (50 tasks)
- Scoring: `python benchmarks/weekly_eval.py`
- RLAIF-lite gate: `learning/evaluator_gate.py` + `learning/constitution.yaml`

## Dashboard KPIs
- MTTR
- pass@2
- msv_hold_rate
- token usage
- pending clarifications
