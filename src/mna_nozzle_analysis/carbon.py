from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
class CarbonTargetMetric:
    target_time_fs: float
    actual_time_fs: float
    target_time_error_fs: float
    initial_kz_MeV: float
    target_kz_MeV: float
    delta_kz_MeV: float
    target_total_kinetic_MeV: float
    target_pz_over_mc: float


def _single_probe_check(raw: np.ndarray) -> None:
    for low, high, label in _EXTREMA_PAIRS:
        if not np.allclose(raw[:, low], raw[:, high], rtol=1.0e-10, atol=1.0e-30):
            raise ValueError(
                f"ParticleExtrema does not describe one probe: {label} min/max differ"
            )


def _strip_trailing_empty_probe_rows(raw: np.ndarray) -> np.ndarray:
    """Remove WarpX ParticleExtrema rows emitted after the species becomes empty.

    AMReX min/max reductions over an empty particle container retain opposite
    extrema sentinels: every minimum is greater than its corresponding maximum.
    In text output, the largest sentinels can parse as +/-inf. Only a trailing
    suffix with this signature is accepted; any other non-finite or malformed
    row remains a hard data error.
    """
    empty_mask = np.logical_and.reduce(
        [raw[:, low] > raw[:, high] for low, high, _ in _EXTREMA_PAIRS]
    )
    if not np.any(empty_mask):
        return raw

    first_empty = int(np.flatnonzero(empty_mask)[0])
    if not np.all(empty_mask[first_empty:]):
        raise ValueError(
            "ParticleExtrema empty-probe rows must form a trailing suffix"
        )
    if first_empty == 0:
        raise ValueError("ParticleExtrema contains no samples with the probe present")
    return raw[:first_empty]


def read_particle_extrema(
    path: str | Path, *, mass_kg: float = CARBON12_MASS_KG
) -> list[dict[str, float]]:
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
    raw = _strip_trailing_empty_probe_rows(raw)
    if not np.all(np.isfinite(raw)):
        raise ValueError("ParticleExtrema contains non-finite values")
    if np.any(np.diff(raw[:, 1]) < 0.0):
        raise ValueError("ParticleExtrema time is not monotonic")
    _single_probe_check(raw)

    mc = mass_kg * C_LIGHT_M_S
    rest_MeV = mass_kg * C_LIGHT_M_S**2 / ELEMENTARY_CHARGE_C / 1.0e6
    rows: list[dict[str, float]] = []
    for values in raw:
        px_mc = values[9] / mc
        py_mc = values[11] / mc
        pz_mc = values[13] / mc
        gamma_from_p = float(np.sqrt(1.0 + px_mc**2 + py_mc**2 + pz_mc**2))
        gamma_diag = float(values[15])
        gamma = gamma_diag
        if not np.isclose(gamma_diag, gamma_from_p, rtol=2.0e-5, atol=2.0e-8):
            raise ValueError(
                "ParticleExtrema gamma and momentum are inconsistent for the probe"
            )
        rows.append(
            {
                "step": float(values[0]),
                "time_s": float(values[1]),
                "time_fs": float(values[1] * 1.0e15),
                "z_m": float(values[7]),
                "z_um": float(values[7] * 1.0e6),
                "px_over_mc": float(px_mc),
                "py_over_mc": float(py_mc),
                "pz_over_mc": float(pz_mc),
                "gamma": gamma,
                "kinetic_energy_MeV": float((gamma - 1.0) * rest_MeV),
                "kinetic_energy_from_pz_MeV": float(
                    (np.sqrt(1.0 + pz_mc**2) - 1.0) * rest_MeV
                ),
            }
        )
    return rows


def carbon_target_metric(
    rows: list[dict[str, float]],
    *,
    target_time_fs: float = 1000.0,
    tolerance_fs: float = 25.0,
) -> CarbonTargetMetric:
    if not rows:
        raise ValueError("carbon probe time series is empty")
    if tolerance_fs < 0.0:
        raise ValueError("target-time tolerance must be non-negative")
    index = min(
        range(len(rows)), key=lambda i: abs(rows[i]["time_fs"] - target_time_fs)
    )
    target = rows[index]
    error = abs(target["time_fs"] - target_time_fs)
    if error > tolerance_fs:
        raise ValueError(
            f"no carbon sample within {tolerance_fs:g} fs of {target_time_fs:g} fs; "
            f"closest is {target['time_fs']:.6g} fs"
        )
    initial_kz = rows[0]["kinetic_energy_from_pz_MeV"]
    target_kz = target["kinetic_energy_from_pz_MeV"]
    return CarbonTargetMetric(
        target_time_fs=float(target_time_fs),
        actual_time_fs=float(target["time_fs"]),
        target_time_error_fs=float(error),
        initial_kz_MeV=float(initial_kz),
        target_kz_MeV=float(target_kz),
        delta_kz_MeV=float(target_kz - initial_kz),
        target_total_kinetic_MeV=float(target["kinetic_energy_MeV"]),
        target_pz_over_mc=float(target["pz_over_mc"]),
    )
