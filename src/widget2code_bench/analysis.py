#!/usr/bin/env python3
"""
Generate metrics statistics from widget evaluation results.
Creates metrics_stats.json and metrics.xlsx summary files, plus per-mode
single-row xlsx files in raw/ black/ white/ zero/ subfolders.
"""

import json
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np


METRIC_CATEGORIES = {
    "LayoutScore": ["MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff"],
    "LegibilityScore": ["TextJaccard", "ContrastDiff", "ContrastLocalDiff"],
    "StyleScore": ["PaletteDistance", "Vibrancy", "PolarityConsistency"],
    "PerceptualScore": ["ssim", "lp"],
    "Geometry": ["geo_score"],
}

# Flat column order for per-mode single-row xlsx files.
FLAT_METRICS: List[str] = [
    "MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff",
    "TextJaccard", "ContrastDiff", "ContrastLocalDiff",
    "PaletteDistance", "Vibrancy", "PolarityConsistency",
    "ssim",
]
FLAT_COLUMNS: List[str] = (
    ["model"] + FLAT_METRICS + ["lp (LPIPS↓)", "Geometry", "SuccessRate"]
)

MODE_ORDER = ["raw", "black", "white", "zero"]
MODE_LABEL_SUFFIX = {
    "raw": "",
    "black": " (+ black fill)",
    "white": " (+ white fill)",
    "zero": " (+ zero fill)",
}


try:
    BENCH_VERSION = _pkg_version("widget2code-bench")
except PackageNotFoundError:
    BENCH_VERSION = "0.0.0"


def load_evaluation_data(results_dir: Path, filename: str = "evaluation.json") -> Dict[str, Dict]:
    """Load all evaluation JSON files from result directories.

    Looks in <sample>/evaluation/<filename> first, then falls back to
    <sample>/<filename> for backward compatibility with pre-0.2.7 layouts.
    """
    evaluation_data = {}

    for image_dir in sorted(results_dir.iterdir()):
        if not image_dir.is_dir():
            continue

        eval_file = image_dir / "evaluation" / filename
        if not eval_file.exists():
            eval_file = image_dir / filename
        if not eval_file.exists():
            continue

        with open(eval_file, 'r') as f:
            data = json.load(f)
            evaluation_data[image_dir.name] = data

    print(f"Loaded {len(evaluation_data)} {filename} files")
    return evaluation_data


def extract_metrics(eval_data: Dict) -> Dict[str, float]:
    """Extract all 12 metrics from evaluation data into a flat dictionary."""
    metrics = {}

    for category, metric_names in METRIC_CATEGORIES.items():
        category_data = eval_data.get(category, {})

        for metric_name in metric_names:
            metrics[metric_name] = category_data.get(metric_name, 0.0)

    return metrics


def calculate_statistics(evaluation_data: Dict[str, Dict]) -> pd.DataFrame:
    """Calculate statistics for all metrics across all images."""
    rows = []

    for image_id, eval_data in evaluation_data.items():
        metrics = extract_metrics(eval_data)
        metrics["image_id"] = image_id
        rows.append(metrics)

    df = pd.DataFrame(rows)
    return df


def _build_flat_row(run_name: str, mode_df: pd.DataFrame, success_ratio) -> Dict[str, object]:
    """Build a single flat row (dict) for a per-mode xlsx."""
    row: Dict[str, object] = {"model": run_name}
    for metric in FLAT_METRICS:
        row[metric] = round(mode_df[metric].mean(), 2)
    row["lp (LPIPS↓)"] = round(mode_df["lp"].mean(), 2)
    row["Geometry"] = round(mode_df["geo_score"].mean(), 2)
    row["SuccessRate"] = success_ratio if success_ratio is not None else ""
    return row


def _build_combined_row(run_name: str, mode: str, mode_df: pd.DataFrame,
                        sr_ratio, sr_count) -> List[object]:
    """Build a single data row for the combined 4-row metrics.xlsx."""
    label = f"{run_name}{MODE_LABEL_SUFFIX[mode]}"
    row: List[object] = [label]
    for category, metrics in METRIC_CATEGORIES.items():
        if category == "Geometry":
            row.append(round(mode_df['geo_score'].mean(), 2))
        else:
            for metric in metrics:
                row.append(round(mode_df[metric].mean(), 2))
    row.append(sr_ratio)
    row.append(sr_count)
    return row


def _build_combined_headers() -> Tuple[List[object], List[object]]:
    """Two-row header for the combined metrics.xlsx."""
    header_row1: List[object] = [None]
    header_row2: List[object] = [None]
    for category, metrics in METRIC_CATEGORIES.items():
        if category == "Geometry":
            header_row1.append('Geometry')
            header_row2.append(None)
        else:
            header_row1.append(category)
            header_row1.extend([None] * (len(metrics) - 1))
            header_row2.extend(metrics)
    header_row1.extend(['SuccessRate', None])
    header_row2.extend(['ratio', 'count'])
    return header_row1, header_row2


def save_statistics_files(df_raw: pd.DataFrame, mode_dfs: Dict[str, pd.DataFrame],
                          output_dir: Path, run_name: str,
                          sr_ratio, sr_count, success_ratio_str):
    """Save metrics_stats.json, per-mode split xlsx, and combined metrics.xlsx.

    Args:
        df_raw: per-image metrics for matched pairs only (drives stats_json)
        mode_dfs: dict of {mode: df} for each of raw/black/white/zero
        output_dir: destination directory
        run_name: run identifier (used in model column and filenames)
        sr_ratio: success rate as float percent (e.g. 99.30)
        sr_count: count string (e.g. "993/1000")
        success_ratio_str: combined success display for split xlsx (e.g. "99.30%")
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. metrics_stats.json (unchanged — quartiles/mean/std over matched pairs)
    all_metrics = []
    for metrics_list in METRIC_CATEGORIES.values():
        all_metrics.extend(metrics_list)

    metric_statistics = {}
    for metric_name in all_metrics:
        values = df_raw[metric_name].values
        metric_statistics[metric_name] = {
            "q1": float(np.percentile(values, 25)),
            "q2": float(np.percentile(values, 50)),
            "q3": float(np.percentile(values, 75)),
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
            "std": float(values.std()),
        }

    stats_file = output_dir / "metrics_stats.json"
    with open(stats_file, 'w') as f:
        json.dump({"total_images": len(df_raw), "metrics": metric_statistics}, f, indent=2)
    print(f"Saved metrics statistics to: {stats_file}")

    # 2. per-mode split xlsx (raw/black/white/zero), single-row flat header
    for mode in MODE_ORDER:
        if mode not in mode_dfs:
            continue
        sub_dir = output_dir / mode
        sub_dir.mkdir(parents=True, exist_ok=True)
        row = _build_flat_row(run_name, mode_dfs[mode], success_ratio_str)
        out_df = pd.DataFrame([row], columns=FLAT_COLUMNS)
        fname = f"{run_name}-{mode}-{BENCH_VERSION}.xlsx"
        out_df.to_excel(sub_dir / fname, index=False)
        print(f"Saved {mode} summary to: {sub_dir / fname}")

    # 3. combined metrics.xlsx (4 rows, two-level header)
    header_row1, header_row2 = _build_combined_headers()
    data_rows = []
    for mode in MODE_ORDER:
        if mode not in mode_dfs:
            continue
        data_rows.append(_build_combined_row(run_name, mode, mode_dfs[mode],
                                             sr_ratio, sr_count))

    combined_df = pd.DataFrame([header_row1, header_row2] + data_rows)
    combined_path = output_dir / "metrics.xlsx"
    combined_df.to_excel(combined_path, index=False, header=False)
    print(f"Saved combined metrics to: {combined_path}")


def generate_statistics(results_dir: str, output_dir: str) -> int:
    """Main entry point for statistics generation.

    Always produces raw/black/white/zero breakdowns.

    Args:
        results_dir: Path to pred directory containing <subfolder>/evaluation.json files
                     (and evaluation_black.json / evaluation_white.json for missing preds)
        output_dir: Path to output directory for statistics files

    Returns:
        0 on success, 1 on failure
    """
    results_dir = Path(results_dir)
    output_dir = Path(output_dir)

    if not results_dir.exists():
        print(f"Error: Results directory does not exist: {results_dir}")
        return 1

    print(f"Results Directory: {results_dir}")
    print(f"Output Directory:  {output_dir}")

    evaluation_data = load_evaluation_data(results_dir)

    if not evaluation_data:
        print("Error: No evaluation.json files found")
        return 1

    df_raw = calculate_statistics(evaluation_data)
    num_matched = len(df_raw)

    black_data = load_evaluation_data(results_dir, "evaluation_black.json")
    white_data = load_evaluation_data(results_dir, "evaluation_white.json")
    num_missing = max(len(black_data), len(white_data))

    df_black = df_raw
    if black_data:
        df_black_only = calculate_statistics(black_data)
        df_black = pd.concat([df_raw, df_black_only], ignore_index=True)

    df_white = df_raw
    if white_data:
        df_white_only = calculate_statistics(white_data)
        df_white = pd.concat([df_raw, df_white_only], ignore_index=True)

    # Zero-fill: missing preds contribute worst-case values
    # (higher-is-better metrics → 0; LPIPS lower-is-better → 1.0).
    if num_missing > 0:
        worst_rows = pd.DataFrame(0.0, index=range(num_missing), columns=df_raw.columns)
        if 'lp' in worst_rows.columns:
            worst_rows['lp'] = 1.0
        if 'image_id' in df_raw.columns:
            worst_rows['image_id'] = [f'zero_{i}' for i in range(num_missing)]
        df_zero = pd.concat([df_raw, worst_rows], ignore_index=True)
    else:
        df_zero = df_raw

    mode_dfs = {
        "raw": df_raw,
        "black": df_black,
        "white": df_white,
        "zero": df_zero,
    }

    total = num_matched + num_missing
    if total > 0:
        sr_ratio = round(num_matched / total * 100, 2)
        sr_count = f"{num_matched}/{total}"
        success_ratio_str = f"{sr_ratio:.2f}%"
        print(f"\nSuccess Rate: {num_matched}/{total} = {sr_ratio:.2f}%")
    else:
        sr_ratio = None
        sr_count = None
        success_ratio_str = None

    run_name = output_dir.parent.name

    save_statistics_files(df_raw, mode_dfs, output_dir, run_name,
                          sr_ratio, sr_count, success_ratio_str)

    print(f"\nSummary Statistics:")
    print(f"  Total matched pairs: {num_matched}")
    print(f"  Missing preds (fill-evaluated): {num_missing}")
    print(f"\n  Average Metrics (raw / matched only):")
    for category, metrics in METRIC_CATEGORIES.items():
        print(f"    {category}:")
        for metric in metrics:
            mean_val = df_raw[metric].mean()
            print(f"      {metric:20s}: {mean_val:6.2f}")

    print("\nStatistics generation complete!")
    return 0
