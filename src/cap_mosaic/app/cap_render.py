"""Render a mosaic from actual cap images (real + fake), not flat colour disks.

Each planned cell is filled with the library cap whose colour is perceptually
closest, pasted as a circular RGBA tile. The result looks like caps up close;
blurred by ``planner_designer.simulate_distance`` it reads as the picture — the
"too close you see caps, far away you see the image" simulation.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

from ..core.palette import RGB, ciede2000, rgb_to_lab
from ..core.plan import GridPlan
from .fake_caps import CapImage, fake_cap_library


def _load_circular(path: str, size: int) -> Image.Image | None:
    """A real cap crop, resized and masked to a circle (RGBA)."""
    try:
        im = Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)
    except (OSError, ValueError):
        return None
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([1, 1, size - 2, size - 2], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


@lru_cache(maxsize=8)
def _real_caps(db_path: str, size: int, mtime: float) -> tuple[CapImage, ...]:
    """Real caps from the dataset as circular tiles, cached (mtime busts it)."""
    from ..data.store import CapDataset

    caps: list[CapImage] = []
    with CapDataset(db_path) as db:
        for c in db.caps(with_frames=True):
            if not c.frames:
                continue
            im = _load_circular(c.frames[0].path, size)
            if im is not None:
                caps.append(CapImage(tuple(c.rgb), im))
    return tuple(caps)


def build_library(
    palette: list[RGB],
    db_path: str | None = None,
    size: int = 64,
    seed: int = 0,
    markings: bool = True,
) -> list[CapImage]:
    """A cap image library covering `palette` (fake caps) plus any real caps from
    ``db_path`` (which the nearest-colour match will prefer when closer). The real
    caps are loaded once and cached, so repeated renders (slider drags) are fast."""
    lib = fake_cap_library(list(palette), size=size, seed=seed, markings=markings)
    if db_path and Path(db_path).exists():
        lib.extend(_real_caps(db_path, size, Path(db_path).stat().st_mtime))
    return lib


def render_mosaic_caps(
    plan: GridPlan,
    cap_lib: list[CapImage],
    px_per_cap: int = 24,
    background: RGB = (235, 235, 235),
) -> Image.Image:
    """Draw the plan by tiling the nearest-colour cap image into each cell."""
    if not cap_lib:
        raise ValueError("cap_lib is empty")
    pitch = plan.cap_diameter_mm
    ppm = px_per_cap / pitch
    w = max(1, round(plan.width_mm * ppm))
    h = max(1, round(plan.height_mm * ppm))
    canvas = Image.new("RGB", (w, h), background)

    labs = [(cap, rgb_to_lab(cap.rgb)) for cap in cap_lib]
    nearest: dict[RGB, CapImage] = {}
    tiles: dict[int, Image.Image] = {}
    for cell in plan.cells:
        if cell.is_hole:
            continue
        key = tuple(cell.rgb)
        cap = nearest.get(key)
        if cap is None:
            lab = rgb_to_lab(key)
            cap = min(labs, key=lambda cl: ciede2000(lab, cl[1]))[0]
            nearest[key] = cap
        tile = tiles.get(id(cap))
        if tile is None:
            tile = cap.image.resize((px_per_cap, px_per_cap), Image.LANCZOS)
            tiles[id(cap)] = tile
        cx, cy = cell.x_mm * ppm, cell.y_mm * ppm
        canvas.paste(tile, (round(cx - px_per_cap / 2), round(cy - px_per_cap / 2)), tile)
    return canvas
