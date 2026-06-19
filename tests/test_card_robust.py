"""Detection robustness: hold the last card location across brief dropouts."""

import cv2
import numpy as np
from PIL import ImageDraw

from cap_mosaic.app.make_card import render_card
from cap_mosaic.core.palette import ciede2000, rgb_to_lab
from cap_mosaic.vision import card_layout as L
from cap_mosaic.vision.card_reader import CardCapReader, card_mm_to_px, detect_card


def _frame_with_cap(true_rgb, dpi=200):
    ppm = dpi / 25.4
    card = render_card(dpi).copy()
    draw = ImageDraw.Draw(card)
    cx, cy = L.CIRCLE_CX_MM * ppm, L.CIRCLE_CY_MM * ppm
    r = L.CIRCLE_R_MM * ppm * 0.85
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=true_rgb)
    return np.asarray(card).copy()


def _blank_markers(frame, h):
    """Paint over the markers so detection fails, leaving grays + cap intact."""
    out = frame.copy()
    for m in L.MARKERS:
        cx, cy = card_mm_to_px(h, m.cx_mm, m.cy_mm)
        ex, ey = card_mm_to_px(h, m.cx_mm + L.MARKER_SIZE_MM * 0.75, m.cy_mm)
        r = int(np.hypot(ex - cx, ey - cy))
        cv2.rectangle(out, (int(cx) - r, int(cy) - r), (int(cx) + r, int(cy) + r), (255, 255, 255), -1)
    return out


def test_hold_homography_across_dropouts():
    true_rgb = (200, 60, 55)
    good = _frame_with_cap(true_rgb)
    h0 = detect_card(good)
    assert h0 is not None
    dropout = _blank_markers(good, h0)
    assert detect_card(dropout) is None  # markers really are gone

    reader = CardCapReader(hold_frames=2)
    first = reader.read(good)
    assert first is not None
    # held for hold_frames misses, and the cap colour is still read correctly
    held = reader.read(dropout)
    assert held is not None
    assert ciede2000(rgb_to_lab(held.rgb), rgb_to_lab(true_rgb)) < 12
    assert reader.read(dropout) is not None  # second held miss
    assert reader.read(dropout) is None  # third miss exceeds hold -> give up


def test_no_hold_by_default():
    good = _frame_with_cap((200, 60, 55))
    h0 = detect_card(good)
    dropout = _blank_markers(good, h0)
    reader = CardCapReader()  # hold_frames=0
    assert reader.read(good) is not None
    assert reader.read(dropout) is None  # no holding
