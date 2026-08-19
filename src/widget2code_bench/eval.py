import hashlib
import os
import re
import json
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from widget_quality.utils import load_image, resize_to_match
from widget_quality.perceptual import compute_perceptual
from widget_quality.layout import compute_layout
from widget_quality.legibility import compute_legibility
from widget_quality.style import compute_style
from widget_quality.geometry import compute_aspect_dimensionality_fidelity
from widget_quality.composite import composite_score


def convert_to_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    else:
        return obj


GT_IMAGE_NAME = "image.png"


def _build_id_to_file_map(directory):
    """Map each 4-digit ground-truth id to its image, relative to `directory`.

    Ground truth is one directory per sample - `image_0001/image.png`, with
    `metadata.json` beside it - which is the layout the published dataset uses
    and the only one read here. A directory of loose PNGs is the older layout and
    is rejected by name rather than silently matching nothing, because "0 matched
    pairs" is a confusing way to learn that a path is out of date.

    Returns a dict mapping 4-digit ID string -> path relative to `directory`.
    """
    id_to_file = {}
    loose_images = 0

    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        match = re.search(r'(\d{4})', name)
        if not match:
            continue
        if os.path.isfile(path):
            loose_images += name.lower().endswith((".png", ".jpg", ".jpeg"))
            continue
        if not os.path.isfile(os.path.join(path, GT_IMAGE_NAME)):
            continue
        four_digit_id = match.group(1)
        if four_digit_id in id_to_file:
            raise ValueError(
                f"Duplicate ID '{four_digit_id}' found in '{directory}': "
                f"'{id_to_file[four_digit_id]}' and '{name}/{GT_IMAGE_NAME}'"
            )
        id_to_file[four_digit_id] = os.path.join(name, GT_IMAGE_NAME)

    if not id_to_file and loose_images:
        raise ValueError(
            f"'{directory}' holds {loose_images} loose images and no "
            f"<id>/{GT_IMAGE_NAME} directories. Ground truth is one directory "
            f"per sample; see the Widget2Code-Data dataset for the layout."
        )
    return id_to_file


def _build_id_to_folder_map(directory):
    """Scan a directory for subfolders and extract 4-digit IDs.

    Returns a dict mapping 4-digit ID string -> folder name.
    Raises ValueError if multiple folders map to the same ID.
    """
    id_to_folder = {}
    for name in os.listdir(directory):
        if not os.path.isdir(os.path.join(directory, name)):
            continue
        match = re.search(r'(\d{4})', name)
        if not match:
            continue
        four_digit_id = match.group(1)
        if four_digit_id in id_to_folder:
            raise ValueError(
                f"Duplicate ID '{four_digit_id}' found in '{directory}': "
                f"folders '{id_to_folder[four_digit_id]}' and '{name}'"
            )
        id_to_folder[four_digit_id] = name
    return id_to_folder


def _evaluate_gt_pred(gt_img, pred_img, return_ocr=False):
    """Run all metrics on a GT/pred image pair. Returns composite result dict.

    If ``return_ocr=True``, also returns (ocr_gt, ocr_gen) as a tuple:
        (result_dict, ocr_gt, ocr_gen)
    """
    gen = resize_to_match(gt_img, pred_img)
    geo = compute_aspect_dimensionality_fidelity(gt_img, pred_img)
    perceptual = compute_perceptual(gt_img, gen)
    layout = compute_layout(gt_img, gen)
    if return_ocr:
        legibility, ocr_gt, ocr_gen = compute_legibility(gt_img, gen, return_ocr=True)
    else:
        legibility = compute_legibility(gt_img, gen)
    style = compute_style(gt_img, gen)
    result = composite_score(geo, perceptual, layout, legibility, style)
    if return_ocr:
        return result, ocr_gt, ocr_gen
    return result


def evaluate_single_pair(sample_id, gt_path, pred_path):
    """Score one GT/prediction pair.

    Nothing is written here. The prediction directory is an input, and 0.2.9
    treating it as scratch space is what made two runs over the same predictions
    overwrite each other. The caller collects results and hands them to
    `report.write_run`.

    Returns (success, result_dict, error_message)
    """
    try:
        result = _evaluate_gt_pred(load_image(gt_path), load_image(pred_path))
        result["id"] = sample_id
        return (True, convert_to_serializable(result), None)

    except Exception as e:
        return (False, None, f"Error evaluating {sample_id}: {str(e)}")


def _fill_from_metadata(gt_path):
    """Rebuild the black/white fill scores from `metadata.json` beside the GT.

    The published dataset ships the GT-only half of the evaluation precomputed
    (see tools/build_metadata.py); the fill scores depend on the ground truth
    alone, so they can be read instead of recomputed. The stored values are the
    raw metric outputs, so feeding them back through `composite_score` yields
    exactly what a fresh evaluation would - the same code path, minus the
    images. The record carries the image's sha256; on any mismatch, absence, or
    unexpected shape this returns None and the caller computes from scratch,
    because a stale cache must never be scored against.

    Returns (black_result, white_result) or None.
    """
    meta_path = os.path.join(os.path.dirname(gt_path), "metadata.json")
    try:
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        with open(gt_path, "rb") as fh:
            if meta.get("sha256") != hashlib.sha256(fh.read()).hexdigest():
                return None
        results = []
        for mode in ("black", "white"):
            f = meta["eval"]["fill"][mode]
            results.append(composite_score(f["geo"], f["perceptual"], f["layout"],
                                           f["legibility"], f["style"]))
        return tuple(results)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def evaluate_single_pair_fill(sample_id, gt_path):
    """Score a ground truth with no prediction against an all-black and an
    all-white image, so the summary can show what different assumptions about a
    failure do to the aggregate. Both depend on the ground truth alone, so a
    dataset that ships them precomputed in `metadata.json` is read instead of
    recomputed - validated by the image's sha256.

    Returns (success, black_result, white_result, from_metadata, error_message)
    """
    try:
        cached = _fill_from_metadata(gt_path)
        if cached is not None:
            black_result, white_result = (dict(r) for r in cached)
        else:
            gt_img = load_image(gt_path)
            black_result = _evaluate_gt_pred(gt_img, np.zeros_like(gt_img))
            white_result = _evaluate_gt_pred(gt_img, np.ones_like(gt_img))
        black_result["id"] = sample_id
        white_result["id"] = sample_id

        return (True, convert_to_serializable(black_result),
                convert_to_serializable(white_result), cached is not None, None)

    except Exception as e:
        return (False, None, None, False,
                f"Error evaluating {sample_id} (fill): {str(e)}")


def _compute_avg(scores, keys):
    """Compute average metrics from a list of score dicts."""
    avg = {}
    for k in keys:
        vals = [s[k] for s in scores if k in s]
        if not vals:
            continue
        if isinstance(vals[0], dict):
            avg[k] = {}
            for sk in vals[0].keys():
                sub_vals = [v[sk] for v in vals if sk in v]
                avg[k][sk] = round(np.mean(sub_vals), 2)
        else:
            avg[k] = round(np.mean(vals), 2)
    return avg


# Worst-case fill values for missing samples (per sub-metric name).
# Most metrics are "higher is better" -> worst = 0. LPIPS (lp) is "lower is better" -> worst = 1.0.
MISSING_WORST_VALUES = {"lp": 1.0}


def _scale_avg_for_missing(avg, num_matched, num_missing):
    """Adjust avg as if num_missing extra samples contributed the worst-case value.

    Missing samples contribute MISSING_WORST_VALUES[metric] (default 0) for each metric.
    """
    total = num_matched + num_missing
    if total == 0 or num_missing == 0:
        return avg

    def _adjust(sub_key, value):
        worst = MISSING_WORST_VALUES.get(sub_key, 0.0)
        return round((value * num_matched + worst * num_missing) / total, 2)

    scaled = {}
    for k, v in avg.items():
        if isinstance(v, dict):
            scaled[k] = {sk: _adjust(sk, sv) for sk, sv in v.items()}
        else:
            scaled[k] = _adjust(k, v)
    return scaled


def _print_avg(avg):
    """Print average metrics."""
    for k, v in avg.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for sk, sv in v.items():
                print(f"    {sk:16s}: {sv:6.3f}")
        else:
            print(f"  {k:18s}: {v:6.3f}")


def _build_excel_headers():
    """Build the two header rows for the evaluation Excel."""
    header_row1 = [None]
    header_row2 = [None]

    for category, metrics in [
        ('LayoutScore', ['MarginAsymmetry', 'ContentAspectDiff', 'AreaRatioDiff']),
        ('LegibilityScore', ['TextJaccard', 'ContrastDiff', 'ContrastLocalDiff']),
        ('StyleScore', ['PaletteDistance', 'Vibrancy', 'PolarityConsistency']),
        ('PerceptualScore', ['ssim', 'lp']),
    ]:
        header_row1.append(category)
        header_row1.extend([None] * (len(metrics) - 1))
        header_row2.extend(metrics)

    header_row1.append('Geometry')
    header_row2.append(None)

    # Success rate columns (after Geometry)
    header_row1.extend(['SuccessRate', None])
    header_row2.extend(['ratio', 'count'])

    return header_row1, header_row2


def _build_excel_data_row(run_name, avg, success_ratio=None, success_count=None):
    """Build a single data row for the evaluation Excel.

    Args:
        success_ratio: Success rate as percentage (e.g. 99.30)
        success_count: Count string like "993/1000"
    """
    data_row = [run_name]

    for category, metrics in [
        ('LayoutScore', ['MarginAsymmetry', 'ContentAspectDiff', 'AreaRatioDiff']),
        ('LegibilityScore', ['TextJaccard', 'ContrastDiff', 'ContrastLocalDiff']),
        ('StyleScore', ['PaletteDistance', 'Vibrancy', 'PolarityConsistency']),
        ('PerceptualScore', ['ssim', 'lp']),
    ]:
        cat_data = avg.get(category, {})
        if isinstance(cat_data, dict):
            for metric in metrics:
                data_row.append(round(cat_data.get(metric, 0), 2))
        else:
            for _ in metrics:
                data_row.append(0)

    geo_data = avg.get('Geometry', {})
    if isinstance(geo_data, dict):
        data_row.append(round(geo_data.get('geo_score', 0), 2))
    else:
        data_row.append(0)

    # Success rate columns
    data_row.append(success_ratio)
    data_row.append(success_count)

    return data_row


def evaluate_pairs(gt_dir="GT", pred_dir="baseline", num_workers=4,
                   pred_name="output.png"):
    """
    Load and evaluate GT-prediction pairs using multithreading.

    GT dir holds one directory per sample - `image_0001/image.png`, with
    `metadata.json` beside it - the layout of the published dataset.
    Pred dir holds subfolders with 4-digit IDs in their names, each containing
    the file named by `pred_name` (a path relative to the subfolder is fine,
    e.g. "sft_render/rendered.png").

    Args:
        gt_dir: Path to ground truth directory (one subdirectory per sample)
        pred_dir: Path to prediction directory (subfolders)
        num_workers: Number of worker threads (default: 4)
        pred_name: Prediction filename inside each subfolder (e.g. "output.png")
    """
    # Build ID maps: GT from flat files, pred from subfolders
    print("Scanning directories for 4-digit IDs...")
    gt_id_map = _build_id_to_file_map(gt_dir)
    pred_id_map = _build_id_to_folder_map(pred_dir)

    # Build task list by matching IDs
    gt_ids = sorted(gt_id_map.keys())
    total_gt = len(gt_ids)

    matched_tasks = []   # (sample_id, gt_path, pred_path, pred_folder)
    fill_tasks = []      # (sample_id, gt_path, pred_folder) — missing preds

    for sample_id in gt_ids:
        gt_path = os.path.join(gt_dir, gt_id_map[sample_id])
        if sample_id not in pred_id_map:
            pred_folder = os.path.join(pred_dir, f"fill_{sample_id}")
            fill_tasks.append((sample_id, gt_path, pred_folder))
            continue
        pred_folder = os.path.join(pred_dir, pred_id_map[sample_id])
        pred_path = os.path.join(pred_folder, pred_name)
        if not os.path.exists(pred_path):
            fill_tasks.append((sample_id, gt_path, pred_folder))
            continue
        matched_tasks.append((sample_id, gt_path, pred_path, pred_folder))

    total_matched = len(matched_tasks)
    total_fill = len(fill_tasks)
    total_tasks = total_matched + total_fill
    evaluated = 0
    errors = 0
    fills_from_metadata = 0

    all_scores = []
    all_black_scores = []
    all_white_scores = []
    lock = Lock()

    print(f"Found {total_gt} GT files, {len(pred_id_map)} pred folders, {total_matched} matched pairs.")
    if total_fill > 0:
        print(f"  ({total_fill} missing predictions will be evaluated with black/white fill)")
    print(f"Using {num_workers} worker threads for parallel processing.\n")

    task_counter = [0]  # mutable counter for progress

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}

        for sid, gp, pp, pf in matched_tasks:
            fut = executor.submit(evaluate_single_pair, sid, gp, pp)
            future_to_info[fut] = ("matched", sid)

        for sid, gp, pf in fill_tasks:
            fut = executor.submit(evaluate_single_pair_fill, sid, gp)
            future_to_info[fut] = ("fill", sid)

        for future in as_completed(future_to_info):
            kind, sample_id = future_to_info[future]

            with lock:
                task_counter[0] += 1
                i = task_counter[0]

                if kind == "matched":
                    success, result, error_msg = future.result()
                    if success:
                        evaluated += 1
                        all_scores.append(result)
                        print(f"[{i}/{total_tasks}] {result['id']} evaluated -> "
                              f"Geo={result['Geometry']['geo_score']:.2f}")
                    else:
                        errors += 1
                        print(f"[{i}/{total_tasks}] Error: {error_msg}")
                else:
                    success, black_res, white_res, from_meta, error_msg = future.result()
                    if success:
                        evaluated += 1
                        fills_from_metadata += from_meta
                        all_black_scores.append(black_res)
                        all_white_scores.append(white_res)
                        source = "metadata" if from_meta else "computed"
                        print(f"[{i}/{total_tasks}] {black_res['id']} evaluated (fill, {source}) -> "
                              f"Geo(black)={black_res['Geometry']['geo_score']:.2f} "
                              f"Geo(white)={white_res['Geometry']['geo_score']:.2f}")
                    else:
                        errors += 1
                        print(f"[{i}/{total_tasks}] Error: {error_msg}")

    num_matched = len(all_scores)
    num_missing_total = total_fill
    success_rate = (num_matched / total_gt * 100) if total_gt > 0 else 0.0

    print(f"\nSummary:")
    print(f"  Total GT files: {total_gt}")
    print(f"  Matched (with output): {num_matched}")
    print(f"  Missing predictions: {num_missing_total}")
    if total_fill > 0:
        print(f"  Fill-evaluated (black/white): {len(all_black_scores)} "
              f"({fills_from_metadata} read from metadata.json)")
    print(f"  Errors during evaluation: {errors}")
    print(f"  Successfully evaluated: {evaluated}")
    print(f"  Success rate: {num_matched}/{total_gt} = {success_rate:.2f}%")

    return {
        "matched": all_scores,
        "black": all_black_scores,
        "white": all_white_scores,
        "total_gt": total_gt,
        "errors": errors,
    }
