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
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v /path/to/GT:/gt -v /path/to/predictions:/pred \
  houstonzhang/w2c-bench:latest \
  --gt_dir /gt --pred_dir /pred --pred_name output.png --workers 32
```

`--gt_dir` is a flat directory of PNGs whose filenames carry a 4-digit id;
`--pred_dir` holds one subdirectory per id, each containing the file named by
`--pred_name`. Add `--minimal` to skip the per-metric visualisations and the
worst-case sample export.

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

## Tags

`latest`, plus the short commit each image was built from. Pin the digest when
it has to be provably the same image.

Apache-2.0.
