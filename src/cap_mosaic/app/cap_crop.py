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


def locate_cap(bgr: np.ndarray) -> tuple[int, int, int] | None:
    """Precise (cx, cy, r) hugging the cap's metal edge, or None.

    The guarded pipeline proven by size measurement, applied to localisation:
    not-card-white mask -> gentle CLOSE (seal glare gaps in the rim, so a
    white cap's faint rim ring stays closed) -> OPEN (drop printed text /
    thin lines) -> hole-fill (a white cap face inside its rim, or any white
    logo, becomes part of the blob instead of splitting it) -> the component
    nearest the frame centre -> centre at the DISTANCE-TRANSFORM PEAK (a
    shadow lobe can't drag it like a centroid) -> per-direction outer radius,
    SYMMETRICALLY FOLDED min(r(θ), r(θ+180°)) so one-sided shadows are
    replaced by the true edge opposite -> 60th percentile: snug on the metal
    edge, marginally inside the teeth tips rather than leaving card padding.
    """
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    mask = (~np.all(rgb >= 215, axis=2)).astype(np.uint8) * 255
    kc = max(3, int(w * 0.02) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((kc, kc), np.uint8))
    ko = max(3, int(w * 0.03) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((ko, ko), np.uint8))
    solid = (mask > 0).astype(np.uint8)
    ff = solid.copy()
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
    solid[(ff == 0)] = 1
    n, labels, stats, cents = cv2.connectedComponentsWithStats(solid, connectivity=8)
    best = None
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 0.02 * w * h:  # specks aren't caps
            continue
        d2 = (cents[i][0] - w / 2) ** 2 + (cents[i][1] - h / 2) ** 2
        if best is None or d2 < best[0]:
            best = (d2, i)
    if best is None:
        return None
    comp = (labels == best[1]).astype(np.uint8)
    dt = cv2.distanceTransform(comp, cv2.DIST_L2, 5)
    cy, cx = np.unravel_index(int(dt.argmax()), dt.shape)
    ys, xs = np.nonzero(comp)
    r = np.hypot(xs - cx, ys - cy)
    bins = (np.degrees(np.arctan2(ys - cy, xs - cx)) % 360.0).astype(int) % 360
    rmax = np.zeros(360)
    np.maximum.at(rmax, bins, r)
    opp = np.roll(rmax, 180)
    both = (rmax > 0) & (opp > 0)
    folded = np.where(both, np.minimum(rmax, opp), np.maximum(rmax, opp))
    folded = folded[folded > 0]
    if folded.size < 180:
        return None
    rr = float(np.percentile(folded, 60))
    if rr < 0.1 * min(w, h):
        return None
    return int(cx), int(cy), max(4, int(round(rr)))


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


def _refine_known_circle(bgr: np.ndarray, r_px: float) -> tuple[int, int, int]:
    """Centre (and slightly refined radius) of a cap of KNOWN size.

    Dataset crops carry their geometry (crop span in mm + the cap's class
    size), which beats any blind detection — especially for a white cap on
    the white card, invisible to thresholds. Hough restricted to a narrow
    radius band around the known r can only lock onto the cap (the printed
    circle has a different radius); if it finds nothing, the cap was placed
    on the crop centre by construction.
    """
    g = cv2.medianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 3)
    h, w = g.shape
    cx, cy = w / 2, h / 2

    def _sane(px: float, py: float) -> bool:
        return abs(px - w / 2) < 0.25 * w and abs(py - h / 2) < 0.25 * h

    # centre: the pixel pipeline's distance-transform peak is the most precise
    # for dark caps; a white cap is invisible to it (it then grabs a shadow
    # blob), so only trust it when its own radius agrees with the known size
    located = locate_cap(bgr)
    if (located is not None and _sane(located[0], located[1])
            and 0.75 * r_px <= located[2] <= 1.2 * r_px):
        cx, cy = float(located[0]), float(located[1])
    else:
        circles = cv2.HoughCircles(
            g, cv2.HOUGH_GRADIENT, dp=1, minDist=w,
            param1=80, param2=25,
            minRadius=int(0.85 * r_px), maxRadius=int(1.12 * r_px))
        if circles is not None and _sane(*circles[0][0][:2]):
            cx, cy = float(circles[0][0][0]), float(circles[0][0][1])
    # radius = the steepest step in the radial brightness profile around the
    # known size: the cap edge. (Hough's own radius often lands on the soft
    # shadow halo outside a dark cap.)
    yy, xx = np.ogrid[:h, :w]
    rmap = np.hypot(xx - cx, yy - cy).astype(int)
    lo, hi = int(0.80 * r_px), min(int(1.15 * r_px), rmap.max() - 1)
    prof = np.array([g[rmap == radius].mean() if (rmap == radius).any() else np.nan
                     for radius in range(lo, hi + 1)])
    grad = np.abs(np.diff(prof))
    if grad.size and np.isfinite(grad).any():
        # strongest step WEIGHTED by closeness to the expected size: a printed
        # label ring inside the cap and the soft shadow halo outside it can
        # both out-gradient the physical edge, but neither sits at ~r_px
        radii = np.arange(lo, lo + grad.size)
        prior = np.exp(-0.5 * ((radii - r_px) / (0.08 * r_px)) ** 2)
        score = np.where(np.isfinite(grad), grad, 0.0) * prior
        r = lo + int(np.argmax(score))
    else:
        r = int(round(r_px))
    return int(round(cx)), int(round(cy)), max(4, r)


def cap_circle(bgr: np.ndarray, radius_frac: float | None = None) -> tuple[int, int, int]:
    """The (cx, cy, r) a cutout will use — geometry-driven when known.

    ``radius_frac`` — the cap's known radius as a fraction of the image width
    (dataset crops: ``(cap_mm / span_mm) / 2``). When given, geometry drives
    the cut and only the centre + exact edge are refined; when None, the cap
    is located from the pixels alone.
    """
    h, w = bgr.shape[:2]
    if radius_frac is not None:
        return _refine_known_circle(bgr, radius_frac * w)
    c = locate_cap(bgr)
    if c is not None:
        return c
    c = detect_cap_circle(bgr)  # e.g. non-card photos the mask pipeline can't parse
    cx, cy, r = c if c is not None else (w // 2, h // 2, min(w, h) // 2 - 1)
    return cx, cy, _shrink_to_cap_edge(bgr, cx, cy, max(4, r))


def cap_cutout(bgr: np.ndarray, size: int = 64,
               radius_frac: float | None = None) -> Image.Image:
    """Tight, centred, circular RGBA cut-out of the cap in `bgr`, `size` px square."""
    cx, cy, r = cap_circle(bgr, radius_frac)
    # pad instead of clamping: a cap near the frame edge must stay a centred
    # circle, not get squished by a truncated crop box
    padded = cv2.copyMakeBorder(bgr, r, r, r, r, cv2.BORDER_REPLICATE)
    crop = padded[cy : cy + 2 * r, cx : cx + 2 * r]
    crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    mask = np.zeros((size, size), np.uint8)
    cv2.circle(mask, (size // 2, size // 2), size // 2 - 1, 255, -1)
    return Image.fromarray(np.dstack([rgb, mask]), "RGBA")


def cap_cutout_from_path(path: str, size: int = 64,
                         radius_frac: float | None = None) -> Image.Image | None:
    bgr = cv2.imread(path)
    return None if bgr is None else cap_cutout(bgr, size, radius_frac=radius_frac)
