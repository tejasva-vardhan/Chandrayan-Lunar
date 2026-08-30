"""Optional nan-aware mean denoising.

Off in the software baseline. A matcher can be harmed by smoothing:
peaks shift and edges weaken. This 3x3 (by default) mean exists only as
an explicit ablation hook.

Kernel
    Odd square window of side ``kernel_size``. ENGINEERING DEFAULT 3.

Numerical behaviour
    For each valid pixel, the output is the mean of finite samples in the
    window (NaN neighbors ignored). Invalid pixels stay NaN — the filter
    does not fill holes.

Why it may help
    Suppress isolated intensity spikes before a detector.

How it may hurt
    Mean filtering is a low-pass operator. Feature localization can
    degrade; this is not a scientifically justified lunar denoiser.
"""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def _nanmean_2d(plane: np.ndarray, kernel_size: int) -> np.ndarray:
    pad = kernel_size // 2
    padded = np.pad(plane, pad, mode="constant", constant_values=np.nan)
    windows = sliding_window_view(padded, (kernel_size, kernel_size))
    with np.errstate(all="ignore"):
        filtered = np.nanmean(windows, axis=(-1, -2))
    out = np.asarray(filtered, dtype=float)
    out[~np.isfinite(plane)] = np.nan
    return out


def mean_denoise(array: np.ndarray, *, kernel_size: int) -> np.ndarray:
    """Odd-square nan-aware mean. Invalid positions stay NaN."""

    if kernel_size == 1:
        out = np.asarray(array, dtype=float).copy()
        out[~np.isfinite(out)] = np.nan
        return out
    if array.ndim == 2:
        return _nanmean_2d(array, kernel_size)
    planes = [_nanmean_2d(array[:, :, band], kernel_size) for band in range(array.shape[2])]
    return np.stack(planes, axis=2)
