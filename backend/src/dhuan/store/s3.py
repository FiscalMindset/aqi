"""S3 access layer: grid GeoJSON, model artifacts, raw archives."""

from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.config import Config

from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger

logger = get_logger("store.s3")


def s3_client(settings: Settings | None = None) -> Any:
    s = settings or get_settings()
    kwargs: dict[str, Any] = {
        "region_name": s.aws_region,
        "config": Config(retries={"max_attempts": 3}),
    }
    if s.aws_endpoint_url:
        kwargs["endpoint_url"] = s.aws_endpoint_url
    return boto3.client("s3", **kwargs)


class ArtifactStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bucket = self.settings.s3_bucket
        self._s3 = s3_client(self.settings)

    def put_json(self, key: str, payload: Any) -> str:
        self._s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(payload).encode(),
            ContentType="application/json",
            CacheControl="public, max-age=300",
        )
        return f"s3://{self.bucket}/{key}"

    def get_json(self, key: str) -> Any:
        resp = self._s3.get_object(Bucket=self.bucket, Key=key)
        return json.loads(resp["Body"].read())

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self.bucket}/{key}"

    def put_grid(self, version: str, grid: dict[str, Any]) -> str:
        return self.put_json(f"grid/{version}/grid.geojson", grid)

    def put_model_artifacts(
        self, version: str, metrics: dict[str, Any], model_bytes: bytes
    ) -> dict[str, str]:
        model_key = f"models/{version}/model.joblib"
        metrics_key = f"models/{version}/metrics.json"
        self.put_bytes(model_key, model_bytes, "application/octet-stream")
        self.put_json(metrics_key, metrics)
        return {"model": model_key, "metrics": metrics_key}

    def presign(self, key: str, expires_in: int = 3600) -> str:
        url: str = self._s3.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in
        )
        return url

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self.bucket, Key=key)
        except Exception:  # BLE001: head raises when missing
            return False
        return True


__all__ = ["ArtifactStore", "s3_client"]
