import functools
import http.server
import socketserver
import threading

from PIL import Image

from cap_mosaic.core.palette import nearest
from cap_mosaic.vision.cap_reader import grab_snapshot, read_dominant_color


def _serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def test_grab_snapshot_fetches_and_reads_color(tmp_path):
    # a phone serving a solid-blue "cap" snapshot
    Image.new("RGB", (80, 80), (40, 80, 160)).save(tmp_path / "shot.jpg")
    httpd = _serve(tmp_path)
    try:
        port = httpd.server_address[1]
        img = grab_snapshot(f"http://127.0.0.1:{port}/shot.jpg")
        assert img.size == (80, 80)
        assert nearest(read_dominant_color(img)).name == "blue"
    finally:
        httpd.shutdown()


def test_grab_snapshot_raises_on_bad_url(tmp_path):
    httpd = _serve(tmp_path)
    try:
        port = httpd.server_address[1]
        try:
            grab_snapshot(f"http://127.0.0.1:{port}/missing.jpg", timeout=2.0)
        except Exception:
            return
        raise AssertionError("expected an error for a missing snapshot")
    finally:
        httpd.shutdown()
