"""CLI for the PS-closing coarse-to-fine correspondence A/B.

Raw products stay outside Git. Configure them with CHANDRAYAN_DATA_ROOT.

    $env:CHANDRAYAN_DATA_ROOT = "<external demo dataset>"
    python scripts/run_ps_correspondence.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.io.exp001.config import PAIR_REGISTRY
from src.io.ps_correspondence.config import FOLLOW_UP_PAIR_ID, PRIMARY_PAIR_ID
from src.io.ps_correspondence.run import PsCorrespondenceError, run_ps_correspondence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run frozen SIFT vs coarse-to-fine tiled multi-scale SIFT on "
            "pair_02, optionally following up on pair_01 if H1 is SUPPORTED."
        )
    )
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument(
        "--pairs",
        nargs="+",
        default=[PRIMARY_PAIR_ID],
        choices=list(PAIR_REGISTRY),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--record-dir", type=Path, default=None)
    parser.add_argument(
        "--no-follow-up",
        action="store_true",
        help=f"Do not run {FOLLOW_UP_PAIR_ID} even if the primary pair is SUPPORTED.",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_ps_correspondence(
            data_root=args.data_root,
            pair_ids=list(args.pairs),
            output_dir=args.output_dir,
            record_dir=args.record_dir,
            follow_up_if_supported=not args.no_follow_up,
        )
    except PsCorrespondenceError as exc:
        print(f"PS-CORRESPONDENCE could not start: {exc}", file=sys.stderr)
        return 2

    print(f"PS-CORRESPONDENCE primary_decision={summary.get('primary_decision')}")
    print(f"follow_up_ran={summary.get('follow_up_ran')}")
    for pair_id, row in (summary.get("pairs") or {}).items():
        print(f"pair {pair_id}: status={row.get('status')} decision={row.get('decision')}")
        comparison = row.get("comparison") or {}
        for item in comparison.get("rows") or []:
            print(
                f"  variant {item.get('variant')}: protocol={item.get('protocol_id')} "
                f"raw={item.get('raw_matches')} "
                f"verified={item.get('verified_inliers')} "
                f"ratio={item.get('inlier_ratio')} "
                f"src_cells={item.get('source_occupied_cells')} "
                f"ref_cells={item.get('reference_occupied_cells')} "
                f"coverage={item.get('verified_match_coverage')} "
                f"cps={item.get('control_point_count')} "
                f"transform={item.get('transform_status')} "
                f"match_s={item.get('match_runtime_seconds')}"
            )
    if not summary.get("pairs"):
        return 1
    failed = [
        pair_id
        for pair_id, row in summary["pairs"].items()
        if row.get("status") != "completed"
    ]
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
