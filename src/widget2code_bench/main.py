#!/usr/bin/env python3
"""
Widget Evaluation Pipeline
Performs widget quality evaluation and generates statistics.

Usage:
    widget2code-bench --gt_dir <GT_DIR> --pred_dir <PRED_DIR> [OPTIONS]
"""

import sys
import argparse
from pathlib import Path

from widget2code_bench.eval import evaluate_pairs
from widget2code_bench.analysis import generate_statistics
from widget_quality.perceptual import set_device


def main():
    parser = argparse.ArgumentParser(
        description="Widget Evaluation Pipeline - Evaluate and generate statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Directory layout (batch mode):
  --gt_dir   flat PNG files with 4-digit IDs (e.g. gt_0001.png)
  --pred_dir subfolders with 4-digit IDs, each containing the file named by --pred_name

Outputs (batch mode):
  <pred_dir>/<subfolder>/evaluation.json        per-pair metrics (matched pairs)
  <pred_dir>/<subfolder>/evaluation_black.json  metrics vs black fill (missing-pred folders only, when fill is on)
  <pred_dir>/<subfolder>/evaluation_white.json  metrics vs white fill (missing-pred folders only, when fill is on)
  <pred_dir>/evaluation.xlsx                    summary written during eval step
  <pred_dir>/.analysis/metrics_stats.json       per-metric quartiles/mean/std (matched pairs)
  <pred_dir>/.analysis/metrics.xlsx             summary written during stats step

Summary xlsx rows (fill mode, default):
  1) <run>                    average over matched pairs only
  2) <run> (+ black fill)     missing preds treated as all-black images
  3) <run> (+ white fill)     missing preds treated as all-white images
  4) <run> (+ zero fill)      missing preds get worst-case values (LPIPS=1.0, others=0)

Notes:
  - Console prints "Success Rate: N/total = X.XX%" (matched pairs / total GT).
  - All metrics are higher-is-better EXCEPT lp (LPIPS) which is lower-is-better.
  - With --no_fill, missing predictions are simply skipped and the xlsx has only row 1.

Examples:
  # Batch mode (default: black/white/zero fill for missing predictions)
  widget2code-bench --gt_dir /path/to/GT --pred_dir /path/to/results --cuda

  # Disable fill — only score matched pairs
  widget2code-bench --gt_dir /path/to/GT --pred_dir /path/to/results --cuda --no_fill

  # Pick a specific GPU
  CUDA_VISIBLE_DEVICES=7 widget2code-bench --gt_dir /path/to/GT --pred_dir /path/to/results --cuda --workers 8

  # Single image mode (prints JSON, no files written)
  widget2code-bench --gt_image /path/to/gt.png --pred_image /path/to/pred.png --cuda

  # Re-generate xlsx from existing evaluation.json files (no recomputation)
  widget2code-bench --gt_dir /path/to/GT --pred_dir /path/to/results --skip_eval

  # Custom stats output directory and thread count
  widget2code-bench --gt_dir /path/to/GT --pred_dir /path/to/results --output_dir /path/to/stats --workers 8
        """
    )

    # Single image mode
    parser.add_argument("--gt_image", type=str, default=None, help="Path to a single ground truth image")
    parser.add_argument("--pred_image", type=str, default=None, help="Path to a single prediction image")

    # Batch mode
    parser.add_argument("--gt_dir", type=str, default=None, help="Path to ground truth directory")
    parser.add_argument("--pred_dir", type=str, default=None, help="Path to prediction directory")
    parser.add_argument("--output_dir", type=str, default=None,
                        help="Path to output directory for statistics (default: {pred_dir}/.analysis)")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads (default: 4)")
    parser.add_argument("--skip_eval", action="store_true",
                        help="Skip evaluation step (assumes evaluation.json files already exist)")
    parser.add_argument("--cuda", action="store_true", help="Use CUDA/GPU for computation")
    parser.add_argument("--pred_name", type=str, default="output.png",
                        help="Prediction filename inside each subfolder (default: output.png)")
    parser.add_argument("--no_fill", action="store_true",
                        help="Disable fill-image evaluation for missing predictions (black/white fill is enabled by default)")

    args = parser.parse_args()

    # Set device for perceptual metrics
    set_device(use_cuda=args.cuda)

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
    _run_batch(args)


def _run_single(args):
    """Evaluate a single GT-prediction image pair. Prints results to stdout, no files saved."""
    import json
    from widget_quality.utils import load_image, resize_to_match
    from widget_quality.perceptual import compute_perceptual
    from widget_quality.layout import compute_layout
    from widget_quality.legibility import compute_legibility
    from widget_quality.style import compute_style
    from widget_quality.geometry import compute_aspect_dimensionality_fidelity
    from widget_quality.composite import composite_score
    from widget2code_bench.eval import convert_to_serializable

    gt_path = Path(args.gt_image)
    pred_path = Path(args.pred_image)

    if not gt_path.exists():
        print(f"Error: GT image does not exist: {gt_path}")
        sys.exit(1)
    if not pred_path.exists():
        print(f"Error: Prediction image does not exist: {pred_path}")
        sys.exit(1)

    print(f"GT Image:   {gt_path}")
    print(f"Pred Image: {pred_path}")
    print()

    gt_img = load_image(str(gt_path))
    pred_img = load_image(str(pred_path))
    gen = resize_to_match(gt_img, pred_img)

    geo = compute_aspect_dimensionality_fidelity(gt_img, pred_img)
    perceptual = compute_perceptual(gt_img, gen)
    layout = compute_layout(gt_img, gen)
    legibility = compute_legibility(gt_img, gen)
    style = compute_style(gt_img, gen)

    result = composite_score(geo, perceptual, layout, legibility, style)
    result = convert_to_serializable(result)

    print(json.dumps(result, indent=2))


def _run_batch(args):
    """Run batch evaluation on directories."""
    gt_dir = Path(args.gt_dir)
    pred_dir = Path(args.pred_dir)

    if not gt_dir.exists():
        print(f"Error: GT directory does not exist: {gt_dir}")
        sys.exit(1)

    if not pred_dir.exists():
        print(f"Error: Prediction directory does not exist: {pred_dir}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else pred_dir / ".analysis"

    print("=" * 80)
    print("Widget Quality Evaluation Pipeline")
    print("=" * 80)
    print(f"GT Directory:     {gt_dir}")
    print(f"Prediction Dir:   {pred_dir}")
    print(f"Output Dir:       {output_dir}")
    print(f"Workers:          {args.workers}")
    print(f"CUDA:             {'Enabled' if args.cuda else 'Disabled (CPU)'}")
    print(f"Pred Name:        {args.pred_name}")
    print(f"Fill Missing:     {'Disabled' if args.no_fill else 'Enabled (black/white)'}")
    print("=" * 80)
    print()

    # Step 1: Run evaluation
    if not args.skip_eval:
        print("=" * 80)
        print("STEP 1: Running Widget Quality Evaluation")
        print("=" * 80)
        evaluate_pairs(str(gt_dir), str(pred_dir), args.workers, pred_name=args.pred_name,
                       use_fill=not args.no_fill)
        print()
    else:
        print("Skipping evaluation step (--skip_eval)\n")

    # Step 2: Generate statistics
    print("=" * 80)
    print("STEP 2: Generating Metrics Statistics")
    print("=" * 80)
    ret = generate_statistics(str(pred_dir), str(output_dir),
                              use_fill=not args.no_fill)
    if ret != 0:
        sys.exit(ret)

    # Summary
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETED")
    print("=" * 80)
    print(f"GT Directory: {gt_dir}")
    print(f"Prediction Directory: {pred_dir}")
    print(f"Statistics Output: {output_dir}")
    print("\nAll steps completed successfully!")


if __name__ == "__main__":
    main()
