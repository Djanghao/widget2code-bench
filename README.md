# widget2code-bench-exp

**Version:** `0.2.9` · Requires Python `>=3.9`

Benchmark evaluation for widget code generation — 12 quality metrics across layout, legibility, perceptual, style, and geometry.

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
pip install widget2code-bench-exp==0.2.9
```

> **Note:** PyPI only ships CPU-only PyTorch. To use `--cuda`, you must install PyTorch from the [official index](https://pytorch.org/get-started/locally/) **before** installing this package.

## Usage

### Single image mode

Evaluate one GT-prediction pair. Prints JSON results to stdout, no files saved.

```bash
widget2code-bench-exp \
  --gt_image /path/to/gt.png \
  --pred_image /path/to/pred.png \
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
