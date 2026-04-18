#!/usr/bin/env python3
"""
Generate metrics statistics from widget evaluation results.
Creates metrics_stats.json and metrics.xlsx summary files.
"""

import json
from pathlib import Path
from typing import Dict
import pandas as pd
import numpy as np


METRIC_CATEGORIES = {
    "LayoutScore": ["MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff"],
    "LegibilityScore": ["TextJaccard", "ContrastDiff", "ContrastLocalDiff"],
    "StyleScore": ["PaletteDistance", "Vibrancy", "PolarityConsistency"],
    "PerceptualScore": ["ssim", "lp"],
    "Geometry": ["geo_score"],
}


def load_evaluation_data(results_dir: Path, filename: str = "evaluation.json") -> Dict[str, Dict]:
    """Load all evaluation JSON files from result directories.

    Supports two directory structures:
      - image_{num}/evaluation.json  (old structure)
      - {num}/evaluation.json        (new structure)

    Args:
        results_dir: Path to results directory
        filename: Name of the evaluation JSON file to load
    """
    evaluation_data = {}

    for image_dir in sorted(results_dir.iterdir()):
        if not image_dir.is_dir():
            continue

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


def _build_metrics_data_row(run_name: str, df: pd.DataFrame,
                             success_ratio=None) -> list:
    """Build a single data row from a DataFrame of per-image metrics."""
    data_row = [run_name]
    for category, metrics in METRIC_CATEGORIES.items():
        if category == "Geometry":
            data_row.append(round(df['geo_score'].mean(), 3))
        else:
            for metric in metrics:
                data_row.append(round(df[metric].mean(), 3))
    data_row.append(success_ratio)
    return data_row


def _build_combined_row(run_name: str, mode_dfs: list,
                        success_ratio=None) -> list:
    """Build a single row combining multiple fill modes with slash-joined values.

    mode_dfs: list of (mode_label, df) tuples in desired order
              e.g. [("raw", df), ("black", df_black), ("white", df_white), ("zero", df_zero)]
    """
    if len(mode_dfs) == 1:
        data_row = [run_name]
    else:
        mode_labels = "/".join(label for label, _ in mode_dfs)
        data_row = [f"{run_name}:{mode_labels}"]

    def join_vals(metric):
        vals = [round(mdf[metric].mean(), 3) for _, mdf in mode_dfs]
        return vals[0] if len(vals) == 1 else "/".join(str(v) for v in vals)

    for category, metrics in METRIC_CATEGORIES.items():
        if category == "Geometry":
            data_row.append(join_vals('geo_score'))
        else:
            for metric in metrics:
                data_row.append(join_vals(metric))

    data_row.append(success_ratio)
    return data_row


def save_statistics_files(df: pd.DataFrame, output_dir: Path,
                          extra_dfs: dict = None,
                          success_ratio=None):
    """Save metrics_stats.json and metrics.xlsx files.

    Args:
        df: DataFrame of per-image metrics (matched pairs only)
        output_dir: Output directory
        extra_dfs: Optional dict of {"label_suffix": DataFrame} for additional rows
                   (e.g. {"+ black fill": df_with_black, "+ white fill": df_with_white})
        success_ratio: Success rate as percentage string (e.g. "99.3%")
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_metrics = []
    for metrics_list in METRIC_CATEGORIES.values():
        all_metrics.extend(metrics_list)

    # 1. Save metrics_stats.json
    stats_file = output_dir / "metrics_stats.json"

    metric_statistics = {}
    for metric_name in all_metrics:
        values = df[metric_name].values
        metric_statistics[metric_name] = {
            "q1": float(np.percentile(values, 25)),
            "q2": float(np.percentile(values, 50)),
            "q3": float(np.percentile(values, 75)),
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
            "std": float(values.std()),
        }

    stats_json = {
        "total_images": len(df),
        "metrics": metric_statistics
    }

    with open(stats_file, 'w') as f:
        json.dump(stats_json, f, indent=2)

    print(f"Saved metrics statistics to: {stats_file}")

    # 2. Save metrics.xlsx
    metrics_xlsx = output_dir / "metrics.xlsx"
    run_name = output_dir.parent.name

    header_row1 = [None]
    header_row2 = [None]
    for category, metrics in METRIC_CATEGORIES.items():
        if category == "Geometry":
            header_row1.append('Geometry')
            header_row2.append(None)
        else:
            header_row1.append(category)
            header_row1.extend([None] * (len(metrics) - 1))
            header_row2.extend(metrics)

    header_row1.append('SuccessRate')
    header_row2.append(None)

    label_map = {"+ black fill": "black", "+ white fill": "white", "+ zero fill": "zero"}
    mode_dfs = [("raw", df)]
    if extra_dfs:
        for label_suffix, extra_df in extra_dfs.items():
            mode_dfs.append((label_map.get(label_suffix, label_suffix), extra_df))

    data_rows = [_build_combined_row(run_name, mode_dfs, success_ratio)]

    metrics_df = pd.DataFrame([header_row1, header_row2] + data_rows)
    metrics_df.to_excel(metrics_xlsx, index=False, header=False)

    print(f"Saved metrics summary to: {metrics_xlsx}")


def generate_statistics(results_dir: str, output_dir: str,
                        use_fill: bool = True) -> int:
    """Main entry point for statistics generation.

    Args:
        results_dir: Path to results directory containing image_*/evaluation.json files
        output_dir: Path to output directory for statistics files
        use_fill: If True, also load black/white fill evaluations and produce 3 rows

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

    df = calculate_statistics(evaluation_data)

    extra_dfs = None
    num_matched = len(df)
    num_missing = 0

    if use_fill:
        black_data = load_evaluation_data(results_dir, "evaluation_black.json")
        white_data = load_evaluation_data(results_dir, "evaluation_white.json")
        num_missing = max(len(black_data), len(white_data))

        if num_missing > 0:
            df_with_black = df
            if black_data:
                df_black = calculate_statistics(black_data)
                df_with_black = pd.concat([df, df_black], ignore_index=True)

            df_with_white = df
            if white_data:
                df_white = calculate_statistics(white_data)
                df_with_white = pd.concat([df, df_white], ignore_index=True)

            # Worst-case fill: most metrics get 0 (higher-is-better),
            # LPIPS (lp) gets 1.0 (lower-is-better -> worst = 1.0).
            worst_rows = pd.DataFrame(0.0, index=range(num_missing), columns=df.columns)
            if 'lp' in worst_rows.columns:
                worst_rows['lp'] = 1.0
            if 'image_id' in df.columns:
                worst_rows['image_id'] = [f'zero_{i}' for i in range(num_missing)]
            df_with_zero = pd.concat([df, worst_rows], ignore_index=True)

            extra_dfs = {
                "+ black fill": df_with_black,
                "+ white fill": df_with_white,
                "+ zero fill": df_with_zero,
            }

    total = num_matched + num_missing
    success_ratio = None
    if use_fill and total > 0:
        # In fill mode we know the total (matched + missing with fill files)
        pct = round(num_matched / total * 100, 2)
        success_ratio = f"{pct}%"
        print(f"\nSuccess Rate: {num_matched}/{total} = {pct:.2f}%")

    save_statistics_files(df, output_dir, extra_dfs=extra_dfs,
                          success_ratio=success_ratio)

    print(f"\nSummary Statistics:")
    print(f"  Total images analyzed: {len(df)}")
    print(f"\n  Average Metrics:")
    for category, metrics in METRIC_CATEGORIES.items():
        print(f"    {category}:")
        for metric in metrics:
            mean_val = df[metric].mean()
            print(f"      {metric:20s}: {mean_val:6.2f}")

    print("\nStatistics generation complete!")
    return 0
