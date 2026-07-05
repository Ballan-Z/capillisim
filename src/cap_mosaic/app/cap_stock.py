"""Interchangeable cap stock: pool duplicate designs into countable groups.

Two physical caps of the same design are interchangeable for building, so the
inventory becomes GROUPS with counts rather than 400 unique items. Grouping is
single-linkage clustering on the same combined score the scanner's re-ID uses
(``similar.py``): ring-signature distance + a scaled mosaic-colour CIEDE2000
term, cut at the scanner's own "likely SAME design" threshold. Caps without a
stored signature fall back to near-identical mosaic colour.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.palette import RGB, ciede2000, rgb_to_lab
from ..data.store import CapDataset
from .cap_signature import MODEL_NAME, signature_distance
from .similar import COLOR_WEIGHT

SAME_DESIGN = 0.8       # combined score below this = duplicates (scanner's cut)
FALLBACK_DE = 4.0       # no signature: mosaic colours this close = duplicates


@dataclass
class Group:
    label: str            # stable display label, e.g. "g07"
    rgb: RGB              # mean mosaic colour of the group (what the planner matches)
    count: int            # how many physical caps you own of this design
    cap_ids: list[int]    # the caps pooled into this group


def _cap_rgb(c) -> RGB:
    return tuple(c.mosaic_rgb or c.rgb)


def load_stock(db_path) -> list[Group]:
    """The owned inventory as interchangeable groups (every cap in exactly one)."""
    with CapDataset(db_path) as db:
        caps = db.caps()
        sigs = {cid: np.asarray(v) for cid, v in db.get_embeddings(MODEL_NAME)}

    labs = {c.id: rgb_to_lab(_cap_rgb(c)) for c in caps}

    # union-find over pairwise "same design" links (single linkage)
    parent = {c.id: c.id for c in caps}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    ids = [c.id for c in caps]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d_col = ciede2000(labs[a], labs[b])
            if a in sigs and b in sigs:
                score = signature_distance(sigs[a], sigs[b]) + COLOR_WEIGHT * d_col
                same = score < SAME_DESIGN
            elif a not in sigs and b not in sigs:
                same = d_col <= FALLBACK_DE
            else:  # one signed, one not: colour alone is too weak to pool them
                same = False
            if same:
                union(a, b)

    clusters: dict[int, list[int]] = {}
    for cid in ids:
        clusters.setdefault(find(cid), []).append(cid)

    by_cap = {c.id: c for c in caps}
    groups: list[Group] = []
    for members in sorted(clusters.values(), key=lambda m: m[0]):
        rgbs = np.array([_cap_rgb(by_cap[m]) for m in members], dtype=float)
        mean = tuple(int(round(v)) for v in rgbs.mean(0))
        groups.append(Group(label=f"g{members[0]:03d}", rgb=mean,
                            count=len(members), cap_ids=sorted(members)))
    return groups
