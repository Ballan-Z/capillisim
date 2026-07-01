import io

from fastapi.testclient import TestClient
from PIL import Image

from cap_mosaic.app.planner_designer import demo_image
from cap_mosaic.app.webapp.server import app

client = TestClient(app)


def _upload() -> str:
    buf = io.BytesIO()
    demo_image(96).save(buf, format="PNG")
    buf.seek(0)
    r = client.post("/upload", files={"file": ("demo.png", buf, "image/png")})
    assert r.status_code == 200
    return r.json()["id"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_returns_id_and_dims():
    buf = io.BytesIO()
    Image.new("RGB", (120, 80), (10, 20, 30)).save(buf, format="PNG")
    buf.seek(0)
    r = client.post("/upload", files={"file": ("x.png", buf, "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["width"] == 120 and body["height"] == 80
    assert abs(body["aspect"] - 1.5) < 1e-6


def test_estimate_from_size_has_caps_legibility_and_bom():
    iid = _upload()
    r = client.get("/estimate", params={"image_id": iid, "size_mm": 2000})
    assert r.status_code == 200
    b = r.json()
    assert b["caps_across"] > 0
    assert "legible" in b
    assert b["total_caps"] > 0
    assert isinstance(b["bom"], dict) and len(b["bom"]) > 0
    assert b["effective_colors"] <= b["colors_used"]


def test_estimate_from_distance_has_size_and_read_quality():
    iid = _upload()
    r = client.get("/estimate", params={"image_id": iid, "distance_m": 6.0})
    assert r.status_code == 200
    b = r.json()
    assert b["width_mm"] > 0
    assert b["read_quality"] in ("caps", "reads", "smooth")


def test_simulate_returns_png():
    iid = _upload()
    r = client.get("/simulate", params={"image_id": iid, "distance_m": 6.0})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 100


def test_unknown_image_id_404():
    r = client.get("/estimate", params={"image_id": "nope", "size_mm": 1000})
    assert r.status_code == 404


def test_index_and_static_served():
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="dropzone"' in r.text and 'id="size"' in r.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200
