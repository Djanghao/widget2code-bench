---
name: w2c-bench
description: >-
  Score generated widget images against their ground truth with the frozen
  widget2code benchmark - 12 metrics across geometry, layout, legibility, style
  and perceptual similarity. Use when evaluating a widget-generation model,
  comparing runs, computing a training reward from image similarity, or reading
  an existing run directory. Covers pulling the image, the two modes (batch and
  single), device selection, the reward daemon, and every parameter.
---

# w2c-bench

Compares a generated widget image against its ground truth. Two of the twelve
metrics are neural networks, so a value only means something together with the
environment that produced it: the dependency versions and the model weights are
frozen into one image, and the container verifies all twelve against golden
values before it serves.

## Two modes

| Mode | Arguments | Use it to |
|---|---|---|
| **batch** | `--gt_dir` + `--pred_dir` | score a directory of predictions, produce one run directory of tables |
| **single** | `--gt_image` + `--pred_image` | score one pair, print JSON, write nothing |

Everything else is deployment. The reward daemon (below) is single mode served
over a socket, not a third mode.

## Deploy

```bash
docker pull houstonzhang/w2c-bench:latest
```

## Batch

Ground truth is one directory per sample, as published in
[`Djanghao/Widget2Code-Data`](https://huggingface.co/datasets/Djanghao/Widget2Code-Data):
`image_0001/image.png` with `metadata.json` beside it. Predictions are
subdirectories with the same 4-digit ids; `--pred_name` may be a path relative
to the subdirectory, such as `sft_render/rendered.png`.

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp --gpus '"device=0"' \
  -v /path/to/gt:/gt:ro -v /path/to/pred:/pred:ro -v /path/to/runs:/runs \
  houstonzhang/w2c-bench:latest widget2code-bench-exp \
  --gt_dir /gt --pred_dir /pred --pred_name rendered.png \
  --out /runs --cuda --workers 8
```

The explicit `widget2code-bench-exp` works on every image version; from 1.1.0
the entrypoint also accepts the flags directly.

| flag | default | meaning |
|---|---|---|
| `--gt_dir` | — | ground truth, one directory per sample |
| `--pred_dir` | — | predictions, one directory per sample; never written to |
| `--pred_name` | `output.png` | the prediction file inside each directory, relative paths fine |
| `--out` | `<pred_dir>/../runs` | directory that holds run directories |
| `--run-name` | `<pred_dir>_<UTC stamp>` | this run's directory, so runs never collide |
| `--decimals` | `4` | digits in the rendered tables |
| `--workers` | `4` | concurrent pairs |
| `--cuda` | off | GPU for LPIPS and OCR (first visible device) |
| `--device N` | — | pin to GPU N; implies `--cuda` |

One run writes one self-contained directory and touches nothing else:

```
<out>/<run-name>/
  run.json        what produced it: paths, workers, image stamp, timing, errors
  samples.jsonl   one line per sample
  metrics.json    per-mode means plus quartiles
  summary.md      the table, to --decimals
  summary.csv     the same table - metrics across the columns, one row per mode
  summary.xlsx
```

Comparing models means putting run directories side by side - one row per run,
metrics across the columns:

```bash
tools/compare_runs.py runs/step25_* runs/step40_* runs/step55_* --mode zero --out comparison.csv
```

`--mode zero` (the default) counts missing predictions at their worst value, so
a model cannot look good by failing on the hard cases; `--mode all` emits every
mode per run.

### One evaluation, one GPU — parallelise by folder

A batch run is one process on one card: `--cuda` puts LPIPS and OCR on the
first visible device, `--device N` (bare metal) or docker's `--gpus
'"device=N"'` chooses which. To evaluate several models at once, give each
prediction folder its own card:

```bash
for i in 0 1 2 3; do
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp --gpus "\"device=$i\"" \
    -v /data/test:/gt:ro -v /eval/model_$i:/pred:ro -v /eval/runs:/runs \
    houstonzhang/w2c-bench:latest widget2code-bench-exp \
    --gt_dir /gt --pred_dir /pred --pred_name rendered.png \
    --out /runs --cuda --workers 8 &
done; wait
```

Measured on an H200: ~3 pairs/s per card at `--cuda --workers 8`, so a
1,000-sample split is roughly five minutes per model, and four models on four
cards still five minutes.

## Single

```bash
docker run --rm -v /data:/data houstonzhang/w2c-bench:latest \
  widget2code-bench-exp --gt_image /data/gt.png --pred_image /data/pred.png \
  --metrics ssim,layout,style,contrast --json-only
```

`--metrics` takes groups (`geometry`, `perceptual`, `layout`, `legibility`,
`style`), leaves (`ssim`, `lpips`, `contrast`, `palette`, …) or `all`. Only what
is asked for is computed: an SSIM request never constructs LPIPS, a contrast
request never constructs an OCR reader. Measured 0.76s against 47s for `all`.

## The daemon, for training rewards

Single mode over a Unix socket - one pair, many times, low latency. Run with no
arguments the image self-checks and serves:

```bash
docker run -d --name w2c-bench --restart unless-stopped --init \
  --user "$(id -u):$(id -g)" -e HOME=/tmp -e USER=w2c \
  -e W2C_BENCH_WORKERS=32 \
  -v /tmp/w2c-bench:/tmp/w2c-bench \
  houstonzhang/w2c-bench:latest
```

| what | why it is there |
|---|---|
| `--user $(id -u):$(id -g)` | the socket has to be connectable by the caller |
| `-e USER=w2c` | a numeric uid absent from the container's passwd breaks `getpass.getuser()` on import |
| `-e HOME=/tmp` | matplotlib and torch want a writable home |
| `-v /tmp/w2c-bench` | the only mount: images cross the socket as bytes, so no host path is shared |

Readiness: `/tmp/w2c-bench/bench.sock` exists and `heartbeat.json` updates.
Environment: `W2C_BENCH_WORKERS` (default 8) processes, `W2C_BENCH_CUDA=1` for
GPU. Throughput is bounded by workers, not client concurrency: measured 0.76s
per reward call, so 32 workers serve roughly 40 calls a second. Reward metrics
(`ssim`, `layout`, `style`, `contrast`) never touch a neural net, and CPU is the
only path promised to reproduce across machines.

```python
from widget2code_bench.bench_client import BenchClient

async with BenchClient() as client:
    scores = await client.evaluate(gt_path, pred_path,
                                   metrics="ssim,layout,style,contrast")
```

The client retries a missing or restarting daemon forever rather than raising,
so a stopped daemon pauses the caller instead of yielding a wrong number. Bad
input raises `BenchEvaluationError` immediately: that is an answer, not an
outage.

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

The published dataset ships these fill scores precomputed in each sample's
`metadata.json` (built by `tools/build_metadata.py` from the evaluator's own
functions), and a batch run reads them instead of recomputing - the console
reports how many it read. Each record carries the image's sha256; a mismatch
means the cache is stale, and that sample is recomputed rather than trusted.

## Troubleshooting

| symptom | cause |
|---|---|
| `holds loose PNGs and no <id>/image.png` | the path is the pre-1.0 flat layout |
| `[FATAL tini] exec --gt_dir failed` | pre-1.1.0 image without the CLI entrypoint: put `widget2code-bench-exp` before the flags |
| socket missing, container exited | the self-check failed; `docker logs w2c-bench` |
| throughput flat as concurrency rises | worker count, not client concurrency |
| numbers differ from another machine | compare image digests; `--cuda` is not promised across GPU architectures |

Pin the digest, not the tag, when a run has to be provably the same evaluator.
