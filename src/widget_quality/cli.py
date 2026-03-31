"""Command-line interface for widget-quality."""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="widget-quality",
        description="Evaluate widget generation quality (12 metrics across 5 categories).",
    )
    sub = parser.add_subparsers(dest="command")

    # --- evaluate pair ---
    pair_p = sub.add_parser("pair", help="Evaluate a single GT/generated image pair")
    pair_p.add_argument("gt", help="Path to ground truth image")
    pair_p.add_argument("gen", help="Path to generated image")
    pair_p.add_argument("--cuda", action="store_true", help="Use GPU for LPIPS")
    pair_p.add_argument("-o", "--output", help="Save JSON results to file")

    # --- evaluate directory ---
    dir_p = sub.add_parser("dir", help="Evaluate all pairs in directories")
    dir_p.add_argument("--gt_dir", required=True, help="Ground truth directory")
    dir_p.add_argument("--pred_dir", required=True, help="Prediction directory")
    dir_p.add_argument("--workers", type=int, default=4, help="Parallel workers")
    dir_p.add_argument("--cuda", action="store_true", help="Use GPU for LPIPS")
    dir_p.add_argument("-o", "--output", help="Save summary JSON to file")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.cuda:
        from .perceptual import set_device
        set_device(use_cuda=True)

    if args.command == "pair":
        from .evaluate import evaluate_pair
        result = evaluate_pair(args.gt, args.gen)
        out = json.dumps(result, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(out)
            print(f"Saved to {args.output}")
        else:
            print(out)

    elif args.command == "dir":
        from .evaluate import evaluate_dir
        results = evaluate_dir(args.gt_dir, args.pred_dir, workers=args.workers)
        out = json.dumps(results, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(out)
            print(f"Evaluated {len(results)} pairs. Saved to {args.output}")
        else:
            print(out)
