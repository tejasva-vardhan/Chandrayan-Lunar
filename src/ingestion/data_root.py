"""Resolve the external lunar demo dataset root.

Raw products stay outside Git. The canonical configuration variable is
``CHANDRAYAN_DATA_ROOT``. No machine-specific path is hardcoded here.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT_ENV = "CHANDRAYAN_DATA_ROOT"

# Initial EXP-000 pair from data/manifests/demo_pairs.yaml (pair_01_equatorial).
PAIR_01_OHRC_ID = "ch2_ohr_ncp_20210402T0546284043_d_img_d18"
PAIR_01_LROC_ID = "M150368601RC"


class DataRootError(ValueError):
    """Raised when CHANDRAYAN_DATA_ROOT is set but unusable."""


def configured_data_root() -> Path | None:
    """Return the configured external data root, or None if unset.

    If the variable is set, the path must exist and be a directory.
    """

    raw = os.environ.get(DATA_ROOT_ENV)
    if raw is None or not raw.strip():
        return None
    path = Path(raw)
    if not path.exists():
        raise DataRootError(f"{DATA_ROOT_ENV} does not exist: {path}")
    if not path.is_dir():
        raise DataRootError(f"{DATA_ROOT_ENV} is not a directory: {path}")
    return path


def find_product(root: Path, product_id: str) -> Path | None:
    """Locate one product under *root* by its declared product id.

    Matches a directory, ZIP archive, or ``.IMG`` file whose name equals the
    product id. Does not guess identity from unrelated filenames.
    """

    if not product_id:
        raise ValueError("product_id must be non-empty")

    direct = _direct_matches(root, product_id)
    if direct:
        return direct[0]

    needle = product_id.lower()
    matches: list[Path] = []
    for path in root.rglob("*"):
        if path.name.lower() in _candidate_names(needle) and _is_product_path(path):
            matches.append(path)
    matches.sort(key=lambda item: (len(item.parts), str(item).lower()))
    return matches[0] if matches else None


def _direct_matches(root: Path, product_id: str) -> list[Path]:
    found: list[Path] = []
    for name in _candidate_names(product_id):
        path = root / name
        if path.exists() and _is_product_path(path):
            found.append(path)
    return found


def _candidate_names(product_id: str) -> tuple[str, ...]:
    return (
        product_id,
        f"{product_id}.zip",
        f"{product_id}.ZIP",
        f"{product_id}.img",
        f"{product_id}.IMG",
        f"{product_id}.xml",
        f"{product_id}.XML",
    )


def _is_product_path(path: Path) -> bool:
    if path.is_dir():
        return True
    if not path.is_file():
        return False
    return path.suffix.lower() in {".img", ".zip", ".xml"}
