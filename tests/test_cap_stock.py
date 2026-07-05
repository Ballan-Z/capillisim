import numpy as np

from cap_mosaic.app.cap_signature import SIG_LEN, MODEL_NAME
from cap_mosaic.app.cap_stock import load_stock
from cap_mosaic.data.store import CapDataset


def _sig(seed: int) -> list[float]:
    return np.random.default_rng(seed).random(SIG_LEN).astype(float).tolist()


def _db(tmp_path):
    path = tmp_path / "caps.db"
    db = CapDataset(path)
    sig_red = _sig(1)
    # two physical caps of the SAME design: identical signature + colour
    a = db.add_cap((200, 30, 30), captured_at="t", mosaic_rgb=(180, 60, 50))
    b = db.add_cap((198, 32, 31), captured_at="t", mosaic_rgb=(181, 61, 52))
    db.add_embedding(a, MODEL_NAME, sig_red, created_at="t")
    db.add_embedding(b, MODEL_NAME, sig_red, created_at="t")
    # a DIFFERENT design (far signature, different colour)
    c = db.add_cap((30, 60, 200), captured_at="t", mosaic_rgb=(50, 70, 180))
    db.add_embedding(c, MODEL_NAME, _sig(2), created_at="t")
    # no signature at all, colour ~equal to another unsigned cap -> colour fallback
    d = db.add_cap((240, 240, 240), captured_at="t")
    e = db.add_cap((242, 241, 239), captured_at="t")
    # unsigned, far colour -> its own group
    f = db.add_cap((10, 10, 10), captured_at="t")
    db.close()
    return path, (a, b, c, d, e, f)


def test_duplicates_merge_and_distinct_stay_separate(tmp_path):
    path, (a, b, c, d, e, f) = _db(tmp_path)
    groups = load_stock(path)
    by_ids = {frozenset(g.cap_ids): g for g in groups}
    dup = by_ids.get(frozenset({a, b}))
    assert dup is not None and dup.count == 2          # same design pooled
    assert any(g.cap_ids == [c] for g in groups)       # different design separate
    assert by_ids.get(frozenset({d, e})) is not None   # colour fallback pools d+e
    assert any(g.cap_ids == [f] for g in groups)       # lone dark cap alone


def test_group_colour_prefers_mosaic_and_total_is_conserved(tmp_path):
    path, ids = _db(tmp_path)
    groups = load_stock(path)
    assert sum(g.count for g in groups) == len(ids)    # every cap in exactly one group
    dup = next(g for g in groups if g.count == 2 and g.cap_ids[0] == ids[0])
    assert max(abs(x - y) for x, y in zip(dup.rgb, (180, 60, 51))) <= 3  # mosaic mean
    assert dup.label                                    # has a stable label
