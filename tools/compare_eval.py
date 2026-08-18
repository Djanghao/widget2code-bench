#!/usr/bin/env python3
"""Compare two evaluation trees metric by metric.

Every change to this evaluator has to answer one question: did the numbers move?
This reads the per-sample evaluation.json written by two runs and answers it,
either exactly (the default, for changes that must be arithmetic-preserving) or
at a stated number of decimals (for comparing execution backends).

    tools/compare_eval.py RUN_A RUN_B
    tools/compare_eval.py RUN_A RUN_B --decimals 4

Each RUN is a prediction directory holding <sample>/evaluation/evaluation.json.
Exit status is 0 when the runs agree under the chosen criterion, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CATEGORIES = {
    "LayoutScore": ["MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff"],
    "LegibilityScore": ["TextJaccard", "ContrastDiff", "ContrastLocalDiff"],
    "StyleScore": ["PaletteDistance", "Vibrancy", "PolarityConsistency"],
    "PerceptualScore": ["ssim", "lp"],
    "Geometry": ["geo_score"],
}
METRICS = [m for ms in CATEGORIES.values() for m in ms]


def load_run(root: Path) -> dict[str, dict[str, float]]:
    """sample id -> {metric: value}, flattened out of the nested categories."""
    out: dict[str, dict[str, float]] = {}
    for path in sorted(root.glob("*/evaluation/evaluation.json")):
        data = json.loads(path.read_text())
        out[path.parent.parent.name] = {
            m: data.get(cat, {}).get(m) for cat, ms in CATEGORIES.items() for m in ms
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_a", type=Path)
    ap.add_argument("run_b", type=Path)
    ap.add_argument("--decimals", type=int, default=None,
                    help="compare at N decimals instead of bit for bit")
    ap.add_argument("--show", type=int, default=5, help="how many divergences to print")
    args = ap.parse_args()

    a, b = load_run(args.run_a), load_run(args.run_b)
    if not a or not b:
        print(f"no evaluation.json found under {args.run_a if not a else args.run_b}")
        return 1

    only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    shared = sorted(set(a) & set(b))
    print(f"{args.run_a}  {len(a)} samples")
    print(f"{args.run_b}  {len(b)} samples")
    print(f"shared {len(shared)}"
          + (f", only in A: {len(only_a)}" if only_a else "")
          + (f", only in B: {len(only_b)}" if only_b else ""))

    def equal(x, y):
        if x is None or y is None:
            return x is y
        if args.decimals is None:
            return x == y
        return round(x, args.decimals) == round(y, args.decimals)

    worst = {m: 0.0 for m in METRICS}
    ndiff = {m: 0 for m in METRICS}
    examples: list[str] = []
    for sid in shared:
        for m in METRICS:
            x, y = a[sid][m], b[sid][m]
            if equal(x, y):
                continue
            ndiff[m] += 1
            if x is not None and y is not None:
                worst[m] = max(worst[m], abs(x - y))
                if len(examples) < args.show:
                    examples.append(f"  {sid:16s} {m:20s} {x!r} vs {y!r}  (delta {abs(x-y):.3e})")
            elif len(examples) < args.show:
                examples.append(f"  {sid:16s} {m:20s} {x!r} vs {y!r}")

    total = sum(ndiff.values())
    criterion = "bit for bit" if args.decimals is None else f"at {args.decimals} decimals"
    print(f"\ncomparison {criterion}: {len(shared) * len(METRICS)} values, {total} differ")
    if total:
        print(f"\n{'metric':22s} {'differing':>10s} {'max |delta|':>13s}")
        for m in METRICS:
            if ndiff[m]:
                print(f"{m:22s} {ndiff[m]:10d} {worst[m]:13.3e}")
        print("\nfirst divergences:")
        print("\n".join(examples))
    else:
        print("identical")

    return 0 if (total == 0 and not only_a and not only_b) else 1


if __name__ == "__main__":
    sys.exit(main())
