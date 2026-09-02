"""CLI for the EXP-000 real-data baseline.

Raw products stay outside Git. Configure them with CHANDRAYAN_DATA_ROOT.

Example (PowerShell):

    $env:CHANDRAYAN_DATA_ROOT = "<external demo dataset>"
    python scripts/run_exp000.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.io.exp000 import run_exp000
from src.io.exp000.run import Exp000Error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run EXP-000 pair 01 through the frozen pipeline.")
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
        help="Directory for diagnostic rasters and the full record (gitignored).",
    )
    parser.add_argument(
        "--record-path",
        type=Path,
        default=None,
        help="Lightweight JSON record path (committed experiment result).",
    )
    args = parser.parse_args(argv)
    try:
        record = run_exp000(
            data_root=args.data_root,
            output_dir=args.output_dir,
            record_path=args.record_path,
        )
    except Exp000Error as exc:
        print(f"EXP-000 could not start: {exc}", file=sys.stderr)
        return 2
    status = record.get("status")
    failed = record.get("failed_stage")
    print(f"EXP-000 status={status} failed_stage={failed}")
    stages = record.get("stages", {})
    match_stage = stages.get("match", {})
    verify_stage = stages.get("verify_matches", {})
    print(f"raw_sift_matches={match_stage.get('raw_match_count')}")
    print(f"verified_inliers={verify_stage.get('verified_inlier_count')}")
    print(f"inlier_ratio={verify_stage.get('inlier_ratio')}")
    print(f"runtime_seconds_total={record.get('runtime_seconds', {}).get('total')}")
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
