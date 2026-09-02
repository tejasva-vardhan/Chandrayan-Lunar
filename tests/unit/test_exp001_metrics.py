"""EXP-001 comparison metric tests."""

from __future__ import annotations

from src.io.exp001.metrics import (
    coverage,
    inlier_ratio,
    inliers_above_model_minimum,
    occupancy,
    status_counts,
    verified_matches,
)
from src.models.common import ImageDimensions
from src.models.correspondence_set import Correspondence
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair


def _pair(width: int = 1000, height: int = 1000) -> RegistrationPair:
    dimensions = ImageDimensions(width_px=width, height_px=height, band_count=1)
    return RegistrationPair(
        pair_id="metrics-pair",
        source=LunarProduct(
            product_id="src",
            instrument="OHRC",
            mission="Chandrayaan-2",
            dimensions=dimensions,
        ),
        reference=LunarProduct(
            product_id="ref",
            instrument="LRO_NAC",
            mission="LRO",
            dimensions=dimensions,
        ),
    )


def _match(x: float, y: float, status: str = "inlier") -> Correspondence:
    return Correspondence(source_xy=(x, y), reference_xy=(x, y), status=status)


def test_status_counts_reports_every_state_including_zero() -> None:
    counts = status_counts([_match(1, 1), _match(2, 2, "rejected")])

    assert counts == {"raw": 0, "filtered": 0, "inlier": 1, "rejected": 1}


def test_verified_matches_selects_only_inliers() -> None:
    matches = [_match(1, 1), _match(2, 2, "rejected"), _match(3, 3, "raw")]

    assert len(verified_matches(matches)) == 1


def test_inlier_ratio_uses_all_raw_matches_as_the_denominator() -> None:
    matches = [_match(1, 1)] + [_match(i, i, "rejected") for i in range(2, 10)]

    assert inlier_ratio(matches) == 1 / 9


def test_inlier_ratio_of_an_empty_set_is_none_not_zero() -> None:
    assert inlier_ratio([]) is None


def test_inliers_above_model_minimum_is_zero_at_the_dlt_minimum() -> None:
    """The EXP-000 situation: four inliers means no corroborating evidence."""

    matches = [_match(float(i), float(i)) for i in range(4)]

    assert inliers_above_model_minimum(matches, 4) == 0


def test_inliers_above_model_minimum_counts_corroborating_evidence() -> None:
    matches = [_match(float(i), float(i)) for i in range(11)]

    assert inliers_above_model_minimum(matches, 4) == 7


def test_coverage_matches_the_bounding_box_area_fraction() -> None:
    matches = [_match(0, 0), _match(500, 500)]

    assert coverage(matches, _pair()) == 0.25


def test_coverage_is_none_without_product_dimensions() -> None:
    pair = RegistrationPair(
        pair_id="no-dims",
        source=LunarProduct(product_id="src", instrument="OHRC", mission="Chandrayaan-2"),
        reference=LunarProduct(product_id="ref", instrument="LRO_NAC", mission="LRO"),
    )

    assert coverage([_match(0, 0), _match(10, 10)], pair) is None


def test_coverage_is_none_with_no_points() -> None:
    assert coverage([], _pair()) is None


def test_occupancy_separates_spread_from_density() -> None:
    """Two point sets with identical bounding boxes but different clustering."""

    corners = [_match(10, 10), _match(990, 990)]
    spread = [_match(10, 10), _match(990, 990)] + [
        _match(125.0 * i + 60, 125.0 * i + 60) for i in range(7)
    ]

    assert coverage(corners, _pair()) == coverage(spread, _pair())
    corner_cells = occupancy(corners, _pair(), 8)["source_occupied_cells"]
    spread_cells = occupancy(spread, _pair(), 8)["source_occupied_cells"]
    assert corner_cells == 2
    assert spread_cells > corner_cells


def test_occupancy_reports_grid_totals_and_fractions() -> None:
    payload = occupancy([_match(10, 10)], _pair(), 8)

    assert payload["grid_bins"] == 8
    assert payload["total_cells"] == 64
    assert payload["source_occupied_cells"] == 1
    assert payload["source_occupied_fraction"] == 1 / 64


def test_occupancy_without_points_is_none_not_zero() -> None:
    payload = occupancy([], _pair(), 8)

    assert payload["source_occupied_cells"] is None
    assert payload["reference_occupied_cells"] is None
