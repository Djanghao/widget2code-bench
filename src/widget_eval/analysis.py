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


def load_evaluation_data(results_dir: Path) -> Dict[str, Dict]:
    """Load all evaluation.json files from result directories.

    Supports two directory structures:
      - image_{num}/evaluation.json  (old structure)
      - {num}/evaluation.json        (new structure)
    """
    evaluation_data = {}

    for image_dir in sorted(results_dir.iterdir()):
        if not image_dir.is_dir():
            continue

        eval_file = image_dir / "evaluation.json"
        if not eval_file.exists():
            continue

        with open(eval_file, 'r') as f:
            data = json.load(f)
            evaluation_data[image_dir.name] = data

    print(f"Loaded {len(evaluation_data)} evaluation files")
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


def save_statistics_files(df: pd.DataFrame, output_dir: Path):
    """Save metrics_stats.json and metrics.xlsx files."""
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
    data_row = [run_name]

    layout_metrics = ["MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff"]
    header_row1.append('LayoutScore')
    header_row1.extend([None] * (len(layout_metrics) - 1))
    for metric in layout_metrics:
        header_row2.append(metric)
        data_row.append(round(df[metric].mean(), 3))

    legibility_metrics = ["TextJaccard", "ContrastDiff", "ContrastLocalDiff"]
    header_row1.append('LegibilityScore')
    header_row1.extend([None] * (len(legibility_metrics) - 1))
    for metric in legibility_metrics:
        header_row2.append(metric)
        data_row.append(round(df[metric].mean(), 3))

    style_metrics = ["PaletteDistance", "Vibrancy", "PolarityConsistency"]
    header_row1.append('StyleScore')
    header_row1.extend([None] * (len(style_metrics) - 1))
    for metric in style_metrics:
        header_row2.append(metric)
        data_row.append(round(df[metric].mean(), 3))

    perceptual_metrics = ["ssim", "lp"]
    header_row1.append('PerceptualScore')
    header_row1.extend([None] * (len(perceptual_metrics) - 1))
    for metric in perceptual_metrics:
        header_row2.append(metric)
        data_row.append(round(df[metric].mean(), 3))

    header_row1.append('Geometry')
    header_row2.append(None)
    data_row.append(round(df['geo_score'].mean(), 3))

    metrics_df = pd.DataFrame([header_row1, header_row2, data_row])
    metrics_df.to_excel(metrics_xlsx, index=False, header=False)

    print(f"Saved metrics summary to: {metrics_xlsx}")


def generate_statistics(results_dir: str, output_dir: str) -> int:
    """Main entry point for statistics generation.

    Args:
        results_dir: Path to results directory containing image_*/evaluation.json files
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

    df = calculate_statistics(evaluation_data)
    save_statistics_files(df, output_dir)

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
