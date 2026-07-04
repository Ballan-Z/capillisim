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
    # far away it shrinks: much more frame background than at 1m
    far = client.get(f"/inventory/test/{inv_db['a']}?distance_m=10.0")
    pf = np.asarray(Image.open(_io.BytesIO(far.content)).convert("RGB"))
    bg = (np.abs(px.astype(int) - [13, 15, 20]).sum(axis=2) < 12).mean()
    bgf = (np.abs(pf.astype(int) - [13, 15, 20]).sum(axis=2) < 12).mean()
    assert bgf > bg


def test_inventory_distance_test_404s(inv_db):
    assert client.get(f"/inventory/test/{inv_db['b']}").status_code == 404  # no crop
    assert client.get("/inventory/test/99999").status_code == 404


def test_inventory_empty_without_db(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_DB", tmp_path / "absent.db")
    assert client.get("/inventory/caps").json() == []
    assert client.delete("/inventory/caps/1").status_code == 404
