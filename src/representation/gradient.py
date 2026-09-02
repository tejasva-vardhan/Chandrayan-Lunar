"""Gradient-magnitude representation.

Computes the Sobel gradient magnitude of the image. This representation
encodes edges and texture rather than absolute intensity, making it more
robust to additive/multiplicative illumination changes (e.g. different
Sun-elevation angles) than raw intensity.

Use for normal/difficult pairs with illumination differences. Not suitable
for very low-texture or heavily shadowed scenes where gradients are near-zero
everywhere.
"""

from __future__ import annotations

import cv2
import numpy as np

from src.representation._loader import load_array


def build_gradient(raster_uri: str, *, ksize: int = 3) -> np.ndarray:
    """Load image and return normalised Sobel gradient magnitude."""
    return build_gradient_array(load_array(raster_uri), ksize=ksize)


def build_gradient_array(img: np.ndarray, *, ksize: int = 3) -> np.ndarray:
    """Load image and return normalised Sobel gradient magnitude (float32, [0, 1]).

    Parameters
    ----------
    raster_uri:
        Filesystem path or URI to the single-band raster file.
    ksize:
        Sobel kernel size. Must be 1, 3, 5, or 7. Default 3 is appropriate for
        most resolution levels. Increase to 5 for very high-resolution products
        with high-frequency sensor noise.

    Returns
    -------
    np.ndarray
        float32 array, shape (H, W), values in [0, 1].
    """
    # Convert to uint8 for OpenCV Sobel (OpenCV Sobel on float32 works but
    # uint8 avoids precision-dependent edge cases on border pixels).
    img_u8 = (img * 255.0).clip(0, 255).astype(np.uint8)

    gx = cv2.Sobel(img_u8, cv2.CV_32F, 1, 0, ksize=ksize)
    gy = cv2.Sobel(img_u8, cv2.CV_32F, 0, 1, ksize=ksize)
    magnitude = np.sqrt(gx**2 + gy**2).astype(np.float32)

    max_val = float(magnitude.max())
    if max_val == 0.0:
        return magnitude  # Flat image — all zeros, return as-is.

    return (magnitude / max_val).astype(np.float32)
