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

    return _to_unit_interval(img)


def load_strided_window(
    raster_uri: str,
    *,
    row: int,
    col: int,
    height: int,
    width: int,
    stride: int,
) -> np.ndarray:
    """Load one stride-decimated window as float32 in [0, 1].

    Only ``.npy`` handles are accepted so a large raster is never decoded
    just to crop a tile. Original rasters are not modified.
    """

    window, dtype = _strided_npy_window(
        raster_uri, row=row, col=col, height=height, width=width, stride=stride
    )
    return _to_unit_interval(window, source_dtype=dtype)


def load_strided_mask_window(
    mask_uri: str,
    *,
    row: int,
    col: int,
    height: int,
    width: int,
    stride: int,
) -> np.ndarray:
    """Load one stride-decimated validity window as a boolean array."""

    window, _dtype = _strided_npy_window(
        mask_uri, row=row, col=col, height=height, width=width, stride=stride
    )
    return np.isfinite(window) & (window != 0)


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


def _strided_npy_window(
    raster_uri: str,
    *,
    row: int,
    col: int,
    height: int,
    width: int,
    stride: int,
) -> tuple[np.ndarray, np.dtype]:
    if stride <= 0:
        raise ValueError("stride must be positive")
    if height <= 0 or width <= 0:
        raise ValueError("window height and width must be positive")
    if row < 0 or col < 0:
        raise ValueError("window origin must be non-negative")

    path = _resolve_raster_path(raster_uri)
    if path.suffix.lower() != ".npy":
        raise ValueError(
            "strided window load requires a memory-mapped .npy raster handle; "
            f"cannot safely crop {raster_uri!r}"
        )
    try:
        array = np.load(path, mmap_mode="r")
    except (OSError, ValueError) as exc:
        raise ValueError(f"NumPy could not load raster at: {path}") from exc
    if array.ndim != 2:
        raise ValueError(f".npy raster must be 2D for window loading: {path}")

    row_end = row + height
    col_end = col + width
    if row_end > array.shape[0] or col_end > array.shape[1]:
        raise ValueError(
            "window exceeds raster bounds: "
            f"requested=({row}:{row_end}, {col}:{col_end}) shape={array.shape}"
        )
    window = np.asarray(array[row:row_end:stride, col:col_end:stride])
    return window, array.dtype


def _to_unit_interval(
    img: np.ndarray, *, source_dtype: np.dtype | None = None
) -> np.ndarray:
    """Convert a raster window to float32 [0, 1] using the original dtype range."""

    dtype = img.dtype if source_dtype is None else source_dtype
    img_f = img.astype(np.float32)
    if dtype == np.uint8:
        img_f /= 255.0
    elif dtype == np.uint16:
        img_f /= 65535.0
    else:
        min_v, max_v = float(img_f.min()), float(img_f.max())
        if max_v > min_v:
            img_f = (img_f - min_v) / (max_v - min_v)
    return img_f.astype(np.float32)


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
