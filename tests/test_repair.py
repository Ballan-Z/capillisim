import numpy as np
from PIL import Image

from cap_mosaic.app.repair_capture import repair_cap
from cap_mosaic.data.store import CapDataset, FrameRecord


def _crop_png(path, color, n=64):
    img = np.full((n, n, 3), 250, np.uint8)
    yy, xx = np.mgrid[0:n, 0:n]
    img[np.hypot(xx - n / 2, yy - n / 2) <= n / 2 - 2] = color
    Image.fromarray(img, "RGB").save(path)


def _cap_with_frames(db, tmp_path, tag, frame_colors, field):
    frames = []
    for k, col in enumerate(frame_colors):
        p = tmp_path / f"{tag}_f{k}.png"
        _crop_png(p, col)
        frames.append(FrameRecord(k, str(p), rgb=col))
    return db.add_cap(field, frames, captured_at="t")


def test_repair_drops_outlier_frames_and_recomputes(tmp_path):
    with CapDataset(tmp_path / "caps.db") as db:
        # 4 agreeing green frames + 1 hand-contaminated frame; the stored field
        # was skewed by the bad frame
        good = (40, 120, 70)
        cid = _cap_with_frames(
            db, tmp_path, "a",
            [good, (42, 118, 72), (180, 140, 120), (41, 121, 69), (39, 119, 71)],
            field=(80, 122, 85),  # skewed
        )
        verdict = repair_cap(db, cid)
        cap = db.caps(with_frames=True)[0]
        assert verdict == "repaired"
        assert all(abs(a - b) <= 4 for a, b in zip(cap.rgb, good))  # field fixed
        assert cap.mosaic_rgb is not None  # recomputed from agreeing crops
        assert cap.notes is None or "corrupt" not in cap.notes


def test_unrepairable_cap_is_marked_not_changed(tmp_path):
    with CapDataset(tmp_path / "caps.db") as db:
        # every frame disagrees with every other -> nothing to trust
        cid = _cap_with_frames(
            db, tmp_path, "b",
            [(10, 10, 10), (200, 40, 40), (40, 200, 40), (40, 40, 200), (200, 200, 40)],
            field=(90, 90, 66),
        )
        verdict = repair_cap(db, cid)
        cap = db.caps()[0]
        assert verdict == "unrepairable"
        assert cap.rgb == (90, 90, 66)  # colours untouched
        assert cap.notes == "corrupt-capture"


def test_clean_cap_is_left_alone(tmp_path):
    with CapDataset(tmp_path / "caps.db") as db:
        cid = _cap_with_frames(
            db, tmp_path, "c",
            [(70, 70, 70)] * 5,
            field=(70, 70, 70),
        )
        assert repair_cap(db, cid) == "clean"
        assert db.caps()[0].rgb == (70, 70, 70)
