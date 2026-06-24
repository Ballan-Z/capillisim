import csv

from cap_mosaic.data.store import (
    SCHEMA_VERSION,
    CapDataset,
    FrameRecord,
    import_labels_csv,
)


def test_add_and_read_back_a_cap(tmp_path):
    with CapDataset(tmp_path / "caps.db") as db:
        cid = db.add_cap((120, 60, 40), captured_at="2026-06-24T00:00:00")
        assert db.count() == 1
        cap = db.caps()[0]
        assert cap.id == cid
        assert cap.rgb == (120, 60, 40)
        # Lab is derived and stored
        assert cap.lab[0] > 0
        assert db.colors() == [(120, 60, 40)]


def test_color_std_flags_a_glary_outlier_frame(tmp_path):
    with CapDataset(tmp_path / "caps.db") as db:
        # four consistent reads + one black (glare-clipped) outlier
        frames = [FrameRecord(i, f"f{i}.png", rgb=c) for i, c in enumerate(
            [(70, 72, 70), (71, 70, 69), (69, 71, 71), (70, 70, 70), (0, 0, 0)]
        )]
        db.add_cap((70, 71, 70), frames, captured_at="2026-06-24T00:00:00")
        cap = db.caps()[0]
        assert cap.n_frames == 5
        # the (0,0,0) frame should push the spread well above a clean read (~1-2)
        assert cap.color_std is not None and cap.color_std > 10


def test_frames_roundtrip_with_their_colors(tmp_path):
    with CapDataset(tmp_path / "caps.db") as db:
        frames = [FrameRecord(0, "a.png", rgb=(10, 20, 30), sha256="abc")]
        db.add_cap((10, 20, 30), frames, captured_at="t")
        cap = db.caps(with_frames=True)[0]
        assert len(cap.frames) == 1
        assert cap.frames[0].path == "a.png"
        assert cap.frames[0].rgb == (10, 20, 30)
        assert cap.frames[0].lab is not None  # derived for the frame too
        assert cap.frames[0].sha256 == "abc"


def test_embedding_store_and_schema_version(tmp_path):
    path = tmp_path / "caps.db"
    with CapDataset(path) as db:
        cid = db.add_cap((1, 2, 3), captured_at="t")
        db.add_embedding(cid, "clip-v1", [0.1, 0.2, 0.3], created_at="t")
        version = db.conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == SCHEMA_VERSION
        row = db.conn.execute(
            "SELECT dim FROM embedding WHERE cap_id = ?", (cid,)
        ).fetchone()
        assert row["dim"] == 3


def test_reopen_is_idempotent(tmp_path):
    path = tmp_path / "caps.db"
    with CapDataset(path) as db:
        db.add_cap((5, 5, 5), captured_at="t")
    # opening again must not wipe data or re-run migrations destructively
    with CapDataset(path) as db:
        assert db.count() == 1


def test_import_legacy_labels_csv_links_crops(tmp_path):
    crops = tmp_path / "crops"
    crops.mkdir()
    for k in range(3):
        (crops / f"cap_0000_f{k}.png").write_bytes(b"x")
    csv_path = tmp_path / "labels.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "r", "g", "b", "n_frames"])
        w.writerow([0, 67, 122, 150, 5])

    with CapDataset(tmp_path / "caps.db") as db:
        n = import_labels_csv(db, csv_path, crops)
        assert n == 1
        cap = db.caps(with_frames=True)[0]
        assert cap.rgb == (67, 122, 150)
        assert len(cap.frames) == 3
