from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .animation import write_ez_animation
from .carbon import (
    CARBON12_MASS_KG,
    CARBON6_CHARGE_PC,
    carbon_terminal_metric,
    read_particle_extrema_series,
)
from .csvio import write_rows
from .fields import (
    FieldFrame,
    frame_metrics,
    iter_npz_ez_frames,
    iter_openpmd_ez_frames,
    select_field_objective,
)
from .geometry import load_geometry
from .plots import plot_carbon, plot_field_snapshot, plot_field_timeseries


def _resolve(case_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else case_dir / path


def _load_resolved(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _copy_frame(frame: FieldFrame) -> FieldFrame:
    return FieldFrame(
        iteration=frame.iteration,
        time_s=frame.time_s,
        ez_v_m=np.array(frame.ez_v_m, copy=True),
        transverse_m=np.array(frame.transverse_m, copy=True),
        z_m=np.array(frame.z_m, copy=True),
        transverse_name=frame.transverse_name,
    )


def analyze_case(
    case_dir: str | Path,
    *,
    diagnostics_dir: str | Path = "diags",
    reduced_diagnostic: str | Path = "diags/reduced/carbon_probe_extrema.txt",
    parameters: str | Path = "resolved_parameters.json",
    output_dir: str | Path = "post",
    field_npz: str | Path | None = None,
    theta_rad: float = 0.0,
    field_window_start_fs: float = 100.0,
    field_window_end_fs: float = 300.0,
    near_wall_um: float = 0.5,
    exit_band_um: float = 5.0,
    terminal_boundary_tolerance_cells: float = 2.0,
    make_animation: bool = False,
) -> dict[str, Any]:
    root = Path(case_dir).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"case directory does not exist: {root}")

    parameter_path = _resolve(root, parameters)
    reduced_path = _resolve(root, reduced_diagnostic)
    destination = _resolve(root, output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    resolved = _load_resolved(parameter_path)
    geometry = load_geometry(parameter_path)
    probe = resolved.get("probe", {})
    mass_kg = (
        float(probe.get("mass_kg", CARBON12_MASS_KG))
        if isinstance(probe, dict)
        else CARBON12_MASS_KG
    )
    grid = resolved.get("grid")
    if not isinstance(grid, dict):
        raise ValueError("resolved parameters must contain a grid object")

    carbon_series = read_particle_extrema_series(reduced_path, mass_kg=mass_kg)
    carbon_rows = carbon_series.rows
    carbon_metric = carbon_terminal_metric(
        carbon_series,
        grid=grid,
        boundary_tolerance_cells=terminal_boundary_tolerance_cells,
    )

    if field_npz is None:
        frames: Iterable[FieldFrame] = iter_openpmd_ez_frames(
            _resolve(root, diagnostics_dir), theta_rad=theta_rad
        )
        field_source = "openpmd_hdf5"
    else:
        frames = iter_npz_ez_frames(_resolve(root, field_npz))
        field_source = "synthetic_npz"

    field_rows: list[dict[str, float | int | str]] = []
    animation_frames: list[FieldFrame] = []
    best_frame: FieldFrame | None = None
    best_p995 = -np.inf
    frame_count = 0

    for frame in frames:
        frame_count += 1
        metrics = frame_metrics(
            frame,
            geometry,
            near_wall_um=near_wall_um,
            exit_band_um=exit_band_um,
        )
        field_rows.extend(metrics)
        exit_row = next(row for row in metrics if row["region"] == "exit_downstream")
        if (
            field_window_start_fs <= float(exit_row["time_fs"]) <= field_window_end_fs
            and np.isfinite(float(exit_row["p995_abs_Ez_V_m"]))
            and float(exit_row["p995_abs_Ez_V_m"]) > best_p995
        ):
            best_p995 = float(exit_row["p995_abs_Ez_V_m"])
            best_frame = _copy_frame(frame)
        if make_animation:
            animation_frames.append(_copy_frame(frame))

    if frame_count == 0:
        raise ValueError("field diagnostic contains no frames")

    field_objective = select_field_objective(
        field_rows,
        window_start_fs=field_window_start_fs,
        window_end_fs=field_window_end_fs,
    )
    if best_frame is None:
        raise RuntimeError("field objective was selected without retaining its frame")

    near_wall_candidates = [
        row
        for row in field_rows
        if row["region"] == "near_inner_wall"
        and field_window_start_fs <= float(row["time_fs"]) <= field_window_end_fs
        and np.isfinite(float(row["p995_abs_Ez_V_m"]))
    ]
    best_near_wall = max(
        near_wall_candidates,
        key=lambda row: float(row["p995_abs_Ez_V_m"]),
        default=None,
    )

    write_rows(destination / "carbon_probe_timeseries.csv", carbon_rows)
    write_rows(destination / "mna_field_timeseries.csv", field_rows)

    plots_dir = destination / "plots"
    plot_carbon(carbon_rows, plots_dir)
    plot_field_timeseries(field_rows, plots_dir / "mna_field_metrics_vs_time.png")
    plot_field_snapshot(best_frame, geometry, plots_dir / "mna_peak_exit_Ez.png")

    animation_path = ""
    if make_animation:
        animation_path = str(
            write_ez_animation(
                animation_frames,
                geometry,
                plots_dir / "mna_Ez_all_frames.mp4",
            ).relative_to(root)
        )

    case_id = resolved.get("case_id", "")
    case_name = resolved.get("case_name", root.name)
    summary: dict[str, Any] = {
        "schema_version": 2,
        "analysis_status": "ok",
        "case_id": case_id,
        "case_name": case_name,
        "geometry_model": "rz_theta_mode_m0_m1",
        "n_azimuthal_modes": int(resolved.get("n_azimuthal_modes", 2)),
        "field_source": field_source,
        "field_theta_rad": float(theta_rad),
        "field_frame_count": int(frame_count),
        "field_window_start_fs": float(field_window_start_fs),
        "field_window_end_fs": float(field_window_end_fs),
        "near_wall_width_um": float(near_wall_um),
        "exit_band_width_um": float(exit_band_um),
        "terminal_boundary_tolerance_cells": float(
            terminal_boundary_tolerance_cells
        ),
        "objective_carbon_terminal_delta_kz_MeV": carbon_metric.delta_kz_MeV,
        "objective_exit_ez_p995_peak_100_300fs_V_m": float(
            field_objective["p995_abs_Ez_V_m"]
        ),
        "carbon_initial_kz_MeV": carbon_metric.initial_kz_MeV,
        "carbon_terminal_kz_MeV": carbon_metric.terminal_kz_MeV,
        "carbon_terminal_total_kinetic_MeV": (
            carbon_metric.terminal_total_kinetic_MeV
        ),
        "carbon_terminal_pz_over_mc": carbon_metric.terminal_pz_over_mc,
        "carbon_terminal_time_fs": carbon_metric.terminal_time_fs,
        "carbon_terminal_step": carbon_metric.terminal_step,
        "carbon_terminal_x_um": carbon_metric.terminal_x_um,
        "carbon_terminal_y_um": carbon_metric.terminal_y_um,
        "carbon_terminal_r_um": carbon_metric.terminal_r_um,
        "carbon_terminal_z_um": carbon_metric.terminal_z_um,
        "carbon_terminal_angle_deg": carbon_metric.terminal_angle_deg,
        "carbon_terminal_reason": carbon_metric.terminal_reason,
        "carbon_terminal_sampling_gap_fs": carbon_metric.terminal_sampling_gap_fs,
        "carbon_trailing_empty_rows": carbon_metric.trailing_empty_rows,
        "carbon_raw_row_count": carbon_series.raw_row_count,
        "carbon_physical_row_count": carbon_series.physical_row_count,
        "exit_ez_peak_iteration": int(field_objective["iteration"]),
        "exit_ez_peak_time_fs": float(field_objective["time_fs"]),
        "exit_ez_peak_max_abs_V_m": float(field_objective["max_abs_Ez_V_m"]),
        "exit_ez_peak_transverse_um": float(
            field_objective["peak_transverse_um"]
        ),
        "exit_ez_peak_z_um": float(field_objective["peak_z_um"]),
        "near_wall_ez_p995_peak_100_300fs_V_m": (
            float(best_near_wall["p995_abs_Ez_V_m"])
            if best_near_wall is not None
            else 0.0
        ),
        "n_macroparticles_selected": 1,
        "charge_selected_pC": CARBON6_CHARGE_PC,
        "animation_path": animation_path,
    }

    for name, value in geometry.to_dict().items():
        summary[f"{name}_um"] = value * 1.0e6

    write_rows(destination / "mna_case_summary.csv", [summary])

    report = {
        "schema_version": 2,
        "summary": summary,
        "carbon_terminal": asdict(carbon_metric),
        "carbon_series": {
            "raw_row_count": carbon_series.raw_row_count,
            "physical_row_count": carbon_series.physical_row_count,
            "trailing_empty_rows": carbon_series.trailing_empty_rows,
            "first_empty_step": carbon_series.first_empty_step,
            "first_empty_time_fs": carbon_series.first_empty_time_fs,
        },
        "outputs": {
            "summary_csv": "post/mna_case_summary.csv",
            "carbon_csv": "post/carbon_probe_timeseries.csv",
            "field_csv": "post/mna_field_timeseries.csv",
            "plots_dir": "post/plots",
            "animation": animation_path,
        },
    }
    (destination / "analysis_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary
