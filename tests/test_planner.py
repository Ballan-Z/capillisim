from PIL import Image

from cap_mosaic.app import planner_designer as designer
from cap_mosaic.core.geometry import Cap, grid_for_caps_across
from cap_mosaic.core.palette import CapColor, distance
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


def _three_color_image(size: int = 240) -> Image.Image:
    """Equal vertical bands of red, green, blue."""
    img = Image.new("RGB", (size, size))
    bands = [(200, 30, 30), (30, 170, 60), (40, 70, 190)]
    for i, col in enumerate(bands):
        for x in range(i * size // 3, (i + 1) * size // 3):
            for y in range(size):
                img.putpixel((x, y), col)
    return img


def test_kmeans_palette_finds_the_dominant_colors():
    img = _three_color_image()
    pal = designer.palette_from_image(img, k=3)
    assert len(pal) == 3
    names = {c.name for c in pal}
    assert {"red", "green", "blue"} <= names


def test_kmeans_palette_is_deterministic():
    img = _three_color_image()
    a = designer.palette_from_image(img, k=3, seed=7)
    b = designer.palette_from_image(img, k=3, seed=7)
    assert [c.rgb for c in a] == [c.rgb for c in b]


def test_palette_intersects_inventory():
    img = _three_color_image()  # wants red, green, blue
    # inventory has red and blue only (no green) plus an irrelevant purple
    inventory = (
        CapColor("myred", (205, 25, 25)),
        CapColor("myblue", (35, 65, 195)),
        CapColor("purple", (120, 30, 160)),
    )
    pal = designer.palette_from_image(img, k=3, inventory=inventory)
    # palette is drawn only from inventory; green has no good match -> maps to
    # whichever inventory cap is nearest, but unused purple should not appear
    assert all(c in inventory for c in pal)


def test_reject_gate_leaves_holes_for_unrepresentable_colors():
    img = _three_color_image()  # red, green, blue thirds
    grid = grid_for_caps_across(12, aspect_ratio=1.0, cap=Cap())
    # palette without green; tight threshold so green cells cannot be faked
    palette = (CapColor("red", (200, 30, 30)), CapColor("blue", (40, 70, 190)))
    plan = designer.plan_from_image(img, grid, palette=palette, reject_threshold=10.0)
    assert plan.hole_count > 0
    # holes are excluded from the bill of materials and are never green-named
    assert "" not in plan.bill_of_materials()
    # without a threshold, the same plan has no holes (green forced to red/blue)
    plan2 = designer.plan_from_image(img, grid, palette=palette)
    assert plan2.hole_count == 0


def test_bare_white_leaves_white_border_as_holes():
    # white border, coloured (red) centre
    size = 240
    img = Image.new("RGB", (size, size), (250, 250, 250))
    m = size // 4
    for x in range(m, size - m):
        for y in range(m, size - m):
            img.putpixel((x, y), (200, 30, 30))
    grid = grid_for_caps_across(12, aspect_ratio=1.0, cap=Cap())

    plan = designer.plan_from_image(img, grid, bare_white=True)
    assert plan.hole_count > 0  # white border dropped
    # every non-hole cell is a real (non-white) cap; holes carry no colour name
    assert all(min(c.rgb) < 238 for c in plan.cells if not c.is_hole)
    assert "" not in plan.bill_of_materials()
    # the coloured centre still produces caps
    assert any(not c.is_hole for c in plan.cells)

    # default (bare_white=False) fills the white region instead of holing it
    plan2 = designer.plan_from_image(img, grid)
    assert plan2.hole_count == 0


def test_inventory_filters_by_size_class(tmp_path):
    from cap_mosaic.data.store import CapDataset

    path = tmp_path / "caps.db"
    with CapDataset(path) as db:
        db.add_cap((200, 30, 30), captured_at="t", diameter_mm=30.2)   # standard
        db.add_cap((30, 60, 200), captured_at="t", diameter_mm=37.4)   # large
        db.add_cap((10, 10, 10), captured_at="t")                       # unmeasured
    assert len(designer.inventory_from_db(path)) == 3                   # no filter
    std = designer.inventory_from_db(path, size_class="standard-26")
    assert [c.rgb for c in std] == [(200, 30, 30)]
    lrg = designer.inventory_from_db(path, size_class="large-38")
    assert [c.rgb for c in lrg] == [(30, 60, 200)]


def test_inventory_from_db_prefers_mosaic_colour(tmp_path):
    from cap_mosaic.data.store import CapDataset

    path = tmp_path / "caps.db"
    with CapDataset(path) as db:
        db.add_cap((8, 6, 2), captured_at="t", mosaic_rgb=(83, 80, 59))  # black+gold
        db.add_cap((200, 30, 30), captured_at="t")  # legacy row, no mosaic yet
    inv = designer.inventory_from_db(path)
    rgbs = {c.rgb for c in inv}
    # the at-distance (mosaic) colour drives matching; legacy falls back to field
    assert (83, 80, 59) in rgbs
    assert (200, 30, 30) in rgbs
    assert (8, 6, 2) not in rgbs


def test_thicken_outlines_widens_thin_dark_strokes():
    # white field with a 1-cap-wide vertical black stripe
    size, across = 200, 20
    cell = size // across
    img = Image.new("RGB", (size, size), (245, 245, 245))
    x = (across // 2) * cell
    for xx in range(x, x + cell):
        for yy in range(size):
            img.putpixel((xx, yy), (20, 20, 20))
    grid = grid_for_caps_across(across, aspect_ratio=1.0, cap=Cap())

    plain = designer.plan_from_image(img, grid)
    thick = designer.plan_from_image(img, grid, thicken_outlines=True)
    # the thin stripe is flagged before thickening and reduced after
    assert designer.count_thin_outlines(plain) > 0
    assert designer.count_thin_outlines(thick) < designer.count_thin_outlines(plain)
    # thickening adds dark caps (the stripe grew wider)
    dark = lambda p: sum(1 for c in p.cells if not c.is_hole and max(c.rgb) < 90)
    assert dark(thick) > dark(plain)


def test_dither_mixes_colours_where_nearest_picks_one():
    # a flat mid-grey field with a black+white palette: nearest -> all one colour,
    # dither -> a black/white mix that averages to the grey
    img = Image.new("RGB", (200, 200), (150, 150, 150))
    grid = grid_for_caps_across(16, aspect_ratio=1.0, cap=Cap())
    palette = (CapColor("black", (0, 0, 0)), CapColor("white", (255, 255, 255)))
    plain = designer.plan_from_image(img, grid, palette=palette)
    dith = designer.plan_from_image(img, grid, palette=palette, dither=True)
    plain_colours = {c.color_name for c in plain.cells if not c.is_hole}
    dith_colours = {c.color_name for c in dith.cells if not c.is_hole}
    assert len(plain_colours) == 1                 # nearest is a solid block
    assert dith_colours == {"black", "white"}      # dither interleaves both


def test_plan_from_inventory_respects_stock_counts():
    from cap_mosaic.app.cap_stock import Group

    img = _three_color_image()  # red / green / blue thirds
    grid = grid_for_caps_across(9, aspect_ratio=1.0, cap=Cap())
    n_cells = len(grid.cells)
    # stock: plenty of red + blue, NO green, and fewer caps than cells overall
    budget = n_cells - 5
    groups = [
        Group("gred", (200, 30, 30), budget // 2, []),
        Group("gblue", (40, 70, 190), budget - budget // 2, []),
    ]
    plan = designer.plan_from_inventory(img, grid, groups)
    used = sum(1 for c in plan.cells if not c.is_hole)
    assert used == budget                        # every owned cap placed, none invented
    assert plan.hole_count == n_cells - budget   # stock exhausted -> holes
    names = {c.color_name for c in plan.cells if not c.is_hole}
    assert names <= {"gred", "gblue"}            # cells carry GROUP labels
    # green cells got SOMETHING (no reject) or ended as the sacrificed holes
    per = {n: sum(1 for c in plan.cells if c.color_name == n) for n in names}
    assert per["gred"] == budget // 2            # counts exactly respected


def test_holes_roundtrip_and_are_skipped_by_matcher():
    from cap_mosaic.core.matcher import Matcher

    img = _three_color_image()
    grid = grid_for_caps_across(12, aspect_ratio=1.0, cap=Cap())
    palette = (CapColor("red", (200, 30, 30)), CapColor("blue", (40, 70, 190)))
    plan = designer.plan_from_image(img, grid, palette=palette, reject_threshold=10.0)
    # JSON roundtrip preserves holes
    import json

    restored = GridPlan.from_dict(json.loads(json.dumps(plan.to_dict())))
    assert restored.hole_count == plan.hole_count
    # the matcher never targets a hole, even with a green cap in hand
    m = Matcher(plan, reject_threshold=100.0)
    match = m.match((30, 170, 60))
    assert match.cell is None or not match.cell.is_hole
