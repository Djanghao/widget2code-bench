import numpy as np
import cv2
from skimage.color import rgb2hsv, rgb2lab, rgb2gray
from scipy.stats import wasserstein_distance
from scipy.optimize import linear_sum_assignment


def compute_palette_distance(gt, gen, bins=36):
    """Hue histogram Earth-Mover's Distance."""
    hsv_gt, hsv_gen = rgb2hsv(gt), rgb2hsv(gen)
    h_gt, h_gen = hsv_gt[..., 0].ravel(), hsv_gen[..., 0].ravel()

    hist_gt, _ = np.histogram(h_gt, bins=bins, range=(0, 1), density=True)
    hist_gen, _ = np.histogram(h_gen, bins=bins, range=(0, 1), density=True)

    emd = wasserstein_distance(
        np.arange(bins), np.arange(bins),
        hist_gt / (hist_gt.sum() + 1e-6),
        hist_gen / (hist_gen.sum() + 1e-6),
    )
    score = float(np.exp(-emd / (bins * 0.08)))
    return np.clip(score, 0, 1)


def compute_vibrancy_consistency(gt, gen, bins=30):
    """HSV saturation histogram EMD."""
    hsv_gt, hsv_gen = rgb2hsv(gt), rgb2hsv(gen)
    s_gt, s_gen = hsv_gt[..., 1].ravel(), hsv_gen[..., 1].ravel()
    hist_gt, _ = np.histogram(s_gt, bins=bins, range=(0, 1), density=True)
    hist_gen, _ = np.histogram(s_gen, bins=bins, range=(0, 1), density=True)
    emd = wasserstein_distance(
        np.arange(bins), np.arange(bins),
        hist_gt / (hist_gt.sum() + 1e-6),
        hist_gen / (hist_gen.sum() + 1e-6),
    )
    score = float(np.exp(-emd / (bins * 0.05)))
    return np.clip(score, 0, 1)


def compute_polarity_consistency(gt, gen):
    """Brightness polarity consistency."""
    L_gt = rgb2gray(gt)
    L_gen = rgb2gray(gen)
    bg_gt = np.median(L_gt)
    bg_gen = np.median(L_gen)
    fg_gt = np.mean(np.sort(L_gt.ravel())[: int(0.1 * L_gt.size)])
    fg_gen = np.mean(np.sort(L_gen.ravel())[: int(0.1 * L_gen.size)])
    pol_gt = np.sign(bg_gt - fg_gt)
    pol_gen = np.sign(bg_gen - fg_gen)
    score = 1.0 if pol_gt == pol_gen else 0.0
    diff = abs((bg_gt - fg_gt) - (bg_gen - fg_gen))
    score *= np.exp(-diff * 5)
    return float(np.clip(score, 0, 1))


def compute_style(gt, gen):
    """
    Compute style metrics.

    Returns dict with: PaletteDistance, Vibrancy, PolarityConsistency
    """
    return {
        "PaletteDistance": compute_palette_distance(gt, gen),
        "Vibrancy": compute_vibrancy_consistency(gt, gen),
        "PolarityConsistency": compute_polarity_consistency(gt, gen),
    }
