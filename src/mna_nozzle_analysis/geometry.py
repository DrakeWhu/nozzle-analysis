from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

import numpy as np


PARAMETER_NAMES = (
    "L1",
    "L2",
    "d_paper",
    "r_head",
    "r_neck",
    "r_exit",
    "z_neck_paper",
)


@dataclass(frozen=True)
class NozzleGeometry:
    """Canonical MNA inner surface, with every value expressed in metres."""

    L1: float
    L2: float
    d_paper: float
    r_head: float
    r_neck: float
    r_exit: float
    z_neck_paper: float = 0.0

    def __post_init__(self) -> None:
        values = asdict(self)
        for name, value in values.items():
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite, got {value!r}")
        for name in PARAMETER_NAMES[:-1]:
            if float(values[name]) <= 0.0:
                raise ValueError(f"{name} must be positive, got {values[name]!r}")
        if not self.r_neck < self.r_head < self.r_exit:
            raise ValueError("geometry requires r_neck < r_head < r_exit")
        if self.r_head - self.r_neck > self.L1:
            raise ValueError("head radial rise must not exceed L1")
        if self.r_exit - self.r_neck > self.L2:
            raise ValueError("skirt radial rise must not exceed L2")

    @property
    def z_head(self) -> float:
        return self.z_neck_paper - self.L1

    @property
    def z_exit(self) -> float:
        return self.z_neck_paper + self.L2

    @property
    def head_circle_radius(self) -> float:
        dr = self.r_head - self.r_neck
        return (self.L1 * self.L1 + dr * dr) / (2.0 * dr)

    def inner_radius(self, z_m: np.ndarray | float) -> np.ndarray:
        """Return the exact inner radius used by the PICMI input.

        The upstream segment is a circular arc; the downstream segment is a
        quarter ellipse.  Points outside the aluminium axial extent are NaN.
        """

        z = np.asarray(z_m, dtype=float)
        s = z - self.z_neck_paper
        radius = np.full(z.shape, np.nan, dtype=float)

        head = (s >= -self.L1) & (s <= 0.0)
        if np.any(head):
            circle = self.head_circle_radius
            radicand = np.maximum(circle * circle - s[head] * s[head], 0.0)
            radius[head] = self.r_neck + circle - np.sqrt(radicand)

        skirt = (s >= 0.0) & (s <= self.L2)
        if np.any(skirt):
            scaled = s[skirt] / self.L2
            radius[skirt] = self.r_exit - (
                (self.r_exit - self.r_neck)
                * np.sqrt(np.maximum(1.0 - scaled * scaled, 0.0))
            )
        return radius

    def to_dict(self) -> dict[str, float]:
        return {name: float(value) for name, value in asdict(self).items()}

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "NozzleGeometry":
        geometry_values: Mapping[str, Any] = values
        if isinstance(values.get("geometry"), Mapping):
            geometry_values = values["geometry"]  # type: ignore[index]
        missing = [name for name in PARAMETER_NAMES if name not in geometry_values]
        if missing:
            raise ValueError(f"missing nozzle geometry parameters: {missing}")
        return cls(**{name: float(geometry_values[name]) for name in PARAMETER_NAMES})


_FLOAT = r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"


def parse_generated_input(path: str | Path) -> NozzleGeometry:
    text = Path(path).read_text(encoding="utf-8", errors="strict")
    values: dict[str, float] = {}
    for name in PARAMETER_NAMES:
        match = re.search(
            rf"^\s*my_constants\.{re.escape(name)}\s*=\s*{_FLOAT}\s*$",
            text,
            flags=re.MULTILINE,
        )
        if not match:
            raise ValueError(f"missing my_constants.{name} in {path}")
        values[name] = float(match.group(1))
    return NozzleGeometry.from_mapping(values)


def load_geometry(path: str | Path) -> NozzleGeometry:
    source = Path(path)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object in {source}")
        return NozzleGeometry.from_mapping(payload)
    return parse_generated_input(source)


def region_masks(
    geometry: NozzleGeometry,
    transverse_m: np.ndarray,
    z_m: np.ndarray,
    *,
    near_wall_m: float,
    exit_band_m: float,
) -> dict[str, np.ndarray]:
    """Construct boolean ROIs on a field array indexed `[transverse, z]`."""

    if near_wall_m <= 0.0 or exit_band_m <= 0.0:
        raise ValueError("ROI widths must be positive")
    transverse = np.asarray(transverse_m, dtype=float)
    z = np.asarray(z_m, dtype=float)
    if transverse.ndim != 1 or z.ndim != 1:
        raise ValueError("transverse and z coordinates must be one-dimensional")

    radial = np.abs(transverse)[:, None]
    zz = z[None, :]
    inner = geometry.inner_radius(z)[None, :]
    inside_axial_extent = np.isfinite(inner)
    near_inner_wall = (
        inside_axial_extent
        & (radial >= np.maximum(inner - near_wall_m, 0.0))
        & (radial <= inner)
    )
    near_skirt_wall = (
        near_inner_wall
        & (zz >= geometry.z_neck_paper)
        & (zz <= geometry.z_exit)
    )
    exit_downstream = (
        (zz >= geometry.z_exit)
        & (zz <= geometry.z_exit + exit_band_m)
        & (radial <= geometry.r_exit)
    )
    return {
        "near_inner_wall": near_inner_wall,
        "near_skirt_wall": near_skirt_wall,
        "exit_downstream": exit_downstream,
    }

