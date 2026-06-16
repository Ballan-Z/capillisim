import numpy as np

from cap_mosaic.procam.calibrate import (
    Calibration,
    apply_homography,
    compute_homography,
)


def _known_transform(pt):
    # an affine map: 4 px/mm, offset, plus a mild shear to mimic keystone
    x, y = pt
    return (4.0 * x + 0.05 * y + 100.0, 4.0 * y + 50.0)


def test_homography_recovers_known_transform():
    src = [(0, 0), (300, 0), (0, 200), (300, 200)]
    dst = [_known_transform(p) for p in src]
    h = compute_homography(src, dst)
    for p in [(150, 100), (50, 175), (290, 10)]:
        got = apply_homography(h, p)
        exp = _known_transform(p)
        assert np.allclose(got, exp, atol=1e-6)


def test_calibration_roundtrips_mm_to_px_to_mm():
    src = [(0, 0), (320, 0), (0, 240), (320, 240)]
    dst = [_known_transform(p) for p in src]
    cal = Calibration.from_correspondences(src, dst, 1920, 1080)
    px, py = cal.table_mm_to_proj_px(123.0, 77.0)
    mm = cal.proj_px_to_table_mm(px, py)
    assert np.allclose(mm, (123.0, 77.0), atol=1e-6)


def test_projected_radius_scales_with_calibration():
    # pure 4 px/mm scale, no offset
    src = [(0, 0), (100, 0), (0, 100), (100, 100)]
    dst = [(4 * x, 4 * y) for x, y in src]
    cal = Calibration.from_correspondences(src, dst, 800, 800)
    r_px = cal.mm_radius_to_px(50, 50, 16.0)
    assert abs(r_px - 64.0) < 1e-6  # 16 mm * 4 px/mm


def test_calibration_persists(tmp_path):
    src = [(0, 0), (300, 0), (0, 200), (300, 200)]
    dst = [_known_transform(p) for p in src]
    cal = Calibration.from_correspondences(src, dst, 1280, 720)
    path = tmp_path / "cal.json"
    cal.save(path)
    loaded = Calibration.load(path)
    assert loaded.proj_width == 1280 and loaded.proj_height == 720
    assert np.allclose(loaded.h_table_to_proj, cal.h_table_to_proj)


def test_too_few_points_raises():
    try:
        compute_homography([(0, 0), (1, 0), (0, 1)], [(0, 0), (1, 0), (0, 1)])
    except ValueError:
        return
    raise AssertionError("expected ValueError for < 4 points")
