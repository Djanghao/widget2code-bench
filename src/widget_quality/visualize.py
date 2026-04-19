"""Per-metric visualizations of the evaluation computation process.

Each call to ``generate_visualizations`` produces one PNG per metric in
``out_dir``, showing GT/Pred intermediates alongside the formula and score.
Used by the batch evaluator when verbose mode is on (default).
"""

from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import wasserstein_distance
from skimage.color import rgb2gray, rgb2hsv
from skimage.metrics import structural_similarity as ssim_fn

from .layout import MAX_DIFF as LAYOUT_MAX_DIFF
from .legibility import (
    ocr_text_easyocr,
    to_gray as leg_to_gray,
)
from .utils import (
    edge_map,
    margin_from_mask,
    remove_border_touching_components,
)


def _save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)


def _text_panel(ax, text: str) -> None:
    ax.axis("off")
    ax.text(0.02, 0.98, text, fontsize=9, va="top", family="monospace",
            transform=ax.transAxes)


# ---------- Layout ----------

def _viz_margin_asymmetry(gt, gen, out: Path) -> None:
    k = np.ones((3, 3), np.uint8)
    m_gt = remove_border_touching_components(cv2.dilate(edge_map(gt), k))
    m_gen = remove_border_touching_components(cv2.dilate(edge_map(gen), k))
    mm_gt = [int(v) for v in margin_from_mask(m_gt)]
    mm_gen = [int(v) for v in margin_from_mask(m_gen)]

    diffs = np.abs(np.array(mm_gt) - np.array(mm_gen))
    mean = diffs.mean()
    score = 0.0 if mean < 1e-6 else float(diffs.std() / mean)

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5))
    for ax, mask, mm, lab in [(ax1, m_gt, mm_gt, "GT"), (ax2, m_gen, mm_gen, "Pred")]:
        ax.imshow(mask, cmap="gray")
        ax.set_title(f"{lab}: T={mm[0]} R={mm[1]} B={mm[2]} L={mm[3]}", fontsize=10)
        ax.axis("off")
        H, W = mask.shape
        ys, xs = np.where(mask > 0)
        if len(ys):
            y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                       fill=False, edgecolor="red", lw=1.5))
            ax.annotate("", xy=(W / 2, 0), xytext=(W / 2, y0),
                        arrowprops=dict(arrowstyle="<->", color="yellow"))
            ax.text(W / 2 + 5, y0 / 2, f"T={mm[0]}", color="yellow", fontsize=8)
            ax.annotate("", xy=(W, H / 2), xytext=(x1, H / 2),
                        arrowprops=dict(arrowstyle="<->", color="yellow"))
            ax.text((W + x1) / 2, H / 2 - 5, f"R={mm[1]}", color="yellow", fontsize=8)
            ax.annotate("", xy=(W / 2, H), xytext=(W / 2, y1),
                        arrowprops=dict(arrowstyle="<->", color="yellow"))
            ax.text(W / 2 + 5, (H + y1) / 2, f"B={mm[2]}", color="yellow", fontsize=8)
            ax.annotate("", xy=(0, H / 2), xytext=(x0, H / 2),
                        arrowprops=dict(arrowstyle="<->", color="yellow"))
            ax.text(x0 / 2, H / 2 - 5, f"L={mm[3]}", color="yellow", fontsize=8)

    txt = (
        "Formula: std(|m_gt - m_gen|) / mean(|m_gt - m_gen|)\n\n"
        f"  m_gt  [T,R,B,L] = {mm_gt}\n"
        f"  m_gen [T,R,B,L] = {mm_gen}\n"
        f"  |diff|          = {[int(v) for v in diffs.tolist()]}\n\n"
        f"  mean = {mean:.3f}\n"
        f"  std  = {diffs.std():.3f}\n\n"
        f"  MarginAsymmetry = {score:.3f}"
    )
    _text_panel(ax3, txt)
    ax3.set_title("Computation")
    fig.suptitle("MarginAsymmetry (lower = more symmetric diff)", fontsize=11)
    _save(fig, out)


def _viz_content_aspect_diff(gt, gen, out: Path) -> None:
    k = np.ones((3, 3), np.uint8)
    m_gt = remove_border_touching_components(cv2.dilate(edge_map(gt), k))
    m_gen = remove_border_touching_components(cv2.dilate(edge_map(gen), k))

    def bbox(mask):
        ys, xs = np.where(mask > 0)
        if len(ys) == 0:
            return None, None
        x0 = int(xs.min()); y0 = int(ys.min())
        x1 = int(xs.max()); y1 = int(ys.max())
        return (x0, y0, x1, y1), (x1 - x0 + 1, y1 - y0 + 1)

    b_gt, wh_gt = bbox(m_gt)
    b_gen, wh_gen = bbox(m_gen)
    ar_gt = wh_gt[0] / wh_gt[1] if wh_gt else float("nan")
    ar_gen = wh_gen[0] / wh_gen[1] if wh_gen else float("nan")
    score = float(abs(np.log(ar_gt / ar_gen))) if (wh_gt and wh_gen) else LAYOUT_MAX_DIFF

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5))
    for ax, img, b, wh, lab in [(ax1, gt, b_gt, wh_gt, "GT"), (ax2, gen, b_gen, wh_gen, "Pred")]:
        ax.imshow(img); ax.axis("off")
        if wh:
            ax.set_title(f"{lab}: {wh[0]}×{wh[1]}  AR={wh[0]/wh[1]:.3f}", fontsize=10)
        else:
            ax.set_title(f"{lab} (empty)", fontsize=10)
        if b:
            x0, y0, x1, y1 = b
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                       fill=False, edgecolor="lime", lw=2))

    txt = (
        "Formula: |log(AR_gt / AR_gen)|,  AR = bbox_w / bbox_h\n\n"
        f"  AR_gt  = {ar_gt:.3f}\n"
        f"  AR_gen = {ar_gen:.3f}\n"
        f"  ratio  = {(ar_gt/ar_gen) if wh_gt and wh_gen else float('nan'):.3f}\n"
        f"  |log|  = {score:.3f}\n\n"
        f"  ContentAspectDiff = {score:.3f}"
    )
    _text_panel(ax3, txt)
    ax3.set_title("Computation")
    fig.suptitle("ContentAspectDiff (lower = closer aspect ratio)", fontsize=11)
    _save(fig, out)


def _viz_area_ratio_diff(gt, gen, out: Path, min_area: int = 10) -> None:
    k = np.ones((3, 3), np.uint8)
    m_gt = remove_border_touching_components(cv2.dilate(edge_map(gt), k))
    m_gen = remove_border_touching_components(cv2.dilate(edge_map(gen), k))

    rng = np.random.RandomState(0)

    def colorize(mask):
        mask_bin = (mask > 0).astype(np.uint8)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(mask_bin, connectivity=8)
        areas = [stats[i, 4] for i in range(1, num) if stats[i, 4] > min_area]
        cmap = rng.randint(60, 255, size=(num, 3), dtype=np.uint8)
        cmap[0] = [0, 0, 0]
        return cmap[labels], areas

    c_gt, a_gt = colorize(m_gt)
    c_gen, a_gen = colorize(m_gen)

    def ratio(areas):
        if not areas:
            return None
        arr = np.array(areas)
        return arr.mean() / arr.sum()

    r_gt = ratio(a_gt)
    r_gen = ratio(a_gen)
    score = abs(r_gen - r_gt) if (r_gt is not None and r_gen is not None) else LAYOUT_MAX_DIFF

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5))
    ax1.imshow(c_gt); ax1.axis("off"); ax1.set_title(f"GT components (n={len(a_gt)})")
    ax2.imshow(c_gen); ax2.axis("off"); ax2.set_title(f"Pred components (n={len(a_gen)})")

    r_gt_str = f"{r_gt:.4f}" if r_gt is not None else "None"
    r_gen_str = f"{r_gen:.4f}" if r_gen is not None else "None"
    txt = (
        "Formula: |mean(areas_gen)/sum(areas_gen) - mean(areas_gt)/sum(areas_gt)|\n"
        "(components with area > 10; border-touching ones removed)\n\n"
        f"  GT   n={len(a_gt)}  sum={sum(a_gt)}  mean={np.mean(a_gt) if a_gt else 0:.1f}\n"
        f"  Pred n={len(a_gen)}  sum={sum(a_gen)}  mean={np.mean(a_gen) if a_gen else 0:.1f}\n\n"
        f"  r_gt  = {r_gt_str}\n"
        f"  r_gen = {r_gen_str}\n\n"
        f"  AreaRatioDiff = {score:.4f}"
    )
    _text_panel(ax3, txt)
    ax3.set_title("Computation")
    fig.suptitle("AreaRatioDiff (lower = similar component area distribution)", fontsize=11)
    _save(fig, out)


# ---------- Legibility ----------

def _viz_text_jaccard(gt, gen, res_gt, res_gen, out: Path) -> None:
    s_gt = set(" ".join([t for _, t, c in res_gt if c >= 0.5 and t.strip()]).split())
    s_gen = set(" ".join([t for _, t, c in res_gen if c >= 0.5 and t.strip()]).split())
    shared = s_gt & s_gen
    gt_only = s_gt - s_gen
    pred_only = s_gen - s_gt
    union = s_gt | s_gen
    jaccard = len(shared) / (len(union) + 1e-6)

    def draw(ax, img, results, title):
        ax.imshow(img); ax.axis("off"); ax.set_title(title)
        for bbox, text, conf in results:
            if conf < 0.5:
                continue
            pts = np.array(bbox, dtype=np.int32)
            x0, y0 = pts[:, 0].min(), pts[:, 1].min()
            x1, y1 = pts[:, 0].max(), pts[:, 1].max()
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                       fill=False, edgecolor="yellow", lw=1.2))
            ax.text(x0, max(0, y0 - 3), text, color="red", fontsize=7)

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5.5))
    draw(ax1, gt, res_gt, f"GT OCR (|tokens|={len(s_gt)})")
    draw(ax2, gen, res_gen, f"Pred OCR (|tokens|={len(s_gen)})")

    def fmt(s, n=10):
        return ", ".join(sorted(s)[:n]) + (f"  (+{len(s)-n} more)" if len(s) > n else "")

    txt = (
        "Formula: |GT ∩ Pred| / |GT ∪ Pred|\n\n"
        f"  shared    ({len(shared):2d}): {fmt(shared)}\n"
        f"  GT-only   ({len(gt_only):2d}): {fmt(gt_only)}\n"
        f"  Pred-only ({len(pred_only):2d}): {fmt(pred_only)}\n\n"
        f"  |union| = {len(union)}\n\n"
        f"  TextJaccard = {jaccard:.3f}"
    )
    _text_panel(ax3, txt)
    ax3.set_title("Computation")
    fig.suptitle("TextJaccard (higher = more OCR tokens overlap)", fontsize=11)
    _save(fig, out)


def _viz_contrast_diff(gt, gen, out: Path) -> None:
    g_gt = leg_to_gray(gt); g_gen = leg_to_gray(gen)
    p_gt = np.percentile(g_gt, [5, 95])
    p_gen = np.percentile(g_gen, [5, 95])
    c_gt = (p_gt[1] + 0.05) / (p_gt[0] + 0.05)
    c_gen = (p_gen[1] + 0.05) / (p_gen[0] + 0.05)
    diff = float(np.clip(abs(c_gt - c_gen), 0, 5))

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5))
    for ax, g, p, c, lab in [(ax1, g_gt, p_gt, c_gt, "GT"), (ax2, g_gen, p_gen, c_gen, "Pred")]:
        ax.hist(g.ravel(), bins=50, color="gray", alpha=0.7)
        ax.axvline(p[0], color="blue", label=f"P5 = {p[0]:.2f}")
        ax.axvline(p[1], color="red", label=f"P95 = {p[1]:.2f}")
        ax.set_title(f"{lab} luminance  contrast = {c:.2f}")
        ax.legend()

    txt = (
        "Formula: contrast = (P95 + 0.05) / (P5 + 0.05)\n"
        "         ContrastDiff = clip(|contrast_gt - contrast_gen|, 0, 5)\n\n"
        f"  GT   P5={p_gt[0]:.2f}  P95={p_gt[1]:.2f}  contrast={c_gt:.2f}\n"
        f"  Pred P5={p_gen[0]:.2f} P95={p_gen[1]:.2f} contrast={c_gen:.2f}\n\n"
        f"  |diff|        = {abs(c_gt-c_gen):.3f}\n"
        f"  ContrastDiff  = {diff:.3f}"
    )
    _text_panel(ax3, txt)
    ax3.set_title("Computation")
    fig.suptitle("ContrastDiff (lower = more similar global contrast)", fontsize=11)
    _save(fig, out)


def _viz_contrast_local_diff(gt, gen, res_gt, res_gen, out: Path) -> None:
    g_gt = leg_to_gray(gt); g_gen = leg_to_gray(gen)

    def per_box(gray, results):
        H, W = gray.shape
        out = []
        for bbox, text, conf in results:
            if conf < 0.5:
                continue
            pts = np.array(bbox, dtype=np.int32)
            x0 = int(np.clip(pts[:, 0].min(), 0, W - 1)); x1 = int(np.clip(pts[:, 0].max(), 0, W - 1))
            y0 = int(np.clip(pts[:, 1].min(), 0, H - 1)); y1 = int(np.clip(pts[:, 1].max(), 0, H - 1))
            if (x1 - x0) * (y1 - y0) < 20:
                continue
            patch = gray[y0:y1, x0:x1]
            if patch.size < 10:
                continue
            p5, p95 = np.percentile(patch, [5, 95])
            out.append((text, (x0, y0, x1, y1), (p95 + 0.05) / (p5 + 0.05)))
        return out

    cs_gt = per_box(g_gt, res_gt)
    cs_gen = per_box(g_gen, res_gen)
    mean_gt = float(np.mean([c for _, _, c in cs_gt])) if cs_gt else None
    mean_gen = float(np.mean([c for _, _, c in cs_gen])) if cs_gen else None

    MAX = 5.0
    if mean_gt is not None and mean_gen is not None:
        local_diff = abs(mean_gt - mean_gen)
    elif mean_gt is None and mean_gen is None:
        local_diff = 0.0
    else:
        local_diff = MAX
    local_diff = float(np.clip(local_diff, 0, MAX))

    def draw(ax, img, rows, title):
        ax.imshow(img); ax.axis("off"); ax.set_title(title)
        for _, (x0, y0, x1, y1), c in rows:
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                       fill=False, edgecolor="yellow", lw=1.2))
            ax.text(x0, max(0, y0 - 3), f"{c:.2f}", color="cyan", fontsize=7)

    mean_gt_str = f"{mean_gt:.2f}" if mean_gt is not None else "—"
    mean_gen_str = f"{mean_gen:.2f}" if mean_gen is not None else "—"
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5.5))
    draw(ax1, gt, cs_gt, f"GT: {len(cs_gt)} boxes  mean={mean_gt_str}")
    draw(ax2, gen, cs_gen, f"Pred: {len(cs_gen)} boxes  mean={mean_gen_str}")

    diff_raw = (abs((mean_gt or 0) - (mean_gen or 0))
                if mean_gt is not None and mean_gen is not None else local_diff)
    txt = (
        "Formula: mean over OCR boxes of (P95 + 0.05)/(P5 + 0.05), then |gt - gen|.\n"
        "Missing on one side only → MAX_DIFF = 5.\n\n"
        f"  GT   n={len(cs_gt)} mean={mean_gt_str}\n"
        f"  Pred n={len(cs_gen)} mean={mean_gen_str}\n\n"
        f"  |diff|            = {diff_raw:.3f}\n"
        f"  ContrastLocalDiff = {local_diff:.3f}"
    )
    _text_panel(ax3, txt)
    ax3.set_title("Computation")
    fig.suptitle("ContrastLocalDiff (lower = more similar per-text contrast)", fontsize=11)
    _save(fig, out)


# ---------- Style ----------

def _viz_hist_emd(gt, gen, out: Path, *, channel_idx: int, bins: int,
                  denom: float, metric_name: str, title: str) -> None:
    hsv_gt = rgb2hsv(gt); hsv_gen = rgb2hsv(gen)
    v_gt = hsv_gt[..., channel_idx].ravel(); v_gen = hsv_gen[..., channel_idx].ravel()
    h_gt, edges = np.histogram(v_gt, bins=bins, range=(0, 1), density=True)
    h_gen, _ = np.histogram(v_gen, bins=bins, range=(0, 1), density=True)
    h_gt_n = h_gt / (h_gt.sum() + 1e-6)
    h_gen_n = h_gen / (h_gen.sum() + 1e-6)
    emd = wasserstein_distance(np.arange(bins), np.arange(bins), h_gt_n, h_gen_n)
    score = float(np.clip(np.exp(-emd / denom), 0, 1))

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5))
    w = edges[1] - edges[0]
    ax1.bar(edges[:-1], h_gt_n, width=w, align="edge", color="steelblue", alpha=0.8)
    ax1.set_title(f"GT {title} hist (bins={bins})")
    ax2.bar(edges[:-1], h_gen_n, width=w, align="edge", color="tomato", alpha=0.8)
    ax2.set_title(f"Pred {title} hist")

    cdf_gt = np.cumsum(h_gt_n); cdf_gen = np.cumsum(h_gen_n)
    ax3.plot(cdf_gt, color="steelblue", label="GT CDF")
    ax3.plot(cdf_gen, color="tomato", label="Pred CDF")
    ax3.fill_between(range(bins), cdf_gt, cdf_gen, color="gray", alpha=0.3,
                     label="|CDF diff| (area ≈ EMD)")
    ax3.set_title(f"CDF overlap  EMD = {emd:.2f}  denom = {denom:.2f}")
    ax3.legend(fontsize=8)

    fig.suptitle(f"{metric_name} = exp(-EMD / denom) = {score:.3f}", fontsize=11)
    _save(fig, out)


def _viz_palette_distance(gt, gen, out: Path) -> None:
    _viz_hist_emd(gt, gen, out, channel_idx=0, bins=36, denom=36 * 0.08,
                  metric_name="PaletteDistance", title="Hue")


def _viz_vibrancy(gt, gen, out: Path) -> None:
    _viz_hist_emd(gt, gen, out, channel_idx=1, bins=30, denom=30 * 0.05,
                  metric_name="Vibrancy", title="Saturation")


def _viz_polarity(gt, gen, out: Path, q: float = 0.1, eps: float = 1e-6) -> None:
    def stats(img):
        L = rgb2gray(img); flat = np.sort(L.ravel()); k = max(1, int(q * flat.size))
        bg = np.median(flat); dark = np.mean(flat[:k]); bright = np.mean(flat[-k:])
        fg = dark if abs(bg - dark) >= abs(bg - bright) else bright
        contrast = bg - fg; polarity = int(np.sign(contrast)); strength = float(abs(contrast))
        return L, bg, dark, bright, fg, contrast, polarity, strength

    L_gt, bg_gt, d_gt, b_gt, fg_gt, c_gt, p_gt, s_gt = stats(gt)
    L_gen, bg_gen, d_gen, b_gen, fg_gen, c_gen, p_gen, s_gen = stats(gen)

    if s_gt < eps or s_gen < eps:
        score = 0.0
    else:
        pol_score = 1.0 if p_gt == p_gen else 0.0
        score = float(np.clip(pol_score * np.exp(-abs(s_gt - s_gen) * 5), 0, 1))

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5.5))
    for ax, L, bg, fg, c, s, lab in [
        (ax1, L_gt, bg_gt, fg_gt, c_gt, s_gt, "GT"),
        (ax2, L_gen, bg_gen, fg_gen, c_gen, s_gen, "Pred"),
    ]:
        ax.imshow(L, cmap="gray", vmin=0, vmax=1)
        pol_txt = ("bg darker than fg (sign -)" if c < 0
                   else "bg lighter than fg (sign +)" if c > 0 else "flat")
        ax.set_title(f"{lab} L — bg={bg:.2f} fg={fg:.2f}\n{pol_txt}  |c|={s:.2f}")
        ax.axis("off")

    txt = (
        "Formula:\n"
        "  pick bg = median(L); fg = stronger extreme tail (bottom-q vs top-q)\n"
        "  polarity = sign(bg - fg); strength = |bg - fg|\n"
        "  score = [polarity_gt == polarity_gen] * exp(-|s_gt - s_gen| * 5)\n\n"
        f"  GT   bg={bg_gt:.3f} fg={fg_gt:.3f} polarity={p_gt} strength={s_gt:.3f}\n"
        f"  Pred bg={bg_gen:.3f} fg={fg_gen:.3f} polarity={p_gen} strength={s_gen:.3f}\n\n"
        f"  |strength diff| = {abs(s_gt-s_gen):.3f}\n\n"
        f"  PolarityConsistency = {score:.3f}"
    )
    _text_panel(ax3, txt)
    ax3.set_title("Computation")
    fig.suptitle("PolarityConsistency (1 = same polarity + similar strength)", fontsize=11)
    _save(fig, out)


# ---------- Perceptual ----------

def _viz_ssim(gt, gen, out: Path) -> None:
    ssim_val, ssim_map = ssim_fn(gt, gen, channel_axis=2, data_range=1.0, full=True)
    smap = ssim_map.mean(axis=-1)

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5))
    ax1.imshow(gt); ax1.axis("off"); ax1.set_title("GT")
    ax2.imshow(gen); ax2.axis("off"); ax2.set_title("Pred (resized)")
    im = ax3.imshow(smap, cmap="viridis", vmin=0, vmax=1)
    ax3.axis("off"); ax3.set_title(f"SSIM map  mean = {ssim_val:.3f}")
    fig.colorbar(im, ax=ax3, fraction=0.046)
    fig.suptitle(f"ssim (higher = more structurally similar)  score = {ssim_val:.3f}",
                 fontsize=11)
    _save(fig, out)


def _viz_lpips(gt, gen, lpips_val: float, out: Path) -> None:
    diff = np.abs(gt - gen).mean(axis=-1)
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5))
    ax1.imshow(gt); ax1.axis("off"); ax1.set_title("GT")
    ax2.imshow(gen); ax2.axis("off"); ax2.set_title("Pred (resized)")
    im = ax3.imshow(diff, cmap="hot", vmin=0, vmax=1)
    ax3.axis("off"); ax3.set_title("|GT - Pred| (per-pixel mean over channels)")
    fig.colorbar(im, ax=ax3, fraction=0.046)
    fig.suptitle(
        f"lp (LPIPS — VGG feature distance, lower = more perceptually similar)  "
        f"score = {lpips_val:.3f}", fontsize=11)
    _save(fig, out)


# ---------- Geometry ----------

def _viz_geometry(gt_raw, pred_raw, out: Path, alpha=0.6, beta=0.4, decay=3.0) -> None:
    h1, w1 = gt_raw.shape[:2]; h2, w2 = pred_raw.shape[:2]
    ar_gt, ar_gen = w1 / h1, w2 / h2
    a1, a2 = w1 * h1, w2 * h2
    ar_diff = abs(np.log(ar_gt / ar_gen))
    area_diff = abs(np.log(a2 / a1))
    aspect_score = float(np.exp(-decay * ar_diff))
    size_score = float(np.exp(-decay * area_diff))
    score = float(np.clip(alpha * aspect_score + beta * size_score, 0, 1))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.add_patch(plt.Rectangle((0, 0), w1, h1, fill=False, edgecolor="blue", lw=2,
                                label=f"GT {w1}×{h1}"))
    ax1.add_patch(plt.Rectangle((0, 0), w2, h2, fill=False, edgecolor="red", lw=2,
                                ls="--", label=f"Pred {w2}×{h2}"))
    ax1.set_xlim(0, max(w1, w2) * 1.1); ax1.set_ylim(max(h1, h2) * 1.1, 0)
    ax1.set_aspect("equal"); ax1.legend(); ax1.set_title("Sizes overlaid")

    txt = (
        f"α={alpha}, β={beta}, decay={decay}\n\n"
        f"  GT   W×H = {w1}×{h1}  AR={ar_gt:.3f}  area={a1}\n"
        f"  Pred W×H = {w2}×{h2}  AR={ar_gen:.3f}  area={a2}\n\n"
        f"  |log(AR_gt/AR_gen)| = {ar_diff:.3f}  → aspect_score = {aspect_score:.3f}\n"
        f"  |log(area_gen/area_gt)| = {area_diff:.3f}  → size_score = {size_score:.3f}\n\n"
        f"  geo_score = {alpha}·{aspect_score:.3f} + {beta}·{size_score:.3f} = {score:.3f}"
    )
    _text_panel(ax2, txt)
    ax2.set_title("Computation")
    fig.suptitle(f"geo_score (higher = aspect + size closer)  score = {score:.3f}",
                 fontsize=11)
    _save(fig, out)


ALL_METRICS = {
    "MarginAsymmetry", "ContentAspectDiff", "AreaRatioDiff",
    "TextJaccard", "ContrastDiff", "ContrastLocalDiff",
    "PaletteDistance", "Vibrancy", "PolarityConsistency",
    "ssim", "lp", "geo_score",
}


def generate_visualizations(gt_raw, pred_raw, gen_resized, pred_folder: str,
                            lpips_val: float,
                            ocr_gt=None, ocr_gen=None,
                            metrics_to_render=None) -> None:
    """Produce per-metric PNGs into <pred_folder>/evaluation/viz/.

    Args:
        gt_raw:            Original GT image (float [0, 1], RGB, HxW[x3]) — geometry uses this.
        pred_raw:          Original pred image (same format) — geometry uses this.
        gen_resized:       Pred resized to GT size — all non-geometry metrics use this.
        pred_folder:       Sample folder; viz files go into pred_folder/evaluation/viz/.
        lpips_val:         Pre-computed LPIPS score (so we don't re-run the model).
        ocr_gt / ocr_gen:  Optional cached EasyOCR output. If None and a legibility
                           metric is rendered, OCR is run on the fly.
        metrics_to_render: Iterable of metric names to render. None → all 12.
    """
    viz_dir = Path(pred_folder) / "evaluation" / "viz"
    viz_dir.mkdir(parents=True, exist_ok=True)

    render = set(metrics_to_render) if metrics_to_render is not None else ALL_METRICS

    needs_ocr = bool({"TextJaccard", "ContrastLocalDiff"} & render)
    if needs_ocr:
        if ocr_gt is None:
            _, ocr_gt = ocr_text_easyocr(gt_raw)
        if ocr_gen is None:
            _, ocr_gen = ocr_text_easyocr(gen_resized)

    if "MarginAsymmetry" in render:
        _viz_margin_asymmetry(gt_raw, gen_resized, viz_dir / "MarginAsymmetry.png")
    if "ContentAspectDiff" in render:
        _viz_content_aspect_diff(gt_raw, gen_resized, viz_dir / "ContentAspectDiff.png")
    if "AreaRatioDiff" in render:
        _viz_area_ratio_diff(gt_raw, gen_resized, viz_dir / "AreaRatioDiff.png")
    if "TextJaccard" in render:
        _viz_text_jaccard(gt_raw, gen_resized, ocr_gt, ocr_gen, viz_dir / "TextJaccard.png")
    if "ContrastDiff" in render:
        _viz_contrast_diff(gt_raw, gen_resized, viz_dir / "ContrastDiff.png")
    if "ContrastLocalDiff" in render:
        _viz_contrast_local_diff(gt_raw, gen_resized, ocr_gt, ocr_gen,
                                 viz_dir / "ContrastLocalDiff.png")
    if "PaletteDistance" in render:
        _viz_palette_distance(gt_raw, gen_resized, viz_dir / "PaletteDistance.png")
    if "Vibrancy" in render:
        _viz_vibrancy(gt_raw, gen_resized, viz_dir / "Vibrancy.png")
    if "PolarityConsistency" in render:
        _viz_polarity(gt_raw, gen_resized, viz_dir / "PolarityConsistency.png")
    if "ssim" in render:
        _viz_ssim(gt_raw, gen_resized, viz_dir / "ssim.png")
    if "lp" in render:
        _viz_lpips(gt_raw, gen_resized, lpips_val, viz_dir / "lp.png")
    if "geo_score" in render:
        _viz_geometry(gt_raw, pred_raw, viz_dir / "geo_score.png")
