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
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    else:
        return obj


def _build_id_to_file_map(directory):
    """Scan a directory for files and extract 4-digit IDs from filenames.

    Returns a dict mapping 4-digit ID string -> filename.
    Raises ValueError if multiple files map to the same ID.
    """
    id_to_file = {}
    for name in os.listdir(directory):
        if not os.path.isfile(os.path.join(directory, name)):
            continue
        match = re.search(r'(\d{4})', name)
        if not match:
            continue
        four_digit_id = match.group(1)
        if four_digit_id in id_to_file:
            raise ValueError(
                f"Duplicate ID '{four_digit_id}' found in '{directory}': "
                f"files '{id_to_file[four_digit_id]}' and '{name}'"
            )
        id_to_file[four_digit_id] = name
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


def _evaluate_gt_pred(gt_img, pred_img):
    """Run all metrics on a GT/pred image pair. Returns result dict."""
    gen = resize_to_match(gt_img, pred_img)
    geo = compute_aspect_dimensionality_fidelity(gt_img, pred_img)
    perceptual = compute_perceptual(gt_img, gen)
    layout = compute_layout(gt_img, gen)
    legibility = compute_legibility(gt_img, gen)
    style = compute_style(gt_img, gen)
    return composite_score(geo, perceptual, layout, legibility, style)


def evaluate_single_pair(sample_id, gt_path, pred_path, pred_folder):
    """
    Evaluate a single GT-prediction pair.

    Args:
        sample_id: The 4-digit ID string
        gt_path: Full path to the GT image
        pred_path: Full path to the prediction image
        pred_folder: Folder containing the prediction (for saving evaluation.json)

    Returns (success, result_dict, error_message)
    """
    try:
        gt_img = load_image(gt_path)
        pred_img = load_image(pred_path)

        result = _evaluate_gt_pred(gt_img, pred_img)
        result["id"] = sample_id

        evaluation_path = os.path.join(pred_folder, "evaluation.json")
        with open(evaluation_path, 'w') as f:
            json.dump(convert_to_serializable(result), f, indent=2)

        return (True, result, None)

    except Exception as e:
        return (False, None, f"Error evaluating {sample_id}: {str(e)}")


def evaluate_single_pair_fill(sample_id, gt_path, pred_folder):
    """
    Evaluate a single GT image against black and white fill images.

    Saves evaluation_black.json and evaluation_white.json in pred_folder.

    Returns (success, black_result, white_result, error_message)
    """
    try:
        gt_img = load_image(gt_path)
        black_img = np.zeros_like(gt_img)
        white_img = np.ones_like(gt_img)

        black_result = _evaluate_gt_pred(gt_img, black_img)
        black_result["id"] = sample_id

        white_result = _evaluate_gt_pred(gt_img, white_img)
        white_result["id"] = sample_id

        os.makedirs(pred_folder, exist_ok=True)
        for fname, res in [("evaluation_black.json", black_result),
                           ("evaluation_white.json", white_result)]:
            with open(os.path.join(pred_folder, fname), 'w') as f:
                json.dump(convert_to_serializable(res), f, indent=2)

        return (True, black_result, white_result, None)

    except Exception as e:
        return (False, None, None, f"Error evaluating {sample_id} (fill): {str(e)}")


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
                avg[k][sk] = round(np.mean(sub_vals), 3)
        else:
            avg[k] = round(np.mean(vals), 3)
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
        return round((value * num_matched + worst * num_missing) / total, 3)

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
                data_row.append(round(cat_data.get(metric, 0), 3))
        else:
            for _ in metrics:
                data_row.append(0)

    geo_data = avg.get('Geometry', {})
    if isinstance(geo_data, dict):
        data_row.append(round(geo_data.get('geo_score', 0), 3))
    else:
        data_row.append(0)

    # Success rate columns
    data_row.append(success_ratio)
    data_row.append(success_count)

    return data_row


def evaluate_pairs(gt_dir="GT", pred_dir="baseline", num_workers=4,
                   pred_name="output.png", use_fill=True):
    """
    Load and evaluate GT-prediction pairs using multithreading.

    GT dir contains flat image files with 4-digit IDs in filenames (e.g. gt_0001.png).
    Pred dir contains subfolders with 4-digit IDs in names (e.g. image_0001/output.png).

    Args:
        gt_dir: Path to ground truth directory (flat files)
        pred_dir: Path to prediction directory (subfolders)
        num_workers: Number of worker threads (default: 4)
        pred_name: Prediction filename inside each subfolder (e.g. "output.png")
    """
    # Build ID maps: GT from flat files, pred from subfolders
    print("Scanning directories for 4-digit IDs...")
    gt_id_map = _build_id_to_file_map(gt_dir)
    pred_id_map = _build_id_to_folder_map(pred_dir)

    # Clean up old evaluation files
    print("Cleaning up old evaluation files...")
    cleaned_count = 0

    excel_path = os.path.join(pred_dir, "evaluation.xlsx")
    if os.path.exists(excel_path):
        os.remove(excel_path)
        cleaned_count += 1

    for folder_name in pred_id_map.values():
        eval_file = os.path.join(pred_dir, folder_name, "evaluation.json")
        if os.path.exists(eval_file):
            os.remove(eval_file)
            cleaned_count += 1

    if cleaned_count > 0:
        print(f"   Cleaned {cleaned_count} old evaluation files.\n")

    # Build task list by matching IDs
    gt_ids = sorted(gt_id_map.keys())
    total_gt = len(gt_ids)

    matched_tasks = []   # (sample_id, gt_path, pred_path, pred_folder)
    fill_tasks = []      # (sample_id, gt_path, pred_folder) — missing preds
    missing_pred = 0

    for sample_id in gt_ids:
        gt_path = os.path.join(gt_dir, gt_id_map[sample_id])
        if sample_id not in pred_id_map:
            if use_fill:
                pred_folder = os.path.join(pred_dir, f"fill_{sample_id}")
                fill_tasks.append((sample_id, gt_path, pred_folder))
            else:
                missing_pred += 1
            continue
        pred_folder = os.path.join(pred_dir, pred_id_map[sample_id])
        pred_path = os.path.join(pred_folder, pred_name)
        if not os.path.exists(pred_path):
            if use_fill:
                fill_tasks.append((sample_id, gt_path, pred_folder))
            else:
                missing_pred += 1
            continue
        matched_tasks.append((sample_id, gt_path, pred_path, pred_folder))

    total_matched = len(matched_tasks)
    total_fill = len(fill_tasks)
    total_tasks = total_matched + total_fill
    evaluated = 0
    errors = 0

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
            fut = executor.submit(evaluate_single_pair, sid, gp, pp, pf)
            future_to_info[fut] = ("matched", sid)

        for sid, gp, pf in fill_tasks:
            fut = executor.submit(evaluate_single_pair_fill, sid, gp, pf)
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
                    success, black_res, white_res, error_msg = future.result()
                    if success:
                        evaluated += 1
                        all_black_scores.append(black_res)
                        all_white_scores.append(white_res)
                        print(f"[{i}/{total_tasks}] {black_res['id']} evaluated (fill) -> "
                              f"Geo(black)={black_res['Geometry']['geo_score']:.2f} "
                              f"Geo(white)={white_res['Geometry']['geo_score']:.2f}")
                    else:
                        errors += 1
                        print(f"[{i}/{total_tasks}] Error: {error_msg}")

    num_matched = len(all_scores)
    # Missing = (real missing pred) + (fill tasks that weren't matched) — both are "no output"
    num_missing_total = missing_pred + total_fill
    success_rate = (num_matched / total_gt * 100) if total_gt > 0 else 0.0

    print(f"\nSummary:")
    print(f"  Total GT files: {total_gt}")
    print(f"  Matched (with output): {num_matched}")
    print(f"  Missing predictions: {num_missing_total}")
    if total_fill > 0:
        print(f"  Fill-evaluated (black/white): {len(all_black_scores)}")
    print(f"  Errors during evaluation: {errors}")
    print(f"  Successfully evaluated: {evaluated}")
    print(f"  Success rate: {num_matched}/{total_gt} = {success_rate:.2f}%")

    if all_scores:
        keys = ["LayoutScore", "LegibilityScore", "StyleScore", "PerceptualScore", "Geometry"]
        avg = _compute_avg(all_scores, keys)

        print("\nAverage metrics across all evaluated pairs:")
        _print_avg(avg)

        # Save average metrics to Excel
        run_name = os.path.basename(pred_dir)
        header_row1, header_row2 = _build_excel_headers()

        sr_ratio = round(success_rate, 2)
        sr_count = f"{num_matched}/{total_gt}"

        data_rows = [_build_excel_data_row(run_name, avg, sr_ratio, sr_count)]

        if all_black_scores:
            avg_black = _compute_avg(all_scores + all_black_scores, keys)
            data_rows.append(_build_excel_data_row(
                f"{run_name} (+ black fill)", avg_black, sr_ratio, sr_count))
            print("\nAverage metrics (with black fill for missing):")
            _print_avg(avg_black)

        if all_white_scores:
            avg_white = _compute_avg(all_scores + all_white_scores, keys)
            data_rows.append(_build_excel_data_row(
                f"{run_name} (+ white fill)", avg_white, sr_ratio, sr_count))
            print("\nAverage metrics (with white fill for missing):")
            _print_avg(avg_white)

        if num_missing_total > 0:
            avg_zero = _scale_avg_for_missing(avg, num_matched, num_missing_total)
            data_rows.append(_build_excel_data_row(
                f"{run_name} (+ zero fill)", avg_zero, sr_ratio, sr_count))
            print("\nAverage metrics (with zero fill for missing):")
            _print_avg(avg_zero)

        df = pd.DataFrame([header_row1, header_row2] + data_rows)

        excel_path = os.path.join(pred_dir, "evaluation.xlsx")
        df.to_excel(excel_path, index=False, header=False)

        print(f"\nAverage metrics saved to: {excel_path}")

    else:
        avg = {}
        print("No valid image pairs to evaluate.")

    return all_scores, avg
