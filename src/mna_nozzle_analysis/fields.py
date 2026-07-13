from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .geometry import NozzleGeometry, region_masks


@dataclass(frozen=True)
class FieldFrame:
    iteration: int
    time_s: float
    ez_v_m: np.ndarray
    transverse_m: np.ndarray
    z_m: np.ndarray
    transverse_name: str


def _orient_field(data: Any, info: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    field = np.squeeze(np.asarray(data))
    if field.ndim != 2:
        raise ValueError(
            "all thetaMode modes must be reconstructed to one 2D plane; "
            f"received shape={field.shape}"
        )
    axes = getattr(info, "axes", None)
    if not isinstance(axes, dict):
        raise ValueError(f"expected dict-like openPMD axes metadata, got {axes!r}")
    names = [str(axes[key]).lower() for key in sorted(axes)]
    if "z" not in names:
        raise ValueError(f"field has no z axis: {axes!r}")
    transverse_name = next((name for name in ("r", "x", "y") if name in names), None)
    if transverse_name is None:
        raise ValueError(f"field has no r/x/y transverse axis: {axes!r}")
    iz = names.index("z")
    it = names.index(transverse_name)
    oriented = np.transpose(field, axes=(it, iz))
    transverse = np.asarray(getattr(info, transverse_name), dtype=float)
    z = np.asarray(getattr(info, "z"), dtype=float)
    if oriented.shape != (transverse.size, z.size):
        raise ValueError(
            "field shape does not match coordinates after orientation: "
            f"field={oriented.shape}, transverse={transverse.size}, z={z.size}"
        )
    return oriented, transverse, z, transverse_name


def iter_openpmd_ez_frames(
    diagnostics_dir: str | Path, *, theta_rad: float = 0.0
) -> Iterator[FieldFrame]:
    """Yield Ez reconstructed from every RZ mode at one observation angle."""

    try:
        from openpmd_viewer import OpenPMDTimeSeries
    except ImportError as exc:
        raise RuntimeError(
            "openPMD-viewer is required for WarpX HDF5 analysis; install the package"
        ) from exc

    series = OpenPMDTimeSeries(str(diagnostics_dir))
    iterations = [int(value) for value in series.iterations]
    times = np.asarray(series.t, dtype=float)
    if len(iterations) != len(times):
        raise ValueError("openPMD iteration/time metadata lengths differ")
    for iteration, time_s in zip(iterations, times):
        data, info = series.get_field(
            iteration=iteration,
            field="E",
            coord="z",
            m="all",
            theta=float(theta_rad),
        )
        ez, transverse, z, transverse_name = _orient_field(data, info)
        yield FieldFrame(
            iteration=iteration,
            time_s=float(time_s),
            ez_v_m=np.asarray(ez, dtype=float),
            transverse_m=transverse,
            z_m=z,
            transverse_name=transverse_name,
        )


def iter_npz_ez_frames(path: str | Path) -> Iterator[FieldFrame]:
    """Read deterministic development frames; not a scientific input format."""

    with np.load(path, allow_pickle=False) as payload:
        required = {"iterations", "times_s", "ez_v_m", "transverse_m", "z_m"}
        missing = required.difference(payload.files)
        if missing:
            raise ValueError(f"synthetic NPZ is missing {sorted(missing)}")
        iterations = np.asarray(payload["iterations"])
        times = np.asarray(payload["times_s"], dtype=float)
        fields = np.asarray(payload["ez_v_m"], dtype=float)
        transverse = np.asarray(payload["transverse_m"], dtype=float)
        z = np.asarray(payload["z_m"], dtype=float)
        if fields.shape != (len(iterations), transverse.size, z.size):
            raise ValueError("synthetic NPZ field shape does not match its coordinates")
        if len(times) != len(iterations):
            raise ValueError("synthetic NPZ iteration/time lengths differ")
        for index, iteration in enumerate(iterations):
            yield FieldFrame(
                iteration=int(iteration),
                time_s=float(times[index]),
                ez_v_m=fields[index],
                transverse_m=transverse,
                z_m=z,
                transverse_name="r",
            )


def _masked_stats(
    frame: FieldFrame, mask: np.ndarray, *, region: str
) -> dict[str, float | int | str]:
    if mask.shape != frame.ez_v_m.shape:
        raise ValueError(
            f"ROI {region!r} shape {mask.shape} differs from field {frame.ez_v_m.shape}"
        )
    valid = mask & np.isfinite(frame.ez_v_m)
    row: dict[str, float | int | str] = {"region": region, "n_cells": int(valid.sum())}
    if not np.any(valid):
        row.update(
            {
                "max_abs_Ez_V_m": float("nan"),
                "p995_abs_Ez_V_m": float("nan"),
                "rms_Ez_V_m": float("nan"),
                "min_Ez_V_m": float("nan"),
                "max_Ez_V_m": float("nan"),
                "peak_transverse_um": float("nan"),
                "peak_z_um": float("nan"),
            }
        )
        return row

    values = frame.ez_v_m[valid]
    absolute = np.abs(values)
    masked_absolute = np.where(valid, np.abs(frame.ez_v_m), -np.inf)
    flat_index = int(np.argmax(masked_absolute))
    transverse_index, z_index = np.unravel_index(flat_index, frame.ez_v_m.shape)
    row.update(
        {
            "max_abs_Ez_V_m": float(np.max(absolute)),
            "p995_abs_Ez_V_m": float(np.percentile(absolute, 99.5)),
            "rms_Ez_V_m": float(np.sqrt(np.mean(values * values))),
            "min_Ez_V_m": float(np.min(values)),
            "max_Ez_V_m": float(np.max(values)),
            "peak_transverse_um": float(frame.transverse_m[transverse_index] * 1.0e6),
            "peak_z_um": float(frame.z_m[z_index] * 1.0e6),
        }
    )
    return row


def frame_metrics(
    frame: FieldFrame,
    geometry: NozzleGeometry,
    *,
    near_wall_um: float = 0.5,
    exit_band_um: float = 5.0,
) -> list[dict[str, float | int | str]]:
    masks = region_masks(
        geometry,
        frame.transverse_m,
        frame.z_m,
        near_wall_m=near_wall_um * 1.0e-6,
        exit_band_m=exit_band_um * 1.0e-6,
    )
    output: list[dict[str, float | int | str]] = []
    for region, mask in masks.items():
        row = _masked_stats(frame, mask, region=region)
        row.update(
            {
                "iteration": int(frame.iteration),
                "time_s": float(frame.time_s),
                "time_fs": float(frame.time_s * 1.0e15),
                "theta_plane": frame.transverse_name,
            }
        )
        output.append(row)
    return output


def select_field_objective(
    rows: list[dict[str, float | int | str]],
    *,
    window_start_fs: float = 100.0,
    window_end_fs: float = 300.0,
) -> dict[str, float | int | str]:
    if window_end_fs < window_start_fs:
        raise ValueError("field window end precedes its start")
    candidates = [
        row
        for row in rows
        if row["region"] == "exit_downstream"
        and window_start_fs <= float(row["time_fs"]) <= window_end_fs
        and np.isfinite(float(row["p995_abs_Ez_V_m"]))
    ]
    if not candidates:
        raise ValueError(
            "no finite exit/downstream Ez frame falls inside the objective window"
        )
    return max(candidates, key=lambda row: float(row["p995_abs_Ez_V_m"]))

