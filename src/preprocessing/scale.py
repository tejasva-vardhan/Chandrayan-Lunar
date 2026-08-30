"""Explicit scale-resampling hook that does not resample.

GSD ratio from pair characterization is a descriptive measurement
(Interface Freeze v1). Pixel origin (centre vs corner) is undefined.
Without a justified resampling kernel and known pixel geometry, resizing
because dimensions or GSD differ would invent scale invariance.

This function returns the array unchanged. ``gsd_ratio`` and ``enabled``
are accepted so callers do not hide a silent resize elsewhere. They are
not used.
"""

from __future__ import annotations

import numpy as np


def apply_scale_hook(
    array: np.ndarray,
    gsd_ratio: float | None,
    enabled: bool,
) -> np.ndarray:
    """Identity. Never resamples. Not scale invariance."""

    del gsd_ratio, enabled
    return array
