"""Resolve allowed local products under CHANDRAYAN_DATA_ROOT.

Only product IDs declared in data/manifests/demo_pairs.yaml are exposed.
This is not a general filesystem browser.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.ingestion.data_root import (
    DATA_ROOT_ENV,
    PAIR_01_LROC_ID,
    PAIR_01_OHRC_ID,
    configured_data_root,
    find_product,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_PAIRS_PATH = _REPO_ROOT / "data" / "manifests" / "demo_pairs.yaml"
PAIR_01_MANIFEST_ID = "pair_01_equatorial"


def load_declared_product_ids(manifest_path: Path | None = None) -> list[str]:
    path = manifest_path or _DEMO_PAIRS_PATH
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pairs = raw.get("demo_pairs") or []
    ordered: list[str] = []
    seen: set[str] = set()
    for entry in pairs:
        for key in ("ohrc_product", "lroc_product"):
            product_id = entry.get(key)
            if not product_id or product_id in seen:
                continue
            seen.add(product_id)
            ordered.append(str(product_id))
    return ordered


def instrument_hint_for(product_id: str) -> str:
    lowered = product_id.lower()
    if lowered.startswith("ch2_ohr") or "ohr" in lowered:
        return "OHRC"
    if lowered.startswith("m") and product_id[:1].upper() == "M":
        return "LRO_NAC"
    return "UNKNOWN"


def catalog_product_id(logical_id: str) -> str:
    return f"catalog-{logical_id}"


def resolve_data_root_products(
    *,
    data_root: Path | None = None,
    manifest_path: Path | None = None,
) -> tuple[Path | None, list[tuple[str, Path]]]:
    """Return (root, [(logical_id, path), ...]) for products found under the data root."""

    root = data_root if data_root is not None else configured_data_root()
    if root is None:
        return None, []
    found: list[tuple[str, Path]] = []
    for logical_id in load_declared_product_ids(manifest_path):
        path = find_product(root, logical_id)
        if path is not None:
            found.append((logical_id, path))
    return root, found


def resolve_exp000_paths(
    *,
    data_root: Path | None = None,
) -> tuple[Path | None, Path | None, Path | None]:
    """Return (root, ohrc_path, lroc_path) for EXP-000 pair_01."""

    root = data_root if data_root is not None else configured_data_root()
    if root is None:
        return None, None, None
    return root, find_product(root, PAIR_01_OHRC_ID), find_product(root, PAIR_01_LROC_ID)


def public_path_label(path: Path, *, data_root: Path | None) -> str:
    """Non-sensitive path label for API responses (never raw absolute machine paths)."""

    name = path.name
    if data_root is not None:
        try:
            relative = path.resolve().relative_to(data_root.resolve())
            return f"<{DATA_ROOT_ENV}>/{relative.as_posix()}"
        except ValueError:
            pass
    return name
