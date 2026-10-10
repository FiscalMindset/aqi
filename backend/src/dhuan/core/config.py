"""Centralized, validated configuration.

All settings come from the environment (or a local .env file) and are
validated once at startup. Secrets are never defaulted here; they are
expected from SSM Parameter Store / Secrets Manager in real deployments
and resolve to empty strings locally.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dhuan.core.units import Bbox, Point

_DELHI_BBOX = Bbox(
    min_lat=28.38, min_lon=76.83, max_lat=28.92, max_lon=77.36
)  # approximates core Delhi-NCR extent; full coverage polygon is in geo/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    env: Literal["dev", "staging", "prod", "test"] = "dev"
    demo_mode: bool = False
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"  # noqa: S104 - container binds all interfaces by design
    api_port: int = 8000
    api_version: str = "0.1.0"
    service_name: str = "dhuan-detective"

    # external sources
    openaq_api_key: str = ""
    openmeteo_base_url: str = "https://api.open-meteo.com"
    openmeteo_aq_base_url: str = "https://air-quality-api.open-meteo.com"
    firms_map_key: str = ""
    overpass_endpoints: list[str] = Field(
        default_factory=lambda: [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
        ]
    )

    # http behaviour
    http_timeout_seconds: float = 10.0
    http_connect_timeout_seconds: float = 5.0
    http_max_retries: int = 3
    http_retry_base_delay_seconds: float = 0.5
    http_retry_max_delay_seconds: float = 8.0

    # aws / services
    aws_region: str = "ap-south-1"
    aws_endpoint_url: str = ""  # LocalStack: http://localhost:4566
    bedrock_model_id: str = ""
    opensearch_endpoint: str = "http://localhost:9200"
    opensearch_index: str = "sources"
    dynamodb_table_estimates: str = "dhuan-estimates"
    dynamodb_table_feeds: str = "dhuan-feeds"
    dynamodb_table_subscriptions: str = "dhuan-subscriptions"
    s3_bucket: str = "dhuan-artifacts"
    sns_topic_arn: str = ""
    ssm_parameter_prefix: str = "/dhuan"

    # model + grid
    model_version: str = "baseline-v1"
    h3_resolution: int = 8
    delhi_bbox: Bbox = _DELHI_BBOX

    # alerts
    sms_enabled: bool = False

    # api surface
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # demo data (recorded fixtures, only used when DEMO_MODE=1)
    demo_data_dir: str = ""

    @field_validator("demo_mode", "sms_enabled", mode="before")
    @classmethod
    def _parse_bool(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on"}
        return v

    @property
    def is_demo(self) -> bool:
        return self.demo_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()


def point_in_delhi(p: Point, settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    b = s.delhi_bbox
    return b.min_lat <= p.lat <= b.max_lat and b.min_lon <= p.lon <= b.max_lon
