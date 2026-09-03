"""CLI for PS-closing scale + cross-sensor optical robustness.

Raw products stay outside Git. Configure them with CHANDRAYAN_DATA_ROOT.

    $env:CHANDRAYAN_DATA_ROOT = "<external demo dataset>"
    python scripts/run_ps_scale_multimodal.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.io.exp001.config import PAIR_REGISTRY
from src.io.ps_scale_multimodal.config import PRIMARY_PAIR_ID
from src.io.ps_scale_multimodal.run import PsScaleMultimodalError, run_ps_scale_multimodal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run coarse-to-fine A/B/C on pair_02: production intensity, "
            "common-physical-GSD scale arm, and CLAHE cross-sensor arm."
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
    args = parser.parse_args(argv)

    try:
        summary = run_ps_scale_multimodal(
            data_root=args.data_root,
            pair_ids=list(args.pairs),
            output_dir=args.output_dir,
            record_dir=args.record_dir,
        )
    except PsScaleMultimodalError as exc:
        print(f"PS-SCALE-MULTIMODAL could not start: {exc}", file=sys.stderr)
        return 2

    print(f"PS-SCALE-MULTIMODAL scale_decision={summary.get('scale_decision')}")
    print(f"cross_sensor_decision={summary.get('cross_sensor_decision')}")
    for pair_id, row in (summary.get("pairs") or {}).items():
        print(
            f"pair {pair_id}: status={row.get('status')} "
            f"scale={row.get('scale_decision')} "
            f"cross_sensor={row.get('cross_sensor_decision')}"
        )
        for item in ((row.get("comparison") or {}).get("rows") or []):
            print(
                f"  variant {item.get('variant')}: rep={item.get('representation_id')} "
                f"scale={item.get('scale_policy')} "
                f"strides={item.get('stride_source')}/{item.get('stride_reference')} "
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
