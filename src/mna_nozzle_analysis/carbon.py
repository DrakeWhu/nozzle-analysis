from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np


C_LIGHT_M_S = 299_792_458.0
ELEMENTARY_CHARGE_C = 1.602_176_634e-19
ATOMIC_MASS_UNIT_KG = 1.660_539_066_60e-27
CARBON12_MASS_KG = 12.0 * ATOMIC_MASS_UNIT_KG
CARBON6_CHARGE_PC = 6.0 * ELEMENTARY_CHARGE_C / 1.0e-12

PARTICLE_EXTREMA_COLUMNS = (
    "step",
    "time_s",
    "xmin_m",
    "xmax_m",
    "ymin_m",
    "ymax_m",
    "zmin_m",
    "zmax_m",
    "pxmin_kg_m_s",
    "pxmax_kg_m_s",
    "pymin_kg_m_s",
    "pymax_kg_m_s",
    "pzmin_kg_m_s",
    "pzmax_kg_m_s",
    "gamma_min",
    "gamma_max",
    "weight_min",
    "weight_max",
)

_EXTREMA_PAIRS = (
    (2, 3, "x"),
    (4, 5, "y"),
    (6, 7, "z"),
    (8, 9, "px"),
    (10, 11, "py"),
    (12, 13, "pz"),
    (14, 15, "gamma"),
    (16, 17, "weight"),
)


@dataclass(frozen=True)
class ParticleExtremaSeries:
    rows: list[dict[str, float]]
    raw_row_count: int
    physical_row_count: int
    trailing_empty_rows: int
    first_empty_step: float | None
    first_empty_time_fs: float | None


@dataclass(frozen=True)
class CarbonTerminalMetric:
    initial_kz_MeV: float
    terminal_kz_MeV: float
    delta_kz_MeV: float
    terminal_total_kinetic_MeV: float
    terminal_pz_over_mc: float
    terminal_time_fs: float
    terminal_step: float
    terminal_x_um: float
    terminal_y_um: float
    terminal_r_um: float
    terminal_z_um: float
    terminal_angle_deg: float
    terminal_reason: str
    terminal_sampling_gap_fs: float
    trailing_empty_rows: int


def _single_probe_check(raw: np.ndarray) -> None:
    for low, high, label in _EXTREMA_PAIRS:
        if not np.allclose(raw[:, low], raw[:, high], rtol=1.0e-10, atol=1.0e-30):
            raise ValueError(
                f"ParticleExtrema does not describe one probe: {label} min/max differ"
            )


def _split_physical_rows(raw: np.ndarray) -> tuple[np.ndarray, int | None]:
    """Split physical samples from WarpX empty-species sentinel rows."""
    empty_mask = np.logical_and.reduce(
        [raw[:, low] > raw[:, high] for low, high, _ in _EXTREMA_PAIRS]
    )
    if not np.any(empty_mask):
        return raw, None

    first_empty = int(np.flatnonzero(empty_mask)[0])
    if not np.all(empty_mask[first_empty:]):
        raise ValueError(
            "ParticleExtrema empty-probe rows must form a trailing suffix"
        )
    if first_empty == 0:
        raise ValueError("ParticleExtrema contains no samples with the probe present")
    return raw[:first_empty], first_empty


def read_particle_extrema_series(
    path: str | Path, *, mass_kg: float = CARBON12_MASS_KG
) -> ParticleExtremaSeries:
    if not np.isfinite(mass_kg) or mass_kg <= 0.0:
        raise ValueError("probe mass must be finite and positive")

    raw = np.loadtxt(path, delimiter=",", comments="#", ndmin=2)
    if raw.size == 0 or raw.shape[1] != len(PARTICLE_EXTREMA_COLUMNS):
        raise ValueError(
            f"expected {len(PARTICLE_EXTREMA_COLUMNS)} ParticleExtrema columns, "
            f"got shape={raw.shape}"
        )
    if not np.all(np.isfinite(raw[:, :2])):
        raise ValueError("ParticleExtrema step/time contains non-finite values")

    physical, first_empty = _split_physical_rows(raw)
    if not np.all(np.isfinite(physical)):
        raise ValueError("ParticleExtrema contains non-finite physical values")
    if np.any(np.diff(raw[:, 1]) < 0.0):
        raise ValueError("ParticleExtrema time is not monotonic")
    _single_probe_check(physical)

    mc = mass_kg * C_LIGHT_M_S
    rest_MeV = mass_kg * C_LIGHT_M_S**2 / ELEMENTARY_CHARGE_C / 1.0e6
    rows: list[dict[str, float]] = []
    for values in physical:
        x_m = float(values[3])
        y_m = float(values[5])
        z_m = float(values[7])
        px_mc = float(values[9] / mc)
        py_mc = float(values[11] / mc)
        pz_mc = float(values[13] / mc)
        p_perp_mc = float(np.hypot(px_mc, py_mc))
        gamma_from_p = float(
            np.sqrt(1.0 + px_mc**2 + py_mc**2 + pz_mc**2)
        )
        gamma_diag = float(values[15])
        if not np.isclose(gamma_diag, gamma_from_p, rtol=2.0e-5, atol=2.0e-8):
            raise ValueError(
                "ParticleExtrema gamma and momentum are inconsistent for the probe"
            )
        radius_m = float(np.hypot(x_m, y_m))
        rows.append(
            {
                "step": float(values[0]),
                "time_s": float(values[1]),
                "time_fs": float(values[1] * 1.0e15),
                "x_m": x_m,
                "x_um": x_m * 1.0e6,
                "y_m": y_m,
                "y_um": y_m * 1.0e6,
                "r_m": radius_m,
                "r_um": radius_m * 1.0e6,
                "z_m": z_m,
                "z_um": z_m * 1.0e6,
                "px_over_mc": px_mc,
                "py_over_mc": py_mc,
                "p_perp_over_mc": p_perp_mc,
                "pz_over_mc": pz_mc,
                "p_perp_over_abs_pz": float(
                    p_perp_mc / abs(pz_mc) if pz_mc != 0.0 else np.inf
                ),
                "trajectory_angle_deg": float(
                    np.degrees(np.arctan2(p_perp_mc, pz_mc))
                ),
                "gamma": gamma_diag,
                "kinetic_energy_MeV": float((gamma_diag - 1.0) * rest_MeV),
                "kinetic_energy_from_pz_MeV": float(
                    (np.sqrt(1.0 + pz_mc**2) - 1.0) * rest_MeV
                ),
            }
        )

    trailing_empty_rows = raw.shape[0] - physical.shape[0]
    first_empty_step = (
        float(raw[first_empty, 0]) if first_empty is not None else None
    )
    first_empty_time_fs = (
        float(raw[first_empty, 1] * 1.0e15)
        if first_empty is not None
        else None
    )
    return ParticleExtremaSeries(
        rows=rows,
        raw_row_count=int(raw.shape[0]),
        physical_row_count=int(physical.shape[0]),
        trailing_empty_rows=int(trailing_empty_rows),
        first_empty_step=first_empty_step,
        first_empty_time_fs=first_empty_time_fs,
    )


def read_particle_extrema(
    path: str | Path, *, mass_kg: float = CARBON12_MASS_KG
) -> list[dict[str, float]]:
    """Backward-compatible row-only ParticleExtrema reader."""
    return read_particle_extrema_series(path, mass_kg=mass_kg).rows


def _terminal_reason(
    terminal: Mapping[str, float],
    *,
    grid: Mapping[str, Any],
    boundary_tolerance_cells: float,
) -> str:
    required = ("cell_size_m", "rmax_m", "zmin_m", "zmax_m")
    missing = [name for name in required if name not in grid]
    if missing:
        raise ValueError(f"resolved grid is missing: {', '.join(missing)}")
    cell_size_m = float(grid["cell_size_m"])
    rmax_m = float(grid["rmax_m"])
    zmin_m = float(grid["zmin_m"])
    zmax_m = float(grid["zmax_m"])
    values = (cell_size_m, rmax_m, zmin_m, zmax_m)
    if not all(np.isfinite(value) for value in values):
        raise ValueError("resolved grid boundaries must be finite")
    if cell_size_m <= 0.0 or not zmin_m < zmax_m or rmax_m <= 0.0:
        raise ValueError("resolved grid boundaries are invalid")
    if boundary_tolerance_cells < 0.0:
        raise ValueError("boundary tolerance must be non-negative")

    tolerance_m = boundary_tolerance_cells * cell_size_m
    near_radial_upper = rmax_m - float(terminal["r_m"]) <= tolerance_m
    near_axial_upper = zmax_m - float(terminal["z_m"]) <= tolerance_m
    near_axial_lower = float(terminal["z_m"]) - zmin_m <= tolerance_m
    matches = [
        name
        for name, matched in (
            ("radial_upper_loss", near_radial_upper),
            ("axial_upper_loss", near_axial_upper),
            ("axial_lower_loss", near_axial_lower),
        )
        if matched
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return "corner_loss"
    return "particle_loss_unresolved"


def carbon_terminal_metric(
    series: ParticleExtremaSeries,
    *,
    grid: Mapping[str, Any],
    boundary_tolerance_cells: float = 2.0,
) -> CarbonTerminalMetric:
    if not series.rows:
        raise ValueError("carbon probe time series is empty")

    initial = series.rows[0]
    terminal = series.rows[-1]
    reason = "simulation_end"
    sampling_gap_fs = 0.0
    if series.trailing_empty_rows:
        reason = _terminal_reason(
            terminal,
            grid=grid,
            boundary_tolerance_cells=boundary_tolerance_cells,
        )
        if series.first_empty_time_fs is None:
            raise ValueError("empty ParticleExtrema suffix has no first-empty time")
        sampling_gap_fs = series.first_empty_time_fs - float(terminal["time_fs"])
        if not np.isfinite(sampling_gap_fs) or sampling_gap_fs < 0.0:
            raise ValueError("terminal sampling gap must be finite and non-negative")

    initial_kz = float(initial["kinetic_energy_from_pz_MeV"])
    terminal_kz = float(terminal["kinetic_energy_from_pz_MeV"])
    return CarbonTerminalMetric(
        initial_kz_MeV=initial_kz,
        terminal_kz_MeV=terminal_kz,
        delta_kz_MeV=terminal_kz - initial_kz,
        terminal_total_kinetic_MeV=float(terminal["kinetic_energy_MeV"]),
        terminal_pz_over_mc=float(terminal["pz_over_mc"]),
        terminal_time_fs=float(terminal["time_fs"]),
        terminal_step=float(terminal["step"]),
        terminal_x_um=float(terminal["x_um"]),
        terminal_y_um=float(terminal["y_um"]),
        terminal_r_um=float(terminal["r_um"]),
        terminal_z_um=float(terminal["z_um"]),
        terminal_angle_deg=float(terminal["trajectory_angle_deg"]),
        terminal_reason=reason,
        terminal_sampling_gap_fs=float(sampling_gap_fs),
        trailing_empty_rows=series.trailing_empty_rows,
    )
