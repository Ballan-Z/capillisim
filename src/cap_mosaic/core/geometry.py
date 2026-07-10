"""Hexagonal cap-packing geometry.

A bottle cap is treated as a circle of a given outer diameter. The densest and
most natural arrangement is hexagonal packing: rows are stacked at a vertical
pitch of d*sqrt(3)/2, and every other row is shifted half a cap to the side.

All coordinates are in millimetres on the physical table, origin at the
top-left of the frame, x to the right, y downwards. Cell positions are cap
*centres*.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Hexagonal packing: each cap "owns" a rhombus of area d^2 * sqrt(3)/2.
HEX_CELL_AREA_FACTOR = math.sqrt(3) / 2

DEFAULT_CAP_DIAMETER_MM = 32.0  # standard crown cap, outer diameter


@dataclass(frozen=True)
class Cap:
    diameter_mm: float = DEFAULT_CAP_DIAMETER_MM

    @property
    def radius_mm(self) -> float:
        return self.diameter_mm / 2.0


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    x_mm: float
    y_mm: float


@dataclass(frozen=True)
class Grid:
    cap: Cap
    width_mm: float
    height_mm: float
    cells: tuple[Cell, ...]

    @property
    def count(self) -> int:
        return len(self.cells)

    @property
    def rows(self) -> int:
        return 1 + max((c.row for c in self.cells), default=-1)


def grid_for_frame(width_mm: float, height_mm: float, cap: Cap) -> Grid:
    """Lay out as many caps as fit inside a width x height frame (mm)."""
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("frame dimensions must be positive")
    d = cap.diameter_mm
    if d <= 0:
        raise ValueError("cap diameter must be positive")

    row_pitch = d * HEX_CELL_AREA_FACTOR
    n_rows = int((height_mm - d) // row_pitch) + 1 if height_mm >= d else 0

    cells: list[Cell] = []
    for row in range(n_rows):
        x_offset = d / 2.0 if row % 2 else 0.0
        usable = width_mm - d - x_offset
        n_cols = int(usable // d) + 1 if usable >= 0 else 0
        y = cap.radius_mm + row * row_pitch
        for col in range(n_cols):
            x = cap.radius_mm + x_offset + col * d
            cells.append(Cell(row=row, col=col, x_mm=x, y_mm=y))

    return Grid(cap=cap, width_mm=width_mm, height_mm=height_mm, cells=tuple(cells))


def hex_neighbors(row: int, col: int) -> tuple[tuple[int, int], ...]:
    """The 6 hex-packing neighbours of a cell (existence not checked).

    Odd rows are shifted +d/2 (see grid_for_frame), so a cell's adjacent-row
    neighbours sit at columns (col-1, col) for even rows and (col, col+1) for
    odd rows; same-row neighbours are col +/- 1.
    """
    a, b = (col - 1, col) if row % 2 == 0 else (col, col + 1)
    return (
        (row, col - 1), (row, col + 1),
        (row - 1, a), (row - 1, b),
        (row + 1, a), (row + 1, b),
    )


def estimate_count(width_mm: float, height_mm: float, cap: Cap) -> int:
    """Rough cap count for an area under hex packing (before exact layout)."""
    cell_area = cap.diameter_mm**2 * HEX_CELL_AREA_FACTOR
    return int((width_mm * height_mm) / cell_area)


def grid_for_caps_across(caps_across: int, aspect_ratio: float, cap: Cap) -> Grid:
    """Build a grid `caps_across` caps wide, at width/height = aspect_ratio."""
    if caps_across < 1:
        raise ValueError("caps_across must be >= 1")
    if aspect_ratio <= 0:
        raise ValueError("aspect_ratio must be positive")
    width_mm = caps_across * cap.diameter_mm
    height_mm = width_mm / aspect_ratio
    return grid_for_frame(width_mm, height_mm, cap)


def grid_for_count(target_count: int, aspect_ratio: float, cap: Cap) -> Grid:
    """Build a grid that totals approximately `target_count` caps."""
    if target_count < 1:
        raise ValueError("target_count must be >= 1")
    # count ~= caps_across^2 / (aspect_ratio * HEX_CELL_AREA_FACTOR)
    caps_across = math.sqrt(target_count * aspect_ratio * HEX_CELL_AREA_FACTOR)
    return grid_for_caps_across(max(1, round(caps_across)), aspect_ratio, cap)
