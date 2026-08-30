"""Frozen pair-aware preprocessing callable.

preprocess(pair) -> RegistrationPair

SOFTWARE BASELINE. Prepares source/reference software rasters for later
representation/matching. Does not match, verify, select control points,
refine, register, resample by GSD, warp, or route.

Original products are not overwritten. A derived ``.preprocessed.npy`` is
written beside a readable software raster. Missing or unsupported rasters
leave that product unchanged (fail closed, no fabricated imagery).
"""

from __future__ import annotations

import numpy as np

from src.models.common import Provenance
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.preprocessing.contrast import robust_contrast
from src.preprocessing.denoise import mean_denoise
from src.preprocessing.intensity import percentile_stretch
from src.preprocessing.mask import apply_invalid_as_nan, valid_mask
from src.preprocessing.raster import (
    load_software_raster,
    preprocessed_uri_for,
    save_software_raster,
)
from src.preprocessing.scale import apply_scale_hook
from src.preprocessing.settings import PreprocessingSettings, unvalidated_software_defaults

_READER = "preprocessing_software_baseline"


def _gsd_ratio(pair: RegistrationPair) -> float | None:
    if pair.characterization is None:
        return None
    return pair.characterization.gsd_ratio


def _notes(settings: PreprocessingSettings, original_uri: str) -> str:
    return (
        f"preprocessed_from={original_uri}; "
        f"intensity={'percentile_stretch' if settings.enable_intensity_normalization else 'off'}; "
        f"contrast={'median_iqr' if settings.enable_contrast_normalization else 'off'}; "
        f"denoise={'nanmean' if settings.enable_denoise else 'off'}; "
        f"scale=identity"
    )


def _derived_provenance(product: LunarProduct, original_uri: str, notes: str) -> Provenance:
    existing = product.provenance
    if existing is None:
        return Provenance(source_uri=original_uri, reader=_READER, notes=notes)
    source_uri = existing.source_uri if existing.source_uri is not None else original_uri
    combined = notes if existing.notes is None else f"{existing.notes}; {notes}"
    reader = existing.reader if existing.reader is not None else _READER
    return existing.model_copy(
        update={"source_uri": source_uri, "reader": reader, "notes": combined}
    )


def _process_array(
    array: np.ndarray,
    product_mask: np.ndarray | None,
    settings: PreprocessingSettings,
    gsd_ratio: float | None,
) -> np.ndarray:
    valid = valid_mask(array, product_mask)
    current = apply_invalid_as_nan(array, valid)
    if settings.enable_intensity_normalization:
        current = percentile_stretch(
            current,
            valid,
            low_percentile=settings.intensity_low_percentile,
            high_percentile=settings.intensity_high_percentile,
            output_low=settings.output_low,
            output_high=settings.output_high,
            clip_to_output_range=settings.clip_to_output_range,
        )
    if settings.enable_contrast_normalization:
        current = robust_contrast(current, valid)
    if settings.enable_denoise:
        current = mean_denoise(current, kernel_size=settings.denoise_kernel_size)
    return apply_scale_hook(current, gsd_ratio, settings.enable_scale_normalization)


def _preprocess_product(
    product: LunarProduct,
    settings: PreprocessingSettings,
    gsd_ratio: float | None,
) -> LunarProduct:
    array, error = load_software_raster(product.raster_uri)
    if array is None or error is not None or product.raster_uri is None:
        return product
    mask_array, _mask_error = load_software_raster(product.mask_uri)
    processed = _process_array(array, mask_array, settings, gsd_ratio)
    derived_uri = preprocessed_uri_for(product.raster_uri)
    written = save_software_raster(derived_uri, processed)
    if written is None:
        return product
    return product.model_copy(
        update={
            "raster_uri": written,
            "provenance": _derived_provenance(
                product, product.raster_uri, _notes(settings, product.raster_uri)
            ),
        }
    )


def preprocess(pair: RegistrationPair) -> RegistrationPair:
    """Return a copy of pair with derived software rasters when available.

    Uses unvalidated_software_defaults(). Intensity percentile stretch is an
    ENGINEERING DEFAULT, not a validated lunar preprocessing configuration.
    """

    return preprocess_with_settings(pair, unvalidated_software_defaults())


def preprocess_with_settings(
    pair: RegistrationPair, settings: PreprocessingSettings
) -> RegistrationPair:
    """Same as preprocess, with explicit settings for tests and ablation."""

    gsd_ratio = _gsd_ratio(pair)
    source = _preprocess_product(pair.source, settings, gsd_ratio)
    reference = _preprocess_product(pair.reference, settings, gsd_ratio)
    return pair.model_copy(update={"source": source, "reference": reference})
