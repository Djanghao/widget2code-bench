"""High-level evaluation API."""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from .composite import composite_score
from .geometry import compute_aspect_dimensionality_fidelity
from .layout import compute_layout
from .legibility import compute_legibility
from .perceptual import compute_perceptual
from .style import compute_style
from .utils import load_image, resize_to_match


def evaluate_pair(gt_path, gen_path):
    """
    Evaluate a single GT / generated image pair.

    Args:
        gt_path: Path to ground truth image.
        gen_path: Path to generated image.

    Returns:
        dict with all metrics (raw + transformed composite scores).
    """
    gt = load_image(gt_path)
    gen = load_image(gen_path)

    geo = compute_aspect_dimensionality_fidelity(gt, gen)
    gen_resized = resize_to_match(gt, gen)

    layout = compute_layout(gt, gen_resized)
    legibility = compute_legibility(gt, gen_resized)
    perceptual = compute_perceptual(gt, gen_resized)
    style = compute_style(gt, gen_resized)

    scores = composite_score(geo, perceptual, layout, legibility, style)
    return scores


def evaluate_dir(gt_dir, pred_dir, workers=4, gt_pattern="gt_{id}.png",
                 pred_patterns=None, output_json=True):
    """
    Evaluate all GT-prediction pairs in directories.

    Args:
        gt_dir: Directory containing ground truth images.
        pred_dir: Directory containing prediction subdirectories or images.
        workers: Number of parallel workers.
        gt_pattern: GT filename pattern. Use {id} as placeholder.
        pred_patterns: List of possible prediction file patterns to try
            within each subdirectory. Defaults to common patterns.
        output_json: If True, write evaluation.json in each pred subfolder.

    Returns:
        dict mapping sample id to evaluation results.
    """
    gt_dir = Path(gt_dir)
    pred_dir = Path(pred_dir)

    if pred_patterns is None:
        pred_patterns = ["output.png", "pred.png", "generated.png"]

    # Discover pairs
    pairs = []
    for gt_file in sorted(gt_dir.glob("*.png")):
        # Extract numeric id from GT filename
        stem = gt_file.stem
        # Try to extract id: gt_0001 -> 0001, or just use stem
        parts = stem.split("_", 1)
        sample_id = parts[1] if len(parts) > 1 else parts[0]

        # Find matching prediction
        pred_path = None
        # Try subdirectory patterns
        for subdir_prefix in [f"image_{sample_id}", sample_id]:
            subdir = pred_dir / subdir_prefix
            if subdir.is_dir():
                for pat in pred_patterns:
                    candidate = subdir / pat
                    if candidate.exists():
                        pred_path = candidate
                        break
            if pred_path:
                break

        # Try flat file patterns
        if pred_path is None:
            for pat in pred_patterns:
                candidate = pred_dir / pat.replace("output", f"pred_{sample_id}")
                if candidate.exists():
                    pred_path = candidate
                    break

        if pred_path:
            pairs.append((sample_id, gt_file, pred_path))

    results = {}

    def _eval_one(sample_id, gt_path, gen_path):
        scores = evaluate_pair(str(gt_path), str(gen_path))
        if output_json:
            out_path = gen_path.parent / "evaluation.json"
            with open(out_path, "w") as f:
                json.dump(scores, f, indent=2)
        return sample_id, scores

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_eval_one, sid, gp, pp): sid
            for sid, gp, pp in pairs
        }
        for fut in as_completed(futures):
            sid, scores = fut.result()
            results[sid] = scores

    return results
