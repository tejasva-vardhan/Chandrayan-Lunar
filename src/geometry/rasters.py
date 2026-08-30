"""Array descriptors for pair characterization.

These functions operate on caller-supplied arrays. characterize_pair does
not load raster_uri or mask_uri: LunarProduct does not embed imagery, the
product file format is not frozen, and zeros are not invalid unless a
product mask says so.

Results are ENGINEERING DESCRIPTORS, not scientifically validated lunar
texture or valid-pixel scores. Intensity statistics are not assumed
comparable across different modalities.

Valid pixel definition used here
--------------------------------
A sample is valid when it is finite (not NaN, not Inf). Zero-valued
samples are valid. An optional boolean mask, when provided, further
restricts validity (True = included). The ratio is
valid_count / array.size. Empty arrays yield None, not 0.0.
"""

from __future__ import annotations

import math

import numpy as np

_MIN_STD_SAMPLES = 1


def _as_float_array(array: np.ndarray | None) -> np.ndarray | None:
    if array is None:
        return None
    values = np.asarray(array, dtype=float)
    if values.size == 0:
        return None
    return values


def _finite_samples(array: np.ndarray, mask: np.ndarray | None) -> np.ndarray | None:
    finite = np.isfinite(array)
    if mask is not None:
        mask_array = np.asarray(mask, dtype=bool)
        if mask_array.shape != array.shape:
            return None
        finite = finite & mask_array
    return array[finite]


def array_valid_pixel_ratio(
    array: np.ndarray | None, mask: np.ndarray | None = None
) -> float | None:
    """valid finite samples / total samples, or None if the array is empty.

    Do not treat zeros as invalid. All-invalid non-empty arrays return 0.0
    (a measured ratio). Shape-mismatched masks return None.
    """

    values = _as_float_array(array)
    if values is None:
        return None
    samples = _finite_samples(values, mask)
    if samples is None:
        return None
    return float(samples.size / values.size)


def pair_valid_pixel_ratio(
    source_array: np.ndarray | None = None,
    reference_array: np.ndarray | None = None,
    overlap_mask: np.ndarray | None = None,
    source_product_ratio: float | None = None,
    reference_product_ratio: float | None = None,
) -> float | None:
    """Pair/overlap-aware valid-pixel ratio.

    PairCharacterization.valid_pixel_ratio is overlap-aware and distinct
    from LunarProduct.valid_pixel_ratio. Per-product ratios are not
    combined. Separate source/reference arrays without an overlap-aware
    valid raster are not a pair measurement.

    When ``overlap_mask`` is a numeric overlap-region raster, the finite-
    sample ratio of that raster is returned. Boolean masks are not treated
    as intensity rasters (True/False would both be finite). A boolean
    overlap mask without a validity definition yields None.
    """

    del source_array, reference_array, source_product_ratio, reference_product_ratio
    if overlap_mask is None:
        return None
    mask = np.asarray(overlap_mask)
    if mask.dtype == bool:
        return None
    return array_valid_pixel_ratio(mask)


def intensity_standard_deviation(array: np.ndarray | None) -> float | None:
    """Population std (ddof=0) of finite samples.

    ENGINEERING DESCRIPTOR. Not a lunar texture score. All-non-finite or
    empty → None. A single finite sample → 0.0.
    """

    values = _as_float_array(array)
    if values is None:
        return None
    finite = values[np.isfinite(values)]
    if finite.size < _MIN_STD_SAMPLES:
        return None
    if finite.size == 1:
        return 0.0
    std = float(np.std(finite, ddof=0))
    if not math.isfinite(std):
        return None
    return std


def robust_contrast_iqr(array: np.ndarray | None) -> float | None:
    """Interquartile range (p75 − p25) of finite samples.

    ENGINEERING DESCRIPTOR. Not a scientifically validated contrast metric.
    """

    values = _as_float_array(array)
    if values is None:
        return None
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    q75, q25 = np.percentile(finite, [75.0, 25.0])
    contrast = float(q75 - q25)
    if not math.isfinite(contrast):
        return None
    return contrast
