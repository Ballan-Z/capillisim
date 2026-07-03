"""Rotation-invariant cap signature for re-identification.

A cap lands on the reading card at a random rotation, so a useful visual
fingerprint must ignore rotation. Concentric rings do that by construction:
we locate the cap disc, split it into ``RINGS`` annuli, and describe each ring
by its mean Lab colour (3) plus a 4-bin luminance histogram — radial structure
(a gold centre vs a gold ring) survives, angular position doesn't.

Stored per cap in the existing ``embedding`` table under model ``'ringsig-v1'``;
compared with plain euclidean distance. Same physical cap re-scanned under
similar conditions lands very close; different caps with different face layouts
land far — two different caps of the SAME design are (correctly) near-identical.
"""

from __future__ import annotations

import numpy as np

from .cap_crop import detect_cap_circle

RINGS = 8
_BINS = 4
SIG_LEN = RINGS * (3 + _BINS)  # 56
MODEL_NAME = "ringsig-v1"


def _rgb_to_lab_np(rgb: np.ndarray) -> np.ndarray:
    c = np.asarray(rgb, dtype=float) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin[:, 0], lin[:, 1], lin[:, 2]
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=1)


def cap_signature(crop_rgb: np.ndarray, rings: int = RINGS) -> np.ndarray:
    """The rotation-invariant descriptor of a cap crop (float32, SIG_LEN)."""
    import cv2

    a = np.asarray(crop_rgb, dtype=np.uint8)
    h, w = a.shape[:2]
    found = detect_cap_circle(cv2.cvtColor(a, cv2.COLOR_RGB2BGR))
    if found is not None:
        cx, cy, r = found
        r *= 0.92  # stay inside the crimped rim
    else:
        cx, cy, r = w / 2.0, h / 2.0, min(h, w) * 0.42
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.hypot(xx - cx, yy - cy)

    feats: list[float] = []
    edges = np.linspace(0.0, r, rings + 1)
    for i in range(rings):
        band = (dist >= edges[i]) & (dist < edges[i + 1])
        px = a[band].reshape(-1, 3)
        if len(px) == 0:
            feats.extend([0.0] * (3 + _BINS))
            continue
        lab = _rgb_to_lab_np(px)
        feats.extend((lab.mean(axis=0) / 100.0).tolist())  # L,a,b scaled ~O(1)
        lum = px.mean(axis=1)
        hist, _ = np.histogram(lum, bins=_BINS, range=(0, 256))
        feats.extend((hist / len(px)).tolist())
    return np.asarray(feats, dtype=np.float32)


def signature_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float)))
