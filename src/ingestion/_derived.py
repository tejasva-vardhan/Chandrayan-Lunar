"""Writable derived-file paths for ingestion outputs."""

from __future__ import annotations

import tempfile
from hashlib import sha1
from pathlib import Path


def derived_output_path(source: Path, suffix: str) -> Path:
    resolved = source.resolve()
    digest = sha1(str(resolved).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    root = Path(tempfile.gettempdir()) / "sih26166_ingestion_cache" / digest
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{source.stem}{suffix}"
