#!/usr/bin/env python3
"""
Widget Evaluation Pipeline
Performs widget quality evaluation and generates statistics.

Usage:
    widget-eval --gt_dir <GT_DIR> --pred_dir <PRED_DIR> [OPTIONS]
"""

import sys
import argparse
from pathlib import Path

from widget_eval.eval import evaluate_pairs
from widget_eval.analysis import generate_statistics
from widget_quality.perceptual import set_device


def main():
    parser = argparse.ArgumentParser(
        description="Widget Evaluation Pipeline - Evaluate and generate statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (CPU)
  widget-eval --gt_dir /path/to/GT --pred_dir /path/to/results

  # Use GPU for faster computation
  widget-eval --gt_dir /path/to/GT --pred_dir /path/to/results --cuda

  # Custom output directory and more workers
  widget-eval --gt_dir /path/to/GT --pred_dir /path/to/results --output_dir /path/to/stats --workers 8

  # Skip evaluation (if evaluation.json already exists)
  widget-eval --gt_dir /path/to/GT --pred_dir /path/to/results --skip_eval
        """
    )

    parser.add_argument("--gt_dir", type=str, required=True, help="Path to ground truth directory")
    parser.add_argument("--pred_dir", type=str, required=True, help="Path to prediction directory")
    parser.add_argument("--output_dir", type=str, default=None,
                        help="Path to output directory for statistics (default: {pred_dir}/.analysis)")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads (default: 4)")
    parser.add_argument("--skip_eval", action="store_true",
                        help="Skip evaluation step (assumes evaluation.json files already exist)")
    parser.add_argument("--cuda", action="store_true", help="Use CUDA/GPU for computation")

    args = parser.parse_args()

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
    print("=" * 80)
    print()

    # Set device for perceptual metrics
    set_device(use_cuda=args.cuda)

    # Step 1: Run evaluation
    if not args.skip_eval:
        print("=" * 80)
        print("STEP 1: Running Widget Quality Evaluation")
        print("=" * 80)
        evaluate_pairs(str(gt_dir), str(pred_dir), args.workers)
        print()
    else:
        print("Skipping evaluation step (--skip_eval)\n")

    # Step 2: Generate statistics
    print("=" * 80)
    print("STEP 2: Generating Metrics Statistics")
    print("=" * 80)
    ret = generate_statistics(str(pred_dir), str(output_dir))
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
