"""Export contract for registration outputs (v3 §22 recommended package)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.models.registration_pair import RegistrationPair
from src.models.registration_result import RegistrationResult


class ExportManifest(BaseModel):
    """URIs for files listed in the v3 output contract.

    Paths are recorded only after a real exporter writes them.
    Names are logical; this contract does not assume image or table formats.
    """

    model_config = ConfigDict(extra="forbid")

    registered_source: str | None = None
    all_matches: str | None = None
    inliers: str | None = None
    control_points: str | None = None
    transformation: str | None = None
    metrics: str | None = None
    before: str | None = None
    matches_visualization: str | None = None
    overlay: str | None = None
    registration_report: str | None = None


def export_result(
    result: RegistrationResult, pair: RegistrationPair, output_dir: Path
) -> ExportManifest:
    """Write the registration package.

    Receives RegistrationPair so source/reference rasters are available for
    before/overlay exports. Not implemented in this foundation. Do not emit
    placeholder metrics or files.
    """
    raise NotImplementedError(
        "export_result is a contract stub. Implement in src/io without inventing values. "
        f"pair_id={result.pair_id} source={pair.source.product_id} "
        f"reference={pair.reference.product_id} output_dir={output_dir}"
    )
