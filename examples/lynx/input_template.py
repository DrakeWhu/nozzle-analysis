#!/usr/bin/env python3
"""Environment-driven WarpX PICMI input for the MNA RZ campaign."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

from pywarpx import picmi


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    value = default if raw is None or raw.strip() == "" else float(raw)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    value = default if raw is None or raw.strip() == "" else int(raw)
    return value


parser = argparse.ArgumentParser()
parser.add_argument(
    "--write-only",
    action="store_true",
    help="Write generated WarpX inputs and resolved parameters, then stop.",
)
args = parser.parse_args()
write_only = args.write_only or os.environ.get("MNA_DRY_RUN", "0") == "1"

case_id = os.environ.get("MNA_CASE_ID", "")
case_name = os.environ.get("MNA_CASE_NAME", Path.cwd().name)

# Geometry: paper x -> WarpX z; abs(paper y) -> WarpX r.
L1 = env_float("MNA_L1_M", 3.1e-6)
L2 = env_float("MNA_L2_M", 9.9e-6)
wall = env_float("MNA_WALL_M", 0.6e-6)
r_head = env_float("MNA_R_HEAD_M", 2.65e-6)
r_neck = env_float("MNA_R_NECK_M", 1.40e-6)
r_exit = env_float("MNA_R_EXIT_M", 6.00e-6)
z_neck = env_float("MNA_Z_NECK_M", 0.0)

if abs(z_neck) > 1.0e-18:
    raise ValueError("z_neck is a fixed coordinate reference and must remain 0 m")
if min(L1, L2, wall, r_head, r_neck, r_exit) <= 0.0:
    raise ValueError("all nozzle dimensions must be positive")
if not r_neck < r_head < r_exit:
    raise ValueError("geometry requires r_neck < r_head < r_exit")
if r_head - r_neck > L1:
    raise ValueError("head radial rise must not exceed L1")
if r_exit - r_neck > L2:
    raise ValueError("skirt radial rise must not exceed L2")

z_head = z_neck - L1
z_exit = z_neck + L2
head_circle_radius = (
    L1 * L1 + (r_head - r_neck) ** 2
) / (2.0 * (r_head - r_neck))

# Numerics.  Fifty nm is the deliberately rough first-campaign resolution;
# the paper uses ten nm and that refinement is a later convergence study.
cell_size = env_float("MNA_CELL_SIZE_M", 50.0e-9)
rmin = 0.0
rmax = env_float("MNA_RMAX_M", 20.0e-6)
zmin = env_float("MNA_ZMIN_M", -15.0e-6)
zmax = env_float("MNA_ZMAX_M", 85.0e-6)
if not zmin < z_head < z_exit < zmax:
    raise ValueError("nozzle does not fit inside the axial simulation domain")
if r_exit + wall >= rmax:
    raise ValueError("nozzle does not fit inside the radial simulation domain")

nr = int(round((rmax - rmin) / cell_size))
nz = int(round((zmax - zmin) / cell_size))
if nr <= 0 or nz <= 0:
    raise ValueError("invalid grid cell count")

n_azimuthal_modes = 2
cfl = env_float("MNA_CFL", 0.95)
stop_time_s = env_float("MNA_STOP_TIME_S", 1.0e-12)
field_diag_period = env_int("MNA_FIELD_DIAG_PERIOD", 100)
probe_diag_period = env_int("MNA_PROBE_DIAG_PERIOD", 10)
if stop_time_s < 1.0e-12:
    raise ValueError("campaign stop time must reach the 1 ps carbon objective")
if field_diag_period <= 0 or probe_diag_period <= 0:
    raise ValueError("diagnostic periods must be positive")

diag_rmin = 0.0
diag_rmax = env_float("MNA_DIAG_RMAX_M", 12.0e-6)
diag_zmin = env_float("MNA_DIAG_ZMIN_M", -7.0e-6)
diag_zmax = env_float("MNA_DIAG_ZMAX_M", 22.0e-6)
if not (rmin <= diag_rmin < diag_rmax <= rmax):
    raise ValueError("field diagnostic radial bounds leave the simulation domain")
if not (zmin <= diag_zmin < diag_zmax <= zmax):
    raise ValueError("field diagnostic axial bounds leave the simulation domain")
if diag_zmin > z_head or diag_zmax < z_exit + 5.0e-6 or diag_rmax < r_exit:
    raise ValueError("field diagnostic does not contain every objective ROI")
diag_nr = int(round((diag_rmax - diag_rmin) / cell_size))
diag_nz = int(round((diag_zmax - diag_zmin) / cell_size))

grid = picmi.CylindricalGrid(
    number_of_cells=[nr, nz],
    n_azimuthal_modes=n_azimuthal_modes,
    lower_bound=[rmin, zmin],
    upper_bound=[rmax, zmax],
    lower_boundary_conditions=["none", "absorbing_silver_mueller"],
    upper_boundary_conditions=[
        "absorbing_silver_mueller",
        "absorbing_silver_mueller",
    ],
    lower_boundary_conditions_particles=["none", "absorbing"],
    upper_boundary_conditions_particles=["absorbing", "absorbing"],
    warpx_max_grid_size=64,
    warpx_blocking_factor=16,
)

solver = picmi.ElectromagneticSolver(
    grid=grid,
    method="Yee",
    cfl=cfl,
    divE_cleaning=0,
)

# The head is one circular arc whose endpoint and zero neck slope are exact.
# The skirt is the quarter ellipse described in the paper-based prototype.
r_inner_expression = (
    "if((z>=z_head)*(z<z_neck_paper), "
    "r_neck + R_head - sqrt(R_head**2 - (z-z_neck_paper)**2), "
    "if((z>=z_neck_paper)*(z<=z_exit), "
    "r_exit - (r_exit-r_neck)*sqrt(1.0 - "
    "((z-z_neck_paper)**2)/(L2**2)), 1.0e99))"
)
nozzle_shape_expression = (
    "if((z>=z_head)*(z<=z_exit), "
    f"if((x>=({r_inner_expression}))"
    f"*(x<=(({r_inner_expression})+d_paper)), 1.0, 0.0), 0.0)"
)

# Fully pre-ionized aluminium, as in the agreed model.
n_aluminum_m3 = 6.0e28
aluminum_charge_state = 13
geometry_constants = {
    "n_Al": n_aluminum_m3,
    "L1": L1,
    "L2": L2,
    "d_paper": wall,
    "r_head": r_head,
    "r_neck": r_neck,
    "r_exit": r_exit,
    "z_neck_paper": z_neck,
    "z_head": z_head,
    "z_exit": z_exit,
    "R_head": head_circle_radius,
}
aluminum_distribution = picmi.AnalyticDistribution(
    density_expression=f"n_Al*({nozzle_shape_expression})",
    lower_bound=[rmin, None, z_head],
    upper_bound=[rmax, None, z_exit],
    warpx_density_min=0.5 * n_aluminum_m3,
    **geometry_constants,
)
electron_distribution = picmi.AnalyticDistribution(
    density_expression=f"{aluminum_charge_state}*n_Al*({nozzle_shape_expression})",
    lower_bound=[rmin, None, z_head],
    upper_bound=[rmax, None, z_exit],
    warpx_density_min=0.5 * aluminum_charge_state * n_aluminum_m3,
    **geometry_constants,
)

aluminum_ions = picmi.Species(
    particle_type="Al",
    charge_state=aluminum_charge_state,
    name="aluminum_ions",
    initial_distribution=aluminum_distribution,
)
electrons = picmi.Species(
    particle_type="electron",
    name="electrons",
    initial_distribution=electron_distribution,
)
ion_layout = picmi.GriddedLayout(
    n_macroparticle_per_cell=[5, 4, 5],
    grid=grid,
)
electron_layout = picmi.GriddedLayout(
    n_macroparticle_per_cell=[5, 4, 10],
    grid=grid,
)

# One non-depositing 12C6+ test ion, initially at 5 keV along +z.
c = picmi.constants.c
eps0 = picmi.constants.ep0
elementary_charge = 1.602176634e-19
atomic_mass_unit = 1.66053906660e-27
carbon12_mass_kg = 12.0 * atomic_mass_unit
carbon12_charge_C = 6.0 * elementary_charge
carbon12_initial_energy_eV = 5.0e3
carbon12_initial_energy_J = carbon12_initial_energy_eV * elementary_charge
carbon12_gamma0 = 1.0 + carbon12_initial_energy_J / (carbon12_mass_kg * c * c)
carbon12_uz0 = math.sqrt(carbon12_gamma0 * carbon12_gamma0 - 1.0) * c
probe_z0 = z_exit + 1.0e-6
carbon_distribution = picmi.ParticleListDistribution(
    x=[0.0],
    y=[0.0],
    z=[probe_z0],
    ux=[0.0],
    uy=[0.0],
    uz=[carbon12_uz0],
    weight=[1.0],
)
carbon_probe = picmi.Species(
    name="carbon_probe",
    mass=carbon12_mass_kg,
    charge=carbon12_charge_C,
    initial_distribution=carbon_distribution,
    method="Boris",
    warpx_do_not_deposit=1,
)

# Paper laser: 0.8 um, 100 fs intensity FWHM, 10 um spot intensity FWHM,
# 1e22 W/cm2, with the peak at the target after 150 fs.
lambda0 = 0.8e-6
pulse_fwhm = 100.0e-15
spot_fwhm = 10.0e-6
gaussian_fwhm_to_parameter = math.sqrt(2.0 * math.log(2.0))
duration = pulse_fwhm / gaussian_fwhm_to_parameter
waist = spot_fwhm / gaussian_fwhm_to_parameter
laser_intensity_w_m2 = 1.0e22 * 1.0e4
laser_E0 = math.sqrt(2.0 * laser_intensity_w_m2 / (eps0 * c))
antenna_z = zmin + 3.0e-6
profile_t_peak = 1.5 * pulse_fwhm
laser = picmi.GaussianLaser(
    wavelength=lambda0,
    waist=waist,
    duration=duration,
    focal_position=[0.0, 0.0, z_neck],
    centroid_position=[0.0, 0.0, antenna_z - c * profile_t_peak],
    propagation_direction=[0.0, 0.0, 1.0],
    polarization_direction=[1.0, 0.0, 0.0],
    E0=laser_E0,
    fill_in=False,
)
laser_antenna = picmi.LaserAntenna(
    position=[0.0, 0.0, antenna_z],
    normal_vector=[0.0, 0.0, 1.0],
)

# Ez-only, native-resolution, cropped diagnostics.  All RZ modes are dumped;
# the analysis reconstructs them at theta=0.  HDF5 is retained only until the
# workflow's manifest-based cleanup is explicitly confirmed.
field_diagnostic = picmi.FieldDiagnostic(
    name="fields",
    grid=grid,
    period=field_diag_period,
    data_list=["Ez"],
    lower_bound=[diag_rmin, diag_zmin],
    upper_bound=[diag_rmax, diag_zmax],
    number_of_cells=[diag_nr, diag_nz],
    warpx_dump_rz_modes=1,
    write_dir="diags",
    warpx_file_prefix="openpmd",
    warpx_format="openpmd",
    warpx_openpmd_backend="h5",
    warpx_openpmd_encoding="f",
)
carbon_diagnostic = picmi.ReducedDiagnostic(
    diag_type="ParticleExtrema",
    name="carbon_probe_extrema",
    species=carbon_probe,
    period=probe_diag_period,
    path="diags/reduced/",
    extension="txt",
    separator=",",
)

simulation = picmi.Simulation(
    solver=solver,
    max_time=stop_time_s,
    verbose=1,
    particle_shape="cubic",
    warpx_use_filter=0,
    warpx_amrex_the_arena_is_managed=1,
    warpx_random_seed=1,
    warpx_load_balance_intervals=100,
    warpx_load_balance_costs_update="heuristic",
)
simulation.add_species(aluminum_ions, layout=ion_layout)
simulation.add_species(electrons, layout=electron_layout)
simulation.add_species(carbon_probe, layout=None)
simulation.add_laser(laser, injection_method=laser_antenna)
simulation.add_diagnostic(field_diagnostic)
simulation.add_diagnostic(carbon_diagnostic)

Path("diags/reduced").mkdir(parents=True, exist_ok=True)
resolved = {
    "schema_version": 1,
    "case_id": case_id,
    "case_name": case_name,
    "geometry_model": "rz_circle_head_quarter_ellipse_skirt",
    "n_azimuthal_modes": n_azimuthal_modes,
    "geometry": {
        "L1": L1,
        "L2": L2,
        "d_paper": wall,
        "r_head": r_head,
        "r_neck": r_neck,
        "r_exit": r_exit,
        "z_neck_paper": z_neck,
    },
    "derived_geometry": {
        "z_head_m": z_head,
        "z_exit_m": z_exit,
        "head_circle_radius_m": head_circle_radius,
    },
    "probe": {
        "species": "C12_6plus",
        "mass_kg": carbon12_mass_kg,
        "charge_C": carbon12_charge_C,
        "initial_energy_eV": carbon12_initial_energy_eV,
        "initial_z_m": probe_z0,
    },
    "grid": {
        "cell_size_m": cell_size,
        "nr": nr,
        "nz": nz,
        "rmin_m": rmin,
        "rmax_m": rmax,
        "zmin_m": zmin,
        "zmax_m": zmax,
    },
    "run": {
        "stop_time_s": stop_time_s,
        "cfl": cfl,
    },
    "field_diagnostic": {
        "period_steps": field_diag_period,
        "data": ["Ez"],
        "dump_all_rz_modes": True,
        "lower_bound_m": [diag_rmin, diag_zmin],
        "upper_bound_m": [diag_rmax, diag_zmax],
        "number_of_cells": [diag_nr, diag_nz],
    },
}
Path("resolved_parameters.json").write_text(
    json.dumps(resolved, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
simulation.write_input_file(file_name="inputs_rz_nozzle_preionized")

if write_only:
    print(
        "MNA PICMI preflight OK: "
        f"case={case_name} nr={nr} nz={nz} stop_time={stop_time_s:.6e}s"
    )
    raise SystemExit(0)

simulation.initialize_inputs()
simulation.initialize_warpx()
simulation.step()

