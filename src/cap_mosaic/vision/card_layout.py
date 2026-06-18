"""Cap Reading Card layout — the single source of truth for the card geometry.

Both the card generator (``app.make_card``) and the card reader
(``vision.card_reader``) import this, so the printed card and the detector can
never drift apart. All positions are in millimetres on a 120 x 90 mm card with
its origin at the top-left.

Features:
- four ArUco markers (DICT_4X4_50, ids 0-3) near the corners, used to locate and
  rectify the card,
- a strip of neutral gray patches for white-balance,
- a central circle where one cap is placed for reading.
"""

from __future__ import annotations

from dataclasses import dataclass

CARD_W_MM = 120.0
CARD_H_MM = 90.0

ARUCO_DICT = "DICT_4X4_50"  # resolved via getattr(cv2.aruco, ARUCO_DICT)
MARKER_SIZE_MM = 16.0


@dataclass(frozen=True)
class Marker:
    id: int
    cx_mm: float
    cy_mm: float


# ids: 0=top-left, 1=top-right, 2=bottom-left, 3=bottom-right
MARKERS: tuple[Marker, ...] = (
    Marker(0, 14.0, 14.0),
    Marker(1, 106.0, 14.0),
    Marker(2, 14.0, 76.0),
    Marker(3, 106.0, 76.0),
)


@dataclass(frozen=True)
class GrayPatch:
    value: int  # 0..255 neutral gray (R=G=B)
    cx_mm: float
    cy_mm: float


GRAY_SIZE_MM = 12.0
REFERENCE_VALUE = 128  # the primary white-balance reference patch
# evenly spaced between the two top markers, on the same y band
GRAY_PATCHES: tuple[GrayPatch, ...] = (
    GrayPatch(255, 31.2, 14.0),
    GrayPatch(192, 45.6, 14.0),
    GrayPatch(128, 60.0, 14.0),
    GrayPatch(64, 74.4, 14.0),
    GrayPatch(0, 88.8, 14.0),
)

# cap placement circle (sized for a ~32 mm cap with margin)
CIRCLE_CX_MM = 60.0
CIRCLE_CY_MM = 48.0
CIRCLE_R_MM = 18.0


def marker_centers_mm() -> dict[int, tuple[float, float]]:
    """Canonical marker centres keyed by id, in card millimetres."""
    return {m.id: (m.cx_mm, m.cy_mm) for m in MARKERS}
