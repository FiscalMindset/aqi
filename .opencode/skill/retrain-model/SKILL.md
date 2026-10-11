---
name: retrain-model
description: Retrain the Dhuan Detective model reproducibly. Use when training data, features, or model config change. Enforces the snapshot hash, deterministic training, evaluation protocol, and model-card regeneration from metrics only.
---

# Retrain the model

```bash
uv run python scripts/fetch_training_data.py   # 1. snapshot (sha256 recorded)
uv run python -m dhuan.model.train             # 2. deterministic training
uv run python -m dhuan.model.evaluate          # 3. regenerate MODEL_CARD.md
uv run pytest tests/model -q                   # 4. gates: leakage, coverage, baseline
git add backend/models/metrics.json docs/MODEL_CARD.md
git commit -m "feat(model): retrain ..."
```

## Determinism

- `random_state=42` everywhere; `early_stopping=False` so budgets don't vary.
- The snapshot sha256 ties metrics to the exact data.
- Commit `metrics.json` + `MODEL_CARD.md` together — never metrics without the card.

## Must report (real numbers only)

- Temporal holdout + leave-one-station-out.
- MAE / RMSE / R² / bias / 80% coverage / mean width.
- Baselines (global mean, climatology, persistence) and the winner by MAE.
- Per-station LOSO table.

## If the model does not beat persistence

Ship the better producer, label it in the UI (`served_by`), and say so in the card. Do not hide it.
