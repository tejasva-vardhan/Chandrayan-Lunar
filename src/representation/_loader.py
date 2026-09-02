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

import numpy as np


def inspect_array_shape(raster_uri: str) -> tuple[int, int] | None:
    """Return the 2-D raster shape without forcing a full in-memory load."""
    path = _resolve_raster_path(raster_uri)

    if path.suffix.lower() == ".npy":
        try:
            img_npy = np.load(path, mmap_mode="r")
        except (OSError, ValueError) as exc:
            raise ValueError(f"NumPy could not inspect raster at: {path}") from exc
        if img_npy.ndim != 2:
            raise ValueError(f".npy raster must be 2D for representation loading: {path}")
        return int(img_npy.shape[0]), int(img_npy.shape[1])

    return None


def load_array(raster_uri: str, *, stride: int = 1) -> np.ndarray:
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
    if stride <= 0:
        raise ValueError("stride must be positive")

    path = _resolve_raster_path(raster_uri)

    if path.suffix.lower() == ".npy":
        try:
            img_npy = np.load(path, mmap_mode="r")
        except (OSError, ValueError) as exc:
            raise ValueError(f"NumPy could not load raster at: {path}") from exc
        if img_npy.ndim != 2:
            raise ValueError(f".npy raster must be 2D for representation loading: {path}")
        img = np.asarray(img_npy[::stride, ::stride])
    else:
        # Load as grayscale. IMREAD_ANYDEPTH preserves 16-bit images (e.g. OHRC).
        try:
            import cv2
        except ImportError as exc:
            raise ImportError(
                "opencv-python-headless is required to load non-.npy image rasters."
            ) from exc
        img = cv2.imread(str(path), cv2.IMREAD_ANYDEPTH | cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"OpenCV could not decode image at: {path}")
        if stride > 1:
            img = img[::stride, ::stride]

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


def load_valid_mask(mask_uri: str, *, stride: int = 1) -> np.ndarray:
    """Load a derived valid-pixel mask as a boolean array.

    This is deliberately separate from ``load_array``: validity values are
    categorical and must not be intensity-normalised before SIFT consumes them.
    """
    if stride <= 0:
        raise ValueError("stride must be positive")

    path = _resolve_raster_path(mask_uri)
    if path.suffix.lower() == ".npy":
        try:
            raw_mask = np.load(path, mmap_mode="r")
        except (OSError, ValueError) as exc:
            raise ValueError(f"NumPy could not load mask at: {path}") from exc
        if raw_mask.ndim != 2:
            raise ValueError(f".npy mask must be 2D for representation loading: {path}")
        mask = np.asarray(raw_mask[::stride, ::stride])
    else:
        try:
            import cv2
        except ImportError as exc:
            raise ImportError(
                "opencv-python-headless is required to load non-.npy masks."
            ) from exc
        mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise ValueError(f"OpenCV could not decode mask at: {path}")
        if stride > 1:
            mask = mask[::stride, ::stride]

    return np.isfinite(mask) & (mask != 0)


def _resolve_raster_path(raster_uri: str) -> Path:
    if not raster_uri:
        raise ValueError("raster_uri is empty; cannot load image.")

    path_str = raster_uri
    if path_str.startswith("file://"):
        path_str = path_str[7:]

    path = Path(path_str)
    if not path.exists():
        raise ValueError(f"raster_uri path does not exist: {path}")
    return path
