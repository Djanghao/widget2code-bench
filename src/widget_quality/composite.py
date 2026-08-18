"""Turn raw metric values into the twelve reported scores.

Per-sample values are quantised to three decimals, as they have been since
0.2.9. That quantisation is part of the contract rather than a display choice:
aggregation happens afterwards, so every published mean was taken over these
values, and keeping it is what makes a mean comparable with an existing table.

What is not kept is the second rounding 0.2.9 applied to the mean itself. That
one only ever threw away digits of a number already fixed by this module, so the
report layer now shows the mean to more decimals; rounding its output to two
recovers the old figure exactly.
"""

# The reported scores have been quantised to three decimals since 0.2.9.
SAMPLE_DIGITS = 3
import numpy as np


def smooth_score(val, scale, method="exp"):
    if method == "exp":
        return 100 * np.exp(-val / scale)
    elif method == "linear":
        return 100 * max(0.0, 1 - val / scale)
    elif method == "logistic":
        return 100 / (1 + np.exp(10 * (val - scale)))


def handling_layout(layout):
    MarginAsymmetry = smooth_score(layout["MarginAsymmetry"], 0.5, "exp")
    ContentAspectDiff = smooth_score(layout["ContentAspectDiff"], 0.05, "exp")
    AreaRatioDiff = smooth_score(layout["AreaRatioDiff"], 0.05, "exp")
    return {
        "MarginAsymmetry": round(MarginAsymmetry, SAMPLE_DIGITS),
        "ContentAspectDiff": round(ContentAspectDiff, SAMPLE_DIGITS),
        "AreaRatioDiff": round(AreaRatioDiff, SAMPLE_DIGITS),
    }


def handling_legibility(legibility):
    TextJaccard = 100 * np.clip(legibility.get("TextJaccard", 0), 0, 1)
    ContrastDiff = np.clip(legibility.get("ContrastDiff", 0), 0, 5)
    ContrastLocalDiff = np.clip(legibility.get("ContrastLocalDiff", 0), 0, 5)
    ContrastDiff = 100 * (1 - ContrastDiff / 5.0)
    ContrastLocalDiff = 100 * (1 - ContrastLocalDiff / 5.0)
    return {
        "TextJaccard": round(TextJaccard, SAMPLE_DIGITS),
        "ContrastDiff": round(ContrastDiff, SAMPLE_DIGITS),
        "ContrastLocalDiff": round(ContrastLocalDiff, SAMPLE_DIGITS),
    }


def handling_style(style):
    return {
        "PaletteDistance": round(100 * style.get("PaletteDistance"), SAMPLE_DIGITS),
        "Vibrancy": round(100 * style.get("Vibrancy"), SAMPLE_DIGITS),
        "PolarityConsistency": round(100 * style.get("PolarityConsistency"), SAMPLE_DIGITS),
    }


def handling_perceptual(perceptual):
    ssim = np.clip(perceptual.get("SSIM", 0), 0, 1)
    lp = np.clip(perceptual.get("LPIPS", 0), 0, 1)
    return {
        "ssim": round(ssim, SAMPLE_DIGITS),
        "lp": round(lp, SAMPLE_DIGITS),
    }


def composite_score(geo, perceptual, layout, legibility, style):
    """Organize metrics with transformations. Returns hierarchical dict."""
    _zero = lambda keys: {k: 0.0 for k in keys}

    layout_score = handling_layout(layout) if layout else _zero(["MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff"])
    legibility_score = handling_legibility(legibility) if legibility else _zero(["TextJaccard", "ContrastDiff", "ContrastLocalDiff"])
    style_score = handling_style(style) if style else _zero(["PaletteDistance", "Vibrancy", "PolarityConsistency"])
    perceptual_score = handling_perceptual(perceptual) if perceptual else _zero(["ssim", "lp"])
    geo_score = 100 * np.clip(geo, 0, 1) if geo is not None else 0.0

    return {
        "LayoutScore": layout_score,
        "LegibilityScore": legibility_score,
        "StyleScore": style_score,
        "PerceptualScore": perceptual_score,
        "Geometry": {"geo_score": float(geo_score)},
    }
