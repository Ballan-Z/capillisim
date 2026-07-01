import numpy as np

from cap_mosaic.core import legibility


def _gradient(size=200):
    """A low-frequency image: a smooth horizontal gradient (reads at few caps)."""
    x = np.linspace(0, 255, size).astype(np.uint8)
    g = np.repeat(x[None, :], size, axis=0)
    return np.stack([g, g, g], axis=-1)


def _fine_checker(size=200, cell=4):
    """A high-frequency image: a fine checkerboard (needs many caps)."""
    yy, xx = np.mgrid[0:size, 0:size]
    c = (((xx // cell) + (yy // cell)) % 2 * 255).astype(np.uint8)
    return np.stack([c, c, c], axis=-1)


def test_flat_image_needs_few_caps():
    solid = np.full((200, 200, 3), 128, np.uint8)
    assert legibility.min_caps_across(solid) <= 8


def test_detailed_image_needs_more_than_simple():
    simple = _gradient()
    detailed = _fine_checker()
    assert legibility.min_caps_across(detailed) > legibility.min_caps_across(simple)


def test_pattern_mode_is_looser_or_equal():
    img = _fine_checker(cell=8)
    assert legibility.min_caps_across(img, mode="pattern") <= legibility.min_caps_across(
        img, mode="picture"
    )


def test_score_increases_with_more_caps():
    img = _fine_checker(cell=6)
    lo = legibility.legibility_score(img, 8, aspect=1.0)
    hi = legibility.legibility_score(img, 64, aspect=1.0)
    assert hi > lo
