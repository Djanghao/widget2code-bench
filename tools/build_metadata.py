#!/usr/bin/env python3
"""Precompute the GT-only half of the evaluation and write it beside each image.

Scoring a prediction pair splits cleanly in two. One half depends on the ground
truth alone - its OCR, its edge mask, its hue and saturation histograms, and the
black/white fill scores used when a prediction is missing - and is recomputed
from scratch by every run of every model. The other half (SSIM and LPIPS against
the prediction) genuinely needs both images.

This writes the first half out once, so a run can read it instead. The values
come from calling the evaluator's own functions in its own order, not from a
parallel implementation, because a reimplementation can drift on a dtype or an
empty-mask branch in a way that only three images out of a thousand reveal.

    tools/build_metadata.py --images DIR --out DIR --split test [--cuda]

Each sample becomes <out>/<id>/{image.png, metadata.json}. metadata.json carries
the image's sha256: the cache is only valid for the bytes it was built from, and
a run that finds a mismatch must fail rather than quietly score against stale
intermediates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
from skimage.color import rgb2gray, rgb2hsv

from widget_quality.utils import load_image, edge_map, margin_from_mask, \
    remove_border_touching_components
from widget_quality.legibility import ocr_text_easyocr, contrast_ratio, \
    local_contrast_from_text_regions, compute_legibility
from widget_quality.perceptual import compute_perceptual, set_device
from widget_quality.layout import compute_layout
from widget_quality.style import compute_style
from widget_quality.geometry import compute_aspect_dimensionality_fidelity


def _f(x):
    return None if x is None else float(x)


def gt_layout(gt):
    """The GT branch of compute_layout, reduced to what the metric consumes."""
    mask = remove_border_touching_components(
        cv2.dilate(edge_map(gt), np.ones((3, 3), np.uint8)))
    _, _, stats, _ = cv2.connectedComponentsWithStats(
        (mask > 0).astype(np.uint8), connectivity=8)
    areas = np.array([w * h for x, y, w, h, a in stats[1:] if a > 10])
    if mask.any():
        ys, xs = np.where(mask > 0)
        bh, bw = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
        bbox_ar = bw / bh if bh > 0 else 1.0
    else:
        bbox_ar = None
    return {
        "margin": [int(v) for v in margin_from_mask(mask)],
        "mask_empty": bool(mask.sum() == 0),
        "bbox_ar": _f(bbox_ar),
        "area_ratio": _f(areas.mean() / areas.sum()) if len(areas) else None,
        "n_comp": int(len(areas)),
    }


def gt_legibility(gt):
    text, results = ocr_text_easyocr(gt)
    return {
        "text": text,
        "contrast": _f(np.nan_to_num(contrast_ratio(gt))),
        "contrast_local": _f(local_contrast_from_text_regions(gt, results)),
        "ocr": [[[[_f(c) for c in pt] for pt in box], txt, _f(conf)]
                for box, txt, conf in results],
    }


def gt_style(gt):
    """The GT histograms, kept unnormalised: the metric divides by their sum."""
    hsv = rgb2hsv(gt)
    hue, _ = np.histogram(hsv[..., 0].ravel(), bins=36, range=(0, 1), density=True)
    sat, _ = np.histogram(hsv[..., 1].ravel(), bins=30, range=(0, 1), density=True)
    flat = np.sort(rgb2gray(gt).ravel())
    k = max(1, int(0.1 * flat.size))
    bg, dark, bright = np.median(flat), np.mean(flat[:k]), np.mean(flat[-k:])
    fg = dark if abs(bg - dark) >= abs(bg - bright) else bright
    contrast = bg - fg
    return {
        "hue_hist": [_f(v) for v in hue],
        "sat_hist": [_f(v) for v in sat],
        "polarity": [_f(np.sign(contrast)), _f(abs(contrast))],
    }


def gt_fill(gt):
    """Black and white fill score the GT against a constant image, so both are
    fixed by the GT alone. Stored before composite_score's rounding, so a
    compatibility mode and a full-precision mode can both be derived from it."""
    out = {}
    for name, img in (("black", np.zeros_like(gt)), ("white", np.ones_like(gt))):
        out[name] = {
            "geo": _f(compute_aspect_dimensionality_fidelity(gt, img)),
            "perceptual": {k: _f(v) for k, v in compute_perceptual(gt, img).items()},
            "layout": {k: _f(v) for k, v in compute_layout(gt, img).items()},
            "legibility": {k: _f(v) for k, v in compute_legibility(gt, img).items()},
            "style": {k: _f(v) for k, v in compute_style(gt, img).items()},
        }
    return out


def build_one(src: Path, dst_dir: Path, split: str, category, has_chart):
    dst_dir.mkdir(parents=True, exist_ok=True)
    image_out = dst_dir / "image.png"
    if not image_out.exists():
        shutil.copy(src, image_out)

    gt = load_image(str(src))
    h, w = gt.shape[:2]
    meta = {
        "id": dst_dir.name,
        "split": split,
        "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "size": [int(w), int(h)],
        "category": category,
        "has_chart": has_chart,
        "eval": {
            "layout": gt_layout(gt),
            "legibility": gt_legibility(gt),
            "style": gt_style(gt),
            "fill": gt_fill(gt),
        },
    }
    (dst_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return dst_dir.name


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", type=Path, required=True, help="flat directory of GT pngs")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--categories", type=Path, default=None,
                    help="directory of <category>/<id>.png, e.g. train_cls")
    ap.add_argument("--chart-list", type=Path, default=None,
                    help="directory whose filenames mark the chart-bearing ids, e.g. sub_charts")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--cuda", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    set_device(use_cuda=args.cuda)
    import easyocr
    from widget_quality import legibility
    legibility._reader = easyocr.Reader(["en"], gpu=args.cuda)

    category = {}
    if args.categories:
        for cat_dir in sorted(p for p in args.categories.iterdir() if p.is_dir()):
            for f in cat_dir.iterdir():
                category[f.stem] = cat_dir.name
    chart_ids = None
    if args.chart_list:
        chart_ids = {p.stem for p in args.chart_list.glob("*.png")}

    srcs = sorted(args.images.glob("*.png"))
    if args.limit:
        srcs = srcs[:args.limit]
    # Longest first: the pool's wall clock is set by whatever is still running
    # when everything else has drained, and these images span 9 kPx to 12.8 MPx.
    srcs.sort(key=lambda p: p.stat().st_size, reverse=True)

    todo = [p for p in srcs if not (args.out / p.stem / "metadata.json").exists()]
    print(f"{len(srcs)} images, {len(srcs) - len(todo)} already built, {len(todo)} to do",
          flush=True)

    t0 = time.time()
    done = failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(build_one, p, args.out / p.stem, args.split,
                        category.get(p.stem),
                        None if chart_ids is None else (p.stem in chart_ids)): p
            for p in todo
        }
        for fut in as_completed(futures):
            src = futures[fut]
            try:
                fut.result()
                done += 1
            except Exception as exc:                       # one bad image must not sink the batch
                failed += 1
                print(f"  FAILED {src.name}: {exc}", flush=True)
            if done % 25 == 0 or done + failed == len(todo):
                rate = done / max(time.time() - t0, 1e-9)
                left = (len(todo) - done - failed) / max(rate, 1e-9)
                print(f"  {done + failed}/{len(todo)}  {rate:.1f}/s  eta {left/60:.1f}min",
                      flush=True)

    print(f"\nbuilt {done}, failed {failed}, {time.time() - t0:.0f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
