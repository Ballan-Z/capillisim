import math

from cap_mosaic.core.geometry import (
    Cap,
    estimate_count,
    grid_for_caps_across,
    grid_for_count,
    grid_for_frame,
)


def test_frame_grid_fits_within_bounds():
    cap = Cap(diameter_mm=32.0)
    grid = grid_for_frame(320.0, 320.0, cap)
    assert grid.count > 0
    for c in grid.cells:
        assert cap.radius_mm - 1e-6 <= c.x_mm <= grid.width_mm - cap.radius_mm + 1e-6
        assert cap.radius_mm - 1e-6 <= c.y_mm <= grid.height_mm - cap.radius_mm + 1e-6


def test_alternate_rows_are_offset():
    cap = Cap(diameter_mm=32.0)
    grid = grid_for_frame(400.0, 400.0, cap)
    row0 = sorted((c for c in grid.cells if c.row == 0), key=lambda c: c.x_mm)
    row1 = sorted((c for c in grid.cells if c.row == 1), key=lambda c: c.x_mm)
    assert row0 and row1
    # row 1 is shifted half a cap to the right of row 0
    assert math.isclose(row1[0].x_mm - row0[0].x_mm, cap.radius_mm, rel_tol=1e-6)


def test_caps_across_controls_width():
    cap = Cap(diameter_mm=32.0)
    grid = grid_for_caps_across(10, aspect_ratio=1.0, cap=cap)
    assert math.isclose(grid.width_mm, 320.0)
    # first row should hold about 10 caps
    row0 = [c for c in grid.cells if c.row == 0]
    assert len(row0) == 10


def test_count_estimate_is_in_the_ballpark():
    cap = Cap(diameter_mm=32.0)
    grid = grid_for_count(500, aspect_ratio=1.5, cap=cap)
    # within 25% of the requested count
    assert 0.75 * 500 <= grid.count <= 1.25 * 500


def test_estimate_count_matches_layout_roughly():
    cap = Cap(diameter_mm=20.0)
    est = estimate_count(400.0, 300.0, cap)
    actual = grid_for_frame(400.0, 300.0, cap).count
    assert abs(est - actual) <= 0.2 * actual + 5
