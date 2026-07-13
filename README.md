# MNA nozzle analysis

Analysis module and campaign adapter for a fully pre-ionized aluminium
micronozzle simulated with WarpX in quasi-cylindrical RZ geometry.

The two optimization metrics are deliberately narrow:

1. `objective_carbon_delta_kz_1ps_MeV`: longitudinal kinetic-energy gain of
   the non-depositing C12 6+ probe at 1 ps.
2. `objective_exit_ez_p995_peak_100_300fs_V_m`: maximum, between 100 and
   300 fs, of the 99.5th percentile of `abs(Ez)` in the first 5 microns
   downstream of the nozzle exit and within the exit radius.

The field objective uses all dumped RZ modes reconstructed at `theta=0`, the
laser-polarization plane.  The 99.5th percentile is the optimization value;
the raw maximum is retained as a QA diagnostic because it is more sensitive
to isolated cells.

## Contents

- `src/mna_nozzle_analysis`: reusable analysis package and CLI.
- `examples/lynx/input_template.py`: environment-driven WarpX/PICMI input.
- `examples/lynx/campaign.json`: `campaign-workflow` contract.
- `examples/lynx/optimizer.json`: `campaign-optimizer` configuration, using
  its generic multichannel/Sobol-to-MORBO adapter.
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
