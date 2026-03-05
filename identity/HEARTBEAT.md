# HEARTBEAT.md

# Lean heartbeat policy: minimize API use, notify only on high signal.
#
# State file: workspace/memory/heartbeat-state.json
# Required output contract:
# - Return HEARTBEAT_OK when no urgent delta exists.
# - Otherwise send one concise actionable update only.
#
# Decision flow (strict):
# 1) Quiet hours gate: 23:00-08:00 local -> HEARTBEAT_OK unless urgent.
# 2) Cooldown gate: if last meaningful check <30m ago -> HEARTBEAT_OK.
# 3) Do at most ONE category check per heartbeat:
#    rotate: email -> calendar -> mentions -> system health.
# 4) If there is no meaningful delta vs last check state -> HEARTBEAT_OK.
# 5) Never run deep scans, web scraping, or broad file reads from heartbeat.
#
# Urgent triggers (override quiet/cooldown):
# - calendar event starts in <2h
# - important unread email from priority sender
# - repeated runtime errors or queue backlog crossing threshold
#
# Message format when notifying:
# <what changed> | <impact> | <next action>
