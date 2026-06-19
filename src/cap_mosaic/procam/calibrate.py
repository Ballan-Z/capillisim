"""Projector <-> table calibration.

The projector hangs above the table but is rarely perfectly perpendicular, so a
projected rectangle lands as a keystoned quadrilateral. A homography (3x3
projective transform) maps table millimetres to projector pixels, recovering
true 1:1 scale and correcting the keystone, so any cell can be drawn at its
correct real-world position and size.

POC calibration flow: project four markers at known projector-pixel positions,
have the user report where each lands on the table in millimetres (e.g. against
a taped ruler / known rectangle), then solve for the homography. Four
correspondences are the minimum; more improve robustness via least squares.

Pure numpy (no OpenCV) so it runs and tests headless.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

Point = tuple[float, float]


def compute_homography(src: list[Point], dst: list[Point]) -> np.ndarray:
    """3x3 homography mapping src points to dst points (Direct Linear Transform).

    Needs >= 4 non-collinear correspondences. With exactly 4 it is exact; with
    more it is a least-squares fit.
    """
    if len(src) != len(dst) or len(src) < 4:
        raise ValueError("need >= 4 matched point pairs")
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        a.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(np.asarray(a, dtype=float))
    h = vt[-1].reshape(3, 3)
    if abs(h[2, 2]) < 1e-12:
        raise ValueError("degenerate correspondences")
    return h / h[2, 2]


def apply_homography(h: np.ndarray, pt: Point) -> Point:
    x, y = pt
    v = h @ np.array([x, y, 1.0])
    return (float(v[0] / v[2]), float(v[1] / v[2]))


@dataclass
class Calibration:
    """Maps table millimetres to projector pixels (and back)."""

    h_table_to_proj: np.ndarray
    proj_width: int
    proj_height: int

    @property
    def h_proj_to_table(self) -> np.ndarray:
        return np.linalg.inv(self.h_table_to_proj)

    @classmethod
    def from_correspondences(
        cls,
        table_mm: list[Point],
        proj_px: list[Point],
        proj_width: int,
        proj_height: int,
    ) -> "Calibration":
        h = compute_homography(table_mm, proj_px)
        return cls(h, proj_width, proj_height)

    @classmethod
    def fit_to_frame(
        cls,
        width_mm: float,
        height_mm: float,
        proj_width: int,
        proj_height: int,
        margin: float = 0.05,
        rotate: int = 0,
        widen: float = 1.0,
    ) -> "Calibration":
        """Calibration-free fallback: map a `width_mm` x `height_mm` plan to fill
        the projector frame (centred, aspect-preserved), no measuring.

        ``rotate`` (0/90/180/270 degrees) re-orients the plan in the frame — e.g.
        90 for a horizontal frame under a landscape projector. ``margin`` shrinks
        the plan inside the frame (0.05 = fill, higher = smaller). ``widen`` > 1
        stretches the projection horizontally to match a wider frame (distorts a
        non-matching aspect; prefer a plan whose aspect matches the frame).

        There is no keystone correction and no true table scale — the projector
        must be squared and focused by its own controls. Use a measured
        :meth:`from_correspondences` calibration when 1:1 / keystone matters.
        """
        avail_w = proj_width * (1 - 2 * margin)
        avail_h = proj_height * (1 - 2 * margin)
        rot = rotate % 360
        eff_w, eff_h = (height_mm, width_mm) if rot in (90, 270) else (width_mm, height_mm)
        scale = min(avail_w / eff_w, avail_h / eff_h)  # px per mm
        cx, cy = proj_width / 2, proj_height / 2
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        src = [(0.0, 0.0), (width_mm, 0.0), (width_mm, height_mm), (0.0, height_mm)]
        dst = []
        for x, y in src:
            rx, ry = (x - width_mm / 2) * scale, (y - height_mm / 2) * scale
            dst.append((cx + (rx * ca - ry * sa) * widen, cy + rx * sa + ry * ca))
        return cls.from_correspondences(src, dst, proj_width, proj_height)

    def table_mm_to_proj_px(self, x_mm: float, y_mm: float) -> Point:
        return apply_homography(self.h_table_to_proj, (x_mm, y_mm))

    def proj_px_to_table_mm(self, px: float, py: float) -> Point:
        return apply_homography(self.h_proj_to_table, (px, py))

    def mm_radius_to_px(self, x_mm: float, y_mm: float, r_mm: float) -> float:
        """Projected radius (px) of an r_mm circle centred at (x_mm, y_mm)."""
        cx, cy = self.table_mm_to_proj_px(x_mm, y_mm)
        ex, ey = self.table_mm_to_proj_px(x_mm + r_mm, y_mm)
        return float(np.hypot(ex - cx, ey - cy))

    def to_dict(self) -> dict:
        return {
            "h_table_to_proj": self.h_table_to_proj.tolist(),
            "proj_width": self.proj_width,
            "proj_height": self.proj_height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Calibration":
        return cls(
            np.asarray(data["h_table_to_proj"], dtype=float),
            int(data["proj_width"]),
            int(data["proj_height"]),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "Calibration":
        return cls.from_dict(json.loads(Path(path).read_text()))
