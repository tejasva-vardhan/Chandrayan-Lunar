"""Optional real-data downstream checks for EXP-000 pair 01.

The raw products remain external and are located through CHANDRAYAN_DATA_ROOT.
This verifies matching-view masks and coordinate restoration only; it does not
claim lunar registration accuracy.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.ingestion import (
    DATA_ROOT_ENV,
    PAIR_01_LROC_ID,
    PAIR_01_OHRC_ID,
    DataRootError,
    configured_data_root,
    find_product,
    ingest_product,
)
from src.matching import match
from src.models import RegistrationPair
from src.representation import RepresentationResult, generate_representation


@pytest.fixture(autouse=True)
def _redirect_derived_outputs(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_MANIFEST_DIR", str(tmp_path / "manifests"))
    monkeypatch.setenv("LUNAR_OUTPUT_DIR", str(tmp_path / "processed"))


def _products() -> tuple[RegistrationPair, RepresentationResult]:
    try:
        root = configured_data_root()
    except DataRootError as exc:
        pytest.fail(str(exc))
    if root is None:
        pytest.skip(f"Set {DATA_ROOT_ENV} to run the external EXP-000 test")

    ohrc_path = find_product(root, PAIR_01_OHRC_ID)
    lroc_path = find_product(root, PAIR_01_LROC_ID)
    if ohrc_path is None or lroc_path is None:
        pytest.skip("EXP-000 pair-01 products are unavailable under the configured root")

    pair = RegistrationPair(
        pair_id="exp000-pair-01",
        source=ingest_product(ohrc_path),
        reference=ingest_product(lroc_path),
    )
    return pair, generate_representation(pair)


@pytest.mark.wiring
def test_pair_01_matching_view_masks_and_coordinates_are_original_space() -> None:
    pair, representation = _products()
    metadata = representation.metadata
    source_mask = metadata["source_valid_mask"]
    reference_mask = metadata["reference_valid_mask"]

    assert isinstance(source_mask, np.ndarray)
    assert isinstance(reference_mask, np.ndarray)
    assert source_mask.shape == representation.array.shape
    assert reference_mask.shape == metadata["reference_array"].shape
    # The LROC PDS3 label declares invalid values; they reach SIFT as a mask.
    assert np.any(~reference_mask)

    matches = match(pair, representation)
    assert matches.matches
    assert pair.source.dimensions is not None
    assert pair.reference.dimensions is not None
    for item in matches.matches:
        sx, sy = item.source_xy
        rx, ry = item.reference_xy
        assert 0.0 <= sx < pair.source.dimensions.width_px
        assert 0.0 <= sy < pair.source.dimensions.height_px
        assert 0.0 <= rx < pair.reference.dimensions.width_px
        assert 0.0 <= ry < pair.reference.dimensions.height_px
