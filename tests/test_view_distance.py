import numpy as np
from PIL import Image

from cap_mosaic.app import planner_designer as designer

BOARD = (230, 230, 230)


def _hf_energy(arr):
    a = arr.astype(float)
    lap = 4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    return lap.var()


def _non_board_bbox(img):
    a = np.asarray(img)
    mask = np.any(np.abs(a.astype(int) - np.array(BOARD)) > 8, axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def _checker(n=240, cell=4):
    yy, xx = np.mgrid[0:n, 0:n]
    arr = np.zeros((n, n, 3), np.uint8)
    arr[((xx // cell + yy // cell) % 2) == 0] = 255
    return Image.fromarray(arr, "RGB")


def _feature_plus_texture(n=400):
    yy, xx = np.mgrid[0:n, 0:n]
    base = np.where(xx < n // 2, 90, 160).astype(np.int16)  # big low-freq edge
    checker = np.where(((xx // 2 + yy // 2) % 2) == 0, 60, -60)  # high freq
    v = np.clip(base + checker, 0, 255).astype(np.uint8)
    return Image.fromarray(np.stack([v, v, v], axis=2), "RGB")


def test_frame_size_is_fixed():
    out = designer.view_at_distance(_checker(), 2000, 5.0, (300, 200), board=BOARD)
    assert out.size == (300, 200)


def test_far_occupies_fewer_pixels_than_near():
    m = _checker()
    near = designer.view_at_distance(m, 2000, 2.0, (400, 400), board=BOARD)
    far = designer.view_at_distance(m, 2000, 25.0, (400, 400), board=BOARD)
    nb_near = _non_board_bbox(near)
    nb_far = _non_board_bbox(far)
    area = lambda b: (b[2] - b[0]) * (b[3] - b[1])
    assert area(nb_far) < area(nb_near)


def test_resample_mixes_in_linear_light():
    # A 50/50 black+white checker, heavily downscaled, must average to the LINEAR
    # midpoint (~188 in sRGB), not the sRGB midpoint (~128).
    m = _checker(n=240, cell=4)
    out = designer.view_at_distance(m, 2000, 30.0, (240, 240), board=BOARD)
    bb = _non_board_bbox(out)
    x0, y0, x1, y1 = bb
    interior = np.asarray(out)[y0 + 2:y1 - 2, x0 + 2:x1 - 2]
    assert interior.size > 0
    assert interior.mean() > 170  # linear mixing, not sRGB averaging (~128)


def test_far_blends_high_frequency_but_keeps_large_feature():
    m = _feature_plus_texture()
    near = designer.view_at_distance(m, 2000, 2.0, (400, 400), board=BOARD)
    far = designer.view_at_distance(m, 2000, 25.0, (400, 400), board=BOARD)
    near_g = np.asarray(near.convert("L"))
    far_g = np.asarray(far.convert("L"))
    assert _hf_energy(far_g) < _hf_energy(near_g)  # caps/texture blend away
    # the big left/right feature still survives in the shrunken far view
    bb = _non_board_bbox(far)
    x0, y0, x1, y1 = bb
    crop = far_g[y0:y1, x0:x1]
    mid = crop.shape[1] // 2
    left, right = crop[:, :mid].mean(), crop[:, mid:].mean()
    assert abs(left - right) > 20
