"""Safe image loader shared by representation and matching.

Loads a raster from a filesystem path or URI and returns a float32 numpy
array normalised to [0, 1]. Only single-band (grayscale) images are accepted
in this baseline. Multi-band support (e.g. IIRS cubes) is a future experiment.

This loader is internal to Chuba's modules. Haruto's ingestion layer owns the
authoritative product reader; this loader is a lightweight convenience for
the matching stage only.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def load_array(raster_uri: str) -> np.ndarray:
    """Load an image file and return a float32 array in [0, 1], shape (H, W).

    Parameters
    ----------
    raster_uri:
        Filesystem path (absolute or relative) or ``file://`` URI to the image.
        Must point to a readable single-band or colour image file that OpenCV
        can decode (PNG, TIFF, JPEG, etc.).

    Returns
    -------
    np.ndarray
        float32, shape (H, W), pixel values in [0, 1].

    Raises
    ------
    ValueError
        If the URI is empty, the file does not exist, or OpenCV cannot decode it.
    """
    if not raster_uri:
        raise ValueError("raster_uri is empty; cannot load image.")

    # Strip file:// scheme if present.
    path_str = raster_uri
    if path_str.startswith("file://"):
        path_str = path_str[7:]

    path = Path(path_str)
    if not path.exists():
        raise ValueError(f"raster_uri path does not exist: {path}")

    # Load as grayscale. IMREAD_ANYDEPTH preserves 16-bit images (e.g. OHRC).
    img = cv2.imread(str(path), cv2.IMREAD_ANYDEPTH | cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"OpenCV could not decode image at: {path}")

    # Normalise to float32 [0, 1] based on dtype range.
    img_f = img.astype(np.float32)
    if img.dtype == np.uint8:
        img_f /= 255.0
    elif img.dtype == np.uint16:
        img_f /= 65535.0
    else:
        # For float images or unusual dtypes: range-normalise.
        min_v, max_v = float(img_f.min()), float(img_f.max())
        if max_v > min_v:
            img_f = (img_f - min_v) / (max_v - min_v)

    return img_f.astype(np.float32)
