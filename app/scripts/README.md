# Scripts

## Patch Bear Event Scores

1. Activate the virtualenv (`source .venv/bin/activate`) or run inside the app container.
2. Execute:

```bash
python -m observatory.cli.patch_bear_scores \
  --scores-file app/scripts/data/bear1_2200_scores.json \
  --trap-id 1
```

Add `--event-id <id>` if you want to target a specific bear event or `--dry-run` to verify without persisting changes. Use `--recorded-at 2024-11-21T22:00:00-05:00` (adjust as needed) if the screenshot timestamp differs from the event's `started_at`.
