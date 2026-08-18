#!/usr/bin/env python3
"""Check that a built cache still equals what recomputing would produce.

The cache is only worth having if reading it is indistinguishable from doing the
work, so this recomputes every ground-truth intermediate and compares leaf by
leaf with no tolerance. Two things can break that and neither is visible by
inspection: JSON can lose the last bits of a float, and an image can be replaced
without its metadata being rebuilt.

    tools/verify_metadata.py --meta DIR [--limit N]

Exit status is 0 when every sample matches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build_metadata import gt_layout, gt_legibility, gt_style, gt_fill  # noqa: E402
from widget_quality.utils import load_image                             # noqa: E402
from widget_quality.perceptual import set_device                        # noqa: E402


def differences(stored, fresh, path=""):
    """Every leaf where the two disagree, as (path, stored, fresh)."""
    if isinstance(stored, dict):
        for key in stored:
            if key not in fresh:
                yield f"{path}.{key}", stored[key], "<missing>"
            else:
                yield from differences(stored[key], fresh[key], f"{path}.{key}")
    elif isinstance(stored, list):
        if len(stored) != len(fresh):
            yield path, f"len {len(stored)}", f"len {len(fresh)}"
        else:
            for i, (a, b) in enumerate(zip(stored, fresh)):
                yield from differences(a, b, f"{path}[{i}]")
    elif stored != fresh:
        yield path, stored, fresh


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meta", type=Path, required=True, help="directory of <id>/metadata.json")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cuda", action="store_true",
                    help="recompute on the GPU; only meaningful if the cache was built there")
    ap.add_argument("--show", type=int, default=4)
    args = ap.parse_args()

    set_device(use_cuda=args.cuda)
    import easyocr
    from widget_quality import legibility
    legibility._reader = easyocr.Reader(["en"], gpu=args.cuda)

    paths = sorted(args.meta.glob("*/metadata.json"))[:args.limit]
    if not paths:
        print(f"no metadata.json under {args.meta}")
        return 1

    mismatched = stale = 0
    for path in paths:
        meta = json.loads(path.read_text())
        image = path.parent / "image.png"
        sample = path.parent.name

        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if digest != meta["sha256"]:
            stale += 1
            print(f"  {sample}: image does not match the sha256 the cache was built from")
            continue

        gt = load_image(str(image))
        fresh = {"layout": gt_layout(gt), "legibility": gt_legibility(gt),
                 "style": gt_style(gt), "fill": gt_fill(gt)}
        diffs = list(differences(meta["eval"], fresh))
        if diffs:
            mismatched += 1
            print(f"  {sample}: {len(diffs)} leaves differ")
            for where, stored, got in diffs[:args.show]:
                print(f"      {where}: stored={stored!r} recomputed={got!r}")

    ok = len(paths) - mismatched - stale
    print(f"\n{len(paths)} samples: {ok} identical, {mismatched} differing, {stale} stale")
    return 0 if (mismatched == 0 and stale == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
