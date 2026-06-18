"""Render the Cap Reading Card (PNG + PDF) from the canonical layout spec.

    python -m cap_mosaic.app.make_card --out cap_reading_card

Renders the ArUco corner markers, the gray white-balance strip, and the cap
placement circle at their true millimetre positions, so the printed card matches
what ``vision.card_reader`` expects. Print at 100% (no scaling).
"""

from __future__ import annotations

import argparse

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..vision import card_layout as L


def _font(size: int, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    try:
        return ImageFont.truetype(rf"C:\Windows\Fonts\{name}", size)
    except OSError:
        return ImageFont.load_default()


def _ctext(d, x, y, s, font, fill="black"):
    box = d.textbbox((0, 0), s, font=font)
    d.text((x - (box[2] - box[0]) / 2, y), s, font=font, fill=fill)


def render_card(dpi: int = 300) -> Image.Image:
    """Render the card to a PIL image at the given print resolution."""
    ppm = dpi / 25.4
    W, H = round(L.CARD_W_MM * ppm), round(L.CARD_H_MM * ppm)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    lw = max(1, round(0.25 * ppm))

    adict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, L.ARUCO_DICT))
    msz = round(L.MARKER_SIZE_MM * ppm)
    for m in L.MARKERS:
        marr = cv2.aruco.generateImageMarker(adict, m.id, msz)
        x = round(m.cx_mm * ppm - msz / 2)
        y = round(m.cy_mm * ppm - msz / 2)
        img.paste(Image.fromarray(marr).convert("RGB"), (x, y))

    gsz = round(L.GRAY_SIZE_MM * ppm)
    hexfont = _font(round(2.6 * ppm), bold=True)
    for g in L.GRAY_PATCHES:
        x = round(g.cx_mm * ppm - gsz / 2)
        y = round(g.cy_mm * ppm - gsz / 2)
        d.rectangle([x, y, x + gsz, y + gsz], fill=(g.value,) * 3, outline="black", width=lw)
        tag = " *" if g.value == L.REFERENCE_VALUE else ""
        _ctext(d, g.cx_mm * ppm, y + gsz + 0.5 * ppm, "#{0:02X}{0:02X}{0:02X}".format(g.value) + tag, hexfont)

    cx, cy, r = L.CIRCLE_CX_MM * ppm, L.CIRCLE_CY_MM * ppm, L.CIRCLE_R_MM * ppm
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(140, 140, 140), width=lw)
    ch = round(3 * ppm)
    d.line([cx - ch, cy, cx + ch, cy], fill=(140, 140, 140), width=lw)
    d.line([cx, cy - ch, cx, cy + ch], fill=(140, 140, 140), width=lw)
    _ctext(d, cx, cy - r - 3.6 * ppm, "PLACE CAP HERE", _font(round(3.6 * ppm), bold=True))
    _ctext(d, cx, cy + r + 1.2 * ppm, "centre one cap, top up", _font(round(2.4 * ppm)))
    _ctext(d, W / 2, H - 4.5 * ppm,
           f"Print 100% - {L.CARD_W_MM:.0f}x{L.CARD_H_MM:.0f} mm - matte - * = 50% reference",
           _font(round(2.3 * ppm)))
    return img


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="cap-mosaic-make-card", description=__doc__)
    ap.add_argument("--out", default="cap_reading_card", help="output basename (writes .png and .pdf)")
    ap.add_argument("--dpi", type=int, default=300, help="print resolution")
    args = ap.parse_args(argv)
    img = render_card(args.dpi)
    img.save(f"{args.out}.png", dpi=(args.dpi, args.dpi))
    img.save(f"{args.out}.pdf", "PDF", resolution=float(args.dpi))
    print(f"saved {args.out}.png + {args.out}.pdf  ({img.size[0]}x{img.size[1]} px)")


if __name__ == "__main__":
    main()
