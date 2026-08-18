---
name: widget2code-bench
description: >-
  Score generated widget images against their ground truth with the frozen
  widget2code benchmark - 12 metrics across geometry, layout, legibility, style
  and perceptual similarity. Use when evaluating a widget-generation model,
  comparing runs, computing a training reward from image similarity, or reading
  an existing evaluation.json / metrics.xlsx. Covers the batch CLI, the
  single-pair path, and the long-lived daemon.
---

# widget2code-bench

Compares a generated widget image against its ground truth. Everything runs
inside a published image whose dependency versions and model weights are frozen,
because two of the metrics are neural nets and a value only means something
together with the environment that produced it.

## Which path to use

| Situation | Path |
|---|---|
| Score a directory of predictions, produce tables | batch CLI |
| One pair, some metrics, occasionally | `--gt_image/--pred_image` |
| One pair, many times, low latency (training reward) | daemon + client |

## Batch

Ground truth is a flat directory of images with 4-digit ids; predictions are
subdirectories with the same ids.

```bash
docker run --rm -v /path/to/gt:/gt -v /path/to/pred:/pred \
  houstonzhang/w2c-bench:latest \
  --gt_dir /gt --pred_dir /pred --pred_name rendered.png \
  --output_dir /pred/.analysis --workers 32 --minimal
```

Writes `evaluation.json` per sample and `metrics.xlsx` under `--output_dir`.
Drop `--minimal` to also get per-metric visualisations and worst-case samples.
`--cuda` uses the GPU for the two neural metrics.

## Single pair

```bash
docker run --rm -v /data:/data houstonzhang/w2c-bench:latest \
  --gt_image /data/gt.png --pred_image /data/pred.png \
  --metrics ssim,layout,style,contrast --json-only
```

`--metrics` takes groups (`geometry`, `perceptual`, `layout`, `legibility`,
`style`), leaves (`ssim`, `lpips`, `contrast`, `palette`, …), or `all`. Only
what is asked for is computed: an SSIM request never constructs LPIPS, a
contrast request never constructs an OCR reader. That is the difference between
0.76s and 47s per pair.

## Daemon, for rewards

```bash
docker/run.sh 32                      # or: houstonzhang/w2c-bench:latest
```

Serves `/tmp/w2c-bench/bench.sock`. Clients send image bytes, so no host path
crosses the boundary and the container mounts nothing but its runtime directory.

```python
from widget2code_bench.bench_client import BenchClient

async with BenchClient() as client:
    scores = await client.evaluate(gt_path, pred_path, metrics="ssim,layout,style,contrast")
```

The client retries a missing or restarting daemon forever rather than raising,
so a stopped daemon pauses the caller instead of yielding a wrong number. Bad
input raises `BenchEvaluationError` immediately - that is an answer, not an
outage. Concurrent calls each take their own connection; throughput is bounded
by the daemon's worker count, not by the client.

## The 12 metrics

All are 0-100 and higher-is-better **except `lp`** (LPIPS), a 0-1 distance where
lower is better. `ssim` is also reported on 0-1.

| Group | Metrics | Needs |
|---|---|---|
| Geometry | `geo_score` | aspect ratio and area vs the ground truth |
| Layout | `MarginAsymmetry`, `ContentAspectDiff`, `AreaRatioDiff` | edge mask, CPU |
| Legibility | `TextJaccard`, `ContrastDiff`, `ContrastLocalDiff` | OCR, except `ContrastDiff` |
| Style | `PaletteDistance`, `Vibrancy`, `PolarityConsistency` | hue/saturation histograms, CPU |
| Perceptual | `ssim`, `lp` | `lp` needs the LPIPS network |

Geometry compares the original sizes; every other metric resizes the prediction
to the ground truth first.

## Missing predictions

A ground truth with no prediction is scored against an all-black and an all-white
image, so the summary can show what different assumptions about failures do to
the aggregate. `metrics.xlsx` carries four rows - matched pairs only, plus black,
white and zero fill - and a success rate. Compare runs on the same row.

## Precomputed ground-truth evidence

`Djanghao/Widget2Code-Data` ships `metadata.json` beside each image holding the
half of a score that depends on the ground truth alone: its OCR, edge-mask layout
terms, histograms, and the black/white fill scores. Reading them instead of
recomputing them is the difference between evaluating one model and re-deriving
the same evidence for every model. Each record carries the image's sha256; a
mismatch means the cache is stale and must not be used.

## Determinism

Every process is held to one thread for BLAS, OpenMP and OpenCV, because their
reduction order changes with the thread count and would move the last digits.
Parallelism belongs at the process level. On startup the image verifies its whole
distribution set and all 12 metrics against golden values and refuses to serve on
any deviation, so a machine proves itself rather than being trusted.

The CPU path is the reproducible one. `--cuda` is faster but cuDNN picks kernels
by GPU architecture, so bit-identical results across different cards are not
promised. Reward metrics never touch CUDA - none of `ssim`, `layout`, `style` or
`contrast` uses a neural net.
