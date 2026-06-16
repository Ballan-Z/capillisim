from cap_mosaic.core.palette import (
    DEFAULT_PALETTE,
    CapColor,
    ciede2000,
    nearest,
    rgb_to_lab,
)


def test_identical_colors_have_zero_distance():
    lab = rgb_to_lab((123, 45, 67))
    assert ciede2000(lab, lab) < 1e-9


def test_nearest_picks_obvious_colors():
    assert nearest((250, 10, 10)).name == "red"
    assert nearest((10, 10, 10)).name == "black"
    assert nearest((250, 250, 250)).name == "white"
    assert nearest((20, 60, 200)).name == "blue"


def test_distance_orders_similar_before_dissimilar():
    red = CapColor("ref-red", (200, 30, 30))
    near = ciede2000(rgb_to_lab((205, 35, 35)), red.lab)
    far = ciede2000(rgb_to_lab((30, 30, 200)), red.lab)
    assert near < far


def test_palette_names_unique():
    names = [c.name for c in DEFAULT_PALETTE]
    assert len(names) == len(set(names))
