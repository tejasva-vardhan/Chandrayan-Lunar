"""CLI for the EXP-004 existing-representation comparison.

Raw products stay outside Git. Configure them with CHANDRAYAN_DATA_ROOT.

Example (PowerShell):

    $env:CHANDRAYAN_DATA_ROOT = "<external demo dataset>"
    python scripts/run_exp004.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.io.exp004.config import VARIANT_A_ID, VARIANT_B_ID, VARIANT_C_ID
from src.io.exp004.run import Exp004Error, run_exp004


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run EXP-004 intensity/gradient/structural comparison on pair 01."
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
        record = run_exp004(
            data_root=args.data_root,
            output_dir=args.output_dir,
            record_path=args.record_path,
        )
    except Exp004Error as exc:
        print(f"EXP-004 could not start: {exc}", file=sys.stderr)
        return 2

    status = record.get("status")
    print(f"EXP-004 status={status} failed_stage={record.get('failed_stage')}")
    interpretation = record.get("interpretation") or {}
    print(f"hypothesis_supported={interpretation.get('hypothesis_supported')}")
    print(
        "verified_inliers_improved="
        f"{interpretation.get('verified_inliers_improved')}"
    )
    print(f"independent_accuracy={interpretation.get('independent_accuracy')}")
    for row in (record.get("comparison") or {}).get("rows") or []:
        variant = row.get("variant")
        print(
            f"variant {variant}: representation={row.get('representation_id')} "
            f"raw={row.get('raw_matches')} "
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
