"""The reported mean must still be the number 0.2.9 published, only with more digits.

0.2.9 quantised every sample to three decimals and then rounded the mean to two.
Only the second rounding is gone. That makes the extra digits a property of the
display rather than of the measurement, and it is what lets a 1.0.0 run be
compared against a table produced before it - so it is worth a test rather than
a comment.
"""
import numpy as np
import pytest

from widget_quality.composite import SAMPLE_DIGITS, composite_score
from widget2code_bench.report import METRICS, aggregate, flatten


def _sample(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    return composite_score(
        float(rng.uniform(0, 1)),
        {"SSIM": float(rng.uniform(0, 1)), "LPIPS": float(rng.uniform(0, 1))},
        {k: float(rng.uniform(0, 2)) for k in
         ("MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff")},
        {"TextJaccard": float(rng.uniform(0, 1)),
         "ContrastDiff": float(rng.uniform(0, 5)),
         "ContrastLocalDiff": float(rng.uniform(0, 5))},
        {k: float(rng.uniform(0, 1)) for k in
         ("PaletteDistance", "Vibrancy", "PolarityConsistency")},
    )


def _mean_as_0_2_9_would(samples, metric):
    """0.2.9: mean over the already-quantised samples, then two decimals."""
    return round(float(np.mean([flatten(s)[metric] for s in samples])), 2)


def test_samples_are_still_quantised_to_three_decimals():
    scores = _sample(0)
    for group, values in scores.items():
        if group == "Geometry":            # 0.2.9 left geo_score unrounded
            continue
        for name, value in values.items():
            assert value == round(value, SAMPLE_DIGITS), f"{group}.{name}"


@pytest.mark.parametrize("n", [1, 5, 37])
def test_reported_mean_rounds_back_to_the_published_figure(n):
    samples = [_sample(i) for i in range(n)]
    modes = aggregate(samples, [], [])
    for metric in METRICS:
        assert round(modes["raw"][metric], 2) == _mean_as_0_2_9_would(samples, metric)


def test_reported_mean_carries_more_digits_than_two():
    """Otherwise there would be no point: the run would just be the old table."""
    samples = [_sample(i) for i in range(37)]
    modes = aggregate(samples, [], [])
    assert any(modes["raw"][m] != round(modes["raw"][m], 2) for m in METRICS)


def test_zero_fill_uses_the_worst_value_per_direction():
    """lp is a distance, so its worst is 1.0 while every score's worst is 0."""
    samples = [_sample(i) for i in range(4)]
    modes = aggregate(samples, samples[:2], samples[:2])
    raw, zero = modes["raw"], modes["zero"]
    assert zero["ssim"] < raw["ssim"]
    assert zero["lp"] > raw["lp"]
