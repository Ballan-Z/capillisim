"""Deterministic patterns from the caps you own — zero colour error.

Instead of approximating an image with the inventory, these lay out the
inventory ITSELF: every owned cap used exactly once, arranged so the colour
distribution becomes the picture. Because the pattern is built from the caps,
there is no quantization loss at all — what you see is exactly buildable.

Kinds (KINDS maps each name to its cap sort + cell walk):
- ``gradient``: light->dark (CIELAB L*), serpentine rows.
- ``bullseye``: hue sweep walked around concentric rings — a colour wheel.
- ``sunburst``: light->dark in concentric rings — bright core, dark rim.
- ``waves``:    light->dark in rippling sinusoidal bands.
- ``stripes``:  hue-sorted vertical colour fields; widths follow owned counts.
- ``diamonds``: light->dark in Manhattan rings — a bright diamond core.
- ``mandala``:  hue in 6-fold rotational symmetry (a kaleidoscope).
- ``swirl``/``chevron``/``arcs``/``patchwork``: researched cap-art favourites.
- ``rays``/``medallions``/``rosettes``/``scales``: modelled on reference photos
  of real cap tables (spokes, tiled diamond motifs, dot-flowers, clamshells).

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
    "bullseye": PatternSpec("hue", "rings", "a colour wheel of concentric rings"),
    "sunburst": PatternSpec("light", "rings", "bright core fading to a dark rim"),
    "waves": PatternSpec("light", "waves", "the gradient in rippling bands"),
    "stripes": PatternSpec("hue", "columns", "vertical colour-field stripes"),
    "diamonds": PatternSpec("light", "manhattan", "a bright diamond core"),
    "mandala": PatternSpec("hue", "mandala", "six-fold kaleidoscope"),
    # researched from real cap-art favourites (murals, table tops, quilts)
    "swirl": PatternSpec("hue", "swirl", "a pinwheel of spiral colour arms"),
    "chevron": PatternSpec("light", "chevron", "zigzag herringbone bands"),
    "arcs": PatternSpec("hue", "arcs", "a rainbow arching over the piece"),
    "patchwork": PatternSpec("hue", "patch", "a quilt of colour blocks"),
    # modelled on the user's reference photos of real cap tables
    "rays": PatternSpec("hue", "rays", "spokes radiating from the centre"),
    "medallions": PatternSpec("light", "medallions", "nested diamond medallions"),
    "rosettes": PatternSpec("hue", "rosettes", "little flowers of colour dots"),
    "scales": PatternSpec("light", "scales", "overlapping clamshell arcs"),
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
    return sorted(caps, key=lambda c: (-labs[c][0], c))  # light -> dark


def _ordered_cells(walk: str, cells, cap: Cap) -> list:
    d = cap.diameter_mm
    rp = d * math.sqrt(3) / 2.0  # hex row pitch
    if walk == "serpentine":
        return sorted(cells, key=lambda c: (c.row, c.col if c.row % 2 == 0 else -c.col))
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
    if walk == "chevron":  # zigzag bands (herringbone): triangle wave, not sine
        width = max(c.x_mm for c in cells) + d / 2.0
        wavelength = max(width / 3.0, d)
        amp = 2.0 * rp

        def key(c):
            t = c.x_mm / wavelength
            tri = 2.0 * abs(2.0 * (t - math.floor(t + 0.5))) - 1.0
            band = round((c.y_mm + amp * tri) / rp)
            return (band, c.x_mm if band % 2 == 0 else -c.x_mm)
        return sorted(cells, key=key)
    if walk == "patch":  # quilt: ~3-cap blocks, filled in a SCATTERED order so
        # neighbouring blocks land in different colour runs (a real patchwork)
        block = 3.0 * d

        def key(c):
            by, bx = int(c.y_mm // block), int(c.x_mm // block)
            return ((bx * 7 + by * 13) % 11, by, bx, c.row, c.col)
        return sorted(cells, key=key)
    if walk == "medallions":  # tiled motifs: nested diamond rings around a
        # lattice of centres (the "trip around the world" quilt-table look)
        motif = 8.0 * d

        def key(c):
            mx = int(c.x_mm // motif)
            my = int(c.y_mm // motif)
            cx0 = (mx + 0.5) * motif
            cy0 = (my + 0.5) * motif
            ring = round((abs(c.x_mm - cx0) + abs(c.y_mm - cy0)) / d)
            return (ring, mx, my, c.row, c.col)
        return sorted(cells, key=key)
    if walk == "rosettes":  # little same-colour dot-flowers on a coarse
        # triangular lattice, filled in a scattered order
        step_x, step_y = 3.0 * d, 3.0 * rp

        def key(c):
            k = round(c.y_mm / step_y)
            m = round((c.x_mm - (k % 2) * 1.5 * d) / step_x)
            cx0 = m * step_x + (k % 2) * 1.5 * d
            cy0 = k * step_y
            dist = math.hypot(c.x_mm - cx0, c.y_mm - cy0)
            return ((m * 7 + k * 13) % 9, k, m, dist)
        return sorted(cells, key=key)
    if walk == "scales":  # rows of overlapping clamshell arcs. Rings are
        # filled ACROSS all scales (like medallions), so every shell carries
        # the same nested colour sequence — the classic clamshell quilt look.
        band_h = 4.0 * rp
        scale_w = 5.0 * d

        def key(c):
            k = int(c.y_mm // band_h)
            off = (k % 2) * 0.5 * scale_w
            m = round((c.x_mm - off) / scale_w)
            cx0 = m * scale_w + off
            cy0 = (k + 1) * band_h
            ring = round(math.hypot(c.x_mm - cx0, c.y_mm - cy0) / d)
            return (ring, k, m, c.x_mm)
        return sorted(cells, key=key)
    if walk == "arcs":  # concentric arcs from the bottom centre: a rainbow arch
        width = max(c.x_mm for c in cells) + d / 2.0
        base_y = max(c.y_mm for c in cells) + d / 2.0
        cx0 = width / 2.0

        def key(c):
            ring = round(math.hypot(c.x_mm - cx0, c.y_mm - base_y) / d)
            return (ring, c.x_mm)
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
    if walk == "swirl":  # pinwheel: six spiral arms twisting out of the centre
        arms = 6

        def key(c):
            r, theta = polar(c)
            arm = int(theta / (2 * math.pi) * arms + r / max(pitch, 1e-6)) % arms
            return (arm, r, theta)
        return sorted(cells, key=key)
    if walk == "rays":  # spokes radiating from the centre to the rim; spokes
        # are filled in a strided order so neighbouring spokes take different
        # colours instead of merging into wedges
        spokes = 16

        def key(c):
            r, theta = polar(c)
            s = int(theta / (2 * math.pi) * spokes) % spokes
            return ((s * 5) % spokes, s, r)
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
