"""Optional robust contrast normalization (median / IQR).

ENGINEERING DESCRIPTOR scaling. Off in the software baseline.

This does not make different sensors radiometrically equivalent. A
transform that helps OHRC↔OHRC may harm OHRC↔IIRS. It is isolated so
later ablation can turn it on with the same pairs and matcher.

Formula (per 2-D plane, finite samples V)
    med = median(V)
    iqr = percentile(V, 75) - percentile(V, 25)
    If |V| == 0: all-NaN.
    If iqr == 0: leave finite samples unchanged (constant contrast).
    Else: y = (x - med) / iqr

Output domain is unbounded robust units. Invalid samples stay NaN.
Spatial structure is a monotonic per-plane affine map of finite values.
"""

from __future__ import annotations

import math

import numpy as np


def _contrast_plane(plane: np.ndarray, valid: np.ndarray) -> np.ndarray:
    out = np.full(plane.shape, np.nan, dtype=float)
    samples = plane[valid]
    if samples.size == 0:
        return out
    median = float(np.median(samples))
    q75, q25 = np.percentile(samples, [75.0, 25.0])
    iqr = float(q75 - q25)
    if not math.isfinite(median) or not math.isfinite(iqr):
        return out
    if iqr == 0.0:
        out[valid] = plane[valid]
        return out
    scaled = (plane.astype(float) - median) / iqr
    out[valid] = scaled[valid]
    return out


def robust_contrast(array: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Median/IQR contrast. Invalid positions stay NaN."""

    if array.ndim == 2:
        return _contrast_plane(array, valid)
    planes = [
        _contrast_plane(
            array[:, :, band],
            valid[:, :, band] if valid.ndim == 3 else valid,
        )
        for band in range(array.shape[2])
    ]
    return np.stack(planes, axis=2)
