"""Structural (log-gradient) representation.

Applies log1p compression to the gradient magnitude. This further reduces the
dominance of high-contrast edges and gives low-contrast structural details
(ridges, subtle terrain undulations) a stronger relative weight.

Useful as a secondary fallback for difficult/cross-modal pairs where raw
gradient magnitude is dominated by a few bright-edge pixels.

This is NOT phase congruency (which requires a full monogenic signal). Phase
congruency is a future experiment (EXP-002, EXP-004).
"""

from __future__ import annotations

import cv2
import numpy as np

from src.representation._loader import load_array


def build_structural(raster_uri: str, *, ksize: int = 3) -> np.ndarray:
    """Load image and return log-gradient structural representation (float32, [0, 1]).

    Parameters
    ----------
    raster_uri:
        Filesystem path or URI to the single-band raster file.
    ksize:
        Sobel kernel size passed to the gradient stage.

    Returns
    -------
    np.ndarray
        float32 array, shape (H, W), values in [0, 1].
    """
    img = load_array(raster_uri)

    img_u8 = (img * 255.0).clip(0, 255).astype(np.uint8)
    gx = cv2.Sobel(img_u8, cv2.CV_32F, 1, 0, ksize=ksize)
    gy = cv2.Sobel(img_u8, cv2.CV_32F, 0, 1, ksize=ksize)
    magnitude = np.sqrt(gx**2 + gy**2).astype(np.float32)

    # log1p compression: suppresses dominant edges, promotes structural detail.
    log_mag = np.log1p(magnitude)

    max_val = float(log_mag.max())
    if max_val == 0.0:
        return log_mag

    return (log_mag / max_val).astype(np.float32)
