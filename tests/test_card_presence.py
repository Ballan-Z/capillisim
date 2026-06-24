"""White / logoed-cap reading + presence detection on the Cap Reading Card.

These synthesize a card frame (via render_card) with a cap drawn in the
placement circle, so the colour/presence stages are exercised headless.
"""

import numpy as np
from PIL import ImageDraw

from cap_mosaic.app.make_card import render_card
from cap_mosaic.core.palette import ciede2000, rgb_to_lab
from cap_mosaic.vision import card_layout as L
from cap_mosaic.vision.card_reader import detect_card, read_cap_color, white_balance


def _card_with_cap(field_rgb, logo_rgb=None, logo_frac=0.0, dpi=200):
    """Render the card with a filled cap disc and an optional centred logo blob.

    `logo_frac` is the logo blob's radius as a fraction of the cap radius.
    Returns the RGB frame (numpy) and the cap centre/radius in pixels.
    """
    ppm = dpi / 25.4
    card = render_card(dpi).copy()
    draw = ImageDraw.Draw(card)
    cx, cy = L.CIRCLE_CX_MM * ppm, L.CIRCLE_CY_MM * ppm
    r = L.CIRCLE_R_MM * ppm * 0.85
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(field_rgb))
    if logo_rgb is not None and logo_frac > 0:
        lr = r * logo_frac
        draw.ellipse([cx - lr, cy - lr, cx + lr, cy + lr], fill=tuple(logo_rgb))
    return np.asarray(card), (cx, cy, r)


def test_glare_majority_keeps_field_not_logo():
    # A bright white cap (mostly > glare level) with a small dark logo: the read
    # must return the white field, not the dark logo the glare mask leaves behind.
    field = (250, 250, 250)
    frame, _ = _card_with_cap(field, logo_rgb=(20, 20, 20), logo_frac=0.25)
    h = detect_card(frame)
    assert h is not None
    got = read_cap_color(white_balance(frame, h), h)
    assert got is not None
    de = ciede2000(rgb_to_lab(got), rgb_to_lab(field))
    assert de < 12, (got, de)
