"""CardCapReader end-to-end: card+cap -> reading; no card -> None."""

import numpy as np
from PIL import ImageDraw

from cap_mosaic.app.make_card import render_card
from cap_mosaic.core.palette import ciede2000, rgb_to_lab
from cap_mosaic.vision import card_layout as L
from cap_mosaic.vision.card_reader import CardCapReader


def _frame_with_cap(true_rgb, cast=(0.9, 0.8, 0.7), dpi=200):
    ppm = dpi / 25.4
    card = render_card(dpi).copy()
    draw = ImageDraw.Draw(card)
    cx, cy = L.CIRCLE_CX_MM * ppm, L.CIRCLE_CY_MM * ppm
    r = L.CIRCLE_R_MM * ppm * 0.85
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=true_rgb)
    return np.clip(np.asarray(card).astype(np.float32) * np.array(cast), 0, 255).astype(np.uint8)


def test_reader_returns_reading_for_card_with_cap():
    true_rgb = (200, 60, 55)  # red cap
    reading = CardCapReader().read(_frame_with_cap(true_rgb))
    assert reading is not None
    assert ciede2000(rgb_to_lab(reading.rgb), rgb_to_lab(true_rgb)) < 10
    assert reading.lab == rgb_to_lab(reading.rgb)


def test_reader_returns_none_without_card():
    blank = np.full((360, 480, 3), 210, np.uint8)
    assert CardCapReader().read(blank) is None
