from pathlib import Path

import pytest

from src.models import LunarProduct, RegistrationPair


@pytest.fixture
def source_product() -> LunarProduct:
    return LunarProduct(product_id="src-001", instrument="OHRC", mission="Chandrayaan-2")


@pytest.fixture
def reference_product() -> LunarProduct:
    return LunarProduct(product_id="ref-001", instrument="LRO_NAC", mission="LRO")


@pytest.fixture
def registration_pair(
    source_product: LunarProduct, reference_product: LunarProduct
) -> RegistrationPair:
    return RegistrationPair(
        pair_id="pair-001",
        source=source_product,
        reference=reference_product,
    )


@pytest.fixture
def tmp_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source.placeholder"
    reference = tmp_path / "reference.placeholder"
    output_dir = tmp_path / "out"
    source.write_text("placeholder-source", encoding="utf-8")
    reference.write_text("placeholder-reference", encoding="utf-8")
    output_dir.mkdir()
    return source, reference, output_dir
