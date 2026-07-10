"""Deterministic patterns from the caps you own — zero colour error.

Instead of approximating an image with the inventory, these lay out the
inventory ITSELF: every owned cap used exactly once, arranged so the colour
distribution becomes the picture. Because the pattern is built from the caps,
there is no quantization loss at all — what you see is exactly buildable.

Kinds (KINDS maps each name to its cap sort + cell walk):
- ``gradient``: light->dark (CIELAB L*), serpentine rows.
- ``spiral``:   hue sweep walked around concentric rings — a colour wheel.
- ``sunburst``: light->dark in concentric rings — bright core, dark rim.
- ``waves``:    light->dark in rippling sinusoidal bands.
- ``diagonal``: light->dark corner-to-corner, 45 degrees.
- ``stripes``:  hue-sorted vertical colour fields; widths follow owned counts.
- ``diamonds``: light->dark in Manhattan rings — a bright diamond core.
- ``mandala``:  hue in 6-fold rotational symmetry (a kaleidoscope).
- ``checker``:  light/dark interleaved shimmer that still graduates overall.

Sizing: with no dims, the smallest near-square grid holding all stock (every
cap exactly once). With ``width_mm``/``height_mm``, the pattern fills that
frame: surplus stock is evenly subsampled (endpoints kept), a shortfall leaves
end-of-walk holes — ``hole_count`` IS the "caps missing" number. With
``unlimited=True`` the distinct stock colours repeat freely in equal shares
(no holes ever); with no stock at all the reference palette stands in.
``keep`` applies a shape mask (see core.shapes) before planning.

Pure core (numpy + geometry + plan + shapes), no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .geometry import Cap, grid_for_caps_across, grid_for_frame
from .palette import DEFAULT_PALETTE, RGB, rgb_to_lab
from .plan import GridPlan, PlannedCell
from .shapes import mask_grid


@dataclass(frozen=True)
class PatternSpec:
    cap_sort: str   # "light" | "hue" | "interleave"
    cell_walk: str  # "serpentine" | "rings" | "waves" | "diagonal" |
    #                 "columns" | "manhattan" | "mandala"
    blurb: str


KINDS: dict[str, PatternSpec] = {
    "gradient": PatternSpec("light", "serpentine", "light-to-dark in serpentine rows"),
    "spiral": PatternSpec("hue", "rings", "a colour wheel sweeping outward"),
    "sunburst": PatternSpec("light", "rings", "bright core fading to a dark rim"),
    "waves": PatternSpec("light", "waves", "the gradient in rippling bands"),
    "diagonal": PatternSpec("light", "diagonal", "corner-to-corner gradient"),
    "stripes": PatternSpec("hue", "columns", "vertical colour-field stripes"),
    "diamonds": PatternSpec("light", "manhattan", "a bright diamond core"),
    "mandala": PatternSpec("hue", "mandala", "six-fold kaleidoscope"),
    "checker": PatternSpec("interleave", "serpentine", "light/dark shimmer"),
}


def _expand(stock: list[tuple[RGB, int]]) -> list[RGB]:
    caps: list[RGB] = []
    for rgb, n in stock:
        caps.extend([tuple(rgb)] * int(n))
    return caps


def _sorted_caps(sort: str, caps: list[RGB]) -> list[RGB]:
    labs = {c: rgb_to_lab(c) for c in set(caps)}
    if sort == "hue":  # hue sweep (a*, b* angle), light first within a hue
        def key(c: RGB):
            l, a, b = labs[c]
            return (math.atan2(b, a), -l)
        return sorted(caps, key=key)
    by_light = sorted(caps, key=lambda c: (-labs[c][0], c))  # light -> dark
    if sort == "light":
        return by_light
    # interleave: split the light-sorted list at the median and zip the halves,
    # so neighbours alternate light/dark while the overall row still graduates
    half = (len(by_light) + 1) // 2
    a, b = by_light[:half], by_light[half:]
    out: list[RGB] = []
    for i in range(half):
        out.append(a[i])
        if i < len(b):
            out.append(b[i])
    return out


def _ordered_cells(walk: str, cells, cap: Cap) -> list:
    d = cap.diameter_mm
    rp = d * math.sqrt(3) / 2.0  # hex row pitch
    if walk == "serpentine":
        return sorted(cells, key=lambda c: (c.row, c.col if c.row % 2 == 0 else -c.col))
    if walk == "diagonal":
        def key(c):
            band = round((c.x_mm + c.y_mm) / d)
            along = c.x_mm - c.y_mm
            return (band, along if band % 2 == 0 else -along)
        return sorted(cells, key=key)
    if walk == "columns":
        def key(c):
            band = int(c.x_mm // d)
            return (band, c.y_mm if band % 2 == 0 else -c.y_mm)
        return sorted(cells, key=key)
    if walk == "waves":
        width = max(c.x_mm for c in cells) + d / 2.0
        wavelength = max(width / 2.5, d)
        amp = 1.5 * rp

        def key(c):
            band = round((c.y_mm + amp * math.sin(2 * math.pi * c.x_mm / wavelength)) / rp)
            return (band, c.x_mm if band % 2 == 0 else -c.x_mm)
        return sorted(cells, key=key)

    # centre-based walks: rings / manhattan / mandala
    cx = float(np.mean([c.x_mm for c in cells]))
    cy = float(np.mean([c.y_mm for c in cells]))
    off_centre = [abs(c.x_mm - cx) + abs(c.y_mm - cy)
                  for c in cells if (c.x_mm, c.y_mm) != (cx, cy)]
    pitch = 2.0 * min(off_centre) if off_centre else d  # 1-cell grid guard

    def polar(c):
        r = math.hypot(c.x_mm - cx, c.y_mm - cy)
        theta = math.atan2(c.y_mm - cy, c.x_mm - cx) % (2 * math.pi)
        return r, theta

    if walk == "manhattan":
        def key(c):
            ring = round((abs(c.x_mm - cx) + abs(c.y_mm - cy)) / d)
            return (ring, polar(c)[1])
        return sorted(cells, key=key)
    if walk == "mandala":
        sector_angle = 2 * math.pi / 6

        def key(c):
            r, theta = polar(c)
            return (round(r / max(pitch, 1e-6)), theta % sector_angle,
                    int(theta // sector_angle))
        return sorted(cells, key=key)

    def key(c):  # "rings"
        r, theta = polar(c)
        return (round(r / max(pitch, 1e-6)), theta)
    return sorted(cells, key=key)


def _unlimited_caps(stock: list[tuple[RGB, int]], n: int) -> list[tuple[RGB, int]]:
    """A virtual stock: the distinct owned colours in equal shares totalling n.

    Equal shares (not proportional to owned counts) so a skewed collection
    still shows the pattern's full range; with no stock at all, the reference
    palette stands in."""
    distinct = list(dict.fromkeys(tuple(rgb) for rgb, cnt in stock if int(cnt) > 0))
    if not distinct:
        distinct = [c.rgb for c in DEFAULT_PALETTE]
    share, rem = divmod(n, len(distinct))
    return [(c, share + (1 if i < rem else 0)) for i, c in enumerate(distinct)]


def pattern_plan(
    kind: str,
    stock: list[tuple[RGB, int]],
    cap: Cap | None = None,
    *,
    width_mm: float | None = None,
    height_mm: float | None = None,
    unlimited: bool = False,
    keep: Callable[[float, float], bool] | None = None,
) -> GridPlan:
    """Lay out `stock` as a `kind` pattern; see the module docstring for the
    sizing / unlimited / shape semantics."""
    if kind not in KINDS:
        raise ValueError(f"unknown pattern kind {kind!r} (choose from {sorted(KINDS)})")
    if (width_mm is None) != (height_mm is None):
        raise ValueError("give both width_mm and height_mm, or neither")
    cap = cap or Cap()
    spec = KINDS[kind]

    if width_mm is not None:
        grid = grid_for_frame(width_mm, height_mm, cap)
        if keep is not None:
            grid = mask_grid(grid, keep)  # ValueError("no cells") propagates
    else:
        caps_once = _expand(stock)
        if not caps_once and not unlimited:
            raise ValueError("empty stock")
        total_once = max(1, len(caps_once))
        # smallest near-square grid whose (masked) cell count holds the stock
        across = max(1, int(math.sqrt(total_once * 0.87)))
        while True:
            grid = grid_for_caps_across(across, 1.0, cap)
            if keep is not None:
                try:
                    grid = mask_grid(grid, keep)
                except ValueError:
                    across += 1
                    continue
            if grid.count >= total_once:
                break
            across += 1

    n = grid.count
    if unlimited:
        caps = _sorted_caps(spec.cap_sort, _expand(_unlimited_caps(stock, n)))
    else:
        caps = _sorted_caps(spec.cap_sort, _expand(stock))
        if not caps:
            raise ValueError("empty stock")
        if len(caps) > n:  # surplus: even subsample, endpoints kept
            t = len(caps)
            caps = ([caps[0]] if n == 1 else
                    [caps[round(j * (t - 1) / (n - 1))] for j in range(n)])
    total = len(caps)  # <= n; the remainder of the walk becomes holes

    ordered = _ordered_cells(spec.cell_walk, grid.cells, cap)
    cells: list[PlannedCell] = []
    for i, cell in enumerate(ordered):
        if i < total:
            cells.append(PlannedCell(row=cell.row, col=cell.col, x_mm=cell.x_mm,
                                     y_mm=cell.y_mm, color_name="", rgb=caps[i]))
        else:  # grid remainder: bare board at the end of the walk
            cells.append(PlannedCell(row=cell.row, col=cell.col, x_mm=cell.x_mm,
                                     y_mm=cell.y_mm, color_name="", rgb=(255, 255, 255),
                                     is_hole=True))
    cells.sort(key=lambda c: (c.row, c.col))
    return GridPlan(cap_diameter_mm=cap.diameter_mm, width_mm=grid.width_mm,
                    height_mm=grid.height_mm, cells=cells, title=f"pattern-{kind}")
