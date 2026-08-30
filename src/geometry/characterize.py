"""Frozen pair-characterization callable.

characterize_pair(source, reference) -> RegistrationPair

Observational only: describes the pair from metadata already present on
the two LunarProduct objects. Does not preprocess, match, verify, select
control points, refine, register, evaluate, or route.
"""

from __future__ import annotations

from src.geometry.adapters import (
    GeometryProvider,
    ProductGeometry,
    ProductMetadataProvider,
)
from src.geometry.difficulty import categorical_difficulty, quality_flags
from src.geometry.measures import (
    acquisition_time_difference_seconds,
    expected_overlap,
    gsd_ratio,
    pair_id_for,
    pair_modality_label,
    sensor_pair_label,
    sun_angle_difference_degrees,
    viewing_geometry_difference,
)
from src.geometry.rasters import pair_valid_pixel_ratio
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import PairCharacterization, RegistrationPair

_DEFAULT_PROVIDER = ProductMetadataProvider()


def build_characterization(
    source: ProductGeometry,
    reference: ProductGeometry,
    *,
    overlap_fraction: float | None = None,
) -> PairCharacterization:
    """Fill PairCharacterization from ProductGeometry records.

    overlap_fraction is used only when a caller supplies a real overlap
    fraction. The product adapter never does. Raster texture is not
    written: LunarProduct does not embed arrays, and a pair-level
    texture_contrast scalar is not defined for two modalities.
    """

    ratio = gsd_ratio(source.gsd_meters, reference.gsd_meters)
    sun_angle = sun_angle_difference_degrees(source.sun_vector, reference.sun_vector)
    viewing = viewing_geometry_difference(source.look_vector, reference.look_vector)
    time_delta = acquisition_time_difference_seconds(
        source.acquisition_time, reference.acquisition_time
    )
    overlap = expected_overlap(overlap_fraction)
    valid_ratio = pair_valid_pixel_ratio(
        source_product_ratio=source.product_valid_pixel_ratio,
        reference_product_ratio=reference.product_valid_pixel_ratio,
    )
    sensor_pair = sensor_pair_label(source.instrument, reference.instrument)
    modality = pair_modality_label(source.instrument, reference.instrument)
    flags = quality_flags(
        gsd_ratio=ratio,
        sun_angle_difference_degrees=sun_angle,
        viewing_geometry_difference=viewing,
        source_instrument=source.instrument,
        reference_instrument=reference.instrument,
        acquisition_time_difference_seconds=time_delta,
    )
    return PairCharacterization(
        sensor_pair=sensor_pair,
        gsd_ratio=ratio,
        acquisition_time_difference_seconds=time_delta,
        sun_angle_difference_degrees=sun_angle,
        viewing_geometry_difference=viewing,
        expected_overlap=overlap,
        valid_pixel_ratio=valid_ratio,
        texture_contrast=None,
        modality=modality,
        quality_flags=flags,
        difficulty=categorical_difficulty(),
    )


def characterize_pair(source: LunarProduct, reference: LunarProduct) -> RegistrationPair:
    """Build a RegistrationPair and fill characterization from product metadata.

    Source and reference products are preserved. Imagery, coordinates, and
    correspondences are not modified. Matcher identity is not selected.
    Uncomputable scientific fields stay None.
    """

    return characterize_pair_with_provider(source, reference, _DEFAULT_PROVIDER)


def characterize_pair_with_provider(
    source: LunarProduct,
    reference: LunarProduct,
    provider: GeometryProvider,
) -> RegistrationPair:
    """Same as characterize_pair, with an injectable GeometryProvider.

    Not a frozen pipeline signature. Exists so a future SPICE adapter can
    supply ProductGeometry without changing characterize_pair(source, reference).
    """

    source_geometry = provider.for_product(source)
    reference_geometry = provider.for_product(reference)
    characterization = build_characterization(source_geometry, reference_geometry)
    return RegistrationPair(
        pair_id=pair_id_for(source.product_id, reference.product_id),
        source=source,
        reference=reference,
        characterization=characterization,
        overlap_mask_uri=None,
    )
