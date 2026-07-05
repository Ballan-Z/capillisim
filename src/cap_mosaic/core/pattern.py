"""Deterministic patterns from the caps you own — zero colour error.

Instead of approximating an image with the inventory, these lay out the
inventory ITSELF: every owned cap used exactly once, arranged so the colour
distribution becomes the picture. Because the pattern is built from the caps,
there is no quantization loss at all — what you see is exactly buildable.

Kinds:
- ``gradient``: caps sorted light->dark (CIELAB L*), laid in serpentine rows.
- ``spiral``:   caps sorted by hue, walked around concentric rings — a colour
                wheel sweeping outward.
- ``sunburst``: caps sorted light->dark, in concentric rings — a bright core
                fading to a dark rim.

Pure core (numpy + geometry + plan), no I/O.
"""

from __future__ import annotations

import math

import numpy as np

from .geometry import Cap, grid_for_caps_across
from .palette import RGB, rgb_to_lab
from .plan import GridPlan, PlannedCell

KINDS = {"gradient", "spiral", "sunburst"}


def _expand(stock: list[tuple[RGB, int]]) -> list[RGB]:
    caps: list[RGB] = []
    for rgb, n in stock:
        caps.extend([tuple(rgb)] * int(n))
    return caps


def _sorted_caps(kind: str, caps: list[RGB]) -> list[RGB]:
    labs = {c: rgb_to_lab(c) for c in set(caps)}
    if kind == "spiral":  # hue sweep (a*, b* angle), light first within a hue
        def key(c: RGB):
            l, a, b = labs[c]
            return (math.atan2(b, a), -l)
    else:  # gradient / sunburst: light -> dark
        def key(c: RGB):
            return (-labs[c][0], c)
    return sorted(caps, key=key)


def _ordered_cells(kind: str, cells) -> list:
    if kind == "gradient":  # serpentine rows, top to bottom
        return sorted(cells, key=lambda c: (c.row, c.col if c.row % 2 == 0 else -c.col))
    # spiral / sunburst: concentric rings from the centre, swept by angle
    cx = float(np.mean([c.x_mm for c in cells]))
    cy = float(np.mean([c.y_mm for c in cells]))
    pitch = 2.0 * min(abs(c.x_mm - cx) + abs(c.y_mm - cy)
                      for c in cells if (c.x_mm, c.y_mm) != (cx, cy))

    def key(c):
        r = math.hypot(c.x_mm - cx, c.y_mm - cy)
        theta = math.atan2(c.y_mm - cy, c.x_mm - cx) % (2 * math.pi)
        return (round(r / max(pitch, 1e-6)), theta)

    return sorted(cells, key=key)


def pattern_plan(kind: str, stock: list[tuple[RGB, int]], cap: Cap | None = None) -> GridPlan:
    """Lay out the whole `stock` as a `kind` pattern on a near-square hex grid."""
    if kind not in KINDS:
        raise ValueError(f"unknown pattern kind {kind!r} (choose from {sorted(KINDS)})")
    cap = cap or Cap()
    caps = _sorted_caps(kind, _expand(stock))
    total = len(caps)
    if total == 0:
        raise ValueError("empty stock")

    # smallest near-square hex grid with at least `total` cells
    across = max(1, int(math.sqrt(total * 0.87)))
    grid = grid_for_caps_across(across, 1.0, cap)
    while len(grid.cells) < total:
        across += 1
        grid = grid_for_caps_across(across, 1.0, cap)

    ordered = _ordered_cells(kind, grid.cells)
    cells: list[PlannedCell] = []
    for i, cell in enumerate(ordered):
        if i < total:
            rgb = caps[i]
            cells.append(PlannedCell(row=cell.row, col=cell.col, x_mm=cell.x_mm,
                                     y_mm=cell.y_mm, color_name="", rgb=rgb))
        else:  # grid remainder: bare board at the end of the walk
            cells.append(PlannedCell(row=cell.row, col=cell.col, x_mm=cell.x_mm,
                                     y_mm=cell.y_mm, color_name="", rgb=(255, 255, 255),
                                     is_hole=True))
    cells.sort(key=lambda c: (c.row, c.col))
    return GridPlan(cap_diameter_mm=cap.diameter_mm, width_mm=grid.width_mm,
                    height_mm=grid.height_mm, cells=cells, title=f"pattern-{kind}")
