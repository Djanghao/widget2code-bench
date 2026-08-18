"""Selective, side-effect-free evaluation of one image pair.

The batch evaluator remains the compatibility path for published tables.  This
module is the low-latency path used by training reward workers: callers can ask
for only the metric groups or leaves they need, so an SSIM-only request does not
load LPIPS and a contrast-only request does not load EasyOCR.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from widget2code_bench.eval import convert_to_serializable
from widget_quality.composite import composite_score
from widget_quality.geometry import compute_aspect_dimensionality_fidelity
from widget_quality.utils import load_image, resize_to_match


GROUP_OUTPUTS = {
    "geometry": ("Geometry", {"geo_score"}),
    "perceptual": ("PerceptualScore", {"ssim", "lp"}),
    "layout": (
        "LayoutScore",
        {"MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff"},
    ),
    "legibility": (
        "LegibilityScore",
        {"TextJaccard", "ContrastDiff", "ContrastLocalDiff"},
    ),
    "style": (
        "StyleScore",
        {"PaletteDistance", "Vibrancy", "PolarityConsistency"},
    ),
}

ALIASES = {
    "geo": ("geometry", "geo_score"),
    "geo_score": ("geometry", "geo_score"),
    "ssim": ("perceptual", "ssim"),
    "lp": ("perceptual", "lp"),
    "lpips": ("perceptual", "lp"),
    "margin": ("layout", "MarginAsymmetry"),
    "margin_asymmetry": ("layout", "MarginAsymmetry"),
    "content_aspect": ("layout", "ContentAspectDiff"),
    "content_aspect_diff": ("layout", "ContentAspectDiff"),
    "area_ratio": ("layout", "AreaRatioDiff"),
    "area_ratio_diff": ("layout", "AreaRatioDiff"),
    "text": ("legibility", "TextJaccard"),
    "text_jaccard": ("legibility", "TextJaccard"),
    "contrast": ("legibility", "ContrastDiff"),
    "contrast_diff": ("legibility", "ContrastDiff"),
    "contrast_local": ("legibility", "ContrastLocalDiff"),
    "contrast_local_diff": ("legibility", "ContrastLocalDiff"),
    "palette": ("style", "PaletteDistance"),
    "palette_distance": ("style", "PaletteDistance"),
    "vibrancy": ("style", "Vibrancy"),
    "polarity": ("style", "PolarityConsistency"),
    "polarity_consistency": ("style", "PolarityConsistency"),
}

_OCR_DEVICE: bool | None = None


def _normalise(token: str) -> str:
    return token.strip().lower().replace("-", "_")


def parse_metric_selection(spec: str | None) -> dict[str, set[str] | None]:
    """Parse comma-separated groups/leaves into a computation selection.

    A group maps to ``None`` (return every leaf); a leaf selection maps to the
    exact output leaves requested.  ``None``, an empty string, and ``all`` all
    select the complete 0.2.9 metric set.
    """
    if not spec or _normalise(spec) == "all":
        return {group: None for group in GROUP_OUTPUTS}

    selected: dict[str, set[str] | None] = {}
    for raw in spec.split(","):
        token = _normalise(raw)
        if not token:
            continue
        if token == "all":
            return {group: None for group in GROUP_OUTPUTS}
        if token in GROUP_OUTPUTS:
            selected[token] = None
            continue
        try:
            group, leaf = ALIASES[token]
        except KeyError as exc:
            choices = ", ".join(sorted({*GROUP_OUTPUTS, *ALIASES, "all"}))
            raise ValueError(f"unknown metric '{raw.strip()}'; choose from: {choices}") from exc
        if group not in selected:
            selected[group] = set()
        if selected[group] is not None:
            selected[group].add(leaf)

    if not selected:
        raise ValueError("--metrics must contain at least one metric")
    return selected


def _filter_result(
    result: dict, selection: dict[str, set[str] | None]
) -> dict:
    filtered = {}
    for group, leaves in selection.items():
        output_group, _ = GROUP_OUTPUTS[group]
        values = result[output_group]
        filtered[output_group] = values if leaves is None else {
            key: values[key] for key in values if key in leaves
        }
    return filtered


def evaluate_single(
    gt_path: str | Path,
    pred_path: str | Path,
    *,
    metrics: str | None = None,
    use_cuda: bool = False,
) -> dict:
    """Evaluate one pair and return only the selected 0.2.9-compatible values."""
    selection = parse_metric_selection(metrics)
    gt = load_image(str(gt_path))
    pred = load_image(str(pred_path))
    gen = None if set(selection) == {"geometry"} else resize_to_match(gt, pred)

    geo = perceptual = layout = legibility = style = None

    if "geometry" in selection:
        geo = compute_aspect_dimensionality_fidelity(gt, pred)

    if "perceptual" in selection:
        from widget_quality import perceptual as perceptual_module

        leaves = selection["perceptual"]
        perceptual = {}
        if leaves is None or "ssim" in leaves:
            perceptual["SSIM"] = perceptual_module.compute_ssim(gt, gen)
        if leaves is None or "lp" in leaves:
            perceptual_module.set_device(use_cuda=use_cuda)
            perceptual["LPIPS"] = perceptual_module.compute_lpips(gt, gen)

    if "layout" in selection:
        from widget_quality.layout import compute_layout

        layout = compute_layout(gt, gen)

    if "legibility" in selection:
        from widget_quality import legibility as legibility_module

        leaves = selection["legibility"]
        if leaves == {"ContrastDiff"}:
            gt_contrast = np.nan_to_num(legibility_module.contrast_ratio(gt))
            gen_contrast = np.nan_to_num(legibility_module.contrast_ratio(gen))
            legibility = {
                "ContrastDiff": float(np.clip(abs(gt_contrast - gen_contrast), 0, 5))
            }
        else:
            import easyocr

            global _OCR_DEVICE
            if legibility_module._reader is None or _OCR_DEVICE != use_cuda:
                legibility_module._reader = easyocr.Reader(["en"], gpu=use_cuda)
                _OCR_DEVICE = use_cuda
            legibility = legibility_module.compute_legibility(gt, gen)

    if "style" in selection:
        from widget_quality.style import compute_style

        style = compute_style(gt, gen)

    result = composite_score(geo, perceptual, layout, legibility, style)
    return convert_to_serializable(_filter_result(result, selection))
