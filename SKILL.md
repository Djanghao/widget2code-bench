---
name: w2c-bench
description: >-
  Score generated widget images against their ground truth with the frozen
  widget2code benchmark - 12 metrics across geometry, layout, legibility, style
  and perceptual similarity. Use when evaluating a widget-generation model,
  comparing runs, computing a training reward from image similarity, or reading
  an existing run directory. Covers pulling the image, running the daemon, the
  batch and single-pair CLIs, the Python client, and every parameter.
---

# w2c-bench

Compares a generated widget image against its ground truth. Two of the twelve
metrics are neural networks, so a value only means something together with the
environment that produced it: the dependency versions and the model weights are
frozen into one image, and the container verifies all twelve against golden
values before it serves.

## Which path to use

| Situation | Path |
|---|---|
| Score a directory of predictions, produce tables | batch CLI |
| One pair, some metrics, occasionally | single-pair CLI |
| One pair, many times, low latency (training reward) | daemon + client |

## Deploy

```bash
docker pull houstonzhang/w2c-bench:latest
```

For the batch and single-pair CLIs nothing else is needed. For rewards, run the
daemon:

```bash
docker run -d --name w2c-bench --restart unless-stopped --init \
  --user "$(id -u):$(id -g)" -e HOME=/tmp -e USER=w2c \
  -e W2C_BENCH_WORKERS=32 \
  -v /tmp/w2c-bench:/tmp/w2c-bench \
  houstonzhang/w2c-bench:latest
```

Or from a checkout, which waits until the socket answers:

```bash
docker/run.sh [workers]        # default 8
```

| what | why it is there |
|---|---|
| `--user $(id -u):$(id -g)` | the socket has to be connectable by the caller |
| `-e USER=w2c` | a numeric uid absent from the container's passwd breaks `getpass.getuser()` on import |
| `-e HOME=/tmp` | matplotlib and torch want a writable home |
| `-v /tmp/w2c-bench` | the only mount: images cross the socket as bytes, so no host path is shared |

Readiness: `/tmp/w2c-bench/bench.sock` exists and `heartbeat.json` updates. A
deviation in any dependency version or metric value stops the container instead
of producing numbers that cannot be compared.

## Environment

| variable | default | effect |
|---|---|---|
| `W2C_BENCH_WORKERS` | `8` | processes, i.e. concurrent evaluations |
| `W2C_BENCH_CUDA` | `0` | GPU for LPIPS and OCR |
| `W2C_BENCH_IMAGE` | `w2c-bench:latest` | image `docker/run.sh` starts |

Throughput is bounded by workers, not by client concurrency: measured 0.76s per
reward call, so 32 workers serve roughly 40 calls a second. Reward metrics never
touch CUDA - none of `ssim`, `layout`, `style` or `contrast` uses a neural net.
CPU is also the only path promised to reproduce across machines, since cuDNN
picks kernels by GPU architecture.

## Batch

Ground truth is one directory per sample, as published in
[`Djanghao/Widget2Code-Data`](https://huggingface.co/datasets/Djanghao/Widget2Code-Data):
`image_0001/image.png`. Predictions are subdirectories with the same ids.

```bash
docker run --rm -v /path/to/gt:/gt -v /path/to/pred:/pred -v /path/to/runs:/runs \
  houstonzhang/w2c-bench:latest \
  --gt_dir /gt --pred_dir /pred --pred_name rendered.png \
  --out /runs --workers 32
```

| flag | default | meaning |
|---|---|---|
| `--gt_dir` | — | ground truth, one directory per sample |
| `--pred_dir` | — | predictions, one directory per sample; never written to |
| `--pred_name` | `output.png` | the prediction file inside each directory |
| `--out` | `<pred_dir>/../runs` | directory that holds run directories |
| `--run-name` | `<pred_dir>_<UTC stamp>` | this run's directory, so runs never collide |
| `--decimals` | `4` | digits in the rendered tables |
| `--workers` | `4` | concurrent pairs |
| `--cuda` | off | GPU for LPIPS and OCR |

One run writes one self-contained directory and touches nothing else:

```
<out>/<run-name>/
  run.json        what produced it: paths, workers, image stamp, timing, errors
  samples.jsonl   one line per sample
  metrics.json    per-mode means plus quartiles
  summary.md      the table, to --decimals
  summary.xlsx
```

## Single pair

```bash
docker run --rm -v /data:/data houstonzhang/w2c-bench:latest \
  --gt_image /data/gt.png --pred_image /data/pred.png \
  --metrics ssim,layout,style,contrast --json-only
```

`--metrics` takes groups (`geometry`, `perceptual`, `layout`, `legibility`,
`style`), leaves (`ssim`, `lpips`, `contrast`, `palette`, …) or `all`. Only what
is asked for is computed: an SSIM request never constructs LPIPS, a contrast
request never constructs an OCR reader. Measured 0.76s against 47s for `all`.

## Client, for rewards

```python
from widget2code_bench.bench_client import BenchClient

async with BenchClient() as client:
    scores = await client.evaluate(gt_path, pred_path,
                                   metrics="ssim,layout,style,contrast")
```

The client retries a missing or restarting daemon forever rather than raising,
so a stopped daemon pauses the caller instead of yielding a wrong number - a
reward silently replaced mid-run trains on a different objective without saying
so. Bad input raises `BenchEvaluationError` immediately: that is an answer, not
an outage. Each call takes its own connection, so concurrency is not serialised.

## The 12 metrics

All are 0-100 and higher-is-better **except `lp`** (LPIPS), a 0-1 distance where
lower is better. `ssim` is also on 0-1.

| Group | Metrics | Needs |
|---|---|---|
| Geometry | `geo_score` | aspect ratio and area, on the original sizes |
| Layout | `MarginAsymmetry`, `ContentAspectDiff`, `AreaRatioDiff` | edge mask, CPU |
| Legibility | `TextJaccard`, `ContrastDiff`, `ContrastLocalDiff` | OCR, except `ContrastDiff` |
| Style | `PaletteDistance`, `Vibrancy`, `PolarityConsistency` | hue/saturation histograms, CPU |
| Perceptual | `ssim`, `lp` | `lp` needs the LPIPS network |

Geometry compares the original sizes; every other metric resizes the prediction
to the ground truth first. Sample values are quantised to three decimals, as
they have been since 0.2.9, so a mean is comparable with an older table.

## Missing predictions

A ground truth with no prediction is scored against an all-black and an
all-white image, so a summary can show what different assumptions about failures
do to the aggregate. `metrics.json` carries four modes - `raw`, `black`, `white`,
`zero` - plus a success rate. Compare runs on the same mode.

## Precomputed ground-truth evidence

Each sample in the published dataset ships `metadata.json` beside its image
holding the half of a score that depends on the ground truth alone: its OCR,
edge-mask layout terms, histograms, and the black/white fill scores. Reading
them instead of recomputing them is the difference between evaluating one model
and re-deriving the same evidence for every model. Each record carries the
image's sha256; a mismatch means the cache is stale and must not be used.

## Troubleshooting

| symptom | cause |
|---|---|
| `holds loose PNGs and no <id>/image.png` | the path is the pre-1.0 flat layout |
| socket missing, container exited | the self-check failed; `docker logs w2c-bench` |
| throughput flat as concurrency rises | worker count, not client concurrency |
| numbers differ from another machine | compare image digests; `--cuda` is not promised across GPU architectures |

Pin the digest, not the tag, when a run has to be provably the same evaluator.
