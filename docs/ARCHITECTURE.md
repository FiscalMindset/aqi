# Architecture

Dhuan Detective turns weather, station, fire and map data into street-level PM2.5 estimates with attributed, evidence-linked explanations.

## System flow

```mermaid
flowchart TB
    subgraph Sources[External data]
        OAQ[OpenAQ v3 API<br/>+ public S3 archive]
        WX[Open-Meteo<br/>forecast + archive]
        FIRMS[NASA FIRMS]
        OSM[OpenStreetMap<br/>via Overpass]
    end

    EB[EventBridge<br/>rate 1 hour] --> SFN
    subgraph SFN[Step Functions: hourly pipeline]
        direction TB
        P1[Parallel ingest<br/>stations / weather / fires] --> V[Validate and merge<br/>reject impossible values]
        V --> PG[Predict H3 grid]
        PG --> PS[Persist to DynamoDB<br/>TTL 90 days]
        PS --> EA[Evaluate alert rules]
        EA --> PA[Publish SNS alerts]
    end

    Sources --> SFN
    OSM -->|seed once + monthly refresh| OS[(OpenSearch: sources index)]
    SFN --> DDB[(DynamoDB: estimates, feeds, subscriptions)]
    SFN --> S3[(S3: grid GeoJSON, model, raw)]

    U[Browser] --> CF[CloudFront]
    CF -->|/| WEB[S3: web app]
    CF -->|/v1/*| APIGW[API Gateway<br/>throttling + usage plan]
    APIGW --> LAM[Lambda: FastAPI container]
    LAM --> DDB
    LAM --> OS
    LAM --> AG[Strands agent on Bedrock]
    AG -->|tools| OS
    AG -->|tools| DDB
    PA --> SNS[SNS topic<br/>per-locality filter policies]
```

## `/v1/explain` sequence

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as FastAPI (Lambda)
    participant AG as Attribution agent
    participant T as Tool registry
    participant OS as OpenSearch
    participant BR as Bedrock

    UI->>API: POST /v1/explain {lat, lon}
    API->>API: coverage polygon check (422 outside)
    API->>AG: run(lat, lon)
    loop agent loop (max 12 tool calls)
        AG->>T: get_station_context()
        T->>DynamoDB: live OpenAQ fetch
        T-->>AG: evidence ev_xxx
        AG->>T: get_air_and_wind()
        T-->>AG: evidence ev_xxx
        AG->>T: find_upwind_sources()
        T->>OS: geo_distance + cone test
        OS-->>T: ranked candidates
        T-->>AG: evidence ev_xxx
        AG->>BR: synthesize with evidence ids
        BR-->>AG: structured JSON
    end
    AG->>API: AttributionResult (claims cite evidence ids)
    API->>AG: advisory synthesis (personas)
    API-->>UI: attribution + advice + tool trace
```

## Pipeline state machine

```mermaid
stateDiagram-v2
    [*] --> FanOutIngest
    FanOutIngest --> ValidateAndMerge: 3 branches complete
    ValidateAndMerge --> PredictGrid
    PredictGrid --> PersistEstimates
    PersistEstimates --> EvaluateAlerts
    EvaluateAlerts --> PublishAlerts
    PublishAlerts --> [*]
    FanOutIngest --> RecordFeedFailure: States.ALL
    PredictGrid --> RecordFeedFailure: States.ALL
    PublishAlerts --> RecordFeedFailure: States.ALL
    RecordFeedFailure --> FailPipeline
    FailPipeline --> [*]
```

Every task state has `Retry` (exponential backoff, `FULL` jitter) and a `Catch` that records feed status and emits a metric — never a silent failure.

## Data model (ER)

```mermaid
erDiagram
    ESTIMATES ||--|{ CELL : "hash key cell#<h3>"
    ESTIMATES {
        string pk "cell#<h3>"
        string sk "ts#<iso>"
        float pm25_low
        float pm25_mid
        float pm25_high
        string model_version
        number ttl "90 days"
    }
    FEEDS {
        string pk "feed=<name>"
        bool ok
        string last_success_at
        string last_error
        int records_last_run
    }
    SUBSCRIPTIONS {
        string pk "sub#<sha256[:16]>"
        string email
        string locality "GSI hash key"
        float lat
        float lon
        string threshold_category
        bool confirmed
        string pending_token
        string last_band
        string last_alerted_at
    }
    SOURCES {
        string osm_id
        keyword type
        text name
        geo_point location
        float area_m2
        object source_tags
        date last_seen
    }
```

## Design decisions

Every major decision is recorded as an ADR in [docs/adr/](adr/): the 8% coverage threshold, the estimate-serving rule (better of model vs nearest-station baseline), the agent backend abstraction, H3 resolution 8, and more.
