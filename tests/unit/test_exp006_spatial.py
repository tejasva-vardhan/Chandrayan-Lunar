"""EXP-006 spatial diagnostics. Not lunar accuracy evidence."""

from __future__ import annotations

from src.io.exp001.metrics import occupancy
from src.io.exp006.spatial import (
    repeat_stability,
    residual_distribution,
    spatial_distribution_report,
)
from src.models.common import ImageDimensions
from src.models.correspondence_set import Correspondence
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair


def _pair(width: int = 80, height: int = 80) -> RegistrationPair:
    dims = ImageDimensions(width_px=width, height_px=height, band_count=1)
    return RegistrationPair(
        pair_id="spatial-pair",
        source=LunarProduct(
            product_id="src",
            instrument="OHRC",
            mission="Chandrayaan-2",
            dimensions=dims,
        ),
        reference=LunarProduct(
            product_id="ref",
            instrument="LRO_NAC",
            mission="LRO",
            dimensions=dims,
        ),
    )


def _inlier(
    source_xy: tuple[float, float],
    reference_xy: tuple[float, float],
    residual: float | None = 1.0,
) -> Correspondence:
    return Correspondence(
        source_xy=source_xy,
        reference_xy=reference_xy,
        residual=residual,
        status="inlier",
    )


def test_occupancy_matches_exp001_full_image_grid() -> None:
    pair = _pair()
    # 8x8 cells are 10 px on an 80 px image. These three points occupy two cells.
    points = [
        _inlier((5.0, 5.0), (5.0, 5.0)),
        _inlier((6.0, 6.0), (6.0, 6.0)),
        _inlier((75.0, 75.0), (75.0, 75.0)),
    ]
    report = spatial_distribution_report(points, pair, grid_bins=8)
    baseline = occupancy(points, pair, 8)

    assert report["verified_match_occupancy"] == baseline
    assert report["source"]["occupied_cells"] == 2
    assert report["reference"]["occupied_cells"] == 2
    assert report["source"]["max_matches_per_cell"] == 2
    assert report["source"]["concentration"] == 2 / 3
    assert report["source"]["spans_multiple_rows"] is True
    assert report["source"]["spans_multiple_cols"] is True
    assert report["spans_usable_overlap_proxy"] is True
    assert report["source"]["clark_evans_r"] is not None
    assert len(report["source"]["cell_counts_row_major"]) == 64


def test_single_cell_cluster_is_not_treated_as_span() -> None:
    pair = _pair()
    points = [
        _inlier((2.0, 2.0), (2.0, 2.0)),
        _inlier((3.0, 3.0), (3.0, 3.0)),
        _inlier((4.0, 4.0), (4.0, 4.0)),
    ]
    report = spatial_distribution_report(points, pair, grid_bins=8)
    assert report["source"]["occupied_cells"] == 1
    assert report["source"]["max_matches_per_cell"] == 3
    assert report["source"]["concentration"] == 1.0
    assert report["spans_usable_overlap_proxy"] is False
    assert report["source"]["clark_evans_r"] is not None
    assert report["source"]["clark_evans_r"] < 1.0


def test_residual_distribution_uses_stored_finite_inlier_residuals() -> None:
    points = [
        _inlier((1.0, 1.0), (1.0, 1.0), residual=0.0),
        _inlier((2.0, 2.0), (2.0, 2.0), residual=3.0),
        Correspondence(
            source_xy=(3.0, 3.0),
            reference_xy=(3.0, 3.0),
            residual=99.0,
            status="rejected",
        ),
    ]
    summary = residual_distribution(points)
    assert summary["count"] == 2
    assert summary["min"] == 0.0
    assert summary["max"] == 3.0
    assert summary["not_accuracy"] is True
    assert summary["rmse"] is not None


def test_repeat_stability_detects_coordinate_changes() -> None:
    first = [_inlier((1.0, 2.0), (3.0, 4.0))]
    same = [_inlier((1.0, 2.0), (3.0, 4.0))]
    different = [_inlier((1.0, 2.0), (3.0, 5.0))]
    assert repeat_stability(first, same)["deterministic"] is True
    assert repeat_stability(first, different)["deterministic"] is False
