# widget2code-bench

Benchmark evaluation for widget code generation — 12 quality metrics across layout, legibility, perceptual, style, and geometry.

## Installation

```bash
# 1. Install PyTorch with CUDA support first (skip if CPU-only)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

# 2. Install widget2code-bench
pip install widget2code-bench
```

> **Note:** PyPI only ships CPU-only PyTorch. To use `--cuda`, you must install PyTorch from the [official index](https://pytorch.org/get-started/locally/) **before** installing this package.

## Usage

### Single image mode

Evaluate one GT-prediction pair. Prints JSON results to stdout, no files saved.

```bash
widget2code-bench \
  --gt_image /path/to/gt.png \
  --pred_image /path/to/pred.png \
  --cuda
```

### Batch mode

Evaluate all matched pairs in directories.

```bash
widget2code-bench \
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
| `--skip_eval` | off | Skip evaluation, only generate statistics |
| `--no_fill` | off | Disable fill-image evaluation for missing predictions (fill is on by default) |

## Output (batch mode)

1. **Evaluation** — Saves `evaluation.json` in each prediction subfolder + `evaluation.xlsx` in pred_dir
2. **Statistics** — Saves `metrics_stats.json` and `metrics.xlsx` to `{pred_dir}/.analysis/`

### Handling missing predictions (fill mode, default)

When a GT image has no matching prediction, the evaluator also scores it against synthetic
fill images so the summary xlsx can show how different assumptions about missing samples
affect the aggregate metrics. Each summary xlsx contains **one row per run**, with metric
values slash-joined across fill modes.

**All predictions present** — row label `<run>`, each cell is a single value:

```
<run>  34.25  17.113  43.526  ...  99.77  100.0%
```

**Some predictions missing** — row label `<run>:raw/black/white/zero`, each cell carries
four slash-joined means in that order:

```
<run>:raw/black/white/zero  30.826/31.996/31.996/29.778  ...  95.145/95.31/95.31/91.91  96.6%
```

The four fill modes:

| Mode | Description |
|------|-------------|
| `raw`   | Matched pairs only (missing skipped) |
| `black` | Missing preds scored against an all-black image |
| `white` | Missing preds scored against an all-white image |
| `zero`  | Missing preds contribute the worst-case value (LPIPS = 1.0, others = 0) |

A single `SuccessRate` column is appended after `Geometry`, showing matched / total as a
percentage string (e.g. `96.6%`). Pass `--no_fill` to disable fill-image evaluation (only
the raw mode is reported and missing preds are skipped).

All metrics are **higher-is-better** except `lp` (LPIPS), which is a distance (lower-is-better).

## License

Apache-2.0