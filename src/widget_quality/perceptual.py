import numpy as np
import torch
from lpips import LPIPS
from skimage.metrics import structural_similarity as ssim

_device = torch.device("cpu")
_lpips_vgg = None


def set_device(use_cuda=False):
    """Set device for LPIPS computation. Call before running evaluation."""
    global _device, _lpips_vgg

    requested = torch.device("cuda" if use_cuda and torch.cuda.is_available() else "cpu")
    if _lpips_vgg is not None and _device == requested:
        return

    _device = requested
    _lpips_vgg = LPIPS(net="vgg").to(_device)


def _ensure_model():
    global _lpips_vgg
    if _lpips_vgg is None:
        set_device(use_cuda=False)


def compute_ssim(gt, gen):
    """Compute the canonical bench SSIM without loading the LPIPS model."""
    return float(ssim(gt, gen, channel_axis=2, data_range=1.0))


def compute_lpips(gt, gen):
    """Compute LPIPS-VGG without also computing SSIM."""
    _ensure_model()
    gt_t = torch.tensor(gt).permute(2, 0, 1).unsqueeze(0).float().to(_device)
    gen_t = torch.tensor(gen).permute(2, 0, 1).unsqueeze(0).float().to(_device)
    with torch.no_grad():
        return float(_lpips_vgg(gt_t, gen_t).item())


def compute_perceptual(gt, gen):
    """Compute both canonical perceptual metrics."""

    return {
        "SSIM": compute_ssim(gt, gen),
        "LPIPS": compute_lpips(gt, gen),
    }
