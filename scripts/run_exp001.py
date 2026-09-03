"""CLI for the EXP-001 controlled matcher comparison.

Raw products stay outside Git. Configure them with CHANDRAYAN_DATA_ROOT.

Example (PowerShell):

    $env:CHANDRAYAN_DATA_ROOT = "<external demo dataset>"
    python scripts/run_exp001.py --pairs pair_01_equatorial

Derived rasters are large. Point LUNAR_OUTPUT_DIR and LUNAR_MANIFEST_DIR at a
volume with room before running all four pairs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.io.exp001.config import PAIR_REGISTRY, PRIMARY_PAIR_ID
from src.io.exp001.run import Exp001Error, run_exp001
from src.matching.portfolio import PORTFOLIO_MATCHER_IDS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the EXP-001 controlled matcher comparison."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="External demo dataset root. Defaults to CHANDRAYAN_DATA_ROOT.",
    )
    parser.add_argument(
        "--pairs",
        nargs="+",
        default=[PRIMARY_PAIR_ID],
        choices=sorted(PAIR_REGISTRY),
        help=f"Pair ids to run. Defaults to {PRIMARY_PAIR_ID}.",
    )
    parser.add_argument(
        "--matchers",
        nargs="+",
        default=list(PORTFOLIO_MATCHER_IDS),
        choices=list(PORTFOLIO_MATCHER_IDS),
        help="Matcher ids to compare.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for full records (gitignored).",
    )
    parser.add_argument(
        "--record-dir",
        type=Path,
        default=None,
        help="Directory for the committed lightweight records.",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_exp001(
            data_root=args.data_root,
            pair_ids=list(args.pairs),
            matcher_ids=list(args.matchers),
            output_dir=args.output_dir,
            record_dir=args.record_dir,
        )
    except Exp001Error as exc:
        print(f"EXP-001 could not start: {exc}", file=sys.stderr)
        return 2

    header = (
        f"{'matcher':8s} {'pair':22s} {'raw':>6s} {'verified':>9s} "
        f"{'ratio':>8s} {'cps':>4s} {'validation':>42s}"
    )
    print(header)
    print("-" * len(header))
    for row in summary["comparison_rows"]:
        ratio = row["inlier_ratio"]
        print(
            f"{row['matcher']:8s} {row['pair']:22s} "
            f"{_number(row['raw']):>6s} {_number(row['verified']):>9s} "
            f"{('n/a' if ratio is None else f'{ratio:.4f}'):>8s} "
            f"{_number(row['control_points']):>4s} "
            f"{str(row['validation']):>42s}"
        )

    incomplete = [
        pair_id
        for pair_id, payload in summary["pairs"].items()
        if payload.get("status") != "completed"
    ]
    if incomplete:
        print(f"pairs that did not complete: {incomplete}", file=sys.stderr)
        return 1
    return 0


def _number(value: object) -> str:
    return "n/a" if value is None else str(value)


if __name__ == "__main__":
    raise SystemExit(main())
