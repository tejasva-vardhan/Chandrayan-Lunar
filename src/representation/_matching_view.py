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
from src.representation.gradient import build_gradient_array
from src.representation.intensity import build_intensity_array
from src.representation.settings import MatchingViewSettings
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
    """Return deterministic matching-view metadata for one product."""
    shape = _product_shape(product)
    if shape is None:
        raise ValueError(
            f"cannot determine raster shape for product_id={product.product_id!r}; "
            "large-raster matching view cannot be selected safely"
        )

    height, width = shape
    stride = stride_for_shape(height, width, settings.max_pixels_per_image)
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
    matching_height = (height + stride - 1) // stride
    matching_width = (width + stride - 1) // stride
    return {
        "policy": "full_resolution" if stride == 1 else settings.downsample_method,
        "stride": stride,
        "x_scale": float(stride),
        "y_scale": float(stride),
        "original_shape": [int(height), int(width)],
        "matching_shape": [int(matching_height), int(matching_width)],
        "max_pixels_per_image": int(settings.max_pixels_per_image),
    }


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


def _product_shape(product: LunarProduct) -> tuple[int, int] | None:
    dims = product.dimensions
    if dims is not None:
        return int(dims.height_px), int(dims.width_px)

    raster_uri = product.raster_uri
    if raster_uri is None:
        return None
    return inspect_array_shape(raster_uri)


__all__ = [
    "build_matching_mask",
    "build_representation_array",
    "determine_matching_view",
    "stride_for_shape",
]
