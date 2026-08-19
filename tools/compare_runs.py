#!/usr/bin/env python3
"""Merge several run directories into one wide table, one row per run.

Each batch evaluation writes one run directory (see report.write_run). Comparing
models means putting those side by side, and a table reads best with the twelve
metrics across the columns and one row per run - not one row per metric.

    tools/compare_runs.py runs/step25_* runs/step40_* runs/step55_* --mode zero
    tools/compare_runs.py runs/* --mode all --out comparison.csv

`--mode` picks which aggregate each row shows (default `zero`: missing
predictions count at their worst value, so a model cannot look good by failing
on the hard cases). `--mode all` emits one row per run and mode instead.
Rows keep the order the runs were given on the command line.
"""
from __future__ import annotations

import argparse
import csv
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
MODES = ("raw", "black", "white", "zero")


def load_run(run_dir: Path) -> dict:
    metrics = json.loads((run_dir / "metrics.json").read_text())
    manifest = json.loads((run_dir / "run.json").read_text())
    return {"name": manifest.get("run", run_dir.name),
            "modes": metrics["modes"],
            "matched": metrics["counts"]["matched"],
            "missing": metrics["counts"]["missing"],
            "success_rate": manifest.get("success_rate")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", type=Path,
                        help="run directories written by the batch mode")
    parser.add_argument("--mode", default="zero", choices=(*MODES, "all"),
                        help="which aggregate each row shows (default: zero); "
                             "'all' emits one row per run and mode")
    parser.add_argument("--decimals", type=int, default=4,
                        help="digits in the table (default: 4)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write CSV here (default: stdout)")
    args = parser.parse_args()

    rows = []
    for run_dir in args.runs:
        try:
            run = load_run(run_dir)
        except (OSError, KeyError, ValueError) as exc:
            print(f"skipping {run_dir}: not a run directory ({exc})", file=sys.stderr)
            continue
        wanted = MODES if args.mode == "all" else (args.mode,)
        for mode in wanted:
            # A run with nothing missing has only `raw`, and every other mode
            # would equal it anyway.
            values = run["modes"].get(mode, run["modes"]["raw"])
            rows.append([run["name"], mode,
                         *(round(values[m], args.decimals) for m in METRICS),
                         run["matched"], run["missing"], run["success_rate"]])

    if not rows:
        print("no run directories could be read", file=sys.stderr)
        return 1

    header = ["run", "mode", *METRICS, "matched", "missing", "success_rate"]
    out = args.out.open("w", newline="") if args.out else sys.stdout
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    if args.out:
        out.close()
        print(f"wrote {args.out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
