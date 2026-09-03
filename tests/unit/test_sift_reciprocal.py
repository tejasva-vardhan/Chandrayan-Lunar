"""Reciprocal SIFT protocol tests. Software validation only.

These tests use synthetic arrays. They are not lunar accuracy results and
not SIH evaluator evidence.
"""

from __future__ import annotations

import numpy as np

from src.matching import match
from src.matching.settings import SiftSettings
from src.matching.sift_adapter import run_sift
from src.models.lunar_product import LunarProduct
from src.models.registration_pair import RegistrationPair
from src.representation._types import RepresentationResult


def _image(seed: int = 5, side: int = 320) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid_y, grid_x = np.mgrid[0:side, 0:side].astype(np.float32)
    image = 0.4 + 0.04 * rng.standard_normal((side, side)).astype(np.float32)
    for _ in range(40):
        centre_x = rng.uniform(0, side)
        centre_y = rng.uniform(0, side)
        radius = rng.uniform(5.0, 18.0)
        distance = np.sqrt((grid_x - centre_x) ** 2 + (grid_y - centre_y) ** 2)
        image += 0.3 * np.exp(-(((distance - radius) / 2.5) ** 2))
    image -= image.min()
    image /= max(float(image.max()), 1e-6)
    return image.astype(np.float32)


def _pair() -> RegistrationPair:
    return RegistrationPair(
        pair_id="reciprocal-pair",
        source=LunarProduct(product_id="src", instrument="OHRC", mission="Chandrayaan-2"),
        reference=LunarProduct(product_id="ref", instrument="LRO_NAC", mission="LRO"),
    )


def _representation(source: np.ndarray, reference: np.ndarray) -> RepresentationResult:
    return RepresentationResult(
        array=source,
        representation_id="intensity",
        metadata={"reference_array": reference},
    )


def test_default_run_sift_equals_frozen_match() -> None:
    source = _image()
    reference = np.roll(source, 11, axis=1)
    pair = _pair()
    representation = _representation(source, reference)

    frozen = match(pair, representation)
    default = run_sift(pair, representation, settings=SiftSettings())

    assert frozen.matcher_id == default.matcher_id == "sift"
    assert len(frozen.matches) == len(default.matches)
    for left, right in zip(frozen.matches, default.matches, strict=True):
        assert left.source_xy == right.source_xy
        assert left.reference_xy == right.reference_xy
        assert left.confidence == right.confidence
        assert left.status == right.status == "raw"


def test_reciprocal_matches_are_a_subset_of_one_way_matches() -> None:
    source = _image()
    reference = np.roll(source, 11, axis=1)
    pair = _pair()
    representation = _representation(source, reference)

    one_way = run_sift(pair, representation, settings=SiftSettings())
    reciprocal = run_sift(
        pair, representation, settings=SiftSettings(), require_reciprocal=True
    )

    assert reciprocal.matcher_id == "sift"
    assert len(reciprocal.matches) <= len(one_way.matches)
    one_way_keys = {(item.source_xy, item.reference_xy) for item in one_way.matches}
    for item in reciprocal.matches:
        assert (item.source_xy, item.reference_xy) in one_way_keys
        assert item.status == "raw"


def test_reciprocal_matching_is_deterministic() -> None:
    source = _image(seed=9)
    reference = np.roll(source, 8, axis=0)
    pair = _pair()
    representation = _representation(source, reference)

    first = run_sift(
        pair, representation, settings=SiftSettings(), require_reciprocal=True
    )
    second = run_sift(
        pair, representation, settings=SiftSettings(), require_reciprocal=True
    )
    assert len(first.matches) == len(second.matches)
    for left, right in zip(first.matches, second.matches, strict=True):
        assert left.source_xy == right.source_xy
        assert left.reference_xy == right.reference_xy
