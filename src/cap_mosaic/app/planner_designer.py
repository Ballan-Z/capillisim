"""Designer: turn a target image into a GridPlan, render it, and simulate how it
reads from a distance.

This is the offline half of the system (Milestone 1): no camera, no projector,
fully testable. It depends on Pillow + numpy but stays otherwise self-contained.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..core.geometry import Grid
from ..core.palette import DEFAULT_PALETTE, CapColor, nearest
from ..core.plan import GridPlan, PlannedCell

# Perceptual "blend threshold": the angular size below which neighbouring caps
# read as a merged tone (a squint/halftone-blending heuristic, larger than raw
# 1-arcminute acuity). Tunable; calibrate against real photos later.
DEFAULT_BLEND_ARCMIN = 8.0


def plan_from_image(
    image: Image.Image,
    grid: Grid,
    palette: tuple[CapColor, ...] = DEFAULT_PALETTE,
    title: str = "untitled",
) -> GridPlan:
    """Sample `image` at each cap location and quantize to the palette."""
    img = image.convert("RGB")
    arr = np.asarray(img)
    img_h, img_w = arr.shape[:2]
    radius_px_x = max(1, int((grid.cap.radius_mm / grid.width_mm) * img_w))
    radius_px_y = max(1, int((grid.cap.radius_mm / grid.height_mm) * img_h))

    cells: list[PlannedCell] = []
    for cell in grid.cells:
        cx = int((cell.x_mm / grid.width_mm) * img_w)
        cy = int((cell.y_mm / grid.height_mm) * img_h)
        x0, x1 = max(0, cx - radius_px_x), min(img_w, cx + radius_px_x + 1)
        y0, y1 = max(0, cy - radius_px_y), min(img_h, cy + radius_px_y + 1)
        patch = arr[y0:y1, x0:x1].reshape(-1, 3)
        mean = tuple(int(v) for v in patch.mean(axis=0)) if patch.size else (0, 0, 0)
        cap_color = nearest(mean, palette)
        cells.append(
            PlannedCell(
                row=cell.row,
                col=cell.col,
                x_mm=cell.x_mm,
                y_mm=cell.y_mm,
                color_name=cap_color.name,
                rgb=cap_color.rgb,
            )
        )

    return GridPlan(
        cap_diameter_mm=grid.cap.diameter_mm,
        width_mm=grid.width_mm,
        height_mm=grid.height_mm,
        cells=cells,
        title=title,
    )


def render_mosaic(
    plan: GridPlan,
    px_per_mm: float = 4.0,
    background: tuple[int, int, int] = (235, 235, 235),
) -> Image.Image:
    """Draw the plan as filled cap-circles for preview/inspection."""
    w = max(1, int(plan.width_mm * px_per_mm))
    h = max(1, int(plan.height_mm * px_per_mm))
    img = Image.new("RGB", (w, h), background)
    draw = ImageDraw.Draw(img)
    r = (plan.cap_diameter_mm / 2.0) * px_per_mm
    for c in plan.cells:
        cx, cy = c.x_mm * px_per_mm, c.y_mm * px_per_mm
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(c.rgb))
    return img


def simulate_distance(
    mosaic: Image.Image,
    px_per_mm: float,
    distance_m: float,
    blend_arcmin: float = DEFAULT_BLEND_ARCMIN,
) -> Image.Image:
    """Blur the rendered mosaic to approximate how it reads from `distance_m`.

    Caps merge into tones as they shrink in your field of view. We model that as
    a Gaussian blur whose width grows with viewing distance, so sliding distance
    shows the pattern-up-close vs. portrait-from-afar trade-off.
    """
    blend_rad = math.radians(blend_arcmin / 60.0)
    sigma_mm = distance_m * 1000.0 * math.tan(blend_rad)
    sigma_px = max(0.0, sigma_mm * px_per_mm)
    return mosaic.filter(ImageFilter.GaussianBlur(radius=sigma_px))


def demo_image(size: int = 512) -> Image.Image:
    """A synthetic target so the pipeline is runnable without supplying art."""
    img = Image.new("RGB", (size, size), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.ellipse([size * 0.2, size * 0.15, size * 0.8, size * 0.75], fill=(225, 200, 70))
    draw.ellipse([size * 0.34, size * 0.32, size * 0.44, size * 0.42], fill=(28, 28, 28))
    draw.ellipse([size * 0.56, size * 0.32, size * 0.66, size * 0.42], fill=(28, 28, 28))
    draw.arc([size * 0.34, size * 0.40, size * 0.66, size * 0.66], 20, 160, fill=(190, 40, 45), width=int(size * 0.03))
    draw.rectangle([0, int(size * 0.8), size, size], fill=(40, 80, 160))
    return img
