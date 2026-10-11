# Gradient boosting

Why gradient boosting, and exactly how it is configured.

## Why gradient boosting

- **Non-linear interactions** — PM2.5 depends on interactions (wind × source density × hour) that linear models cannot express.
- **Tabular data strength** — tree ensembles remain the strongest family on tabular data without GPU-scale compute.
- **Quantile loss** — native quantile regression gives us an 80% interval without distributional assumptions.
- **Fast, dependency-light** — scikit-learn's `HistGradientBoostingRegressor` needs no extra runtime beyond scikit-learn.

We deliberately did **not** use LightGBM/XGBoost: sklearn's implementation is already fast enough (22k rows train in seconds), and one fewer native dependency keeps the Lambda container and the security surface smaller.

## Configuration

```python
HistGradientBoostingRegressor(
    loss="quantile",          # p10 / p50 / p90 models
    quantile=<0.10 | 0.50 | 0.90>,
    max_iter=600,
    learning_rate=0.05,
    max_leaf_nodes=31,
    min_samples_leaf=30,
    l2_regularization=1.0,
    early_stopping=False,     # fixed budget: reproducible everywhere
    random_state=42,          # fixed seed
)
```

Three models are trained: the 10th, 50th and 90th percentiles. Median-error mode was measured to be worse on MAE than the quantile median, so `loss="quantile"` is used for all three.

## From quantile models to the served interval

The raw p10/p90 models **under-cover** during rapid AQI swings (measured coverage 0.707 on the holdout). We therefore apply **split conformal calibration**:

```
radius = quantile_0.80(|y_true − median| on holdout)   → 28.65 µg/m³
served interval = [median − radius, median + radius]
```

Empirical coverage after calibration: **0.800** (asserted within [0.75, 0.85] by a test). This is standard split-conformal and is reported as such.

## Overfitting control

- `min_samples_leaf=30` and `l2_regularization=1.0` constrain leaf structure.
- The temporal holdout and LOSO are the honest generalization tests; if you want to tune further, tune against those, never against training error.
- Every feature is available at prediction time (see `docs/MODEL.md` leakage policy).

## Baseline comparison

Persistence (lag-1h of the nearest station) wins on MAE. That is the honest answer for strongly autocorrelated hourly PM2.5 — and the reason the API's `served_by` field always tells the user which producer made the number.
