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


def _edge_circle_search(
    gray: np.ndarray,
    r_lo: float,
    r_hi: float,
    r_prior: float | None = None,
    prior_sigma: float = 0.20,
    centre_frac: float = 0.20,
    k_angles: int = 180,
    seeds: list[tuple[float, float]] | None = None,
) -> tuple[int, int, int]:
    """Best circle by CIRCULAR-EDGE RESPONSE: the (cx, cy, r) maximizing the mean
    radial brightness step |g(r+2) − g(r−2)| sampled along the circle.

    Why this replaces blob/Hough trust: a cap+shadow blob shifts a centroid or
    distance-transform peak toward the shadow, and Hough constrained to a wrong
    recorded radius shifts the circle off the cap to keep edge overlap. Scoring
    the actual circular edge over a centre grid × radius band is immune to both;
    a MILD radius prior breaks ties without overruling a strong true edge (so an
    over-measured diameter or a wrong crop-span assumption still snaps to the
    real rim). Two-stage grid (coarse then ±3 px fine) keeps it fast.
    """
    h, w = gray.shape
    g = gray.astype(np.float32)
    radii = np.arange(max(4.0, r_lo), max(5.0, r_hi) + 1, 1.0)
    ang = np.linspace(0, 2 * np.pi, k_angles, endpoint=False)
    ca, sa = np.cos(ang), np.sin(ang)
    prior = (np.exp(-0.5 * ((radii - r_prior) / (prior_sigma * max(r_prior, 1.0))) ** 2)
             if r_prior else np.ones_like(radii))

    def score_at(cx: float, cy: float) -> tuple[float, float]:
        xo = cx + np.outer(radii + 2, ca)
        yo = cy + np.outer(radii + 2, sa)
        xi = cx + np.outer(np.maximum(radii - 2, 1), ca)
        yi = cy + np.outer(np.maximum(radii - 2, 1), sa)
        inb = (xo >= 0) & (xo <= w - 1) & (yo >= 0) & (yo <= h - 1)

        def samp(x, y):
            return g[np.clip(np.rint(y).astype(int), 0, h - 1),
                     np.clip(np.rint(x).astype(int), 0, w - 1)]

        # signed, brighter-outside step (caps sit on a white card): a TRUE rim
        # has it along (almost) the whole circle, while a mixed impostor (rim on
        # one arc, shadow outline on another) collapses at a low percentile.
        # Out-of-frame samples are NaN so a cap near the border isn't punished
        # by phantom zero-edges; heavily out-of-frame circles are down-weighted.
        diff = np.clip(samp(xo, yo) - samp(xi, yi), 0, None)
        diff = np.where(inb, diff, np.nan)
        with np.errstate(invalid="ignore"):
            mean = np.nan_to_num(np.nanmean(diff, axis=1))
            floor = np.nan_to_num(np.nanpercentile(diff, 30, axis=1))
        s = (0.5 * mean + 0.5 * floor) * np.where(inb.mean(1) > 0.55, 1.0, 0.35) * prior
        i = int(s.argmax())
        return float(s[i]), float(radii[i])

    def sweep(cxs, cys):
        best = (-1.0, w / 2, h / 2, float(radii[len(radii) // 2]))
        for cy in cys:
            for cx in cxs:
                s, r = score_at(cx, cy)
                if s > best[0]:
                    best = (s, cx, cy, r)
        return best

    span = centre_frac * min(w, h)
    best = (-1.0, w / 2, h / 2, float(radii[len(radii) // 2]))
    for sx, sy in (seeds or [(w / 2, h / 2)]):
        cand = sweep(np.arange(sx - span, sx + span + 1, 3.0),
                     np.arange(sy - span, sy + span + 1, 3.0))
        if cand[0] > best[0]:
            best = cand
    _, cx0, cy0, _ = best
    _, cx, cy, r = sweep(np.arange(cx0 - 3, cx0 + 3.5, 1.0),
                         np.arange(cy0 - 3, cy0 + 3.5, 1.0))
    return int(round(cx)), int(round(cy)), max(4, int(round(r)))


def _refine_known_circle(bgr: np.ndarray, r_px: float) -> tuple[int, int, int]:
    """Centre + radius of a cap of KNOWN (but possibly mis-recorded) size.

    The recorded geometry is a PRIOR, not the truth: legacy rows can carry the
    wrong crop-span assumption (radius up to ~27% overstated) and some measured
    diameters are off. The circular-edge search over a generous band around the
    prior finds the physical rim in all those cases — including white caps on
    the white card, where the rim's faint edge is still the strongest circle.
    """
    g = cv2.medianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 3)
    return _edge_circle_search(g, 0.62 * r_px, 1.12 * r_px,
                               r_prior=r_px, prior_sigma=0.20)


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
    # blind: the same circular-edge search decides, seeded by the classic
    # detectors (their circles position centre windows but are never trusted —
    # locate_cap can return an insane blob when cap, shadow and card marks
    # merge). Radius band = anything physically plausible for a cap in a crop.
    g = cv2.medianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 3)
    seeds = [(w / 2, h / 2)]
    for cand in (locate_cap(bgr), detect_cap_circle(bgr)):
        if cand is not None and 0 <= cand[0] <= w and 0 <= cand[1] <= h:
            seeds.append((float(cand[0]), float(cand[1])))
    return _edge_circle_search(g, 0.15 * w, 0.51 * w, centre_frac=0.14,
                               seeds=seeds)


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
