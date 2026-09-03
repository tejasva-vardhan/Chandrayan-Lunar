"""CLI for the EXP-005 subpixel-refinement ablation.

Raw products stay outside Git. Configure them with CHANDRAYAN_DATA_ROOT.

Example (PowerShell):

    $env:CHANDRAYAN_DATA_ROOT = "<external demo dataset>"
    python scripts/run_exp005.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.io.exp005.config import VARIANT_A_ID, VARIANT_B_ID
from src.io.exp005.run import Exp005Error, run_exp005


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run EXP-005 identity vs ZNCC parabolic refinement on pair 02."
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
        record = run_exp005(
            data_root=args.data_root,
            output_dir=args.output_dir,
            record_path=args.record_path,
        )
    except Exp005Error as exc:
        print(f"EXP-005 could not start: {exc}", file=sys.stderr)
        return 2

    status = record.get("status")
    print(f"EXP-005 status={status} failed_stage={record.get('failed_stage')}")
    interpretation = record.get("interpretation") or {}
    print(f"hypothesis_supported={interpretation.get('hypothesis_supported')}")
    print(f"coordinates_changed={interpretation.get('coordinates_changed')}")
    print(f"held_out_improved={interpretation.get('held_out_improved')}")
    print(f"independent_accuracy={interpretation.get('independent_accuracy')}")
    for row in (record.get("comparison") or {}).get("rows") or []:
        variant = row.get("variant")
        print(
            f"variant {variant}: method={row.get('method_id')} "
            f"verified={row.get('verified_inliers')} "
            f"cps={row.get('control_point_count')} "
            f"changed={row.get('coordinates_changed_count')} "
            f"mean_dx={row.get('mean_displacement_pixels')} "
            f"max_dx={row.get('max_displacement_pixels')} "
            f"held_out_rmse={row.get('unselected_checkpoint_rmse')} "
            f"cp_kfold_rmse={row.get('control_point_held_out_rmse')} "
            f"accepted={row.get('accepted_count')} "
            f"rejected={row.get('rejected_count')} "
            f"refinement={row.get('refinement_status')}"
        )
    present = record.get("variants") or {}
    if VARIANT_A_ID not in present or VARIANT_B_ID not in present:
        return 1
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
