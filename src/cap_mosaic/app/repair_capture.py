"""Repair corrupted captures by software — for caps that can't be re-scanned.

A capture is 5 frames; a hand still in frame, a glare streak, or a passing
reflection usually contaminates only 1–2 of them. Repair drops the outlier
frames (CIEDE2000 > ``max_de`` from the frame median) and recomputes the cap's
field colour (median of the agreeing frames' reads) and mosaic colour (median
of the agreeing crops' linear means). Caps where fewer than 2 frames agree are
left untouched and marked ``notes='corrupt-capture'``.

    PYTHONPATH=src python -m cap_mosaic.app.repair_capture --db dataset/caps.db \
        --caps 16,31,100,105,106
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from ..core.palette import ciede2000, rgb_to_lab
from ..data.store import CapDataset
from .cap_color import median_rgb, mosaic_rgb_from_crop

MAX_DE = 12.0  # frames farther than this from the frame median are contaminated


def repair_cap(db: CapDataset, cap_id: int, max_de: float = MAX_DE) -> str:
    """Repair one cap; returns 'repaired' | 'unrepairable' | 'clean'."""
    cap = next((c for c in db.caps(with_frames=True) if c.id == cap_id), None)
    if cap is None or not cap.frames:
        return "unrepairable"
    cols = [(f, f.rgb) for f in cap.frames if f.rgb]
    if len(cols) < 2:
        db.set_notes(cap_id, "corrupt-capture")
        return "unrepairable"

    med = tuple(int(round(v)) for v in np.median(
        np.asarray([c for _, c in cols], float), axis=0))
    med_lab = rgb_to_lab(med)
    agreeing = [(f, c) for f, c in cols if ciede2000(med_lab, rgb_to_lab(c)) <= max_de]
    if len(agreeing) < 2:
        db.set_notes(cap_id, "corrupt-capture")
        return "unrepairable"
    if len(agreeing) == len(cols):
        return "clean"  # nothing contaminated; leave as captured

    field = median_rgb([c for _, c in agreeing])
    mosaics = []
    for f, _ in agreeing:
        p = Path(f.path)
        if p.exists():
            try:
                mosaics.append(mosaic_rgb_from_crop(np.asarray(Image.open(p).convert("RGB"))))
            except OSError:
                continue
    db.set_field(cap_id, field)
    if mosaics:
        db.set_mosaic(cap_id, median_rgb(mosaics))
    return "repaired"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="cap-mosaic-repair", description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--caps", required=True, help="comma-separated cap ids")
    args = ap.parse_args(argv)
    ids = [int(x) for x in args.caps.split(",")]
    with CapDataset(args.db) as db:
        for cid in ids:
            before = next((c for c in db.caps() if c.id == cid), None)
            verdict = repair_cap(db, cid)
            after = next((c for c in db.caps() if c.id == cid), None)
            print(f"cap {cid}: {verdict}"
                  + (f"  field {before.rgb} -> {after.rgb}  mosaic {before.mosaic_rgb} -> {after.mosaic_rgb}"
                     if verdict == "repaired" else ""), flush=True)


if __name__ == "__main__":
    main()
