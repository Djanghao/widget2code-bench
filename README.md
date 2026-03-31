# Widget Eval

Evaluation pipeline for widget generation — runs [widget-quality](https://github.com/WebAgent-Arena/widget-quality) metrics and generates statistics reports.

## Installation

```bash
pip install widget-eval
```

## Usage

```bash
# Basic usage (CPU)
widget-eval --gt_dir /path/to/GT --pred_dir /path/to/results

# Use GPU
widget-eval --gt_dir /path/to/GT --pred_dir /path/to/results --cuda

# Skip evaluation, only generate statistics
widget-eval --gt_dir /path/to/GT --pred_dir /path/to/results --skip_eval

# Custom output directory and workers
widget-eval --gt_dir /path/to/GT --pred_dir /path/to/results --output_dir /path/to/stats --workers 8
```

## Pipeline

1. **Evaluation** — Computes 12 quality metrics (layout, legibility, style, perceptual, geometry) for each GT-prediction pair
2. **Statistics** — Aggregates results into `metrics_stats.json` and `metrics.xlsx`

## License

Apache-2.0
