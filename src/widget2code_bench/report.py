"""Write one run's results into a directory of its own.

0.2.9 wrote its results back into the prediction directory - a JSON beside every
sample, an xlsx at the top, and a cleanup pass that deleted the previous run's
files before starting. That made predictions read-write, made two runs over the
same predictions overwrite each other, and left the numbers spread over a
thousand directories.

A run now writes one self-contained folder and touches nothing else, so
predictions stay an input and runs never collide. samples.jsonl carries every sample for downstream
analysis; the rendered tables carry as many digits as a reader asked for.

Sample values keep the three-decimal quantisation they have had since 0.2.9, so
a mean here is the same number an older table averaged. What that table then
rounded to two decimals is shown to more, which is where the extra digits come
from - not from changing what was measured.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

CATEGORIES = {
    "LayoutScore": ["MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff"],
    "LegibilityScore": ["TextJaccard", "ContrastDiff", "ContrastLocalDiff"],
    "StyleScore": ["PaletteDistance", "Vibrancy", "PolarityConsistency"],
    "PerceptualScore": ["ssim", "lp"],
    "Geometry": ["geo_score"],
}
METRICS = [m for ms in CATEGORIES.values() for m in ms]

# Higher is better everywhere except LPIPS, which is a distance.
LOWER_IS_BETTER = {"lp"}

MODES = ("raw", "black", "white", "zero")
MODE_LABEL = {
    "raw": "matched pairs only",
    "black": "missing scored against an all-black image",
    "white": "missing scored against an all-white image",
    "zero": "missing contribute the worst possible value",
}
# What a missing sample contributes under `zero`: worst means 0 for a score and
# 1 for a distance.
WORST = {"lp": 1.0}


def flatten(scores: dict) -> dict[str, float]:
    return {m: scores.get(cat, {}).get(m) for cat, ms in CATEGORIES.items() for m in ms}


def _mean(values: Iterable[float]) -> float:
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else 0.0


def aggregate(matched: list[dict], black: list[dict],
              white: list[dict]) -> dict[str, dict[str, float]]:
    """Per-mode means over full-precision samples."""
    m, b, w = ([flatten(r) for r in rows] for rows in (matched, black, white))
    n_missing = len(b)

    out = {"raw": {k: _mean(r[k] for r in m) for k in METRICS}}
    if n_missing:
        out["black"] = {k: _mean(r[k] for r in m + b) for k in METRICS}
        out["white"] = {k: _mean(r[k] for r in m + w) for k in METRICS}
        total = len(m) + n_missing
        out["zero"] = {
            k: (out["raw"][k] * len(m) + WORST.get(k, 0.0) * n_missing) / total
            for k in METRICS
        }
    return out


def quartiles(matched: list[dict]) -> dict[str, dict[str, float]]:
    rows = [flatten(r) for r in matched]
    stats = {}
    for metric in METRICS:
        values = np.array([r[metric] for r in rows if r[metric] is not None], dtype=float)
        if not values.size:
            continue
        stats[metric] = {
            "min": float(values.min()), "q1": float(np.percentile(values, 25)),
            "median": float(np.percentile(values, 50)),
            "q3": float(np.percentile(values, 75)), "max": float(values.max()),
            "mean": float(values.mean()), "std": float(values.std()),
        }
    return stats


def _table(modes: dict[str, dict[str, float]], digits: int) -> str:
    header = "| mode | " + " | ".join(METRICS) + " |"
    rule = "|---" * (len(METRICS) + 1) + "|"
    lines = [header, rule]
    for mode in MODES:
        if mode not in modes:
            continue
        cells = [f"{modes[mode][m]:.{digits}f}" for m in METRICS]
        lines.append(f"| {mode} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_run(
    out_dir: Path,
    *,
    manifest: dict[str, Any],
    matched: list[dict],
    black: list[dict],
    white: list[dict],
    digits: int = 4,
) -> Path:
    """Write one run's directory and return it."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Full precision, one line per sample: everything downstream reads this.
    with (out_dir / "samples.jsonl").open("w") as fh:
        for row in matched:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    modes = aggregate(matched, black, white)
    (out_dir / "metrics.json").write_text(json.dumps({
        "modes": modes,
        "distribution": quartiles(matched),
        "counts": {"matched": len(matched), "missing": len(black)},
    }, indent=2))

    n_gt = len(matched) + len(black)
    rate = (len(matched) / n_gt * 100) if n_gt else 0.0
    summary = [
        f"# {manifest.get('run', out_dir.name)}",
        "",
        f"- ground truth: `{manifest.get('gt_dir')}`",
        f"- predictions: `{manifest.get('pred_dir')}`",
        f"- matched {len(matched)}/{n_gt} ({rate:.2f}%)",
        f"- samples quantised to 3 decimals (as since 0.2.9); means shown to {digits}",
        "",
        _table(modes, digits),
        "",
        "`lp` is a distance - lower is better. Every other column is a score.",
        "",
        "| mode | meaning |", "|---|---|",
        *(f"| {m} | {MODE_LABEL[m]} |" for m in MODES if m in modes),
    ]
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n")

    try:
        import pandas as pd

        pd.DataFrame(
            [[mode] + [round(modes[mode][m], digits) for m in METRICS]
             for mode in MODES if mode in modes],
            columns=["mode"] + METRICS,
        ).to_excel(out_dir / "summary.xlsx", index=False)
    except ImportError:      # pandas/openpyxl are optional for a JSON-only run
        pass

    manifest = dict(manifest)
    manifest.update({"matched": len(matched), "missing": len(black),
                     "success_rate": round(rate, 2), "digits": digits})
    (out_dir / "run.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    return out_dir
