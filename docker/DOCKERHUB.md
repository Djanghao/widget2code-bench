# w2c-bench — a widget evaluator whose numbers do not move

Scores a generated UI widget against its ground truth on 12 metrics across five
dimensions — layout, legibility, style, perceptual and geometry. It exists
because a benchmark number has to mean the same thing on every machine and every
month: the whole numeric stack — Python, NumPy, OpenCV, scikit-image, torch, and
the two neural nets the metrics depend on — is frozen inside this image, weights
included.

Published from [Djanghao/widget2code-bench](https://github.com/Djanghao/widget2code-bench).

## Run it

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp --gpus '"device=0"' \
  -v /path/to/GT:/gt:ro -v /path/to/predictions:/pred:ro -v /path/to/runs:/runs \
  houstonzhang/w2c-bench:1.1.0 widget2code-bench-exp \
  --gt_dir /gt --pred_dir /pred --pred_name output.png \
  --out /runs --cuda --workers 8
```

One batch run writes one self-contained run directory (`run.json`,
`samples.jsonl`, `metrics.json`, `summary.md`, `summary.csv`, `summary.xlsx`);
the prediction directory is never written to. From 1.1.0 the entrypoint
dispatches on its arguments, so the explicit `widget2code-bench-exp` is
optional there — keep it if you also run older tags.

For training reward, start the long-lived socket service instead:

```bash
W2C_BENCH_IMAGE=houstonzhang/w2c-bench:1.1.0 docker/run.sh 8
```

Only `/tmp/w2c-bench` is mounted. Ground truth and prediction bytes cross the
Unix socket, and callers may select leaves/groups such as
`ssim,layout,style,contrast`. A golden 12-metric self-check and exact dependency
manifest run before the socket appears.

`--gt_dir` holds one directory per sample — `image_0001/image.png` with
`metadata.json` beside it, the layout of the published
[Widget2Code-Data](https://huggingface.co/datasets/Djanghao/Widget2Code-Data)
dataset; `--pred_dir` holds one subdirectory per id, each containing the file
named by `--pred_name` (relative paths work). `--cuda` runs LPIPS and OCR on
the first visible GPU; `--device N` pins the process to card N — one process
per card.

## Why an image

Two of the twelve metrics run a neural network — EasyOCR's detector and
recogniser for the text metrics, and LPIPS's VGG trunk for the perceptual
distance. Floating-point convolution is not portable the way integer
rasterisation is: results shift with the BLAS build, the thread count, the CPU's
instruction set and, on a GPU, with the architecture and cuDNN's timing-based
autotuning.

So the image pins what it can and constrains the rest:

- **Weights baked in.** EasyOCR and LPIPS otherwise download on first use; a
  silent upstream re-release would move the metrics. The build checks their
  SHA-256.
- **One thread per process.** BLAS, oneDNN and OpenCV's own pool all change
  their reduction order with the thread count. Parallelism belongs at the
  process level, where each pair is independent and the arithmetic is untouched.
- **CPU by default.** This is the reproducible path. `--cuda` is available and
  much faster, but cuDNN picks kernels by architecture, so a GPU run is only
  as portable as the machine it ran on.

Measured on the reference host, the container reproduces a direct install of the
same evaluator **bit for bit** — 20 samples, 240 metric values, zero differences.
That is a per-host property, not a promise: `tools/verify_image.sh` in the
repository runs the same comparison wherever you are.

## Metrics

| Dimension | Metrics |
|---|---|
| Layout | `MarginAsymmetry`, `ContentAspectDiff`, `AreaRatioDiff` |
| Legibility | `TextJaccard`, `ContrastDiff`, `ContrastLocalDiff` |
| Style | `PaletteDistance`, `Vibrancy`, `PolarityConsistency` |
| Perceptual | `ssim`, `lp` (LPIPS) |
| Geometry | `geo_score` |

All are higher-is-better **except `lp`**, which is a distance.

When a ground-truth image has no matching prediction, the run also scores it
against synthetic fills, so the summary shows how the aggregate moves under
different assumptions about the missing samples: matched-only, black fill, white
fill, and worst-case.

## Also in the image

`tools/` ships alongside the evaluator, because the point of freezing an
environment is that the intermediates are produced inside it:

- `build_metadata.py` — precomputes the half of the evaluation that depends on
  the ground truth alone (its OCR, edge mask, histograms and fill scores), so
  every later run reads them instead of recomputing them per model.
- `compare_eval.py` — compares two evaluation trees metric by metric, exactly or
  at a stated number of decimals.
- `verify_metadata.py` — re-derives a built cache and checks it against itself.

## Using it from an agent

The full instructions - deploy, batch, single pair, the client, every flag, and
how to read a failure - are one file:

**https://github.com/Djanghao/widget2code-bench/blob/main/SKILL.md**

It also ships inside the image, so an installed copy carries its own manual:

```bash
docker run --rm houstonzhang/w2c-bench:latest --skill-path
```

## Tags

`1.1.0`, `1.0.0`, `latest`, plus the short commit each image was built from. Pin the
digest when it has to be provably the same image.

Apache-2.0.
