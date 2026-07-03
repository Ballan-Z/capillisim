import numpy as np
from PIL import Image

from cap_mosaic.app.cap_signature import SIG_LEN, cap_signature, signature_distance


def _cap(n=128, body=(30, 60, 160), ring_logo=False, text_blob=False):
    """Synthetic card-style crop: cap disc on white, optional radial structure."""
    img = np.full((n, n, 3), 250, np.uint8)
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.hypot(xx - n / 2, yy - n / 2)
    img[r <= n * 0.42] = body
    if ring_logo:  # a contrasting ring at mid radius
        img[(r > n * 0.20) & (r <= n * 0.28)] = (230, 220, 90)
    if text_blob:  # an off-centre blob (rotates with the cap)
        blob = np.hypot(xx - n * 0.62, yy - n * 0.40) <= n * 0.09
        img[blob & (r <= n * 0.42)] = (240, 240, 240)
    return img


def _rot(img, k):
    return np.rot90(img, k).copy()


def test_signature_shape_and_finite():
    s = cap_signature(_cap())
    assert s.shape == (SIG_LEN,)
    assert np.all(np.isfinite(s))


def test_rotation_invariance():
    a = _cap(ring_logo=True, text_blob=True)
    s0 = cap_signature(a)
    for k in (1, 2, 3):
        d = signature_distance(s0, cap_signature(_rot(a, k)))
        # small residual comes from circle re-detection jitter, not rotation;
        # different-structure caps score > 0.5 (asserted below), so 0.15 is strict
        assert d < 0.15, (k, d)


def test_small_brightness_jitter_stays_close():
    a = _cap(ring_logo=True)
    b = np.clip(a.astype(int) + 8, 0, 255).astype(np.uint8)  # lighting shift
    assert signature_distance(cap_signature(a), cap_signature(b)) < 0.5


def test_different_structure_is_far():
    plain = _cap()                       # flat blue cap
    ringed = _cap(ring_logo=True)        # same body + yellow ring
    self_d = signature_distance(cap_signature(plain), cap_signature(_rot(plain, 1)))
    diff_d = signature_distance(cap_signature(plain), cap_signature(ringed))
    assert diff_d > max(0.5, 3 * self_d), (self_d, diff_d)


def test_same_colour_different_layout_distinguishable():
    # two dark caps with the same average colour but different radial structure
    inner = _cap(body=(20, 20, 20))
    inner[np.hypot(*(np.mgrid[0:128, 0:128] - 64)) <= 20] = (200, 170, 60)  # gold centre
    outer = _cap(body=(20, 20, 20), ring_logo=True)
    d = signature_distance(cap_signature(inner), cap_signature(outer))
    assert d > 0.5
