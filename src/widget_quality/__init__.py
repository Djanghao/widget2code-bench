"""Widget Quality — evaluation toolkit for widget generation quality."""

__version__ = "0.1.0"

from .composite import composite_score
from .geometry import compute_aspect_dimensionality_fidelity
from .layout import compute_layout
from .legibility import compute_legibility
from .perceptual import compute_perceptual, set_device
from .style import compute_style
from .utils import load_image, resize_to_match
from .evaluate import evaluate_pair, evaluate_dir

__all__ = [
    "composite_score",
    "compute_aspect_dimensionality_fidelity",
    "compute_layout",
    "compute_legibility",
    "compute_perceptual",
    "compute_style",
    "set_device",
    "load_image",
    "resize_to_match",
    "evaluate_pair",
    "evaluate_dir",
]
