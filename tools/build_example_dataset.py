"""Build a small, colour-diverse example cap dataset from the full scanned one.

The app ships this so a fresh clone has caps to plan with immediately (see the
`_DB` fallback in webapp/server.py). It is NOT the real thing — users scan their
own caps into `dataset/` with the reading card, which then takes precedence.

    python tools/build_example_dataset.py            # ~100 caps -> examples/dataset/

Selection is a greedy farthest-point walk in CIELAB so the sample spans the
colour wheel instead of clustering on whatever was scanned most. Only the first
crop of each chosen cap is copied; frame paths are rewritten to the example
location so they resolve from the repo root.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

SRC_DB = Path("dataset/caps.db")
SRC_CROPS = Path("dataset/crops")
OUT_DIR = Path("examples/dataset")
OUT_DB = OUT_DIR / "caps.db"
OUT_CROPS = OUT_DIR / "crops"
TARGET = 100


def _farthest_point(caps: list[tuple[int, float, float, float]], k: int) -> list[int]:
    """Greedy max-min in Lab: start at the most colourful cap, then repeatedly
    add the cap farthest from everything picked so far."""
    if len(caps) <= k:
        return [c[0] for c in caps]

    def d2(a, b):
        return (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2 + (a[3] - b[3]) ** 2

    # seed: highest chroma (a,b farthest from neutral) — a vivid, memorable cap
    start = max(caps, key=lambda c: c[2] ** 2 + c[3] ** 2)
    picked = [start]
    picked_ids = {start[0]}
    nearest = {c[0]: d2(c, start) for c in caps}
    while len(picked) < k:
        nxt = max((c for c in caps if c[0] not in picked_ids),
                  key=lambda c: nearest[c[0]])
        picked.append(nxt)
        picked_ids.add(nxt[0])
        for c in caps:
            if c[0] not in picked_ids:
                nearest[c[0]] = min(nearest[c[0]], d2(c, nxt))
    return [c[0] for c in picked]


def main() -> None:
    if not SRC_DB.exists():
        raise SystemExit(f"no source dataset at {SRC_DB} — run from the repo root")

    OUT_CROPS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_DB, OUT_DB)

    conn = sqlite3.connect(OUT_DB)
    # caps that actually have a crop file we can copy
    have_crop = {cid for (cid,) in conn.execute(
        "SELECT DISTINCT cap_id FROM frame")}
    caps = [(cid, ll, la, lb) for (cid, ll, la, lb) in conn.execute(
        "SELECT id, lab_l, lab_a, lab_b FROM cap") if cid in have_crop]
    keep = set(_farthest_point(caps, TARGET))
    print(f"selected {len(keep)} of {len(caps)} caps")

    # keep only the lowest-index frame per kept cap
    keep_frames = {}
    for fid, cap_id, idx in conn.execute(
            "SELECT id, cap_id, frame_index FROM frame ORDER BY cap_id, frame_index"):
        if cap_id in keep and cap_id not in keep_frames:
            keep_frames[cap_id] = fid
    keep_frame_ids = set(keep_frames.values())

    ph_caps = ",".join("?" * len(keep))
    conn.execute(f"DELETE FROM cap WHERE id NOT IN ({ph_caps})", tuple(keep))
    conn.execute(f"DELETE FROM embedding WHERE cap_id NOT IN ({ph_caps})", tuple(keep))
    ph_fr = ",".join("?" * len(keep_frame_ids))
    conn.execute(f"DELETE FROM frame WHERE id NOT IN ({ph_fr})", tuple(keep_frame_ids))

    # rewrite each kept frame's path to the example location and copy the file
    copied = 0
    for fid, path in list(conn.execute("SELECT id, path FROM frame")):
        base = Path(path.replace("\\", "/")).name
        src = SRC_CROPS / base
        dst = OUT_CROPS / base
        if src.exists():
            shutil.copy2(src, dst)
            copied += 1
        new_path = f"examples/dataset/crops/{base}"
        conn.execute("UPDATE frame SET path = ? WHERE id = ?", (new_path, fid))

    conn.commit()
    conn.execute("VACUUM")
    conn.commit()
    conn.close()
    print(f"copied {copied} crops -> {OUT_CROPS}")


if __name__ == "__main__":
    main()
