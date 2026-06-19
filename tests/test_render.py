import numpy as np

from cap_mosaic.app import planner_designer as designer
from cap_mosaic.core.geometry import Cap, grid_for_caps_across
from cap_mosaic.procam.calibrate import Calibration
from cap_mosaic.procam.render import render_projection


def _plan_and_cal():
    grid = grid_for_caps_across(6, aspect_ratio=1.0, cap=Cap(32.0))
    from PIL import Image

    img = Image.new("RGB", (128, 128), (40, 120, 70))
    plan = designer.plan_from_image(img, grid)
    # simple 4 px/mm calibration onto a 1024x1024 projector frame
    src = [(0, 0), (192, 0), (0, 192), (192, 192)]
    dst = [(4 * x, 4 * y) for x, y in src]
    cal = Calibration.from_correspondences(src, dst, 1024, 1024)
    return plan, cal


def test_projection_frame_matches_projector_size():
    plan, cal = _plan_and_cal()
    frame = render_projection(plan, cal)
    assert frame.size == (1024, 1024)


def test_highlight_lights_up_its_cell():
    plan, cal = _plan_and_cal()
    target = plan.cells[len(plan.cells) // 2]
    plain = np.asarray(render_projection(plan, cal, show_template=False))
    lit = np.asarray(render_projection(plan, cal, highlight=target, show_template=False))
    # the highlighted frame is much brighter where the target cell projects
    cx, cy = cal.table_mm_to_proj_px(target.x_mm, target.y_mm)
    half = 110  # wide enough to include the glow rings (~64-102 px radius)
    box = lit[int(cy) - half : int(cy) + half, int(cx) - half : int(cx) + half]
    assert box.max() > 200
    assert lit.sum() > plain.sum()


def test_template_draws_rings_without_highlight():
    plan, cal = _plan_and_cal()
    frame = np.asarray(render_projection(plan, cal, show_template=True))
    assert frame.max() > 0  # something was drawn


def test_mosaic_projection_fills_with_cell_colors():
    from cap_mosaic.procam.render import render_mosaic_projection

    plan, cal = _plan_and_cal()
    frame = render_mosaic_projection(plan, cal)
    assert frame.size == (1024, 1024)
    arr = np.asarray(frame)
    assert arr.sum() > 0  # not a black frame
    assert arr[..., 1].max() > 50  # greenish source -> filled cells, not just rings
