"""S3 artifact store unit tests against LocalStack."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_put_and_get_json(s3: object, env: dict[str, str]) -> None:
    from dhuan.store.s3 import ArtifactStore

    store = ArtifactStore()
    store.put_json("grid/v1/grid.geojson", {"type": "FeatureCollection", "features": [1, 2]})
    got = store.get_json("grid/v1/grid.geojson")
    assert got["type"] == "FeatureCollection"
    assert len(got["features"]) == 2


def test_put_bytes_and_model_artifacts(s3: object, env: dict[str, str]) -> None:
    from dhuan.store.s3 import ArtifactStore

    store = ArtifactStore()
    store.put_bytes("models/v1/model.joblib", b"binary-bytes", "application/octet-stream")
    keys = store.put_model_artifacts("v2", {"mae": 25.0}, b"model")
    assert keys["model"] == "models/v2/model.joblib"
    assert store.exists(keys["model"])
    assert store.get_json("models/v2/metrics.json")["mae"] == 25.0


def test_presign_and_exists(s3: object, env: dict[str, str]) -> None:
    from dhuan.store.s3 import ArtifactStore

    store = ArtifactStore()
    store.put_json("grid/v1/grid.geojson", {"a": 1})
    url = store.presign("grid/v1/grid.geojson", expires_in=600)
    assert url.startswith("http")
    assert "grid/v1/grid.geojson" in url
    assert store.exists("grid/v1/grid.geojson")
    assert not store.exists("nope/none.json")


def test_put_grid_helper(s3: object, env: dict[str, str]) -> None:
    from dhuan.store.s3 import ArtifactStore

    store = ArtifactStore()
    store.put_grid("v9", {"type": "FeatureCollection", "features": []})
    assert store.exists("grid/v9/grid.geojson")


def test_s3_client_uses_localstack_endpoint(env: dict[str, str]) -> None:
    from dhuan.store.s3 import s3_client

    client = s3_client()
    assert client.meta.endpoint_url.startswith("http://localhost:4567")
