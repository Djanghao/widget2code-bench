#!/usr/bin/env python3
"""
Generate metrics statistics from widget evaluation results.

Produces:
- <output_dir>/metrics_stats.json         quartiles/mean/std per metric (matched pairs)
- <output_dir>/metrics/metrics.xlsx       4-row combined summary (raw/black/white/zero)
- <output_dir>/metrics/<mode>/<run>-<mode>-<ver>.xlsx  single-row per fill mode

In verbose mode (default), also produces:
- <output_dir>/bad_cases/<metric>/<rank>_score<s>_<sample>/   worst samples per metric
- <output_dir>/bad_cases/_catastrophic_Nplus/                 samples bad on ≥N metrics
"""

import json
import shutil
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

# Metrics used for bad-case selection. `lp` (lower-is-better, tight distribution)
# and `geo_score` (usually constant 100) are excluded by design.
BAD_METRICS = [
    "MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff",
    "TextJaccard", "ContrastDiff", "ContrastLocalDiff",
    "PaletteDistance", "Vibrancy", "PolarityConsistency",
    "ssim",
]

# bad = (score < BAD_SCORE_THRESHOLD) ∪ (score in worst BAD_TOP_PERCENT %)
BAD_SCORE_THRESHOLD = 5.0
BAD_TOP_PERCENT = 5.0
CATASTROPHIC_MIN_METRICS = 5


try:
    BENCH_VERSION = _pkg_version("widget2code-bench")
except PackageNotFoundError:
    BENCH_VERSION = "0.0.0"


def load_evaluation_data(results_dir: Path, filename: str = "evaluation.json") -> Dict[str, Dict]:
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
            evaluation_data[image_dir.name] = json.load(f)
    print(f"Loaded {len(evaluation_data)} {filename} files")
    return evaluation_data


def extract_metrics(eval_data: Dict) -> Dict[str, float]:
    metrics = {}
    for category, metric_names in METRIC_CATEGORIES.items():
        category_data = eval_data.get(category, {})
        for metric_name in metric_names:
            metrics[metric_name] = category_data.get(metric_name, 0.0)
    return metrics


def calculate_statistics(evaluation_data: Dict[str, Dict]) -> pd.DataFrame:
    rows = []
    for image_id, eval_data in evaluation_data.items():
        metrics = extract_metrics(eval_data)
        metrics["image_id"] = image_id
        rows.append(metrics)
    return pd.DataFrame(rows)


def _build_flat_row(run_name: str, mode_df: pd.DataFrame, success_ratio) -> Dict[str, object]:
    row: Dict[str, object] = {"model": run_name}
    for metric in FLAT_METRICS:
        row[metric] = round(mode_df[metric].mean(), 2)
    row["lp (LPIPS↓)"] = round(mode_df["lp"].mean(), 2)
    row["Geometry"] = round(mode_df["geo_score"].mean(), 2)
    row["SuccessRate"] = success_ratio if success_ratio is not None else ""
    return row


def _build_combined_row(run_name: str, mode: str, mode_df: pd.DataFrame,
                        sr_ratio, sr_count) -> List[object]:
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
    """metrics_stats.json (top-level) + metrics/ subfolder with all xlsx outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = output_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    # 1. metrics_stats.json at top level (unchanged location)
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

    stats_file = metrics_dir / "metrics_stats.json"
    with open(stats_file, 'w') as f:
        json.dump({"total_images": len(df_raw), "metrics": metric_statistics}, f, indent=2)
    print(f"Saved metrics statistics to: {stats_file}")

    # 2. per-mode split xlsx under metrics/<mode>/
    for mode in MODE_ORDER:
        if mode not in mode_dfs:
            continue
        sub_dir = metrics_dir / mode
        sub_dir.mkdir(parents=True, exist_ok=True)
        row = _build_flat_row(run_name, mode_dfs[mode], success_ratio_str)
        out_df = pd.DataFrame([row], columns=FLAT_COLUMNS)
        fname = f"{run_name}-{mode}-{BENCH_VERSION}.xlsx"
        out_df.to_excel(sub_dir / fname, index=False)
        print(f"Saved {mode} summary to: {sub_dir / fname}")

    # 3. combined metrics.xlsx under metrics/
    header_row1, header_row2 = _build_combined_headers()
    data_rows = []
    for mode in MODE_ORDER:
        if mode not in mode_dfs:
            continue
        data_rows.append(_build_combined_row(run_name, mode, mode_dfs[mode],
                                             sr_ratio, sr_count))

    combined_df = pd.DataFrame([header_row1, header_row2] + data_rows)
    combined_path = metrics_dir / "metrics.xlsx"
    combined_df.to_excel(combined_path, index=False, header=False)
    print(f"Saved combined metrics to: {combined_path}")


def _score_for_metric(df: pd.DataFrame, metric: str) -> np.ndarray:
    """Return 0-100 higher-is-better score array for a metric. `ssim` ×100."""
    arr = df[metric].to_numpy(dtype=float)
    if metric == "ssim":
        arr = arr * 100.0
    return arr


def _bad_mask(scores: np.ndarray, score_threshold: float, top_percent: float) -> np.ndarray:
    """Union of {score < threshold} and {worst top_percent%}."""
    if len(scores) == 0:
        return np.zeros(0, dtype=bool)
    under_threshold = scores < score_threshold
    top_k = max(1, int(np.ceil(len(scores) * top_percent / 100.0)))
    order = np.argsort(scores)
    top_mask = np.zeros(len(scores), dtype=bool)
    top_mask[order[:top_k]] = True
    return under_threshold | top_mask


def save_bad_cases(results_dir: Path, output_dir: Path, df_raw: pd.DataFrame,
                   score_threshold: float = BAD_SCORE_THRESHOLD,
                   top_percent: float = BAD_TOP_PERCENT,
                   catastrophic_min: int = CATASTROPHIC_MIN_METRICS) -> None:
    """Per-metric worst-case sample copies + catastrophic cross-metric summary."""
    bad_root = output_dir / "bad_cases"
    bad_root.mkdir(parents=True, exist_ok=True)

    # Track per-sample bad-metric memberships for catastrophic rollup.
    sample_bad_metrics: Dict[str, List[str]] = {sid: [] for sid in df_raw["image_id"].tolist()}

    for metric in BAD_METRICS:
        scores = _score_for_metric(df_raw, metric)
        mask = _bad_mask(scores, score_threshold, top_percent)

        ids = df_raw["image_id"].to_numpy()
        bad_ids = ids[mask]
        bad_scores = scores[mask]

        # Sort ascending (worst first).
        order = np.argsort(bad_scores)
        bad_ids = bad_ids[order]
        bad_scores = bad_scores[order]

        if len(bad_ids) == 0:
            continue

        metric_dir = bad_root / metric
        metric_dir.mkdir(parents=True, exist_ok=True)

        scores_txt_lines = []
        for sid, s in zip(bad_ids, bad_scores):
            sample_bad_metrics.setdefault(sid, []).append(metric)
            rank = min(99, int(np.floor(s)))
            folder_name = f"{rank:03d}_score{s:05.1f}_{sid}"
            src = results_dir / sid
            dst = metric_dir / folder_name
            if dst.exists():
                shutil.rmtree(dst)
            if src.is_dir():
                try:
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                except Exception as e:
                    print(f"  warn: copy failed for {sid} -> {dst}: {e}")
            scores_txt_lines.append(f"{s:6.1f}  {sid}")

        with open(metric_dir / "_scores.txt", "w") as f:
            f.write("\n".join(scores_txt_lines) + "\n")
        print(f"Saved {len(bad_ids):4d} bad cases for {metric}")

    # Catastrophic: samples bad on ≥ catastrophic_min metrics.
    catastrophic = [(sid, ms) for sid, ms in sample_bad_metrics.items()
                    if len(ms) >= catastrophic_min]
    catastrophic.sort(key=lambda t: (-len(t[1]), t[0]))

    if catastrophic:
        cat_dir = bad_root / f"_catastrophic_{catastrophic_min}plus"
        cat_dir.mkdir(parents=True, exist_ok=True)

        summary_lines = []
        for sid, ms in catastrophic:
            summary_lines.append(f"bad-in-{len(ms):2d}  {sid}  {','.join(ms)}")
            folder_name = f"bad{catastrophic_min:02d}_{sid}"
            src = results_dir / sid
            dst = cat_dir / folder_name
            if dst.exists():
                shutil.rmtree(dst)
            if src.is_dir():
                try:
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                except Exception as e:
                    print(f"  warn: copy failed for {sid} -> {dst}: {e}")

        with open(cat_dir / "_summary.txt", "w") as f:
            f.write("\n".join(summary_lines) + "\n")
        print(f"Saved {len(catastrophic):4d} catastrophic (bad in ≥{catastrophic_min}) cases")


def generate_statistics(results_dir: str, output_dir: str,
                        verbose: bool = True,
                        bad_score_threshold: float = BAD_SCORE_THRESHOLD,
                        bad_top_percent: float = BAD_TOP_PERCENT,
                        catastrophic_min: int = CATASTROPHIC_MIN_METRICS) -> int:
    """Entry point for statistics generation. Always produces raw/black/white/zero.

    In verbose mode, also writes bad_cases/ with per-metric worst samples and a
    cross-metric catastrophic rollup.
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

    if num_missing > 0:
        worst_rows = pd.DataFrame(0.0, index=range(num_missing), columns=df_raw.columns)
        if 'lp' in worst_rows.columns:
            worst_rows['lp'] = 1.0
        if 'image_id' in df_raw.columns:
            worst_rows['image_id'] = [f'zero_{i}' for i in range(num_missing)]
        df_zero = pd.concat([df_raw, worst_rows], ignore_index=True)
    else:
        df_zero = df_raw

    mode_dfs = {"raw": df_raw, "black": df_black, "white": df_white, "zero": df_zero}

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

    if verbose:
        print(f"\nGenerating bad_cases (score<{bad_score_threshold} ∪ top {bad_top_percent}%)...")
        save_bad_cases(results_dir, output_dir, df_raw,
                       score_threshold=bad_score_threshold,
                       top_percent=bad_top_percent,
                       catastrophic_min=catastrophic_min)

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
