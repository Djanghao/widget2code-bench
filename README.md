# widget2code-bench-exp

**Version:** `1.0.0` · Metric-compatible with `0.2.9` · Requires Python `>=3.9`

Benchmark evaluation for widget code generation — 12 quality metrics across layout, legibility, perceptual, style, and geometry.

## Docker (recommended)

The metrics run two neural networks, so their values depend on the numeric stack
underneath them. The image freezes that stack — Python, NumPy, OpenCV,
scikit-image, torch, and both networks' weights — and pins every library to one
thread, because BLAS and OpenCV change their reduction order with the thread
count.

[![Docker Hub](https://img.shields.io/badge/docker-houstonzhang%2Fw2c--bench-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/houstonzhang/w2c-bench)

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v /path/to/GT:/gt -v /path/to/predictions:/pred \
  houstonzhang/w2c-bench:1.0.0 widget2code-bench-exp \
  --gt_dir /gt --pred_dir /pred --pred_name output.png --workers 32
```

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

### Shared single-pair service (training reward)

Like `widget2code-render`, the image normally runs a supervised Unix-socket
daemon. It mounts only `/tmp/w2c-bench`; both images travel over the socket, so
the evaluator never sees or mounts the training repository or dataset.

```bash
W2C_BENCH_IMAGE=houstonzhang/w2c-bench:1.0.0 docker/run.sh 8
```

```python
from widget2code_bench.bench_client import BenchClient

async with BenchClient() as bench:
    scores = await bench.evaluate(
        "target.png", "rendered.png",
        metrics="ssim,layout,style,contrast",
    )
```

The pure-stdlib client waits across daemon restarts. The daemon has the same
heartbeat/supervisor contract as `widget2code-render`; a single invalid image
returns an evaluation error without taking the service down. Startup checks the
installed dependency manifest and two golden pairs across all 12 metrics before
creating the socket.

CPU mode is the reproducible default. For GPU mode use one worker per GPU unless
memory measurements justify more:

```bash
W2C_BENCH_CUDA=1 docker/run.sh 1
```

The frozen image versions include Python 3.12.14, torch 2.11.0+cu130,
torchvision 0.26.0+cu130, EasyOCR 1.7.2, LPIPS 0.1.4, NumPy 2.4.4,
OpenCV 4.13.0.92, Pillow 12.2.0, and scikit-image 0.26.0. The full checked
manifest is [`docker/versions.json`](docker/versions.json).

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
pip install widget2code-bench-exp==1.0.0
```

> **Note:** PyPI only ships CPU-only PyTorch. To use `--cuda`, you must install PyTorch from the [official index](https://pytorch.org/get-started/locally/) **before** installing this package.

## Usage

### Single image mode

Evaluate one GT-prediction pair. Prints JSON results to stdout, no files saved.

```bash
widget2code-bench-exp \
  --gt_image /path/to/gt.png \
  --pred_image /path/to/pred.png \
  --metrics ssim,geometry,contrast \
  --json-only \
  --cuda
```

### Batch mode

Evaluate all matched pairs in directories.

```bash
widget2code-bench-exp \
  --gt_dir /path/to/GT \ # /shared/zhixiang_team/widget_research/Comparison/GT
  --pred_dir /path/to/predictions \
  --pred_name output.png \
  --cuda
```

### Directory Structure (batch mode)

- **GT dir**: flat image files with 4-digit IDs in filenames (e.g. `gt_0001.png`)
- **Pred dir**: subfolders with 4-digit IDs in names, each containing `--pred_name` file

```
gt_dir/                     pred_dir/
  gt_0001.png                 image_0001/
  gt_0002.png                   output.png
  ...                         image_0002/
                                output.png
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--gt_image` | — | Single GT image path |
| `--pred_image` | — | Single prediction image path |
| `--metrics` | `all` | Single mode only: comma-separated groups/leaves |
| `--json-only` | off | Single mode only: emit machine-readable JSON only |
| `--gt_dir` | — | GT directory (flat image files) |
| `--pred_dir` | — | Prediction directory (subfolders) |
| `--pred_name` | `output.png` | Prediction filename inside each subfolder |
| `--output_dir` | `{pred_dir}/.analysis` | Statistics output directory |
| `--workers` | 4 | Parallel threads |
| `--cuda` | off | Enable GPU |
| `--skip_eval` | off | Skip evaluation, only regenerate statistics xlsx files from existing `evaluation.json` |
| `--minimal` | off | Skip per-metric visualization PNGs (default: verbose with viz) |

## Output (batch mode)

### Per-sample outputs

Every matched pair writes one `evaluation.json` plus (by default) a full per-metric
visualization set into its sample folder:

```
<pred_dir>/
  image_0001/
    output.png
    evaluation/
      evaluation.json                 # 12 metrics
      viz/
        MarginAsymmetry.png
        ContentAspectDiff.png
        AreaRatioDiff.png
        TextJaccard.png
        ContrastDiff.png
        ContrastLocalDiff.png
        PaletteDistance.png
        Vibrancy.png
        PolarityConsistency.png
        ssim.png
        lp.png
        geo_score.png
```

Each viz PNG shows **left/middle = GT/Pred intermediates** and **right = formula +
intermediate values + final score**, so you can see exactly how the metric was computed.

Pass `--minimal` to skip the `viz/` directory (much faster, ~10x less disk).

### Missing-prediction handling

The evaluator always produces all four fill modes. When a GT image has no matching
prediction:

- Existing subfolder, pred missing → fill results go in the same folder's `evaluation/`
- No subfolder at all → evaluator creates `pred_dir/fill_<id>/evaluation/`

In either case it writes:

```
evaluation/
  evaluation_black.json   # GT vs all-black image
  evaluation_white.json   # GT vs all-white image
```

`zero` fill isn't a per-sample file — it's a worst-case contribution (LPIPS = 1.0, others = 0)
used only when aggregating the combined summary.

### Aggregate outputs (`.analysis/`)

```
<pred_dir>/.analysis/
  metrics_stats.json                 # per-metric quartiles/mean/std over matched pairs
  metrics.xlsx                       # 4-row combined summary (raw/black/white/zero)
  raw/<run>-raw-<ver>.xlsx           # single-row summary per mode
  black/<run>-black-<ver>.xlsx
  white/<run>-white-<ver>.xlsx
  zero/<run>-zero-<ver>.xlsx
```

| Mode | Description |
|------|-------------|
| `raw`   | Matched pairs only (missing skipped) |
| `black` | Missing preds scored against an all-black image |
| `white` | Missing preds scored against an all-white image |
| `zero`  | Missing preds contribute the worst-case value (LPIPS = 1.0, others = 0) |

All numeric values are rounded to **2 decimals**. Combined `metrics.xlsx` has a two-level
header grouping metrics by category (Layout / Legibility / Style / Perceptual / Geometry)
plus `SuccessRate` (`ratio`, `count`). Per-mode xlsx uses flat single-level headers.

All metrics are **higher-is-better** except `lp` (LPIPS), which is a distance (lower-is-better).

## License

Apache-2.0
