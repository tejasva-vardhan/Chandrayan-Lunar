"""Experimental registration settings. Not a scientific freeze.

The frozen callable is register(pair, control_points, correspondences).
It has no settings argument, so a software model_id is required. That label
is an engineering baseline, not a selected lunar model (D-010).

Do not copy these into configs/default.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegistrationSettings:
    """Configuration for one registration run.

    model_id
        Registry label for a replaceable 2D map. The two-argument API uses
        projective_2d_baseline as a software baseline consistent with
        verification, not as a final lunar model.

    max_output_pixels
        Engineering memory and disk guard for the full-resolution warp. A
        registration larger than this fails with a quality flag instead of
        risking an unbounded allocation. It is not a scientific threshold.
    """

    model_id: str
    max_output_pixels: int = 16_777_216

    def __post_init__(self) -> None:
        if self.max_output_pixels < 1:
            raise ValueError("max_output_pixels must be >= 1")


# Frozen two-argument API: engineering default only.
# NOT an SIH threshold, lunar-validated model, or benchmark result.
UNVALIDATED_SOFTWARE_MODEL_ID = "projective_2d_baseline"


def unvalidated_software_defaults() -> RegistrationSettings:
    """Engineering default used by register(pair, control_points, correspondences).

    model_id=projective_2d_baseline exists only because the frozen signature
    cannot accept settings. It is not D-010's selected lunar transform.
    """

    return RegistrationSettings(model_id=UNVALIDATED_SOFTWARE_MODEL_ID)
