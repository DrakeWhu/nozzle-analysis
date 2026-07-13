# Audited Lynx smoke launch

This is a one-case reference run.  The commands intentionally perform a
materialization dry run before writing case files and keep HDF5 cleanup in
dry-run mode after successful analysis.

Assumptions:

- `campaign-workflow` is at commit `82bbea6` or a compatible descendant.
- WarpX is loaded by module
  `WarpX/26.03_lynx_cpu_rz_yee_openpmd_py311`.
- the package has been committed and pulled to
  `${HOME}/apps/src/mna-nozzle-analysis`.

Install the versioned analysis package into the existing Python 3.11 WarpX
environment:

```bash
bash --noprofile --norc
cd "${HOME}/apps/src/mna-nozzle-analysis"
git pull --ff-only
module purge
module use "${HOME}/apps/modules"
module load WarpX/26.03_lynx_cpu_rz_yee_openpmd_py311
source "${HOME}/apps/venvs/warpx-26.03-py311/bin/activate"
python -m pip install .
python -m unittest discover -s tests -p "test_*.py"
```

Create the campaign from the versioned static files:

```bash
export MNA_SOURCE="${HOME}/apps/src/mna-nozzle-analysis/examples/lynx"
export CAMPAIGN_ROOT="${HOME}/campaigns/mna_nozzle_rz_smoke"
mkdir -p "${CAMPAIGN_ROOT}" "${CAMPAIGN_ROOT}/array_logs"
cp "${MNA_SOURCE}/campaign.json" "${CAMPAIGN_ROOT}/"
cp "${MNA_SOURCE}/cases.tsv" "${CAMPAIGN_ROOT}/"
cp "${MNA_SOURCE}/input_template.py" "${CAMPAIGN_ROOT}/"
cp "${MNA_SOURCE}/run_mna_case_cycle_lynx.sh" "${CAMPAIGN_ROOT}/"
cp "${MNA_SOURCE}/run_warpx_mna_case_lynx.sh" "${CAMPAIGN_ROOT}/"
cp "${MNA_SOURCE}/run_mna_case_analysis_lynx.sh" "${CAMPAIGN_ROOT}/"
cp "${MNA_SOURCE}/submit_mna_smoke_lynx.sh" "${CAMPAIGN_ROOT}/"
chmod 0755 "${CAMPAIGN_ROOT}"/*.sh
source "${HOME}/apps/env/campaign_workflow_lynx.sh"
python -m campaign_workflow.cli.materialize_cases \
  --campaign-root "${CAMPAIGN_ROOT}" --case-id 0 --dry-run --verbose
python -m campaign_workflow.cli.materialize_cases \
  --campaign-root "${CAMPAIGN_ROOT}" --case-id 0 --verbose
python -m campaign_workflow.cli.init_case_states \
  --campaign-root "${CAMPAIGN_ROOT}" --case-id 0 --dry-run --verbose
python -m campaign_workflow.cli.init_case_states \
  --campaign-root "${CAMPAIGN_ROOT}" --case-id 0 --verbose
python -m campaign_workflow.cli.init_case_states \
  --campaign-root "${CAMPAIGN_ROOT}" --case-id 0 --check --verbose
```

Submit the one array element.  Leave animation off until the core CSV/plot
contract passes; set `MNA_MAKE_ANIMATION=1` on a later rerun if desired.

```bash
cd "${CAMPAIGN_ROOT}"
sbatch --export=ALL,CAMPAIGN_ROOT="${CAMPAIGN_ROOT}",WORKFLOW_ENV="${HOME}/apps/env/campaign_workflow_lynx.sh" submit_mna_smoke_lynx.sh
```

The success criteria are:

- case state reaches `Raw_delete_eligible`;
- `validation.json` reports raw and reduced outputs as valid;
- `post/mna_case_summary.csv` contains finite values for both objective
  columns;
- `post/carbon_probe_timeseries.csv` reaches approximately 1000 fs;
- the cleanup phase only prints a dry-run manifest and leaves every H5 file
  intact.
