#!/usr/bin/env python3
"""
Widget Evaluation Pipeline
Performs widget quality evaluation and generates statistics.

Usage:
    widget2code-bench-exp --gt_dir <GT_DIR> --pred_dir <PRED_DIR> [OPTIONS]
    widget2code-bench-exp --gt_image <GT_PNG> --pred_image <PRED_PNG> [OPTIONS]
"""

import os
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Widget Evaluation Pipeline - two modes: batch (a directory of "
                    "predictions) or single (one image pair)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
There are exactly two ways to run this tool:

  batch    --gt_dir + --pred_dir      score a prediction directory, write one run
  single   --gt_image + --pred_image  score one pair, print JSON, write nothing

Directory layout (batch mode):
  --gt_dir   one directory per sample - image_0001/image.png with metadata.json
             beside it - as published in Djanghao/Widget2Code-Data
  --pred_dir subfolders with 4-digit IDs, each holding the file named by
             --pred_name (a relative path such as sft_render/rendered.png works)

Outputs (batch mode) - one self-contained run directory, predictions never written to:
  <out>/<run-name>/
    run.json        what produced it: paths, workers, image stamp, timing, errors
    samples.jsonl   one line per matched sample
    metrics.json    per-mode means (raw/black/white/zero) plus quartiles
    summary.md      the table, to --decimals
    summary.csv     the same table - metrics across the columns, one row per mode
    summary.xlsx
  Default <out> is <pred_dir>/../runs, default <run-name> is <pred_dir>_<UTC stamp>.

Missing predictions are scored against all-black and all-white images; when the
ground truth ships precomputed fill scores in metadata.json (validated by the
image's sha256) they are read instead of recomputed.

Device selection:
  --cuda          use the GPU (first visible device) for LPIPS and OCR
  --device N      pin this process to GPU N (implies --cuda). One evaluation
                  uses one GPU; to use several cards, run one process per card.

Notes:
  - Console prints "Success rate: N/total = X.XX%" (matched pairs / total GT).
  - All metrics are higher-is-better EXCEPT lp (LPIPS), which is lower-is-better.

Examples:
  # Batch mode on GPU 0
  widget2code-bench-exp --gt_dir /data/test --pred_dir /eval/step40 \\
      --pred_name sft_render/rendered.png --device 0 --workers 8

  # One prediction folder per GPU, in parallel
  for i in 0 1 2 3; do
    widget2code-bench-exp --gt_dir /data/test --pred_dir /eval/model_$i \\
        --pred_name rendered.png --device $i --workers 8 &
  done; wait

  # Single pair, some metrics, machine-readable
  widget2code-bench-exp --gt_image gt.png --pred_image pred.png \\
      --metrics ssim,layout,style,contrast --json-only
        """
    )

    # Single mode
    parser.add_argument("--gt_image", type=str, default=None, help="Path to a single ground truth image")
    parser.add_argument("--pred_image", type=str, default=None, help="Path to a single prediction image")
    parser.add_argument(
        "--metrics",
        type=str,
        default=None,
        help=("Comma-separated metric groups or leaves for single mode "
              "(e.g. ssim,geometry,contrast or perceptual,layout; default: all)"),
    )
    parser.add_argument(
        "--json-only",
        "--json_only",
        dest="json_only",
        action="store_true",
        help="Print only the JSON result in single mode (for reward workers)",
    )

    # Batch mode
    parser.add_argument("--gt_dir", type=str, default=None,
                        help="Ground truth directory, one subdirectory per sample")
    parser.add_argument("--pred_dir", type=str, default=None,
                        help="Prediction directory, one subfolder per sample; never written to")
    parser.add_argument("--out", type=str, default=None,
                        help="Directory that holds run directories (default: <pred_dir>/../runs)")
    parser.add_argument("--run-name", type=str, default=None,
                        help="Name of this run's directory (default: <pred_dir>_<UTC timestamp>)")
    parser.add_argument("--decimals", type=int, default=4,
                        help="Decimals in the rendered tables (default: 4). Sample values are "
                             "quantised to 3 as they have been since 0.2.9; samples.jsonl is "
                             "unaffected by this flag")
    parser.add_argument("--workers", type=int, default=4,
                        help="Batch mode: number of worker threads (default: 4)")
    parser.add_argument("--pred_name", type=str, default="output.png",
                        help="Prediction filename inside each subfolder (default: output.png)")

    # Device (both modes)
    parser.add_argument("--cuda", action="store_true",
                        help="Use the GPU for LPIPS and OCR (first visible device)")
    parser.add_argument("--device", type=int, default=None, metavar="N",
                        help="GPU index to run on, as numbered by nvidia-smi; implies --cuda. "
                             "Sets CUDA_VISIBLE_DEVICES for this process, so run one process "
                             "per card to use several")

    parser.add_argument("--skill-path", action="store_true",
                        help="Print the path of the bundled agent skill and exit")

    args = parser.parse_args()

    if args.skill_path:
        print(_skill_path())
        return

    # Pin the card before anything touches CUDA. Torch and EasyOCR both address
    # "the" GPU, so the way to choose one is to make it the only one visible.
    if args.device is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(args.device)
        args.cuda = True

    single_args = bool(args.gt_image or args.pred_image)
    batch_args = bool(args.gt_dir or args.pred_dir)
    if single_args and batch_args:
        print("Error: --gt_image/--pred_image (single) and --gt_dir/--pred_dir (batch) "
              "are two different modes; provide one set, not both")
        sys.exit(1)

    if single_args:
        if not args.gt_image or not args.pred_image:
            print("Error: --gt_image and --pred_image must both be provided")
            sys.exit(1)
        _run_single(args)
        return

    if not args.gt_dir or not args.pred_dir:
        print("Error: Provide either --gt_image/--pred_image or --gt_dir/--pred_dir")
        sys.exit(1)
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
    import time
    from datetime import datetime, timezone

    from widget2code_bench.eval import evaluate_pairs
    from widget2code_bench.report import write_run
    from widget_quality.legibility import set_ocr_device
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

    device = "cpu"
    if args.cuda:
        device = f"gpu {args.device}" if args.device is not None else "gpu"
    print(f"gt         {gt_dir}")
    print(f"pred       {pred_dir}  (read-only)")
    print(f"run        {out_dir}")
    print(f"workers    {args.workers}   device {device}   decimals {args.decimals}")
    print()

    # Both neural nets follow the same switch: without it, EasyOCR would grab
    # any GPU it can see while --cuda-less LPIPS stays on the CPU.
    set_device(use_cuda=args.cuda)
    set_ocr_device(args.cuda)
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
            "device": args.device,
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
    for name in ("run.json", "samples.jsonl", "metrics.json", "summary.md",
                 "summary.csv", "summary.xlsx"):
        if (out_dir / name).exists():
            print(f"  {name}")


if __name__ == "__main__":
    main()
