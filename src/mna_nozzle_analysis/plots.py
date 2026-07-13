from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .fields import FieldFrame
from .geometry import NozzleGeometry


def _finish(fig: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_carbon(rows: list[dict[str, float]], output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    time = np.asarray([row["time_fs"] for row in rows])

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(time, [row["kinetic_energy_MeV"] for row in rows], label="total")
    ax.plot(
        time,
        [row["kinetic_energy_from_pz_MeV"] for row in rows],
        label="from pz only",
    )
    ax.set(xlabel="time [fs]", ylabel="energy [MeV]", title="C12 6+ probe energy")
    ax.grid(alpha=0.3)
    ax.legend()
    energy = _finish(fig, destination / "carbon_probe_energy_vs_time.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(time, [row["pz_over_mc"] for row in rows])
    ax.set(
        xlabel="time [fs]",
        ylabel="pz / (mC c)",
        title="C12 6+ probe longitudinal momentum",
    )
    ax.grid(alpha=0.3)
    momentum = _finish(fig, destination / "carbon_probe_pz_vs_time.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(time, [row["z_um"] for row in rows])
    ax.set(xlabel="time [fs]", ylabel="z [um]", title="C12 6+ probe axial position")
    ax.grid(alpha=0.3)
    position = _finish(fig, destination / "carbon_probe_z_vs_time.png")
    return [energy, momentum, position]


def plot_field_timeseries(
    rows: list[dict[str, float | int | str]], output: str | Path
) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    for region in ("near_inner_wall", "near_skirt_wall", "exit_downstream"):
        selected = [row for row in rows if row["region"] == region]
        ax.plot(
            [float(row["time_fs"]) for row in selected],
            [float(row["p995_abs_Ez_V_m"]) * 1.0e-12 for row in selected],
            label=region,
        )
    ax.axvspan(100.0, 300.0, color="0.5", alpha=0.12, label="objective window")
    ax.set(
        xlabel="time [fs]",
        ylabel="P99.5 |Ez| [TV/m]",
        title="Longitudinal-field metrics",
    )
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    return _finish(fig, Path(output))


def _overlay_geometry(ax: Any, geometry: NozzleGeometry, *, signed: bool) -> None:
    z = np.linspace(geometry.z_head, geometry.z_exit, 800)
    inner = geometry.inner_radius(z)
    outer = inner + geometry.d_paper
    z_um = z * 1.0e6
    ax.plot(z_um, inner * 1.0e6, "w--", linewidth=1.0, label="inner surface")
    ax.plot(z_um, outer * 1.0e6, "w-", linewidth=1.0, label="outer surface")
    if signed:
        ax.plot(z_um, -inner * 1.0e6, "w--", linewidth=1.0)
        ax.plot(z_um, -outer * 1.0e6, "w-", linewidth=1.0)


def plot_field_snapshot(
    frame: FieldFrame,
    geometry: NozzleGeometry,
    output: str | Path,
) -> Path:
    finite = frame.ez_v_m[np.isfinite(frame.ez_v_m)]
    vmax = float(np.percentile(np.abs(finite), 99.5)) if finite.size else 1.0
    vmax = max(vmax, np.finfo(float).tiny)
    z_um = frame.z_m * 1.0e6
    transverse_um = frame.transverse_m * 1.0e6
    fig, ax = plt.subplots(figsize=(9, 5))
    image = ax.pcolormesh(
        z_um,
        transverse_um,
        frame.ez_v_m * 1.0e-12,
        cmap="RdBu_r",
        vmin=-vmax * 1.0e-12,
        vmax=vmax * 1.0e-12,
        shading="auto",
    )
    _overlay_geometry(
        ax,
        geometry,
        signed=bool(np.nanmin(frame.transverse_m) < 0.0),
    )
    ax.set(
        xlabel="z [um]",
        ylabel=f"{frame.transverse_name} [um]",
        title=f"Ez, all RZ modes at theta=0 | {frame.time_s * 1.0e15:.2f} fs",
    )
    fig.colorbar(image, ax=ax, label="Ez [TV/m]")
    return _finish(fig, Path(output))

