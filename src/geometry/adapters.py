"""Metadata extraction for pair characterization.

This module reads fields that already exist on LunarProduct. It does not
infer GSD, Sun geometry, viewing geometry, overlap, or modality from
filenames, placeholders, or bounding boxes.

SPICE and DEM are not implemented here. ProductGeometry.sun_vector,
look_vector, and terrain_available are extension slots so a future adapter
can supply those values without changing PairCharacterization or the frozen
characterize_pair(source, reference) signature.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.models.lunar_product import LunarProduct


@dataclass(frozen=True, slots=True)
class ProductGeometry:
    """Defensible per-product metadata used by characterization math.

    This is an internal geometry record, not a frozen pipeline contract.
    Missing scientific values stay None. Arrays are not loaded.
    """

    product_id: str
    instrument: str | None
    mission: str | None
    width_px: int | None
    height_px: int | None
    band_count: int | None
    gsd_meters: float | None
    acquisition_time: datetime | None
    product_valid_pixel_ratio: float | None
    raster_uri: str | None
    mask_uri: str | None
    sun_vector: tuple[float, float, float] | None
    look_vector: tuple[float, float, float] | None
    terrain_available: bool


class GeometryProvider(Protocol):
    """Supplies ProductGeometry for one LunarProduct.

    Current implementation: ProductMetadataProvider (product fields only).
    Future SPICE adapter: may fill sun_vector and look_vector in a common frame.
    Future DEM adapter: may set terrain_available when a terrain source exists.
    """

    def for_product(self, product: LunarProduct) -> ProductGeometry: ...


class ProductMetadataProvider:
    """Extract geometry metadata that LunarProduct already carries.

    Never invents Sun vectors, look vectors, GSD, dimensions, or overlap.
    Does not read raster_uri or mask_uri. Does not call SPICE.
    """

    def for_product(self, product: LunarProduct) -> ProductGeometry:
        return geometry_from_product(product)


def geometry_from_product(product: LunarProduct) -> ProductGeometry:
    """Copy extractable LunarProduct fields into ProductGeometry.

    Sun, look, and terrain slots stay empty: those quantities are not on
    the frozen LunarProduct contract and this stage does not run SPICE or DEM.
    """

    dimensions = product.dimensions
    return ProductGeometry(
        product_id=product.product_id,
        instrument=product.instrument,
        mission=product.mission,
        width_px=dimensions.width_px if dimensions is not None else None,
        height_px=dimensions.height_px if dimensions is not None else None,
        band_count=dimensions.band_count if dimensions is not None else None,
        gsd_meters=product.gsd_meters,
        acquisition_time=product.acquisition_time,
        product_valid_pixel_ratio=product.valid_pixel_ratio,
        raster_uri=product.raster_uri,
        mask_uri=product.mask_uri,
        sun_vector=None,
        look_vector=None,
        terrain_available=False,
    )
