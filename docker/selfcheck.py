"""Verify the frozen dependency stack and all 12 public benchmark metrics."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
GOLDEN_JSON = HERE / "golden.json"
VERSIONS_JSON = HERE / "versions.json"


def _canary_pair(root: Path, variant: int) -> tuple[Path, Path]:
    height, width = (192, 256)
    background = 245 if variant == 0 else 28
    foreground = (24, 72, 132) if variant == 0 else (210, 170, 55)
    gt = np.full((height, width, 3), background, dtype=np.uint8)
    pred = gt.copy()
    cv2.rectangle(gt, (18, 20), (237, 171), foreground, -1)
    cv2.rectangle(pred, (22, 23), (233, 168), foreground, -1)
    cv2.circle(gt, (68, 78), 25, (230, 90, 50), -1)
    cv2.circle(pred, (72, 80), 23, (220, 100, 55), -1)
    cv2.putText(gt, "Widget 42", (98, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255 - background,) * 3, 1, cv2.LINE_AA)
    cv2.putText(pred, "Widget 42", (98, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255 - background,) * 3, 1, cv2.LINE_AA)
    cv2.line(gt, (38, 130), (216, 130), (50, 170, 90), 4)
    cv2.line(pred, (42, 132), (211, 132), (55, 165, 95), 4)
    gt_path = root / f"gt-{variant}.png"
    pred_path = root / f"pred-{variant}.png"
    if not cv2.imwrite(str(gt_path), gt) or not cv2.imwrite(str(pred_path), pred):
        raise RuntimeError("could not write self-check images")
    return gt_path, pred_path


def installed_versions() -> dict[str, str]:
    return {
        str(dist.metadata["Name"]): dist.version
        for dist in importlib.metadata.distributions()
    }


def _normalise_versions(versions: dict[str, str]) -> dict[str, str]:
    return {
        name.lower().replace("_", "-").replace(".", "-"): version
        for name, version in versions.items()
    }


def scores(*, use_cuda: bool) -> dict:
    from widget2code_bench.single import evaluate_single

    with tempfile.TemporaryDirectory(prefix="w2c-bench-selfcheck-") as tmp:
        root = Path(tmp)
        return {
            f"canary-{variant}": evaluate_single(
                *_canary_pair(root, variant), metrics="all", use_cuda=use_cuda
            )
            for variant in (0, 1)
        }


def _marker() -> Path:
    runtime = Path(os.environ.get("W2C_BENCH_RUNTIME_DIR", "/tmp/w2c-bench"))
    device = "cuda" if os.environ.get("W2C_BENCH_CUDA") == "1" else "cpu"
    return runtime / f"selfcheck-ok-{os.environ.get('W2C_BENCH_STAMP', 'dev')}-{device}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--make-golden", action="store_true")
    parser.add_argument("--cached", action="store_true")
    parser.add_argument("--cuda", action="store_true")
    parser.add_argument("--out", type=Path, default=GOLDEN_JSON)
    args = parser.parse_args()
    if args.cached and _marker().exists():
        print(f"selfcheck: already proven ({_marker().name})", flush=True)
        return 0

    expected_versions = _normalise_versions(json.loads(VERSIONS_JSON.read_text()))
    actual_versions = _normalise_versions(installed_versions())
    if actual_versions != expected_versions:
        print(f"selfcheck: dependency mismatch\nwant={expected_versions}\n got={actual_versions}", file=sys.stderr)
        return 1
    current = scores(use_cuda=args.cuda)
    if args.make_golden:
        args.out.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"selfcheck: recorded {len(current)} canaries to {args.out}")
        return 0
    expected = json.loads(GOLDEN_JSON.read_text())
    if current != expected:
        print("selfcheck: metric mismatch; refusing to serve", file=sys.stderr)
        print(json.dumps({"expected": expected, "actual": current}, indent=2), file=sys.stderr)
        return 1
    print(f"selfcheck: versions exact; {len(current)}/{len(current)} metric canaries exact", flush=True)
    if args.cached:
        _marker().parent.mkdir(parents=True, exist_ok=True)
        _marker().touch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
