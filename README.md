# MNA nozzle analysis

Analysis module and campaign adapter for a fully pre-ionized aluminium
micronozzle simulated with WarpX in quasi-cylindrical RZ geometry.

The two optimization metrics are deliberately narrow:

1. `objective_carbon_terminal_delta_kz_MeV`: longitudinal kinetic-energy gain
   of the non-depositing C12 6+ probe between its initial state and its last
   physical `ParticleExtrema` sample.  The terminal sample is either the end of
   the simulation or the final sample immediately before the probe leaves an
   absorbing particle boundary.
2. `objective_exit_ez_p995_peak_100_300fs_V_m`: maximum, between 100 and
   300 fs, of the 99.5th percentile of `abs(Ez)` in the first 5 microns
   downstream of the nozzle exit and within the exit radius.

The carbon objective uses only the kinetic energy associated with `pz`; total
kinetic energy, terminal time, position, trajectory angle, sampling gap and
loss reason are retained as QA.  WarpX empty-species min/max sentinels are
accepted only as a trailing suffix.  A disappearance is classified against the
resolved radial and axial domain boundaries with a two-cell tolerance.

The field objective uses all dumped RZ modes reconstructed at `theta=0`, the
laser-polarization plane.  The 99.5th percentile is the optimization value;
the raw maximum is retained as a QA diagnostic because it is more sensitive
to isolated cells.

## Contents

- `src/mna_nozzle_analysis`: reusable analysis package and CLI.
- `examples/lynx/input_template.py`: environment-driven WarpX/PICMI input.
- `examples/lynx/campaign.json`: `campaign-workflow` contract.
- `examples/lynx/optimizer.json`: `campaign-optimizer` configuration, using
  its generic multichannel/Sobol-to-MORBO-like adapter.
- `examples/lynx/cases.tsv`: one nominal paper-based smoke case.
- `examples/lynx/run_*_lynx.sh`: simulation and analysis runners for the
  `novas` partition.
- `examples/dev/generate_synthetic_case.py`: deterministic end-to-end
  analysis smoke data; it is never used for scientific results.

## Parameter space

All bounds include the nominal geometry and are intentionally conservative
for the first campaign.  They also guarantee the ordering and aspect-ratio
constraints without asking the optimizer to understand nonlinear geometry.

| Parameter | Nominal [um] | First bounds [um] |
|---|---:|---:|
| L1 | 3.10 | 2.50 - 4.50 |
| L2 | 9.90 | 7.00 - 14.00 |
| wall thickness | 0.60 | 0.30 - 1.00 |
| head radius | 2.65 | 2.20 - 3.40 |
| neck radius | 1.40 | 1.00 - 1.80 |
| exit radius | 6.00 | 4.50 - 8.00 |
| neck z | 0.00 | fixed at 0.00 |

Guaranteed over the box: `r_neck < r_head < r_exit`,
`r_head-r_neck <= L1`, and `r_exit-r_neck <= L2`.

## Local checks

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"
python examples/dev/generate_synthetic_case.py /tmp/mna_synthetic
PYTHONPATH=src python -m mna_nozzle_analysis.cli analyze-case \
  /tmp/mna_synthetic --field-npz /tmp/mna_synthetic/synthetic_fields.npz
```

`campaign-optimizer` currently emits its legacy `WRITE_FIELD_DIAGNOSTIC`
column for the generic multichannel adapter.  This input intentionally ignores
that switch and always writes the cropped Ez diagnostic: Ez is an objective for
every MNA candidate, not just for the reference case.

## Lynx smoke case

Install this package in the analysis environment, copy the contents of
`examples/lynx` into a new campaign directory, then materialize and submit the
single case through `campaign-workflow`.  `LAUNCH.md` contains the exact
commands and keeps raw-HDF5 deletion disabled for the first run.

The current Lynx campaign enables animation in `case.env` and requires the
MP4 along with the CSVs and PNGs. `imageio-ffmpeg` is an optional library
dependency but is required for this profile; the launch procedure installs
the `animation` extra. This is a configuration requirement, not an intrinsic
physical requirement for evaluating the objectives. Their numerical values
come from carbon-probe samples and Ez field diagnostics, not from the MP4.
An absent MP4 can still block validation under this profile, and an animation
error when rendering is enabled can interrupt analysis. Required Ez diagnostics
and sufficient temporal sampling remain distinct from video production.
No animation flag or required-output declaration is changed here.
A cleanup dry run writes a manifest and evidence,
although it does not delete HDF5.

## Optimizer and retention boundaries

`examples/lynx/optimizer.json` maps the generic multichannel
`particle_summary` input to `post/mna_case_summary.csv`. The summary sets
`n_macroparticles_selected=1` and `charge_selected_pC` to the C6+ probe charge
for adapter eligibility. They are not electron-beam statistics. The configured
objectives remain the carbon longitudinal gain and the exit-field peak above.

The current configuration requests field diagnostics for all candidates.
Do not remove those diagnostics as an optimization of storage: every candidate
needs the Ez objective. Nozzle's last physical probe sample and field-window
peak must not be replaced by a shared "last frame" policy.

Whether animation should remain cleanup-blocking, which QA products must
survive reduction, and whether a dedicated optimizer adapter is needed remain
scientific/interface review questions. No behavior is changed here.
See campaign-workflow's `docs/INTEGRATION_REVIEW.md` and
campaign-optimizer's `docs/OBSERVATION_CONTRACT_REVIEW.md` at compatible revisions.

The isolated Cloud test result, dependencies, and evidence limitations are in
`docs/BASELINE_2026-10-20.md`.
That report is historical evidence for its recorded revision and environment,
not validation of future versions or SUNRISE/LYNX execution.
See `docs/DEVELOPMENT_BRANCH_REVIEW_2026-10-20.md` for the inspected remote
snapshot and cross-repository integration consequences.
