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
