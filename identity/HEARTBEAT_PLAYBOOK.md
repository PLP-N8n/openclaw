# HEARTBEAT Playbook

This file holds reference guidance so `AGENTS.md` can stay small.

## Rotation idea

- Check one category per heartbeat in a round-robin:
- `email` -> `calendar` -> `mentions` -> `system-health`

## Suggested thresholds

- Quiet hours: `23:00-08:00` local
- Cooldown between meaningful checks: `30m`
- Notify if calendar event starts in `<2h`
- Notify if queue depth `>50` or recent errors `>20`

## State shape example

```json
{
  "lastChecks": {
    "email": 1703275200,
    "calendar": 1703260800,
    "mentions": 1703271600,
    "system-health": 1703273400
  },
  "lastHash": {
    "email": "sha256:...",
    "calendar": "sha256:...",
    "mentions": "sha256:...",
    "system-health": "sha256:..."
  }
}
```

## Output pattern

- No urgent change: `HEARTBEAT_OK`
- Urgent change: one short line:
- `<what changed> | <impact> | <next action>`
