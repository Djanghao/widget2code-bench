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
        gen = resize_to_match(gt_img, pred_img)

        geo = compute_aspect_dimensionality_fidelity(gt_img, pred_img)
        perceptual = compute_perceptual(gt_img, gen)
        layout = compute_layout(gt_img, gen)
        legibility = compute_legibility(gt_img, gen)
        style = compute_style(gt_img, gen)

        result = composite_score(geo, perceptual, layout, legibility, style)
        result["id"] = sample_id

        evaluation_path = os.path.join(pred_folder, "evaluation.json")
        with open(evaluation_path, 'w') as f:
            json.dump(convert_to_serializable(result), f, indent=2)

        return (True, result, None)

    except Exception as e:
        return (False, None, f"Error evaluating {sample_id}: {str(e)}")


def evaluate_pairs(gt_dir="GT", pred_dir="baseline", num_workers=4,
                   pred_name="output.png"):
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

    tasks = []
    missing_pred = 0
    for sample_id in gt_ids:
        gt_path = os.path.join(gt_dir, gt_id_map[sample_id])
        if sample_id not in pred_id_map:
            missing_pred += 1
            continue
        pred_folder = os.path.join(pred_dir, pred_id_map[sample_id])
        pred_path = os.path.join(pred_folder, pred_name)
        if not os.path.exists(pred_path):
            missing_pred += 1
            continue
        tasks.append((sample_id, gt_path, pred_path, pred_folder))

    total_tasks = len(tasks)
    evaluated = 0
    errors = 0

    all_scores = []
    lock = Lock()

    print(f"Found {total_gt} GT files, {len(pred_id_map)} pred folders, {total_tasks} matched pairs.")
    print(f"Using {num_workers} worker threads for parallel processing.\n")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_id = {
            executor.submit(evaluate_single_pair, sid, gp, pp, pf): (i, sid)
            for i, (sid, gp, pp, pf) in enumerate(tasks, start=1)
        }

        for future in as_completed(future_to_id):
            i, sample_id = future_to_id[future]
            success, result, error_msg = future.result()

            with lock:
                if success:
                    evaluated += 1
                    all_scores.append(result)

                    print(f"[{i}/{total_tasks}] {result['id']} evaluated -> "
                          f"Geo={result['Geometry']['geo_score']:.2f}")
                else:
                    errors += 1
                    print(f"[{i}/{total_tasks}] Error: {error_msg}")

    print(f"\nSummary:")
    print(f"  Total GT files: {total_gt}")
    print(f"  Missing predictions: {missing_pred}")
    print(f"  Errors during evaluation: {errors}")
    print(f"  Successfully evaluated: {evaluated}")

    if all_scores:
        keys = ["LayoutScore", "LegibilityScore", "StyleScore", "PerceptualScore", "Geometry"]
        avg = {}

        for k in keys:
            vals = [s[k] for s in all_scores if k in s]

            if isinstance(vals[0], dict):
                sub_keys = vals[0].keys()
                avg[k] = {}
                for sk in sub_keys:
                    sub_vals = [v[sk] for v in vals if sk in v]
                    avg[k][sk] = round(np.mean(sub_vals), 3)
            else:
                avg[k] = round(np.mean(vals), 3)

        print("\nAverage metrics across all evaluated pairs:")
        for k, v in avg.items():
            if isinstance(v, dict):
                print(f"  {k}:")
                for sk, sv in v.items():
                    print(f"    {sk:16s}: {sv:6.3f}")
            else:
                print(f"  {k:18s}: {v:6.3f}")

        # Save average metrics to Excel
        header_row1 = [None]
        header_row2 = [None]
        data_row = []

        run_name = os.path.basename(pred_dir)
        data_row.append(run_name)

        if 'LayoutScore' in avg and isinstance(avg['LayoutScore'], dict):
            layout_metrics = ['MarginAsymmetry', 'ContentAspectDiff', 'AreaRatioDiff']
            header_row1.append('LayoutScore')
            header_row1.extend([None] * (len(layout_metrics) - 1))
            for metric in layout_metrics:
                header_row2.append(metric)
                data_row.append(round(avg['LayoutScore'].get(metric, 0), 3))

        if 'LegibilityScore' in avg and isinstance(avg['LegibilityScore'], dict):
            legibility_metrics = ['TextJaccard', 'ContrastDiff', 'ContrastLocalDiff']
            header_row1.append('LegibilityScore')
            header_row1.extend([None] * (len(legibility_metrics) - 1))
            for metric in legibility_metrics:
                header_row2.append(metric)
                data_row.append(round(avg['LegibilityScore'].get(metric, 0), 3))

        if 'StyleScore' in avg and isinstance(avg['StyleScore'], dict):
            style_metrics = ['PaletteDistance', 'Vibrancy', 'PolarityConsistency']
            header_row1.append('StyleScore')
            header_row1.extend([None] * (len(style_metrics) - 1))
            for metric in style_metrics:
                header_row2.append(metric)
                data_row.append(round(avg['StyleScore'].get(metric, 0), 3))

        if 'PerceptualScore' in avg and isinstance(avg['PerceptualScore'], dict):
            perceptual_metrics = ['ssim', 'lp']
            header_row1.append('PerceptualScore')
            header_row1.extend([None] * (len(perceptual_metrics) - 1))
            for metric in perceptual_metrics:
                header_row2.append(metric)
                data_row.append(round(avg['PerceptualScore'].get(metric, 0), 3))

        if 'Geometry' in avg and isinstance(avg['Geometry'], dict):
            header_row1.append('Geometry')
            header_row2.append(None)
            data_row.append(round(avg['Geometry']['geo_score'], 3))

        df = pd.DataFrame([header_row1, header_row2, data_row])

        excel_path = os.path.join(pred_dir, "evaluation.xlsx")
        df.to_excel(excel_path, index=False, header=False)

        print(f"\nAverage metrics saved to: {excel_path}")

    else:
        avg = {}
        print("No valid image pairs to evaluate.")

    return all_scores, avg
