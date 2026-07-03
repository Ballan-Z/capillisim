import base64
import io

from PIL import Image

from cap_mosaic.app import ai_edit


def _png_bytes(color=(30, 120, 60), size=(20, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _src():
    return Image.new("RGB", (64, 48), (200, 40, 40))


def test_request_shape_and_b64_response():
    cap = {}
    out_b64 = base64.b64encode(_png_bytes()).decode()

    def post(url, headers, body):
        cap.update(url=url, headers=headers, body=body)
        return {"output": {"choices": [{"message": {"content": [
            {"image_base64": out_b64}]}}]}}

    img = ai_edit.ai_simplify(_src(), "flatten to 6 colours", key="k", post=post)
    assert img.size == (20, 20)  # decoded the returned image
    assert "multimodal-generation/generation" in cap["url"]
    assert cap["headers"]["Authorization"] == "Bearer k"
    assert cap["body"]["model"] == "qwen-image-edit-plus"
    content = cap["body"]["input"]["messages"][0]["content"]
    assert content[0]["image"].startswith("data:image/jpeg;base64,")
    assert content[1]["text"] == "flatten to 6 colours"
    assert cap["body"]["parameters"]["watermark"] is False


def test_url_response_is_fetched_via_injected_get():
    def post(url, headers, body):
        return {"output": {"choices": [{"message": {"content": [
            {"image": "https://example.test/out.png"}]}}]}}

    fetched = {}

    def get_bytes(url):
        fetched["url"] = url
        return _png_bytes(color=(10, 10, 200))

    img = ai_edit.ai_simplify(_src(), "p", key="k", post=post, get_bytes=get_bytes)
    assert fetched["url"] == "https://example.test/out.png"
    assert img.getpixel((0, 0)) == (10, 10, 200)


def test_no_image_in_response_raises():
    import pytest

    def post(url, headers, body):
        return {"output": {"choices": [{"message": {"content": [{"text": "no"}]}}]}}

    with pytest.raises(RuntimeError, match="no image"):
        ai_edit.ai_simplify(_src(), "p", key="k", post=post)
