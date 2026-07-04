import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from cap_mosaic.vision import card_layout as L
from cap_mosaic.vision.card_reader import measure_cap_diameter_mm


def _frame(scale=4.0, cap_mm=None, printed_ring=True, size=(900, 900)):
    """Synthetic white frame at `scale` px/mm with an optional dark cap disc."""
    h = np.array([[scale, 0, 60.0], [0, scale, 60.0], [0, 0, 1.0]])
    img = np.full((*size, 3), 250, np.uint8)
    cx = int(L.CIRCLE_CX_MM * scale + 60)
    cy = int(L.CIRCLE_CY_MM * scale + 60)
    if printed_ring:  # the thin printed placement circle
        cv2.circle(img, (cx, cy), int(L.CIRCLE_R_MM * scale), (150, 150, 150), 2)
    if cap_mm:
        r = int(cap_mm / 2 * scale)
        cv2.circle(img, (cx, cy), r, (30, 40, 120), -1)      # cap body
        cv2.circle(img, (cx, cy), r, (20, 20, 20), 3)         # rim
    return img, h


def test_measures_a_standard_crown():
    img, h = _frame(cap_mm=26.0)
    d = measure_cap_diameter_mm(img, h)
    assert d is not None and abs(d - 26.0) < 1.5, d


def test_measures_a_large_cap():
    img, h = _frame(cap_mm=38.0)
    d = measure_cap_diameter_mm(img, h)
    assert d is not None and abs(d - 38.0) < 1.5, d


def test_empty_circle_returns_none():
    img, h = _frame(cap_mm=None)  # just the printed ring, no cap
    assert measure_cap_diameter_mm(img, h) is None


def test_works_at_a_different_camera_scale():
    img, h = _frame(scale=6.5, cap_mm=29.0)
    d = measure_cap_diameter_mm(img, h)
    assert d is not None and abs(d - 29.0) < 1.5, d


def test_ignores_dark_table_at_roi_edge():
    # dark table visible past the card edge is a BIGGER blob than the cap;
    # the measurement must size the cap (nearest the placement centre), not it
    img, h = _frame(cap_mm=26.0)
    img[:, 380:] = 25                       # dark table strip through the ROI edge
    d = measure_cap_diameter_mm(img, h)
    assert d is not None and abs(d - 26.0) < 1.5, d


def test_shadow_bridge_does_not_inflate():
    # a shadow bridging cap -> dark table merged the blob; minEnclosingCircle
    # then spanned both (live: a standard crown read 40mm -> large-38)
    img, h = _frame(cap_mm=26.0)
    scale = 4.0
    cx = int(L.CIRCLE_CX_MM * scale + 60)
    cy = int(L.CIRCLE_CY_MM * scale + 60)
    img[:, 380:] = 25                                       # dark table
    cv2.line(img, (cx, cy), (420, cy - 80), (40, 40, 40),   # 3mm-wide shadow bridge
             int(3 * scale))
    d = measure_cap_diameter_mm(img, h)
    assert d is not None and abs(d - 26.0) < 3.0, d


def test_white_logo_does_not_shrink_measurement():
    # a big white logo/text is a HOLE in the not-card-white mask; the inscribed
    # circle must be taken on the hole-filled blob or a 38mm cap reads ~26
    img, h = _frame(cap_mm=38.0)
    scale = 4.0
    cx = int(L.CIRCLE_CX_MM * scale + 60)
    cy = int(L.CIRCLE_CY_MM * scale + 60)
    cv2.circle(img, (cx, cy), int(11 * scale), (245, 245, 245), -1)  # near-white logo
    d = measure_cap_diameter_mm(img, h)
    assert d is not None and abs(d - 38.0) < 1.5, d


def test_white_text_ring_does_not_split_measurement():
    # a white text ring (e.g. 'OVER WORKS' band) splits the mask into inner
    # disc + rim ring; sizing the nearest component alone reads a 38mm cap ~27
    img, h = _frame(cap_mm=38.0)
    scale = 4.0
    cx = int(L.CIRCLE_CX_MM * scale + 60)
    cy = int(L.CIRCLE_CY_MM * scale + 60)
    cv2.circle(img, (cx, cy), int(15 * scale), (245, 245, 245), int(4 * scale))
    d = measure_cap_diameter_mm(img, h)
    assert d is not None and abs(d - 38.0) < 1.5, d


def test_shadow_lobe_does_not_inflate():
    # a soft cast shadow forms a wide dark lobe attached to one side of the
    # cap (live: made a standard crown read large even without a bridge);
    # the symmetric fold must replace it with the true edge opposite
    img, h = _frame(cap_mm=26.0)
    scale = 4.0
    cx = int(L.CIRCLE_CX_MM * scale + 60)
    cy = int(L.CIRCLE_CY_MM * scale + 60)
    cv2.ellipse(img, (cx + int(8 * scale), cy + int(8 * scale)),
                (int(12 * scale), int(9 * scale)), 45, 0, 360, (140, 140, 140), -1)
    d = measure_cap_diameter_mm(img, h)
    assert d is not None and abs(d - 26.0) < 2.0, d


def test_crop_cap_default_span_unchanged():
    from cap_mosaic.vision.card_reader import crop_cap

    img, h = _frame(cap_mm=26.0)
    a = crop_cap(img, h, 128)
    b = crop_cap(img, h, 128, span_mm=None)
    assert a is not None and np.array_equal(a, b)  # regression: None == old behaviour


def test_wide_span_contains_a_large_cap_fully():
    from cap_mosaic.vision.card_reader import crop_cap

    img, h = _frame(cap_mm=38.0)
    tight = crop_cap(img, h, 128)                # 37.8mm window: cap touches edges
    wide = crop_cap(img, h, 128, span_mm=48.0)   # adaptive window
    def edge_touch(crop):
        dark = ~np.all(crop >= 215, axis=2)
        border = np.concatenate([dark[0], dark[-1], dark[:, 0], dark[:, -1]])
        return border.mean() > 0.05
    assert edge_touch(tight)          # the clipping bug being fixed
    assert not edge_touch(wide)       # whole cap inside the wide window
