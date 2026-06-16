from PIL import Image

from cap_mosaic.app import planner_designer as designer
from cap_mosaic.core.geometry import Cap, grid_for_caps_across
from cap_mosaic.core.plan import GridPlan


def _plan():
    cap = Cap(diameter_mm=32.0)
    grid = grid_for_caps_across(8, aspect_ratio=1.0, cap=cap)
    img = Image.new("RGB", (256, 256), (200, 30, 30))  # solid red
    return designer.plan_from_image(img, grid, title="solid")


def test_solid_image_maps_to_single_color():
    plan = _plan()
    assert plan.count > 0
    assert all(c.color_name == "red" for c in plan.cells)
    assert plan.bill_of_materials() == {"red": plan.count}


def test_plan_roundtrips_through_json(tmp_path):
    plan = _plan()
    path = tmp_path / "p.capproj.json"
    plan.save(path)
    loaded = GridPlan.load(path)
    assert loaded.count == plan.count
    assert loaded.cells[0].rgb == plan.cells[0].rgb
    assert loaded.width_mm == plan.width_mm


def test_remaining_bom_tracks_filled_cells():
    plan = _plan()
    total = plan.count
    plan.cells[0].filled = True
    assert plan.filled_count == 1
    assert plan.remaining_bom().get("red", 0) == total - 1


def test_render_and_distance_simulation_produce_images():
    plan = _plan()
    mosaic = designer.render_mosaic(plan, px_per_mm=3.0)
    assert mosaic.size[0] > 0 and mosaic.size[1] > 0
    blurred = designer.simulate_distance(mosaic, px_per_mm=3.0, distance_m=5.0)
    assert blurred.size == mosaic.size


def test_demo_image_is_runnable():
    img = designer.demo_image(128)
    grid = grid_for_caps_across(10, aspect_ratio=1.0, cap=Cap())
    plan = designer.plan_from_image(img, grid)
    assert plan.count > 0
    # demo image uses several palette colors
    assert len(plan.bill_of_materials()) >= 2
