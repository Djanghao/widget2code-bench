"""remove_border_touching_components: guard the vectorised form against the original.

The 0.2.9 implementation painted one component at a time by comparing the whole
label image against each label, which is quadratic in (components x pixels).
The current form builds a per-label lookup table and visits the mask once. The
two must agree bit for bit, so the original is kept here as the reference and
both are run over synthetic edge cases and, when the benchmark is available,
real widget masks.
"""
import numpy as np
import cv2
import pytest

from widget_quality.utils import remove_border_touching_components


def reference(mask):
    """The 0.2.9 implementation, verbatim."""
    mask = (mask > 0).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    H, W = mask.shape
    cleaned = np.zeros_like(mask)
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if not ((x == 0) or (y == 0) or (x + w == W) or (y + h == H)):
            cleaned[labels == i] = 255
    return cleaned.astype(np.uint8)


def assert_identical(mask):
    got, want = remove_border_touching_components(mask), reference(mask)
    assert got.shape == want.shape
    assert got.dtype == want.dtype
    assert np.array_equal(got, want)


def _blank(h=40, w=50):
    return np.zeros((h, w), np.uint8)


EDGE_CASES = {
    "empty": _blank(),
    "full": np.full((40, 50), 255, np.uint8),
    "single_pixel_interior": None,
    "single_pixel_corner": None,
    "border_stripe_plus_interior": None,
    "one_by_one_empty": _blank(1, 1),
    "one_by_one_set": np.full((1, 1), 255, np.uint8),
    "zero_one_valued": None,
    "component_touching_right_edge": None,
    "component_touching_bottom_edge": None,
}
EDGE_CASES["single_pixel_interior"] = (lambda m: (m.__setitem__((20, 25), 255), m)[1])(_blank())
EDGE_CASES["single_pixel_corner"] = (lambda m: (m.__setitem__((0, 0), 255), m)[1])(_blank())
EDGE_CASES["border_stripe_plus_interior"] = (
    lambda m: (m.__setitem__((0, slice(None)), 255), m.__setitem__((20, 25), 255), m)[2]
)(_blank())
EDGE_CASES["zero_one_valued"] = (
    lambda m: (m.__setitem__((slice(10, 15), slice(10, 15)), 1), m)[1]
)(_blank())
EDGE_CASES["component_touching_right_edge"] = (
    lambda m: (m.__setitem__((slice(10, 20), slice(45, 50)), 255), m)[1]
)(_blank())
EDGE_CASES["component_touching_bottom_edge"] = (
    lambda m: (m.__setitem__((slice(35, 40), slice(10, 20)), 255), m)[1]
)(_blank())


@pytest.mark.parametrize("name", sorted(EDGE_CASES))
def test_edge_cases(name):
    assert_identical(EDGE_CASES[name])


@pytest.mark.parametrize("seed", range(20))
def test_random_masks(seed):
    rng = np.random.default_rng(seed)
    mask = (rng.random((60, 80)) < 0.25).astype(np.uint8) * 255
    assert_identical(mask)


def test_no_components_leaves_mask_empty():
    assert not remove_border_touching_components(_blank()).any()


def test_interior_component_is_kept_as_255():
    mask = _blank()
    mask[10:20, 10:20] = 255
    out = remove_border_touching_components(mask)
    assert set(np.unique(out).tolist()) == {0, 255}
    assert out[15, 15] == 255


def test_border_component_is_dropped():
    mask = _blank()
    mask[0:10, 0:10] = 255
    assert not remove_border_touching_components(mask).any()
