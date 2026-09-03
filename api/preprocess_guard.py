"""API-layer preprocess guard for oversized full rasters.

Mirrors the EXP-000 identity passthrough: the frozen preprocess contract is
unchanged; when a product exceeds the existing engineering pixel cap, the API
skips full-raster float64 materialization and leaves matching-view stretch to
generate_representation. This is not silent resize.
"""

from __future__ import annotations

from collections.abc import Callable

from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.registration.settings import unvalidated_software_defaults

PREPROCESS_IDENTITY_FLAG = "preprocess_identity_passthrough_oversized_raster"


def _product_pixels(product: LunarProduct) -> int | None:
    if product.dimensions is None:
        return None
    return int(product.dimensions.height_px) * int(product.dimensions.width_px)


def guarded_preprocess(
    pair: RegistrationPair,
    preprocess: Callable[[RegistrationPair], RegistrationPair],
    *,
    on_identity: Callable[[str], None] | None = None,
) -> RegistrationPair:
    """Run frozen preprocess, or identity-passthrough when rasters exceed the cap."""

    cap = unvalidated_software_defaults().max_output_pixels
    source_pixels = _product_pixels(pair.source)
    reference_pixels = _product_pixels(pair.reference)
    oversize = (
        source_pixels is None
        or reference_pixels is None
        or source_pixels > cap
        or reference_pixels > cap
    )
    if not oversize:
        return preprocess(pair)

    warning = (
        "preprocess identity passthrough: full-raster preprocess would "
        f"materialise source_pixels={source_pixels} and "
        f"reference_pixels={reference_pixels} as float64, which exceeds "
        f"the existing {cap}-pixel engineering cap. Matching-view "
        "intensity representation still applies 2-98 percentile stretch."
    )
    if on_identity is not None:
        on_identity(warning)
    return pair
