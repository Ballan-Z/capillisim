"""The /inventory browser: list caps, serve crop thumbnails, mouse-delete."""

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from cap_mosaic.app.webapp import server
from cap_mosaic.app.webapp.server import app
from cap_mosaic.data.store import CapDataset, FrameRecord

client = TestClient(app)


@pytest.fixture()
def inv_db(tmp_path, monkeypatch):
    """A tiny cap DB (2 caps, one with a crop file) wired into the server."""
    crops = tmp_path / "crops"
    crops.mkdir()
    p = crops / "cap_0000_f0.png"
    Image.fromarray(np.full((32, 32, 3), 90, np.uint8)).save(p)
    db = CapDataset(tmp_path / "caps.db")
    a = db.add_cap((10, 20, 30), frames=[FrameRecord(0, str(p), rgb=(10, 20, 30))],
                   captured_at="2026-07-04T00:00:00", source="test",
                   mosaic_rgb=(50, 60, 70), diameter_mm=30.2, crop_span_mm=37.8)
    b = db.add_cap((200, 10, 10), captured_at="2026-07-04T00:00:01", source="test",
                   diameter_mm=38.4)
    db.close()
    monkeypatch.setattr(server, "_DB", tmp_path / "caps.db")
    return {"a": a, "b": b, "crop": p, "db": tmp_path / "caps.db"}


def test_inventory_page_served():
    r = client.get("/inventory")
    assert r.status_code == 200
    assert "Cap inventory" in r.text


def test_inventory_lists_caps_newest_first(inv_db):
    r = client.get("/inventory/caps")
    assert r.status_code == 200
    caps = r.json()
    assert [c["id"] for c in caps] == [inv_db["b"], inv_db["a"]]
    a = caps[1]
    assert a["field"] == [10, 20, 30] and a["mosaic"] == [50, 60, 70]
    assert a["size_class"] == "standard-26" and a["has_crop"]
    assert caps[0]["size_class"] == "large-38" and not caps[0]["has_crop"]


def test_inventory_serves_crop_image(inv_db):
    r = client.get(f"/inventory/crop/{inv_db['a']}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert client.get(f"/inventory/crop/{inv_db['b']}").status_code == 404  # no crop
    assert client.get("/inventory/crop/99999").status_code == 404


def test_inventory_delete_removes_row_and_files(inv_db):
    assert Path(inv_db["crop"]).exists()
    r = client.delete(f"/inventory/caps/{inv_db['a']}")
    assert r.status_code == 200 and r.json()["deleted"] == inv_db["a"]
    assert not Path(inv_db["crop"]).exists()          # crop file gone too
    with CapDataset(inv_db["db"]) as db:
        assert [c.id for c in db.caps()] == [inv_db["b"]]
    assert client.delete(f"/inventory/caps/{inv_db['a']}").status_code == 404


def test_inventory_distance_test_renders(inv_db):
    import io as _io

    r = client.get(f"/inventory/test/{inv_db['a']}?distance_m=1.0")
    assert r.status_code == 200
    img = Image.open(_io.BytesIO(r.content))
    assert img.size == (900, 620)
    # nearby the patch is big: frame carries both the tiled cap (gray 90-ish)
    # and the solid mosaic half (50,60,70) as distinct colours
    px = np.asarray(img.convert("RGB"))
    assert (np.abs(px.astype(int) - [50, 60, 70]).sum(axis=2) < 12).any()
    # far away it shrinks: much more (white, default) background than at 1m
    far = client.get(f"/inventory/test/{inv_db['a']}?distance_m=10.0")
    pf = np.asarray(Image.open(_io.BytesIO(far.content)).convert("RGB"))
    bg = (px >= 250).all(axis=2).mean()
    bgf = (pf >= 250).all(axis=2).mean()
    assert bgf > bg


def test_inventory_distance_test_selectable_background(inv_db):
    import io as _io

    r = client.get(f"/inventory/test/{inv_db['a']}?distance_m=6.0&bg=%23103050")
    px = np.asarray(Image.open(_io.BytesIO(r.content)).convert("RGB"))
    corner = px[:20, :20].reshape(-1, 3)
    assert (np.abs(corner.astype(int) - [16, 48, 80]).sum(axis=1) < 12).all()


def test_inventory_distance_test_404s(inv_db):
    assert client.get(f"/inventory/test/{inv_db['b']}").status_code == 404  # no crop
    assert client.get("/inventory/test/99999").status_code == 404


def test_split_patch_hex_packs_caps_close():
    # glued caps touch: board must show ONLY in the small curved gaps between
    # circles (~9% hex interstices + edges), never as full margins
    from cap_mosaic.app.webapp.server import _split_test_patch

    tile = 48
    disc = Image.new("RGBA", (tile, tile), (0, 0, 0, 0))
    from PIL import ImageDraw

    ImageDraw.Draw(disc).ellipse([0, 0, tile - 1, tile - 1], fill=(40, 90, 40, 255))
    patch = _split_test_patch(disc, tile, 12, (255, 0, 255), (10, 10, 10))
    px = np.asarray(patch)
    half = 6 * tile
    left = px[:, :half]
    board_frac = ((left == [255, 0, 255]).all(axis=2)).mean()
    assert board_frac < 0.17, board_frac          # hex-close, not sparse grid
    right = px[:, half:]
    assert ((right == [10, 10, 10]).all(axis=2)).mean() > 0.99  # clean solid half


def test_cap_cutout_shrinks_past_printed_circle():
    # Hough locks onto the printed placement circle; the cutout must walk in
    # to the real cap edge or every tile carries a white card ring
    import cv2
    from cap_mosaic.app.cap_crop import cap_cutout

    img = np.full((128, 128, 3), 245, np.uint8)
    cv2.circle(img, (64, 64), 55, (150, 150, 150), 2)    # printed circle
    cv2.circle(img, (64, 64), 34, (30, 40, 120), -1)     # the actual cap
    cut = np.asarray(cap_cutout(img, 48))
    # the ring just inside the cutout edge must be cap, not card-white
    yy, xx = np.ogrid[:48, :48]
    d2 = (xx - 24) ** 2 + (yy - 24) ** 2
    band = (d2 >= 20 ** 2) & (d2 <= 23 ** 2)
    edge = cut[band]
    white = (edge[:, :3] >= 215).all(axis=1) & (edge[:, 3] > 0)
    assert white.mean() < 0.2, white.mean()


def test_inventory_empty_without_db(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_DB", tmp_path / "absent.db")
    assert client.get("/inventory/caps").json() == []
    assert client.delete("/inventory/caps/1").status_code == 404
