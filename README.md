# widget2code-bench

Benchmark evaluation for widget code generation — 12 quality metrics across layout, legibility, perceptual, style, and geometry.

## Installation

```bash
pip install widget2code-bench
```

## Usage

```bash
widget2code-bench \
  --gt_dir /path/to/GT \
  --pred_dir /path/to/predictions \
  --pred_name output.png
```

### Directory Structure

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
| `--gt_dir` | (required) | GT directory (flat image files) |
| `--pred_dir` | (required) | Prediction directory (subfolders) |
| `--pred_name` | `output.png` | Prediction filename inside each subfolder |
| `--output_dir` | `{pred_dir}/.analysis` | Statistics output directory |
| `--workers` | 4 | Parallel threads |
| `--cuda` | off | Enable GPU |
| `--skip_eval` | off | Skip evaluation, only generate statistics |

## Pipeline

1. **Evaluation** — Computes 12 quality metrics for each GT-prediction pair
2. **Statistics** — Aggregates results into `metrics_stats.json` and `metrics.xlsx`

## License

Apache-2.0
