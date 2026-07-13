from __future__ import annotations

import argparse
import json
from typing import Sequence

from .analysis import analyze_case


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mna-nozzle")
    subcommands = parser.add_subparsers(dest="command", required=True)
    analyze = subcommands.add_parser("analyze-case", help="analyze one materialized case")
    analyze.add_argument("case_dir")
    analyze.add_argument("--diagnostics-dir", default="diags")
    analyze.add_argument(
        "--reduced-diagnostic", default="diags/reduced/carbon_probe_extrema.txt"
    )
    analyze.add_argument("--parameters", default="resolved_parameters.json")
    analyze.add_argument("--output-dir", default="post")
    analyze.add_argument(
        "--field-npz",
        default=None,
        help="development-only NPZ field source; production reads openPMD HDF5",
    )
    analyze.add_argument("--theta-rad", type=float, default=0.0)
    analyze.add_argument("--target-time-fs", type=float, default=1000.0)
    analyze.add_argument("--target-tolerance-fs", type=float, default=25.0)
    analyze.add_argument("--field-window-start-fs", type=float, default=100.0)
    analyze.add_argument("--field-window-end-fs", type=float, default=300.0)
    analyze.add_argument("--near-wall-um", type=float, default=0.5)
    analyze.add_argument("--exit-band-um", type=float, default=5.0)
    analyze.add_argument("--make-animation", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "analyze-case":
        summary = analyze_case(
            args.case_dir,
            diagnostics_dir=args.diagnostics_dir,
            reduced_diagnostic=args.reduced_diagnostic,
            parameters=args.parameters,
            output_dir=args.output_dir,
            field_npz=args.field_npz,
            theta_rad=args.theta_rad,
            target_time_fs=args.target_time_fs,
            target_tolerance_fs=args.target_tolerance_fs,
            field_window_start_fs=args.field_window_start_fs,
            field_window_end_fs=args.field_window_end_fs,
            near_wall_um=args.near_wall_um,
            exit_band_um=args.exit_band_um,
            make_animation=args.make_animation,
        )
        print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

