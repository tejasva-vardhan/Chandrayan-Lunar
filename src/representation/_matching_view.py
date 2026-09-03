"""Derived matching-view helpers for large raster handling.

This module creates deterministic lower-resolution views for matching when a
full-resolution representation would exceed the engineering pixel budget.
Original source rasters are never modified.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from src.models.lunar_product import LunarProduct
from src.representation._loader import inspect_array_shape, load_array, load_valid_mask
from src.representation.cross_sensor import build_cross_sensor_array
from src.representation.gradient import build_gradient_array
from src.representation.intensity import build_intensity_array
from src.representation.settings import (
    SCALE_POLICY_COMMON_PHYSICAL_GSD,
    SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET,
    MatchingViewSettings,
)
from src.representation.structural import build_structural_array


def build_representation_array(
    raster_uri: str,
    representation_id: str,
    *,
    stride: int = 1,
) -> np.ndarray:
    """Load one raster and build the requested representation."""
    img = load_array(raster_uri, stride=stride)
    if representation_id == "gradient":
        return build_gradient_array(img)
    if representation_id == "structural":
        return build_structural_array(img)
    if representation_id == "cross_sensor":
        return build_cross_sensor_array(img)
    return build_intensity_array(img)


def build_matching_mask(
    mask_uri: str | None,
    *,
    stride: int,
    expected_shape: tuple[int, int],
) -> np.ndarray | None:
    """Load and decimate a product validity mask for matcher consumption."""
    if mask_uri is None:
        return None

    mask = load_valid_mask(mask_uri, stride=stride)
    if mask.shape != expected_shape:
        raise ValueError(
            "derived matching mask shape does not match its representation: "
            f"mask={mask.shape}, representation={expected_shape}"
        )
    return mask


def determine_matching_view(
    product: LunarProduct,
    settings: MatchingViewSettings,
) -> dict[str, object]:
    """Return deterministic matching-view metadata for one product.

    This is the EXP-000 per-image pixel-budget rule. Pair-aware scale
    policies must call ``determine_pair_matching_views``.
    """
    if settings.scale_policy == SCALE_POLICY_COMMON_PHYSICAL_GSD:
        raise ValueError(
            "common_physical_gsd is pair-aware; call determine_pair_matching_views"
        )
    if settings.scale_policy != SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET:
        raise ValueError(
            "unsupported matching-view scale_policy: "
            f"{settings.scale_policy!r}; expected "
            f"{SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET!r} or "
            f"{SCALE_POLICY_COMMON_PHYSICAL_GSD!r}"
        )
    shape = _require_shape(product)
    stride = stride_for_shape(shape[0], shape[1], settings.max_pixels_per_image)
    return _view_from_stride(product, settings, stride)


def apply_relative_stride(stride: int, factor: float) -> int:
    """Return ``max(1, round(stride * factor))`` for a relative scale variant."""
    if stride <= 0:
        raise ValueError("stride must be positive")
    number = float(factor)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(
            f"relative stride factor must be finite and positive, got {factor!r}"
        )
    return max(1, int(round(stride * number)))


def determine_pair_matching_views(
    source: LunarProduct,
    reference: LunarProduct,
    settings: MatchingViewSettings,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return matching-view metadata for both products under one scale policy."""
    policy = settings.scale_policy or SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET
    if policy == SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET:
        return (
            determine_matching_view(source, settings),
            determine_matching_view(reference, settings),
        )
    if policy == SCALE_POLICY_COMMON_PHYSICAL_GSD:
        return _common_physical_gsd_views(source, reference, settings)
    raise ValueError(
        "unsupported matching-view scale_policy: "
        f"{policy!r}; expected {SCALE_POLICY_PER_IMAGE_PIXEL_BUDGET!r} or "
        f"{SCALE_POLICY_COMMON_PHYSICAL_GSD!r}"
    )


def stride_for_shape(height: int, width: int, max_pixels_per_image: int) -> int:
    """Return the deterministic decimation stride for one image shape."""
    if height <= 0 or width <= 0:
        raise ValueError("image dimensions must be positive")
    if max_pixels_per_image <= 0:
        raise ValueError("max_pixels_per_image must be positive")

    pixel_count = int(height) * int(width)
    if pixel_count <= max_pixels_per_image:
        return 1

    return int(math.ceil(math.sqrt(pixel_count / max_pixels_per_image)))


def matching_shape_for_stride(height: int, width: int, stride: int) -> tuple[int, int]:
    """Return (height, width) of a stride-decimated view."""
    if stride <= 0:
        raise ValueError("stride must be positive")
    return (int(height) + stride - 1) // stride, (int(width) + stride - 1) // stride


def common_scale_stride(
    height: int,
    width: int,
    gsd_meters: float,
    target_gsd_meters: float,
    max_pixels_per_image: int,
) -> int:
    """Integer stride so ``gsd * stride`` approximates *target_gsd_meters*.

    Never chooses a stride finer than the per-image pixel-budget stride, so
    the derived view cannot exceed ``max_pixels_per_image``.
    """
    gsd = _finite_positive(gsd_meters)
    target = _finite_positive(target_gsd_meters)
    if gsd is None or target is None:
        raise ValueError("common-scale stride requires finite positive GSD values")

    budget = stride_for_shape(height, width, max_pixels_per_image)
    chosen = max(budget, int(round(target / gsd)))
    if chosen < 1:
        chosen = 1
    while True:
        match_h, match_w = matching_shape_for_stride(height, width, chosen)
        if match_h * match_w <= max_pixels_per_image:
            return chosen
        chosen += 1


def resolve_matching_gsd(
    product: LunarProduct,
    settings: MatchingViewSettings,
) -> tuple[float, str]:
    """Return (gsd_meters, origin) for matching-view scale selection.

    Prefers ingested ``LunarProduct.gsd_meters``. A catalog fallback is used
    only when that field is missing. SPICE is not queried. The product is
    not modified.
    """
    ingested = _finite_positive(product.gsd_meters)
    if ingested is not None:
        return ingested, "ingested_lunar_product_gsd_meters"

    catalog = _catalog_gsd(settings, product.instrument)
    if catalog is not None:
        return catalog, "catalog_gsd_meters_by_instrument"

    raise ValueError(
        "common_physical_gsd requires a GSD for "
        f"product_id={product.product_id!r} instrument={product.instrument!r}; "
        "ingested gsd_meters is missing and no catalog fallback was provided. "
        "SPICE is not used to invent a ground sample distance."
    )


def _common_physical_gsd_views(
    source: LunarProduct,
    reference: LunarProduct,
    settings: MatchingViewSettings,
) -> tuple[dict[str, object], dict[str, object]]:
    source_shape = _require_shape(source)
    reference_shape = _require_shape(reference)
    source_gsd, source_origin = resolve_matching_gsd(source, settings)
    reference_gsd, reference_origin = resolve_matching_gsd(reference, settings)

    source_budget = stride_for_shape(
        source_shape[0], source_shape[1], settings.max_pixels_per_image
    )
    reference_budget = stride_for_shape(
        reference_shape[0], reference_shape[1], settings.max_pixels_per_image
    )
    target_gsd = max(source_gsd * source_budget, reference_gsd * reference_budget)
    source_stride = common_scale_stride(
        source_shape[0],
        source_shape[1],
        source_gsd,
        target_gsd,
        settings.max_pixels_per_image,
    )
    reference_stride = common_scale_stride(
        reference_shape[0],
        reference_shape[1],
        reference_gsd,
        target_gsd,
        settings.max_pixels_per_image,
    )
    source_view = _view_from_stride(
        source,
        settings,
        source_stride,
        extra={
            "scale_policy": SCALE_POLICY_COMMON_PHYSICAL_GSD,
            "gsd_meters": source_gsd,
            "gsd_source": source_origin,
            "effective_gsd_meters": source_gsd * source_stride,
            "target_gsd_meters": target_gsd,
            "pixel_budget_stride": source_budget,
        },
    )
    reference_view = _view_from_stride(
        reference,
        settings,
        reference_stride,
        extra={
            "scale_policy": SCALE_POLICY_COMMON_PHYSICAL_GSD,
            "gsd_meters": reference_gsd,
            "gsd_source": reference_origin,
            "effective_gsd_meters": reference_gsd * reference_stride,
            "target_gsd_meters": target_gsd,
            "pixel_budget_stride": reference_budget,
        },
    )
    return source_view, reference_view


def _view_from_stride(
    product: LunarProduct,
    settings: MatchingViewSettings,
    stride: int,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    stride, relative_extra = _apply_relative_stride_override(product, settings, stride)
    if extra is None:
        extra = relative_extra
    elif relative_extra:
        extra = {**extra, **relative_extra}
    if settings.downsample_method != "stride_decimation":
        raise ValueError(
            "unsupported matching-view method: "
            f"{settings.downsample_method!r}; expected 'stride_decimation'"
        )
    if stride > 1 and Path(product.raster_uri or "").suffix.lower() != ".npy":
        raise ValueError(
            "large-raster matching requires a memory-mapped .npy raster handle; "
            f"cannot safely decimate {product.raster_uri!r}"
        )
    height, width = _require_shape(product)
    matching_height, matching_width = matching_shape_for_stride(height, width, stride)
    view: dict[str, object] = {
        "policy": "full_resolution" if stride == 1 else settings.downsample_method,
        "stride": stride,
        "x_scale": float(stride),
        "y_scale": float(stride),
        "original_shape": [int(height), int(width)],
        "matching_shape": [int(matching_height), int(matching_width)],
        "max_pixels_per_image": int(settings.max_pixels_per_image),
    }
    if extra:
        view.update(extra)
    return view


def _apply_relative_stride_override(
    product: LunarProduct,
    settings: MatchingViewSettings,
    stride: int,
) -> tuple[int, dict[str, object]]:
    factor = _relative_stride_factor(settings, product.instrument)
    if factor is None:
        return stride, {}
    chosen = apply_relative_stride(stride, factor)
    height, width = _require_shape(product)
    match_h, match_w = matching_shape_for_stride(height, width, chosen)
    return chosen, {
        "relative_stride_factor": factor,
        "baseline_stride": stride,
        "exceeds_max_pixels_per_image": (
            match_h * match_w > int(settings.max_pixels_per_image)
        ),
    }


def _relative_stride_factor(
    settings: MatchingViewSettings, instrument: str
) -> float | None:
    for name, value in settings.relative_stride_factor_by_instrument:
        if name == instrument:
            parsed = _finite_positive(value)
            if parsed is None:
                raise ValueError(
                    "relative stride factor for "
                    f"instrument={instrument!r} must be finite and positive, "
                    f"got {value!r}"
                )
            return parsed
    return None


def _catalog_gsd(settings: MatchingViewSettings, instrument: str) -> float | None:
    for name, value in settings.catalog_gsd_meters_by_instrument:
        if name == instrument:
            return _finite_positive(value)
    return None


def _finite_positive(value: float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _require_shape(product: LunarProduct) -> tuple[int, int]:
    shape = _product_shape(product)
    if shape is None:
        raise ValueError(
            f"cannot determine raster shape for product_id={product.product_id!r}; "
            "large-raster matching view cannot be selected safely"
        )
    return shape


def _product_shape(product: LunarProduct) -> tuple[int, int] | None:
    dims = product.dimensions
    if dims is not None:
        return int(dims.height_px), int(dims.width_px)

    raster_uri = product.raster_uri
    if raster_uri is None:
        return None
    return inspect_array_shape(raster_uri)


__all__ = [
    "apply_relative_stride",
    "build_matching_mask",
    "build_representation_array",
    "common_scale_stride",
    "determine_matching_view",
    "determine_pair_matching_views",
    "matching_shape_for_stride",
    "resolve_matching_gsd",
    "stride_for_shape",
]
