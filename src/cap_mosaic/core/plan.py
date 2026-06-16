"""GridPlan: the design + live build state, serialized for staged builds.

A plan is the full description of a piece: the cap size, the frame, and one
entry per cell giving its table position, its target cap color, and whether a
cap has been placed there yet. Persisting this to JSON is what lets a build span
many sessions as caps trickle in.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .geometry import Cap, Grid
from .palette import RGB


@dataclass
class PlannedCell:
    row: int
    col: int
    x_mm: float
    y_mm: float
    color_name: str
    rgb: RGB
    filled: bool = False


@dataclass
class GridPlan:
    cap_diameter_mm: float
    width_mm: float
    height_mm: float
    cells: list[PlannedCell] = field(default_factory=list)
    title: str = "untitled"

    @property
    def count(self) -> int:
        return len(self.cells)

    @property
    def filled_count(self) -> int:
        return sum(1 for c in self.cells if c.filled)

    def bill_of_materials(self) -> dict[str, int]:
        """How many caps of each color the finished piece needs."""
        counts = Counter(c.color_name for c in self.cells)
        return dict(counts.most_common())

    def remaining_bom(self) -> dict[str, int]:
        """Caps of each color still needed (unfilled cells only)."""
        counts = Counter(c.color_name for c in self.cells if not c.filled)
        return dict(counts.most_common())

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "cap_diameter_mm": self.cap_diameter_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "cells": [asdict(c) for c in self.cells],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GridPlan":
        cells = [
            PlannedCell(
                row=c["row"],
                col=c["col"],
                x_mm=c["x_mm"],
                y_mm=c["y_mm"],
                color_name=c["color_name"],
                rgb=tuple(c["rgb"]),
                filled=c.get("filled", False),
            )
            for c in data["cells"]
        ]
        return cls(
            cap_diameter_mm=data["cap_diameter_mm"],
            width_mm=data["width_mm"],
            height_mm=data["height_mm"],
            cells=cells,
            title=data.get("title", "untitled"),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "GridPlan":
        return cls.from_dict(json.loads(Path(path).read_text()))


def grid_to_cap(grid: Grid) -> Cap:
    return grid.cap
