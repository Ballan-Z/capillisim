"""AI image simplify — qwen-image-edit via DashScope (olga_movie's pattern).

Sends the image + an edit instruction (built from the AI judge's own tips) to
``qwen-image-edit-plus`` and returns the edited image: fewer flat colours,
thicker lines — a cap-friendly version of the same subject. Always opt-in and
non-destructive: callers store the result as a NEW image. Network is injected
(``post``/``get_bytes``) so tests run offline; key = ``QWEEN_KEY`` (shared
loader with ``llm_judge``).
"""

from __future__ import annotations

import base64
import io
import json
from typing import Callable

from PIL import Image

from .llm_judge import _load_key

EDIT_URL = ("https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/"
            "multimodal-generation/generation")
EDIT_MODEL = "qwen-image-edit-plus"

DEFAULT_INSTRUCTIONS = (
    "Simplify this image for a bottle-cap mosaic: flatten shading into at most "
    "6 flat poster colours, thicken all thin lines and outlines so none is "
    "hairline, remove fine texture and background clutter, keep the same "
    "subject and composition. PRESERVE THE ORIGINAL COLOURS EXACTLY: every "
    "element must keep its own hue from the source image (pick each element's "
    "dominant existing colour; do not recolour, restyle or shift any hue). "
    "Bold, high-contrast, pixel-art friendly."
)

# steer the edit model away from its habit of re-palette-ing the picture
NEGATIVE_PROMPT = "recolored, changed colors, different palette, hue shift, new color scheme"


def _default_post(url: str, headers: dict, body: dict) -> dict:
    import urllib.request

    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def _default_get_bytes(url: str) -> bytes:
    import urllib.request

    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def ai_simplify(
    image: Image.Image,
    instructions: str = DEFAULT_INSTRUCTIONS,
    key: str | None = None,
    model: str = EDIT_MODEL,
    post: Callable[[str, dict, dict], dict] = _default_post,
    get_bytes: Callable[[str], bytes] = _default_get_bytes,
) -> Image.Image:
    """Edit `image` into a cap-friendly simplified version. Returns a new image."""
    key = key or _load_key()
    im = image.convert("RGB")
    im.thumbnail((2048, 2048))  # DashScope 10MB payload cap
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    data_uri = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

    body = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": [
            {"image": data_uri},
            {"text": instructions},
        ]}]},
        "parameters": {"negative_prompt": NEGATIVE_PROMPT, "watermark": False},
    }
    resp = post(EDIT_URL, {"Authorization": f"Bearer {key}"}, body)
    return _image_from_response(resp, get_bytes)


def _image_from_response(resp: dict, get_bytes: Callable[[str], bytes]) -> Image.Image:
    """Pull the generated/edited image out of a DashScope generation response."""
    for ch in resp.get("output", {}).get("choices") or []:
        for item in ch.get("message", {}).get("content", []):
            url = item.get("image")
            if url:
                return Image.open(io.BytesIO(get_bytes(url))).convert("RGB")
            b64 = item.get("image_base64") or item.get("data")
            if b64:
                return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    raise RuntimeError(f"no image in response: {str(resp)[:200]}")


# text-to-image: same DashScope endpoint, text-only message (verified live)
T2I_MODEL = "qwen-image-plus"
# sizes the model supports, widest to tallest — picked by nearest aspect
T2I_SIZES = ("1664*928", "1472*1140", "1328*1328", "1140*1472", "928*1664")


def t2i_size_for(aspect: float) -> str:
    """The supported generation size whose aspect is closest to `aspect`."""
    def ratio(s: str) -> float:
        w, h = s.split("*")
        return int(w) / int(h)
    return min(T2I_SIZES, key=lambda s: abs(ratio(s) - aspect))


def ai_pattern(
    prompt: str,
    size: str = "1328*1328",
    key: str | None = None,
    model: str = T2I_MODEL,
    post: Callable[[str, dict, dict], dict] = _default_post,
    get_bytes: Callable[[str], bytes] = _default_get_bytes,
) -> Image.Image:
    """Generate a decorative pattern image from a text prompt (the owned-cap
    palette prompt). Returns a new image; callers store it like an upload."""
    key = key or _load_key()
    body = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {"size": size, "watermark": False, "prompt_extend": True},
    }
    resp = post(EDIT_URL, {"Authorization": f"Bearer {key}"}, body)
    return _image_from_response(resp, get_bytes)
