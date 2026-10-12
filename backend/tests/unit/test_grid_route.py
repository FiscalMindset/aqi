

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
