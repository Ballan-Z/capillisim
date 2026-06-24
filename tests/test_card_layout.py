"""Card layout spec + generator: self-consistency and a render->detect round-trip."""

import cv2
import numpy as np

from cap_mosaic.app.make_card import render_card
from cap_mosaic.vision import card_layout as L


def test_layout_self_consistent():
    assert sorted(m.id for m in L.MARKERS) == [0, 1, 2, 3]
    assert any(g.value == L.REFERENCE_VALUE for g in L.GRAY_PATCHES)
    half = L.MARKER_SIZE_MM / 2
    for m in L.MARKERS:  # markers (with their footprint) inside the card
        assert 0 < m.cx_mm - half and m.cx_mm + half < L.CARD_W_MM
        assert 0 < m.cy_mm - half and m.cy_mm + half < L.CARD_H_MM
    assert L.CIRCLE_CX_MM - L.CIRCLE_R_MM > 0
    assert L.CIRCLE_CX_MM + L.CIRCLE_R_MM < L.CARD_W_MM
    assert L.CIRCLE_CY_MM + L.CIRCLE_R_MM < L.CARD_H_MM


def test_circle_value_fills_placement_circle_gray():
    dpi = 200
    ppm = dpi / 25.4
    gray_card = np.asarray(render_card(dpi, circle_value=128))
    white_card = np.asarray(render_card(dpi))  # default: unfilled (white) circle
    cy, cx = int(L.CIRCLE_CY_MM * ppm), int(L.CIRCLE_CX_MM * ppm)
    # sample just off-centre to avoid the printed crosshair at the exact centre
    off = int(6 * ppm)
    g = gray_card[cy - off, cx + off]
    w = white_card[cy - off, cx + off]
    assert abs(int(g.mean()) - 128) < 25, g  # circle now mid-gray
    assert int(w.mean()) > 240, w           # default still white


def test_render_roundtrip_detect_all_markers():
    img = render_card(dpi=200)
    gray = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
    adict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, L.ARUCO_DICT))
    detector = cv2.aruco.ArucoDetector(adict, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)
    assert ids is not None
    assert set(int(i) for i in ids.flatten()) == {0, 1, 2, 3}
