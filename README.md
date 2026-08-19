# widget2code-bench-exp

**Version:** `1.1.0` · Metric-compatible with `0.2.9` · Requires Python `>=3.9`

Benchmark evaluation for widget code generation — 12 quality metrics across layout, legibility, perceptual, style, and geometry.

There are exactly two ways to use the evaluator:

| Mode | Arguments | What it does |
|---|---|---|
| **batch** | `--gt_dir` + `--pred_dir` | score a directory of predictions, write one run directory |
| **single** | `--gt_image` + `--pred_image` | score one pair, print JSON, write nothing |

## Docker (recommended)

The metrics run two neural networks, so their values depend on the numeric stack
underneath them. The image freezes that stack — Python, NumPy, OpenCV,
scikit-image, torch, and both networks' weights — and pins every library to one
thread, because BLAS and OpenCV change their reduction order with the thread
count.

[![Docker Hub](https://img.shields.io/badge/docker-houstonzhang%2Fw2c--bench-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/houstonzhang/w2c-bench)

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp --gpus '"device=0"' \
  -v /path/to/GT:/gt:ro -v /path/to/predictions:/pred:ro -v /path/to/runs:/runs \
  houstonzhang/w2c-bench:1.1.0 widget2code-bench-exp \
  --gt_dir /gt --pred_dir /pred --pred_name output.png \
  --out /runs --cuda --workers 8
```

Inside a container, pick the card with docker's `--gpus '"device=N"'`; the
container then sees exactly one GPU and `--cuda` uses it. (`--device` is the
bare-metal equivalent — see the options table.) From 1.1.0 the image dispatches
on its arguments — none runs the daemon, `--gt_dir ...` runs the CLI directly —
so the explicit `widget2code-bench-exp` above is optional there, but works with
every version.

On the reference host the container reproduces a direct install of the same
evaluator **bit for bit** (20 samples, 240 metric values, zero differences).
That is a property of a machine rather than a promise, so
[`tools/verify_image.sh`](tools/verify_image.sh) runs the same comparison
wherever you are:

```bash
tools/verify_image.sh 20      # host run, container run, then compare every metric
```

Build and publish it yourself with [`docker/build.sh`](docker/build.sh) and
[`docker/publish.sh`](docker/publish.sh); [`docker/DOCKERHUB.md`](docker/DOCKERHUB.md)
is the registry overview.

The frozen image versions include Python 3.12.14, torch 2.11.0+cu130,
torchvision 0.26.0+cu130, EasyOCR 1.7.2, LPIPS 0.1.4, NumPy 2.4.4,
OpenCV 4.13.0.92, Pillow 12.2.0, and scikit-image 0.26.0. The full checked
manifest is [`docker/versions.json`](docker/versions.json).

### The daemon is a deployment of single mode, not a third mode

Run with no arguments, the image self-checks and serves single-pair evaluations
over a Unix socket — the low-latency transport training reward workers use via
`widget2code_bench.bench_client.BenchClient`. It evaluates exactly what single
mode evaluates; see [SKILL.md](SKILL.md) for deployment.

## Installation (conda env)

If the `widget2code` env already exists, just activate it — no reinstall needed:

```bash
conda activate widget2code
widget2code-bench-exp --help
```

Otherwise, create it once:

```bash
# 1. Create and activate a fresh conda env
conda create -n widget2code python=3.11 -y
conda activate widget2code

# 2. Install PyTorch with CUDA support first (skip if CPU-only)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

# 3. Install widget2code-bench-exp
pip install widget2code-bench-exp
```

> **Note:** PyPI only ships CPU-only PyTorch. To use `--cuda`/`--device`, you must install PyTorch from the [official index](https://pytorch.org/get-started/locally/) **before** installing this package.

## Batch mode

Score every prediction in a directory against its ground truth.

```bash
widget2code-bench-exp \
  --gt_dir /path/to/GT \
  --pred_dir /path/to/predictions \
  --pred_name output.png \
  --device 0 --workers 8
```

One evaluation uses one GPU. To use several cards, run one prediction folder
per card:

```bash
for i in 0 1 2 3; do
  widget2code-bench-exp --gt_dir /data/test --pred_dir /eval/model_$i \
      --pred_name rendered.png --device $i --workers 8 &
done; wait
```

### Directory layout

Ground truth is one directory per sample, as published in
[`Djanghao/Widget2Code-Data`](https://huggingface.co/datasets/Djanghao/Widget2Code-Data);
predictions are subfolders with the same 4-digit ids. `--pred_name` may be a
path relative to the subfolder.

```
gt_dir/                       pred_dir/
  image_0001/                   image_0001/
    image.png                     output.png
    metadata.json                 ...
  image_0002/                   image_0002/
    ...                           output.png
```

### Output — one run directory

A run writes one self-contained directory and touches nothing else; the
prediction directory is read-only, and two runs over the same predictions never
collide.

```
<out>/<run-name>/               # default: <pred_dir>/../runs/<pred_dir>_<UTC stamp>/
  run.json        what produced it: paths, workers, image stamp, timing, errors
  samples.jsonl   one line per matched sample, full precision
  metrics.json    per-mode means plus quartiles
  summary.md      the table, to --decimals
  summary.csv     the same table - metrics across the columns, one row per mode
  summary.xlsx
```

To put several runs side by side - one row per run, metrics across the
columns - merge their run directories:

```bash
tools/compare_runs.py runs/step25_* runs/step40_* runs/step55_* --mode zero --out comparison.csv
```

### Missing predictions

A ground truth with no prediction is scored against an all-black and an
all-white image, so the summary can show what different assumptions about
failures do to the aggregate. `metrics.json` carries four modes plus a success
rate; compare runs on the same mode.

| Mode | Meaning |
|------|---------|
| `raw`   | matched pairs only |
| `black` | missing scored against an all-black image |
| `white` | missing scored against an all-white image |
| `zero`  | missing contribute the worst value (LPIPS = 1.0, others = 0) |

When the ground truth ships precomputed fill scores in `metadata.json` — the
published dataset does — they are read instead of recomputed, validated against
the image's sha256. A stale record is recomputed, never trusted.

## Single mode

Evaluate one GT-prediction pair. Prints JSON to stdout, writes nothing.

```bash
widget2code-bench-exp \
  --gt_image /path/to/gt.png \
  --pred_image /path/to/pred.png \
  --metrics ssim,geometry,contrast \
  --json-only
```

`--metrics` takes groups (`geometry`, `perceptual`, `layout`, `legibility`,
`style`), leaves (`ssim`, `lpips`, `contrast`, `palette`, …) or `all`. Only what
is asked for is computed: an SSIM request never constructs LPIPS, a contrast
request never constructs an OCR reader.

## Options

| Flag | Mode | Default | Description |
|------|------|---------|-------------|
| `--gt_dir` | batch | — | GT directory, one subdirectory per sample |
| `--pred_dir` | batch | — | prediction directory (read-only) |
| `--pred_name` | batch | `output.png` | prediction file inside each subfolder |
| `--out` | batch | `<pred_dir>/../runs` | directory that holds run directories |
| `--run-name` | batch | `<pred_dir>_<UTC stamp>` | this run's directory name |
| `--decimals` | batch | `4` | digits in the rendered tables |
| `--workers` | batch | `4` | worker threads |
| `--gt_image` | single | — | one ground truth image |
| `--pred_image` | single | — | one prediction image |
| `--metrics` | single | `all` | comma-separated groups/leaves |
| `--json-only` | single | off | emit machine-readable JSON only |
| `--cuda` | both | off | GPU for LPIPS and OCR (first visible device) |
| `--device N` | both | — | pin to GPU N (implies `--cuda`); one process per card |

All metrics are **higher-is-better** except `lp` (LPIPS), which is a distance (lower-is-better).

## License

Apache-2.0
