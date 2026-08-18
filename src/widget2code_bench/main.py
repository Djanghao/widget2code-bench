#!/usr/bin/env python3
"""
Widget Evaluation Pipeline
Performs widget quality evaluation and generates statistics.

Usage:
    widget2code-bench-exp --gt_dir <GT_DIR> --pred_dir <PRED_DIR> [OPTIONS]
"""

import sys
import argparse
from pathlib import Path

from widget2code_bench.eval import evaluate_pairs
from widget2code_bench.analysis import generate_statistics


def main():
    parser = argparse.ArgumentParser(
        description="Widget Evaluation Pipeline - Evaluate and generate statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Directory layout (batch mode):
  --gt_dir   flat PNG files with 4-digit IDs (e.g. gt_0001.png)
  --pred_dir subfolders with 4-digit IDs, each containing the file named by --pred_name

Outputs (batch mode):
  <pred_dir>/<subfolder>/evaluation/evaluation.json         per-pair metrics (matched pairs)
  <pred_dir>/<subfolder>/evaluation/evaluation_black.json   per-pair metrics vs black fill (missing preds only)
  <pred_dir>/<subfolder>/evaluation/evaluation_white.json   per-pair metrics vs white fill (missing preds only)
  <pred_dir>/<subfolder>/evaluation/viz/*.png               per-metric computation visualizations (unless --minimal)
  <pred_dir>/evaluation.xlsx                          summary written during eval step
  <pred_dir>/.analysis/metrics_stats.json             per-metric quartiles/mean/std (matched pairs)
  <pred_dir>/.analysis/metrics.xlsx                   4-row combined summary (raw/black/white/zero)
  <pred_dir>/.analysis/<mode>/<run>-<mode>-<v>.xlsx   single-row summary per fill mode (raw/black/white/zero)

Summary xlsx rows (combined metrics.xlsx):
  1) <run>                    average over matched pairs only
  2) <run> (+ black fill)     missing preds treated as all-black images
  3) <run> (+ white fill)     missing preds treated as all-white images
  4) <run> (+ zero fill)      missing preds get worst-case values (LPIPS=1.0, others=0)

Notes:
  - Console prints "Success Rate: N/total = X.XX%" (matched pairs / total GT).
  - All metrics are higher-is-better EXCEPT lp (LPIPS) which is lower-is-better.

Examples:
  # Batch mode (always produces raw/black/white/zero)
  widget2code-bench-exp --gt_dir /path/to/GT --pred_dir /path/to/results --cuda

  # Pick a specific GPU
  CUDA_VISIBLE_DEVICES=7 widget2code-bench-exp --gt_dir /path/to/GT --pred_dir /path/to/results --cuda --workers 8

  # Single image mode (prints JSON, no files written)
  widget2code-bench-exp --gt_image /path/to/gt.png --pred_image /path/to/pred.png --cuda

  # Re-generate xlsx from existing evaluation.json files (no recomputation)
  widget2code-bench-exp --gt_dir /path/to/GT --pred_dir /path/to/results --skip_eval

  # Custom stats output directory and thread count
  widget2code-bench-exp --gt_dir /path/to/GT --pred_dir /path/to/results --output_dir /path/to/stats --workers 8
        """
    )

    # Single image mode
    parser.add_argument("--gt_image", type=str, default=None, help="Path to a single ground truth image")
    parser.add_argument("--pred_image", type=str, default=None, help="Path to a single prediction image")
    parser.add_argument(
        "--metrics",
        type=str,
        default=None,
        help=("Comma-separated metric groups or leaves for single-image mode "
              "(e.g. ssim,geometry,contrast or perceptual,layout; default: all)"),
    )
    parser.add_argument(
        "--json-only",
        "--json_only",
        dest="json_only",
        action="store_true",
        help="Print only the JSON result in single-image mode (for reward workers)",
    )

    # Batch mode
    parser.add_argument("--gt_dir", type=str, default=None, help="Path to ground truth directory")
    parser.add_argument("--pred_dir", type=str, default=None, help="Path to prediction directory")
    parser.add_argument("--out", type=str, default=None,
                        help="Directory that holds run directories (default: <pred_dir>/../runs)")
    parser.add_argument("--run-name", type=str, default=None,
                        help="Name of this run's directory (default: <pred_dir>_<UTC timestamp>)")
    parser.add_argument("--decimals", type=int, default=4,
                        help="Decimals in the rendered tables (default: 4). Sample values are "
                             "quantised to 3 as they have been since 0.2.9; samples.jsonl is "
                             "unaffected by this flag")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads (default: 4)")
    parser.add_argument("--cuda", action="store_true", help="Use CUDA/GPU for computation")
    parser.add_argument("--pred_name", type=str, default="output.png",
                        help="Prediction filename inside each subfolder (default: output.png)")
    parser.add_argument("--skill-path", action="store_true",
                        help="Print the path of the bundled agent skill and exit")

    args = parser.parse_args()

    if args.skill_path:
        print(_skill_path())
        return

    # Single image mode
    if args.gt_image or args.pred_image:
        if not args.gt_image or not args.pred_image:
            print("Error: --gt_image and --pred_image must both be provided")
            sys.exit(1)
        _run_single(args)
        return

    # Batch mode
    if not args.gt_dir or not args.pred_dir:
        print("Error: Provide either --gt_image/--pred_image or --gt_dir/--pred_dir")
        sys.exit(1)
    from widget_quality.perceptual import set_device
    set_device(use_cuda=args.cuda)
    _run_batch(args)


def _skill_path() -> str:
    """Where the bundled skill landed, so an agent can read it without the repo."""
    from importlib.resources import files

    return str(files("widget2code_bench") / "skill" / "SKILL.md")


def _run_single(args):
    """Evaluate a single GT-prediction image pair. Prints results to stdout, no files saved."""
    import json
    from widget2code_bench.single import evaluate_single

    gt_path = Path(args.gt_image)
    pred_path = Path(args.pred_image)

    if not gt_path.exists():
        print(f"Error: GT image does not exist: {gt_path}")
        sys.exit(1)
    if not pred_path.exists():
        print(f"Error: Prediction image does not exist: {pred_path}")
        sys.exit(1)

    if not args.json_only:
        print(f"GT Image:   {gt_path}")
        print(f"Pred Image: {pred_path}")
        print()

    try:
        result = evaluate_single(
            gt_path,
            pred_path,
            metrics=args.metrics,
            use_cuda=args.cuda,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    print(json.dumps(result, indent=2))


def _run_batch(args):
    """Score a prediction directory and write one run directory."""
    import os
    import time
    from datetime import datetime, timezone

    from widget2code_bench.eval import evaluate_pairs
    from widget2code_bench.report import write_run
    from widget_quality.perceptual import set_device

    gt_dir = Path(args.gt_dir)
    pred_dir = Path(args.pred_dir)
    for label, path in (("GT", gt_dir), ("Prediction", pred_dir)):
        if not path.exists():
            print(f"Error: {label} directory does not exist: {path}")
            sys.exit(1)

    # One run, one directory. `--out` only names where runs are kept, so several
    # runs over the same predictions sit side by side instead of overwriting each
    # other, and the predictions themselves are never written to.
    runs_dir = Path(args.out) if args.out else pred_dir.parent / "runs"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_name = args.run_name or f"{pred_dir.name}_{stamp}"
    out_dir = runs_dir / run_name

    print(f"gt         {gt_dir}")
    print(f"pred       {pred_dir}  (read-only)")
    print(f"run        {out_dir}")
    print(f"workers    {args.workers}   cuda {'on' if args.cuda else 'off'}   "
          f"decimals {args.decimals}")
    print()

    set_device(use_cuda=args.cuda)
    started = time.time()
    results = evaluate_pairs(str(gt_dir), str(pred_dir), args.workers,
                             pred_name=args.pred_name)
    elapsed = time.time() - started

    if not results["matched"]:
        print("No matched pairs to evaluate.")
        sys.exit(1)

    write_run(
        out_dir,
        manifest={
            "run": run_name,
            "gt_dir": str(gt_dir),
            "pred_dir": str(pred_dir),
            "pred_name": args.pred_name,
            "workers": args.workers,
            "cuda": bool(args.cuda),
            "image_stamp": os.environ.get("W2C_BENCH_STAMP"),
            "errors": results["errors"],
            "seconds": round(elapsed, 1),
            "finished_at": stamp,
        },
        matched=results["matched"],
        black=results["black"],
        white=results["white"],
        digits=args.decimals,
    )

    print(f"\nwrote {out_dir}")
    for name in ("run.json", "samples.jsonl", "metrics.json", "summary.md", "summary.xlsx"):
        if (out_dir / name).exists():
            print(f"  {name}")


if __name__ == "__main__":
    main()
