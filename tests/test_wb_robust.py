import numpy as np

from cap_mosaic.vision.card_reader import white_balance


def test_white_balance_survives_offframe_homography():
    # a bogus card detection can map the gray patches OFF the frame -> NaN
    # medians -> polyfit SVD crash. Must return the frame unchanged instead.
    frame = np.full((120, 120, 3), 128, np.uint8)
    h = np.array([[100.0, 0, 5000], [0, 100.0, 5000], [0, 0, 1.0]])  # far off-frame
    out = white_balance(frame, h)
    assert out.shape == frame.shape
    assert np.array_equal(out, frame)  # degenerate samples -> no-op, no crash


def test_white_balance_survives_constant_samples():
    # all patches landing on identical pixels (uniform frame) is rank-deficient
    frame = np.full((400, 400, 3), 90, np.uint8)
    h = np.eye(3)
    out = white_balance(frame, h)  # must not raise
    assert out.shape == frame.shape


def test_white_balance_still_corrects_a_valid_strip():
    # sanity: a frame with a real-ish gradient strip still gets corrected
    from cap_mosaic.vision import card_layout as L

    frame = np.full((400, 400, 3), 60, np.uint8)
    h = np.eye(3)
    # paint each gray patch darker than nominal (simulating dim light)
    for g in L.GRAY_PATCHES:
        x, y = int(g.cx_mm), int(g.cy_mm)
        v = max(0, int(g.value * 0.6))
        frame[max(0, y - 4):y + 5, max(0, x - 4):x + 5] = v
    out = white_balance(frame, h)
    assert out.shape == frame.shape
    assert out.mean() > frame.mean()  # exposure lifted toward nominal
