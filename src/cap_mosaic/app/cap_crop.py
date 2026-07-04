"""Auto-crop a bottle cap out of a photo so every cap is equal and cut out.

Captured cap crops are framed inconsistently — the cap sits off-centre on a
background, sometimes with guide text. To make a mosaic where every cap is the
same size, we detect the cap disc (Hough circle, with a saturation/darkness blob
fallback) and return a tight, circular RGBA cut-out. cv2 lives in the app layer,
not core.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def detect_cap_circle(bgr: np.ndarray) -> tuple[int, int, int] | None:
    """(cx, cy, r) of the cap in a BGR image, or None if nothing plausible."""
    h, w = bgr.shape[:2]
    gray = cv2.medianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 5)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1, minDist=w,
        param1=100, param2=30, minRadius=int(w * 0.2), maxRadius=int(w * 0.55))
    if circles is not None:
        cx, cy, r = np.round(circles[0][0]).astype(int)
        return int(cx), int(cy), int(r)
    # fallback: the cap is more saturated / darker than a white-ish background
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    dark = 255 - cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = ((hsv[:, :, 1] > 40) | (dark > 90)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    (cx, cy), r = cv2.minEnclosingCircle(max(cnts, key=cv2.contourArea))
    return int(cx), int(cy), int(r)


def _shrink_to_cap_edge(bgr: np.ndarray, cx: int, cy: int, r: int) -> int:
    """Walk the radius inward while the outer ring is still card-white.

    Hough often locks onto the printed placement circle (bigger than the cap),
    which pads the cutout with white card — glued caps must meet at their real
    edges, so the circle has to hug the cap. Stop as soon as the ring band just
    inside the radius is mostly non-white (the cap edge), floor at 0.55·r.
    """
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    rr = float(r)
    while rr > 0.55 * r:
        band = (d2 >= (0.90 * rr) ** 2) & (d2 <= rr ** 2)
        px = rgb[band]
        if px.size and (px >= 215).all(axis=1).mean() < 0.5:
            break
        rr *= 0.96
    return max(4, int(rr))


def cap_cutout(bgr: np.ndarray, size: int = 64) -> Image.Image:
    """Tight, centred, circular RGBA cut-out of the cap in `bgr`, `size` px square."""
    h, w = bgr.shape[:2]
    c = detect_cap_circle(bgr)
    cx, cy, r = c if c is not None else (w // 2, h // 2, min(w, h) // 2 - 1)
    r = _shrink_to_cap_edge(bgr, cx, cy, max(4, r))
    x0, y0, x1, y1 = max(0, cx - r), max(0, cy - r), min(w, cx + r), min(h, cy + r)
    crop = cv2.resize(bgr[y0:y1, x0:x1], (size, size), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    mask = np.zeros((size, size), np.uint8)
    cv2.circle(mask, (size // 2, size // 2), size // 2 - 1, 255, -1)
    return Image.fromarray(np.dstack([rgb, mask]), "RGBA")


def cap_cutout_from_path(path: str, size: int = 64) -> Image.Image | None:
    bgr = cv2.imread(path)
    return None if bgr is None else cap_cutout(bgr, size)
