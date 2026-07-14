from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .carbon import (
    ATOMIC_MASS_UNIT_KG,
    C_LIGHT_M_S,
    ELEMENTARY_CHARGE_C,
)
from .geometry import NozzleGeometry


def write_synthetic_case(destination: str | Path) -> Path:
    """Write deterministic development data for an end-to-end contract test."""

    root = Path(destination).expanduser().resolve()
    reduced = root / "diags" / "reduced"
    reduced.mkdir(parents=True, exist_ok=True)
    geometry = NozzleGeometry(
        L1=3.1e-6,
        L2=9.9e-6,
        d_paper=0.6e-6,
        r_head=2.65e-6,
        r_neck=1.4e-6,
        r_exit=6.0e-6,
        z_neck_paper=0.0,
    )
    mass = 12.0 * ATOMIC_MASS_UNIT_KG
    resolved = {
        "schema_version": 1,
        "case_id": "synthetic",
        "case_name": "synthetic_contract_smoke",
        "geometry_model": "rz_circle_head_quarter_ellipse_skirt",
        "n_azimuthal_modes": 2,
        "geometry": geometry.to_dict(),
        "probe": {
            "species": "C12_6plus",
            "mass_kg": mass,
            "charge_C": 6.0 * ELEMENTARY_CHARGE_C,
            "initial_energy_eV": 5.0e3,
        },
        "grid": {
            "cell_size_m": 50.0e-9,
            "rmin_m": 0.0,
            "rmax_m": 20.0e-6,
            "zmin_m": -15.0e-6,
            "zmax_m": 85.0e-6,
        },
    }
    (root / "resolved_parameters.json").write_text(
        json.dumps(resolved, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    times_fs = np.linspace(0.0, 1000.0, 101)
    rest_MeV = mass * C_LIGHT_M_S**2 / ELEMENTARY_CHARGE_C / 1.0e6
    kinetic_MeV = 0.005 + 4.0 * (times_fs / 1000.0) ** 2
    gamma = 1.0 + kinetic_MeV / rest_MeV
    pz = mass * C_LIGHT_M_S * np.sqrt(gamma * gamma - 1.0)
    z = geometry.z_exit + 1.0e-6 + 8.0e-6 * (times_fs / 1000.0) ** 2
    raw = np.zeros((times_fs.size, 18), dtype=float)
    raw[:, 0] = np.arange(times_fs.size) * 10
    raw[:, 1] = times_fs * 1.0e-15
    raw[:, 6] = z
    raw[:, 7] = z
    raw[:, 12] = pz
    raw[:, 13] = pz
    raw[:, 14] = gamma
    raw[:, 15] = gamma
    raw[:, 16] = 1.0
    raw[:, 17] = 1.0
    np.savetxt(
        reduced / "carbon_probe_extrema.txt",
        raw,
        delimiter=",",
        fmt="%.17e",
    )

    frame_times_fs = np.asarray(
        [0.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 400.0, 1000.0]
    )
    transverse = np.linspace(0.0, 10.0e-6, 121)
    z_axis = np.linspace(-5.0e-6, 16.0e-6, 253)
    rr, zz = np.meshgrid(transverse, z_axis, indexing="ij")
    exit_profile = np.exp(-((zz - (geometry.z_exit + 2.0e-6)) / 0.9e-6) ** 2)
    exit_profile *= np.exp(-(rr / 4.0e-6) ** 4)
    inner = geometry.inner_radius(z_axis)[None, :]
    wall_distance = np.abs(rr - np.nan_to_num(inner, nan=1.0))
    wall_profile = np.exp(-(wall_distance / 0.25e-6) ** 2) * np.isfinite(inner)
    fields = []
    for time_fs in frame_times_fs:
        exit_amplitude = 2.0e12 + 1.1e13 * np.exp(-((time_fs - 200.0) / 65.0) ** 2)
        wall_amplitude = 1.5e12 + 5.0e12 * np.exp(-((time_fs - 175.0) / 80.0) ** 2)
        field = exit_amplitude * exit_profile - wall_amplitude * wall_profile
        fields.append(field)
    np.savez_compressed(
        root / "synthetic_fields.npz",
        iterations=np.arange(frame_times_fs.size) * 100,
        times_s=frame_times_fs * 1.0e-15,
        ez_v_m=np.asarray(fields),
        transverse_m=transverse,
        z_m=z_axis,
    )
    return root
