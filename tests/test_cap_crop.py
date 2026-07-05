import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from cap_mosaic.app.cap_crop import cap_cutout, detect_cap_circle


def _cap_on_white(n=128, cx=44, cy=52, r=28, color=(40, 60, 200)):
    """A BGR image: an off-centre coloured disc (with a dark rim) on white."""
    img = np.full((n, n, 3), 255, np.uint8)
    cv2.circle(img, (cx, cy), r, color, -1)             # BGR fill
    cv2.circle(img, (cx, cy), r, (30, 30, 30), 3)       # dark crimped rim
    return img


def test_detects_offcentre_cap():
    img = _cap_on_white(cx=44, cy=52, r=28)
    c = detect_cap_circle(img)
    assert c is not None
    cx, cy, r = c
    assert abs(cx - 44) <= 6 and abs(cy - 52) <= 6
    assert abs(r - 28) <= 8


def test_cutout_is_centred_and_circular():
    img = _cap_on_white(cx=44, cy=52, r=28, color=(40, 60, 200))
    out = cap_cutout(img, size=64)
    assert out.size == (64, 64) and out.mode == "RGBA"
    a = np.asarray(out)
    # centre is the cap colour: BGR fill (40,60,200) -> RGB (200,60,40), opaque
    r, g, b, alpha = a[32, 32]
    assert alpha == 255 and r > 150 and b < 120
    # corners are outside the circle -> transparent
    assert a[0, 0, 3] == 0 and a[63, 63, 3] == 0


def _cap_with_shadow(n=128, cx=70, cy=56, r=30, color=(60, 90, 40)):
    """Card-style crop: cap disc + a soft dark shadow lobe DOWN-LEFT of it —
    the exact artefact that drags blob-based centres off the cap."""
    img = np.full((n, n, 3), 250, np.uint8)
    cv2.ellipse(img, (cx - 14, cy + 14), (int(r * 1.05), int(r * 0.8)), 30, 0, 360,
                (205, 205, 208), -1)                     # shadow (not card-white)
    cv2.circle(img, (cx, cy), r, color, -1)
    cv2.circle(img, (cx, cy), r, (25, 25, 25), 3)        # crimped rim
    return img


def test_geometry_centre_resists_shadow():
    img = _cap_with_shadow(cx=70, cy=56, r=30)
    from cap_mosaic.app.cap_crop import cap_circle

    cx, cy, r = cap_circle(img, radius_frac=30 / 128)    # known radius
    assert abs(cx - 70) <= 3 and abs(cy - 56) <= 3        # centre ON the cap
    assert abs(r - 30) <= 3


def test_overstated_diameter_snaps_to_true_edge():
    img = _cap_with_shadow(cx=64, cy=64, r=28)
    from cap_mosaic.app.cap_crop import cap_circle

    # recorded diameter 15% too large: the strong physical edge must win
    cx, cy, r = cap_circle(img, radius_frac=(28 * 1.15) / 128)
    assert abs(r - 28) <= 3
    assert abs(cx - 64) <= 3 and abs(cy - 64) <= 3


def test_blind_path_respects_physical_band_despite_shadow():
    img = _cap_with_shadow(cx=58, cy=60, r=45)           # 45/128 = 0.35 width: in band
    from cap_mosaic.app.cap_crop import cap_circle

    cx, cy, r = cap_circle(img, radius_frac=None)
    assert abs(cx - 58) <= 4 and abs(cy - 60) <= 4
    assert 0.30 * 128 <= r <= 0.52 * 128                  # never a tiny/huge grab


def _cutout_quality(path, rf, ref_rgb):
    """(white-fringe fraction, dE00 of linear-mean vs the cap's known colour)."""
    from cap_mosaic.app.cap_crop import cap_cutout_from_path
    from cap_mosaic.core.palette import ciede2000, rgb_to_lab

    a = np.asarray(cap_cutout_from_path(path, 64, radius_frac=rf))
    n = a.shape[0]
    yy, xx = np.ogrid[:n, :n]
    rr = np.hypot(xx - n / 2, yy - n / 2)
    ring = (rr >= 0.80 * n / 2) & (rr <= 0.97 * n / 2) & (a[:, :, 3] > 128)
    fringe = float((a[ring][:, :3] >= 235).all(1).mean())
    body = a[a[:, :, 3] > 128][:, :3].astype(float) / 255.0
    lin = np.where(body <= 0.04045, body / 12.92, ((body + 0.055) / 1.055) ** 2.4).mean(0)
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    mean = tuple(int(round(v * 255)) for v in srgb)
    return fringe, ciede2000(rgb_to_lab(mean), rgb_to_lab(ref_rgb))


def test_real_crop_26_wrong_span_prior():
    # legacy row: span unknown (37.8 assumed) but captured with the 48mm window,
    # so the radius prior is ~27% too large — the cut must still hug the cap
    fringe, de = _cutout_quality("tests/fixtures/crop_26.png", 0.3968, (116, 48, 15))
    assert fringe < 0.15, fringe
    assert de < 12, de


def test_real_crop_236_overmeasured_diameter():
    # diameter_mm over-measured (41.7): the true edge must win over the prior
    fringe, de = _cutout_quality("tests/fixtures/crop_236.png", 0.4345, (91, 89, 85))
    assert fringe < 0.15, fringe


def test_real_crop_16_blind_sanity():
    # blind path: locate_cap returned centre (0,0), radius = whole image; the
    # cut must land on the cap (orange) instead
    fringe, de = _cutout_quality("tests/fixtures/crop_16.png", None, (166, 90, 83))
    assert fringe < 0.15, fringe
    assert de < 14, de


def test_cutout_handles_blank_image():
    blank = np.full((100, 100, 3), 255, np.uint8)
    out = cap_cutout(blank, size=48)  # no cap -> falls back to centre disc
    assert out.size == (48, 48)
