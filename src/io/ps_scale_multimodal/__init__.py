"""PS-closing phase 3 scale + cross-sensor optical experiment package."""

from src.io.ps_scale_multimodal.config import RECORD_ID
from src.io.ps_scale_multimodal.run import (
    PsScaleMultimodalError,
    run_ps_scale_multimodal,
    run_ps_scale_multimodal_from_products,
)

__all__ = [
    "PsScaleMultimodalError",
    "RECORD_ID",
    "run_ps_scale_multimodal",
    "run_ps_scale_multimodal_from_products",
]
