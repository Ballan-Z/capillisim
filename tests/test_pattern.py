import numpy as np
import pytest

from cap_mosaic.core.pattern import KINDS, pattern_plan
from cap_mosaic.core.palette import rgb_to_lab

STOCK = [((230, 230, 235), 40), ((160, 120, 60), 70), ((90, 60, 40), 55),
         ((40, 70, 190), 12), ((200, 30, 30), 8)]
TOTAL = sum(n for _, n in STOCK)


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_every_cap_used_exactly_once(kind):
    plan = pattern_plan(kind, STOCK)
    placed = [c for c in plan.cells if not c.is_hole]
    assert len(placed) == TOTAL                      # each owned cap exactly once
    from collections import Counter
    used = Counter(tuple(c.rgb) for c in placed)
    assert used == Counter({rgb: n for rgb, n in STOCK})  # zero colour error


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_deterministic(kind):
    a = pattern_plan(kind, STOCK)
    b = pattern_plan(kind, STOCK)
    assert [(c.row, c.col, c.rgb, c.is_hole) for c in a.cells] == \
           [(c.row, c.col, c.rgb, c.is_hole) for c in b.cells]


def test_gradient_is_light_to_dark():
    plan = pattern_plan("gradient", STOCK)
    placed = [c for c in plan.cells if not c.is_hole]
    rows = sorted({c.row for c in placed})
    first = [c for c in placed if c.row == rows[0]]
    last = [c for c in placed if c.row == rows[-1]]
    L = lambda cs: np.mean([rgb_to_lab(c.rgb)[0] for c in cs])
    assert L(first) > L(last) + 10                   # top clearly lighter than bottom


def test_unknown_kind_raises():
    with pytest.raises(ValueError):
        pattern_plan("plaid", STOCK)


# --- sized / unlimited / masked patterns ---

def test_sized_pattern_fills_the_frame_and_reports_missing():
    from cap_mosaic.core.geometry import Cap, grid_for_frame

    plan = pattern_plan("gradient", STOCK, width_mm=1000.0, height_mm=750.0)
    frame = grid_for_frame(1000.0, 750.0, Cap())
    assert plan.count == frame.count
    placed = sum(1 for c in plan.cells if not c.is_hole)
    if frame.count > TOTAL:      # short stock -> holes are the missing caps
        assert placed == TOTAL
        assert plan.hole_count == frame.count - TOTAL
    else:                        # surplus stock -> every cell filled
        assert placed == frame.count and plan.hole_count == 0


def test_surplus_stock_subsamples_but_keeps_endpoints():
    from collections import Counter

    big = [((250, 250, 250), 300), ((128, 128, 128), 300), ((10, 10, 10), 300)]
    plan = pattern_plan("gradient", big, width_mm=480.0, height_mm=480.0)
    placed = [c for c in plan.cells if not c.is_hole]
    assert plan.hole_count == 0 and 0 < len(placed) < 900
    used = Counter(tuple(c.rgb) for c in placed)
    assert set(used) == {(250, 250, 250), (128, 128, 128), (10, 10, 10)}
    for rgb, n in big:                       # never exceeds owned counts
        assert used[tuple(rgb)] <= n
    rows = sorted({c.row for c in placed})
    first = [c for c in placed if c.row == rows[0]]
    last = [c for c in placed if c.row == rows[-1]]
    L = lambda cs: np.mean([rgb_to_lab(c.rgb)[0] for c in cs])
    assert L(first) > L(last) + 10           # endpoints survived the subsample


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_unlimited_fills_every_cell_from_owned_colours(kind):
    plan = pattern_plan(kind, STOCK, width_mm=640.0, height_mm=480.0,
                        unlimited=True)
    assert plan.hole_count == 0
    owned = {tuple(rgb) for rgb, _ in STOCK}
    assert {tuple(c.rgb) for c in plan.cells} <= owned


def test_unlimited_with_no_stock_uses_reference_palette():
    from cap_mosaic.core.palette import DEFAULT_PALETTE

    plan = pattern_plan("gradient", [], width_mm=480.0, height_mm=480.0,
                        unlimited=True)
    assert plan.hole_count == 0
    assert {tuple(c.rgb) for c in plan.cells} <= {c.rgb for c in DEFAULT_PALETTE}


def test_empty_stock_without_unlimited_raises():
    with pytest.raises(ValueError):
        pattern_plan("gradient", [], width_mm=480.0, height_mm=480.0)


def test_mandala_has_sixfold_colour_symmetry():
    import math

    plan = pattern_plan("mandala", STOCK, width_mm=800.0, height_mm=800.0,
                        unlimited=True)
    cells = [c for c in plan.cells if not c.is_hole]
    cx = np.mean([c.x_mm for c in cells])
    cy = np.mean([c.y_mm for c in cells])
    pos = []
    for c in cells:
        r = math.hypot(c.x_mm - cx, c.y_mm - cy)
        th = math.atan2(c.y_mm - cy, c.x_mm - cx) % (2 * math.pi)
        pos.append((r, th))
    # for sampled cells, the cell one sector (60deg) around at the same radius
    # carries the same colour
    import random
    rng = random.Random(0)
    sample = rng.sample(range(len(cells)), min(80, len(cells)))
    matched = checked = 0
    for i in sample:
        r, th = pos[i]
        if r < 32:
            continue
        target_th = (th + math.pi / 3) % (2 * math.pi)
        best, bd = None, 1e9
        for j, (ro, tho) in enumerate(pos):
            d = abs(ro - r) + 20 * min(abs(tho - target_th),
                                       2 * math.pi - abs(tho - target_th))
            if d < bd:
                best, bd = j, d
        if best is not None and bd < 24:
            checked += 1
            matched += tuple(cells[best].rgb) == tuple(cells[i].rgb)
    assert checked > 20 and matched / checked > 0.7


def test_stripes_columns_are_near_monochrome():
    plan = pattern_plan("stripes", STOCK, width_mm=960.0, height_mm=480.0)
    cells = [c for c in plan.cells if not c.is_hole]
    bands = {}
    for c in cells:
        bands.setdefault(int(c.x_mm // 32), []).append(tuple(c.rgb))
    mono = sum(1 for col in bands.values() if len(set(col)) <= 2)
    assert mono / len(bands) > 0.6           # most columns hold 1-2 colours
    first_cols = bands[min(bands)]
    last_cols = bands[max(bands)]
    assert set(first_cols) != set(last_cols)  # ends differ


def test_one_cell_grid_does_not_crash():
    plan = pattern_plan("sunburst", [((10, 10, 10), 1)], width_mm=33.0,
                        height_mm=33.0)
    assert plan.count == 1 and plan.hole_count == 0


def test_keep_mask_confines_the_pattern():
    from cap_mosaic.core.shapes import shape_mask

    keep = shape_mask("circle", 800.0, 800.0)
    plan = pattern_plan("sunburst", STOCK, width_mm=800.0, height_mm=800.0,
                        keep=keep)
    assert all(keep(c.x_mm, c.y_mm) for c in plan.cells)
    rect = pattern_plan("sunburst", STOCK, width_mm=800.0, height_mm=800.0)
    assert plan.count < rect.count


def test_dims_must_come_in_pairs():
    with pytest.raises(ValueError):
        pattern_plan("gradient", STOCK, width_mm=500.0)
