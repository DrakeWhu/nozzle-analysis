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
    else