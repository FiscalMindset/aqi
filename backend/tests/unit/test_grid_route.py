

class TestPrecomputedCells:
    """The grid cell set is precomputed into the image.

    Enumerating it from the boundary polygon costs ~100 s and pushed the route
    into Lambda OOM at 1024 MB. The shipped index makes it a 10 ms lookup; this
    guards the fallback so a missing file is still correct, just slow.
    """

    def test_precomputed_index_matches_the_boundary_enumeration(self) -> None:
        from dhuan.geo.grid import _enumerate_cells, grid_cells

        assert set(grid_cells(8)) == set(_enumerate_cells(8))

    def test_resolution_without_an_index_falls_back_to_enumeration(self) -> None:
        from dhuan.geo.grid import _precomputed_cells

        assert _precomputed_cells(11) is None

    def test_lookup_is_fast(self) -> None:
        import time

        from dhuan.geo.grid import grid_cells

        start = time.monotonic()
        grid_cells(8)
        assert time.monotonic() - start < 5.0


class TestGridGeometryLimit:
    """The full geometry cannot be delivered through API Gateway.

    Delhi-NCR at res-8 serialises to ~17.8 MB; API Gateway REST caps a response
    at 10 MB and truncates beyond it, which the client sees as a bare 502. The
    route refuses the full form with a typed problem instead.
    """

    def test_requesting_geometry_returns_a_typed_problem(self) -> None:
        from fastapi.testclient import TestClient

        from dhuan.api.app import create_app

        with TestClient(create_app()) as client:
            resp = client.get("/v1/grid?include_geometry=true")
        assert resp.status_code == 422
        assert resp.headers["content-type"].startswith("application/problem+json")
        body = resp.json()
        assert "10 MB" in body["detail"]
        assert body["correlation_id"]

    def test_ids_only_is_served(self) -> None:
        from fastapi.testclient import TestClient

        from dhuan.api.app import create_app

        with TestClient(create_app()) as client:
            resp = client.get("/v1/grid")
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "FeatureCollection"
        assert body["features"]
        assert body["features"][0]["geometry"] is None
