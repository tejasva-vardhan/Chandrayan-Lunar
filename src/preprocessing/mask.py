"""Finite/valid masking for software preprocessing.

ENGINEERING DEFINITION only. This is not a PDS or lunar invalid-pixel
product. Image zeros are valid unless a caller-supplied product mask
excludes them.

Pixel classes
-------------
valid
    Finite sample, and product-mask True when a mask is aligned.
invalid
    NaN or Inf in the raster, or excluded by an aligned product mask.
unknown
    No raster, unreadable raster, or a mask that cannot be aligned.
    Preprocessing does not invent a mask in that case.
"""

from __future__ import annotations

import numpy as np


def decode_product_mask(mask: np.ndarray) -> np.ndarray:
    """Interpret a loaded product mask as a boolean valid-region.

    bool: True = valid.
    numeric: finite and != 0 = valid. That is mask encoding (0 meaning
    excluded in the mask raster), not a claim that image intensity 0 is
    no-data.
    """

    array = np.asarray(mask)
    if array.dtype == bool:
        return array
    return np.isfinite(array) & (array != 0)


def align_mask(mask: np.ndarray, shape: tuple[int, ...]) -> np.ndarray | None:
    """Broadcast a decoded mask onto a raster shape, or None if it cannot.

    2-D masks may apply to all bands of an (H, W, C) raster. Other shape
    mismatches are not guessed.
    """

    decoded = decode_product_mask(mask)
    if decoded.shape == shape:
        return decoded
    if len(shape) == 3 and decoded.ndim == 2 and decoded.shape == shape[:2]:
        return np.broadcast_to(decoded[:, :, np.newaxis], shape)
    return None


def valid_mask(array: np.ndarray, product_mask: np.ndarray | None = None) -> np.ndarray:
    """True where the sample is finite and included by an aligned product mask.

    Image zeros remain valid. Unaligned product masks are ignored.
    """

    valid = np.isfinite(array)
    if product_mask is None:
        return valid
    aligned = align_mask(product_mask, array.shape)
    if aligned is None:
        return valid
    return valid & aligned


def apply_invalid_as_nan(array: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Copy the array as float64 with invalid samples set to NaN."""

    out = np.asarray(array, dtype=float).copy()
    out[~valid] = np.nan
    return out
