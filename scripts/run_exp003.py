"""CLI for the EXP-003 matching-view scale-robustness comparison.

Raw products stay outside Git. Configure them with CHANDRAYAN_DATA_ROOT.

Example (PowerShell):

    $env:CHANDRAYAN_DATA_ROOT = "<external demo dataset>"
    python scripts/run_exp003.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.io.exp003.config import VARIANT_A_ID, VARIANT_B_ID, VARIANT_C_ID
from src.io.exp003.run import Exp003Error, run_exp003


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run EXP-003 LROC matching-view scale robustness on pair 01."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="External demo dataset root. Defaults to CHANDRAYAN_DATA_ROOT.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for the full record (gitignored).",
    )
    parser.add_argument(
        "--record-path",
        type=Path,
        default=None,
        help="Lightweight JSON record path (committed experiment result).",
    )
    args = parser.parse_args(argv)

    try:
        record = run_exp003(
            data_root=args.data_root,
            output_dir=args.output_dir,
            record_path=args.record_path,
        )
    except Exp003Error as exc:
        print(f"EXP-003 could not start: {exc}", file=sys.stderr)
        return 2

    status = record.get("status")
    print(f"EXP-003 status={status} failed_stage={record.get('failed_stage')}")
    interpretation = record.get("interpretation") or {}
    print(f"hypothesis_supported={interpretation.get('hypothesis_supported')}")
    print(
        "scale_changes_materially_affect_verified_yield="
        f"{interpretation.get('scale_changes_materially_affect_verified_yield')}"
    )
    print(f"independent_accuracy={interpretation.get('independent_accuracy')}")
    for row in (record.get("comparison") or {}).get("rows") or []:
        variant = row.get("variant")
        print(
            f"variant {variant}: raw={row.get('raw_matches')} "
            f"verified={row.get('verified_inliers')} "
            f"ratio={row.get('inlier_ratio')} "
            f"coverage={row.get('spatial_coverage')} "
            f"cps={row.get('control_point_count')} "
            f"transform={row.get('transform_status')} "
            f"refinement={row.get('refinement_status')} "
            f"stride={row.get('stride_source')}/{row.get('stride_reference')}"
        )
    present = record.get("variants") or {}
    if VARIANT_A_ID not in present or VARIANT_B_ID not in present or VARIANT_C_ID not in present:
        return 1
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
