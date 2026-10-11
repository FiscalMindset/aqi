# Backend engineering

Everything inside `backend/`: layout, patterns, and the rules that keep it production-grade.

## Module map

```mermaid
flowchart TB
    subgraph API[api/]
        APP[app.py - FastAPI factory]
        RT[routers/ - one file per route]
        ERR[errors.py - RFC 9457]
        MW[middleware.py - correlation id]
        DEP[deps.py - client singletons]
    end
    subgraph Core[core/]
        CFG[config.py]
        LOG[logging.py]
        MET[metrics.py]
        TR[tracing.py]
        HTTP[http.py - timeouts + retries]
        CACHE[cache.py - last-good value]
        UN[units.py - geo primitives]
    end
    subgraph Ingest[ingest/]
        OA[openaq.py]
        WE[weather.py]
        FI[firms.py]
        OS[osm.py]
    end
    subrest[Model + geo]
    subgraph Geo[geo/]
        GM[geo_math.py]
        SC[scoring.py]
        GR[grid.py]
        BD[boundary.py]
    end
    subgraph Model[model/]
        FE[features.py]
        TR2[train.py]
        EV[evaluate.py]
        PR[predict.py]
        CP[cpcb.py]
    end
    subgraph Agents[agents/]
        TO[tools.py]
        RU[runtime.py]
        GU[guardrails.py]
        AT[attribution.py]
    end
    subgraph Store[store/]
        DD[dynamodb.py]
        OP[opensearch.py]
        S3[s3.py]
    end
    subgraph Pipeline[pipeline/]
        TA[tasks.py]
    end
    subgraph Alerts[alerts/]
        AL[alerts.py]
    end
    APP --> RT
    RT --> ERR
    RT --> DEP
    RT --> Core
    API --> Ingest
    API --> Store
    AT --> TO
    AT --> RU
    TA --> Store
    AL --> Store
```

## Route pattern (every route, no exceptions)

```
1. Pydantic request schema (src/dhuan/api/schemas.py)
2. Typed response model (src/dhuan/api/models.py) with OpenAPI examples
3. FastAPI router with Query/Path validation + Depends(get_settings)
4. Coverage/business guards raise typed Problem exceptions (RFC 9457)
5. Store/upstream failures become typed 503 problems, never unhandled 500s
6. Structured logs carry the correlation id; EMF metrics on every path
7. Unit tests (respx-mocked upstreams) + integration tests (containers)
   + contract coverage (Schemathesis)
```

Reference implementation: `src/dhuan/api/routers/estimate.py`.

## HTTP discipline

Every outbound call goes through `core/http.py`:

- `httpx.Timeout` with connect + read timeouts (never a naked timeout).
- `tenacity` retries with `wait_exponential_jitter` and `FULL` jitter.
- Retryable statuses: 408, 425, 429, 500, 502, 503, 504. Client errors (4xx other) raise immediately.
- Transport errors become `UpstreamError` with the source name — never a bare exception.
- Metrics: `UpstreamRequests`, `UpstreamRetries`, `UpstreamErrors`.

## Conventions

- **No `print`** — `get_logger`/`log_event` only; JSON lines with correlation ids.
- **No bare `except`** — `except Exception as exc:` with a log and a metric.
- **Clients are singletons** in `api/deps.py` with `reset_clients()` for tests.
- **Store types**: DynamoDB uses `Decimal` (float serialisation raises `TypeError`).
- **Lazy imports** where they keep cold starts small (pipeline handlers).
- **Typed everywhere**: `mypy --strict` clean on `src/`.

## Quality gates

```bash
cd backend
uv run ruff check src tests          # 50+ rule families
uv run mypy --strict src             # zero errors
uv run pytest tests/unit             # hermetic
uv run pytest tests/integration      # OpenSearch + LocalStack containers
uv run pytest tests/model            # leakage, coverage, baseline regression
uv run pytest tests/agent_evals      # 6 deterministic scenarios
uv run pytest tests/contract         # Schemathesis, zero unhandled 5xx
uv run pytest tests/ --cov=src/dhuan # 84.65% (threshold 84, documented)
```

Known measured numbers: **230 passing tests** (1 skipped without a trained artifact), 84.65% line coverage, ruff clean, mypy --strict clean.
