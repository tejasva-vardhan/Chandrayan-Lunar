"""Unit tests for external data-root discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion.data_root import (
    DATA_ROOT_ENV,
    PAIR_01_LROC_ID,
    PAIR_01_OHRC_ID,
    DataRootError,
    configured_data_root,
    find_product,
)


def test_unset_data_root_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)
    assert configured_data_root() is None


def test_missing_data_root_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    monkeypatch.setenv(DATA_ROOT_ENV, str(missing))
    with pytest.raises(DataRootError, match="does not exist"):
        configured_data_root()


def test_configured_data_root_returns_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    assert configured_data_root() == tmp_path


def test_find_product_matches_img_and_directory(tmp_path: Path) -> None:
    lroc = tmp_path / f"{PAIR_01_LROC_ID}.IMG"
    lroc.write_bytes(b"not-a-real-image")
    ohrc = tmp_path / PAIR_01_OHRC_ID
    ohrc.mkdir()

    assert find_product(tmp_path, PAIR_01_LROC_ID) == lroc
    assert find_product(tmp_path, PAIR_01_OHRC_ID) == ohrc


def test_find_product_does_not_use_hardcoded_windows_path() -> None:
    source = Path("src/ingestion/data_root.py").read_text(encoding="utf-8")
    readme = Path("data/README.md").read_text(encoding="utf-8")
    assert "C:\\Users" not in source
    assert "C:\\Users" not in readme
    assert DATA_ROOT_ENV in readme
