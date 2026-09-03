"""EXP-001 orchestration tests on synthetic products.

These run the whole comparison without the external dataset, so the control
guarantees and the record shape are checked on every CI run rather than only
when someone has the real products mounted.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.ingestion import DATA_ROOT_ENV
from src.io.exp001.config import EXPERIMENT_ID
from src.io.exp001.run import Exp001Error, run_exp001, run_exp001_pair_from_products
from src.io.exp001.validation import INDEPENDENT_ACCURACY_NOT_VALIDATED
from src.matching.portfolio import PORTFOLIO_MATCHER_IDS
from src.models.common import ImageDimensions, Provenance
from src.models.lunar_product import LunarProduct

pytestmark = pytest.mark.wiring

_SIDE = 384
_SHIFT = 17


@pytest.fixture(autouse=True)
def _redirect_derived_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_MANIFEST_DIR", str(tmp_path / "manifests"))
    monkeypatch.setenv("LUNAR_OUTPUT_DIR", str(tmp_path / "processed"))


def _texture(side: int = _SIDE, seed: int = 11) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:side, 0:side].astype(np.float32)
    image = 0.4 + 0.04 * rng.standard_normal((side, side)).astype(np.float32)
    for _ in range(45):
        centre_x = rng.uniform(0, side)
        centre_y = rng.uniform(0, side)
        radius = rng.uniform(5.0, 18.0)
        distance = np.sqrt((grid_x - centre_x) ** 2 + (grid_y - centre_y) ** 2)
        image += 0.3 * np.exp(-(((distance - radius) / 2.5) ** 2))
    image -= image.min()
    image /= max(float(image.max()), 1e-6)
    return image.astype(np.float32)


def _product(
    tmp_path: Path, name: str, array: np.ndarray, instrument: str, mission: str
) -> LunarProduct:
    raster = tmp_path / f"{name}.npy"
    np.save(raster, array)
    return LunarProduct(
        product_id=name,
        instrument=instrument,
        mission=mission,
        raster_uri=str(raster),
        dimensions=ImageDimensions(
            width_px=array.shape[1], height_px=array.shape[0], band_count=1
        ),
        provenance=Provenance(source_uri=str(raster), reader="synthetic"),
    )


@pytest.fixture
def synthetic_products(tmp_path: Path) -> tuple[LunarProduct, LunarProduct]:
    source_array = _texture()
    reference_array = np.roll(source_array, _SHIFT, axis=1)
    source = _product(tmp_path, "synthetic-ohrc", source_array, "OHRC", "Chandrayaan-2")
    reference = _product(tmp_path, "synthetic-lroc", reference_array, "LRO_NAC", "LRO")
    return source, reference


def test_every_matcher_gets_an_arm(synthetic_products) -> None:
    source, reference = synthetic_products
    record = run_exp001_pair_from_products("pair_01_equatorial", source, reference)

    assert record["status"] == "completed"
    assert set(record["matchers"]) == set(PORTFOLIO_MATCHER_IDS)
    for matcher_id, arm in record["matchers"].items():
        assert arm["status"] == "completed", f"{matcher_id}: {arm.get('failure')}"


def test_representation_is_generated_once_and_shared(synthetic_products) -> None:
    """The control guarantee: one matching view for the whole comparison."""

    source, reference = synthetic_products
    record = run_exp001_pair_from_products("pair_01_equatorial", source, reference)

    stage = record["stages"]["generate_representation"]
    assert stage["shared_across_matchers"] is True
    assert record["runtime_seconds"]["generate_representation"] > 0
    # One shared call, so the per-arm runtimes never include representation.
    for arm in record["matchers"].values():
        assert "generate_representation" not in arm["runtime_seconds"]


def test_arms_record_every_required_primary_metric(synthetic_products) -> None:
    source, reference = synthetic_products
    record = run_exp001_pair_from_products("pair_01_equatorial", source, reference)

    for matcher_id, arm in record["matchers"].items():
        verify = arm["verify_matches"]
        assert verify["raw_match_count"] >= 0
        assert verify["verified_inlier_count"] >= 0
        assert verify["rejected_count"] >= 0
        assert "inlier_ratio" in verify
        assert "inliers_above_model_minimum" in verify
        assert "exceeds_model_minimum" in verify
        assert "verified_match_coverage" in arm["spatial_distribution"]
        assert "verified_match_occupancy" in arm["spatial_distribution"]
        assert "control_point_count" in arm["select_control_points"]
        assert "selection_succeeded" in arm["select_control_points"]
        assert "transform_fitted" in arm["register"]
        assert "outcome" in arm["refine_points"]
        assert arm["runtime_seconds"]["match"] > 0, matcher_id
        assert arm["memory"]["match"]["memory_source"]
        assert arm["held_out_validation"]["status"]


def test_no_arm_ever_claims_independent_accuracy(synthetic_products) -> None:
    source, reference = synthetic_products
    record = run_exp001_pair_from_products("pair_01_equatorial", source, reference)

    for arm in record["matchers"].values():
        assert arm["evaluate"]["independent_accuracy"] == INDEPENDENT_ACCURACY_NOT_VALIDATED
        assert arm["evaluate"]["independent_ground_truth_used"] is False
        assert (
            arm["held_out_validation"]["independent_accuracy"]
            == INDEPENDENT_ACCURACY_NOT_VALIDATED
        )
        assert (
            arm["cross_matcher_validation"]["independent_accuracy"]
            == INDEPENDENT_ACCURACY_NOT_VALIDATED
        )
    assert record["interpretation"]["independent_accuracy"] == (
        INDEPENDENT_ACCURACY_NOT_VALIDATED
    )


def test_cross_matcher_checkpoints_exclude_the_matchers_own_points(
    synthetic_products,
) -> None:
    source, reference = synthetic_products
    record = run_exp001_pair_from_products("pair_01_equatorial", source, reference)

    for matcher_id, arm in record["matchers"].items():
        cross = arm["cross_matcher_validation"]
        assert cross["transform_from_matcher_id"] == matcher_id
        assert matcher_id not in cross["checkpoint_matcher_ids"]


def test_interpretation_reports_yield_against_the_model_minimum(
    synthetic_products,
) -> None:
    source, reference = synthetic_products
    record = run_exp001_pair_from_products("pair_01_equatorial", source, reference)

    interpretation = record["interpretation"]
    assert interpretation["model_min_samples"] == 4
    assert set(interpretation["verified_inliers_by_matcher"]) == set(PORTFOLIO_MATCHER_IDS)
    assert set(interpretation["highest_verified_yield_matchers"]) <= set(PORTFOLIO_MATCHER_IDS)
    assert interpretation["highest_verified_yield_matchers"]
    assert "single_pair_caveat" in interpretation


def test_a_tied_highest_yield_is_reported_as_a_tie(monkeypatch) -> None:
    """Naming one winner out of a tie would read as a finding where there is none."""

    from src.io.exp001 import run as run_module

    def arm(count: int) -> dict[str, object]:
        return {
            "verify_matches": {
                "verified_inlier_count": count,
                "exceeds_model_minimum": count > 4,
            }
        }

    record = {"matchers": {"sift": arm(4), "orb": arm(4), "rift": arm(0)}}
    interpretation = run_module._interpretation(record, 4)

    assert interpretation["highest_verified_yield_is_tied"] is True
    assert interpretation["highest_verified_yield_matchers"] == ["orb", "sift"]
    assert interpretation["highest_verified_yield_matcher"] is None
    assert interpretation["any_matcher_exceeds_model_minimum"] is False


def test_a_clean_synthetic_pair_exceeds_the_model_minimum(synthetic_products) -> None:
    """Positive control: the pipeline can exceed four inliers when a true
    correspondence exists, so a four-inlier real-data result is a statement
    about the data rather than about the harness."""

    source, reference = synthetic_products
    record = run_exp001_pair_from_products("pair_01_equatorial", source, reference)

    assert record["interpretation"]["any_matcher_exceeds_model_minimum"] is True
    for matcher_id, arm in record["matchers"].items():
        assert arm["verify_matches"]["verified_inlier_count"] > 4, matcher_id
        assert (
            arm["held_out_validation"]["status"]
            == "HELD_OUT_CROSS_VALIDATION_COMPLETED"
        ), matcher_id


def test_selecting_a_subset_of_matchers_is_honoured(synthetic_products) -> None:
    source, reference = synthetic_products
    record = run_exp001_pair_from_products(
        "pair_01_equatorial", source, reference, matcher_ids=["sift"]
    )

    assert set(record["matchers"]) == {"sift"}


def test_record_carries_the_hypothesis_and_fixed_configuration(
    synthetic_products,
) -> None:
    source, reference = synthetic_products
    record = run_exp001_pair_from_products("pair_01_equatorial", source, reference)

    assert record["experiment_id"] == EXPERIMENT_ID
    assert "H1:" in record["hypothesis"]
    assert record["fixed_configuration"]["independent_variable"] == "matcher_id"
    assert set(record["matcher_configuration"]) == set(PORTFOLIO_MATCHER_IDS)


def test_missing_data_root_is_reported_not_guessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)

    with pytest.raises(Exp001Error, match=DATA_ROOT_ENV):
        run_exp001(data_root=None, pair_ids=["pair_01_equatorial"])


def test_unknown_pair_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(Exp001Error, match="unknown pair ids"):
        run_exp001(data_root=tmp_path, pair_ids=["pair_99_nowhere"])


def test_unknown_matcher_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(Exp001Error, match="unknown matcher ids"):
        run_exp001(
            data_root=tmp_path, pair_ids=["pair_01_equatorial"], matcher_ids=["loftr"]
        )


def test_missing_products_are_recorded_without_inventing_counts(tmp_path: Path) -> None:
    summary = run_exp001(
        data_root=tmp_path,
        pair_ids=["pair_01_equatorial"],
        output_dir=tmp_path / "out",
        record_dir=tmp_path / "records",
    )

    pair = summary["pairs"]["pair_01_equatorial"]
    assert pair["status"] == "could_not_start"
    assert pair["matchers"] == {}
    assert len(summary["comparison_rows"]) == 1
    assert summary["comparison_rows"][0]["role"] == "EXP-000_baseline_reference"
    assert summary["scientific_conclusion"]["independent_accuracy"] == (
        INDEPENDENT_ACCURACY_NOT_VALIDATED
    )


def test_summary_and_records_are_written(tmp_path: Path) -> None:
    run_exp001(
        data_root=tmp_path,
        pair_ids=["pair_01_equatorial"],
        output_dir=tmp_path / "out",
        record_dir=tmp_path / "records",
    )

    assert (tmp_path / "records" / "pair_01_equatorial.json").is_file()
    assert (tmp_path / "records" / "summary.json").is_file()
    assert (tmp_path / "out" / "summary.json").is_file()
