# Lynx smoke launch procedure

This is a one-case reference run.  The commands intentionally perform a
materialization dry run before writing case files and keep HDF5 cleanup in
dry-run mode after successful analysis.

This is a procedure, not evidence that a run was completed. The 2026-10-20
Cloud baseline did not launch WarpX or SLURM.

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
python -m pip install '.[animation]'
python -m unittest discover -s tests -p "test_*.py"
```

Create the campaign from the versioned static files:

```bash
export MNA_SOURCE="${HOME}/apps/src/mna-nozzle-analysis/examples/lynx"
export RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
export CAMPAIGN_ROOT="${HOME}/warpx_runs/mna_nozzle_rz_smoke_${RUN_STAMP}"
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

STALE="$(
  find "${CAMPAIGN_ROOT}" -maxdepth 5 \
    \( -name '*.h5' -o -name '*.hdf5' -o -name 'carbon_probe_extrema.txt' \) \
    -print -quit
)"
if [[ -n "${STALE}" ]]; then
  echo "ERROR: fresh campaign unexpectedly contains stale diagnostics"
  find "${CAMPAIGN_ROOT}" -maxdepth 5 \
    \( -name '*.h5' -o -name '*.hdf5' -o -name 'carbon_probe_extrema.txt' \) \
    -print
  exit 1
fi
```

Submit the one array element only after the site environment is ready.
The current campaign sets `MNA_MAKE_ANIMATION=1` in materialized `case.env`
and requires `post/plots/mna_Ez_all_frames.mp4`. Keep animation enabled for
this profile and provide the animation dependency. Disabling the environment
flag alone does not remove the required-output contract; a different profile
needs a separately reviewed configuration.

The MP4 requirement belongs to this campaign configuration. Video is not an
input to the carbon-gain or Ez-percentile objective formulas and is not an
intrinsic physical prerequisite for evaluating them. The field diagnostics and
their temporal coverage are still needed for the field objective. Treat video
production and numerical/scientific checks separately when reviewing a future
profile; the instructions here preserve the current required-output behavior.
The dated Cloud baseline does not validate this LYNX launch procedure.

```bash
cd "${CAMPAIGN_ROOT}"
JOB_ID="$(
  sbatch --parsable \
    --export=ALL,CAMPAIGN_ROOT="${CAMPAIGN_ROOT}",WORKFLOW_ENV="${HOME}/apps/env/campaign_workflow_lynx.sh" \
    submit_mna_smoke_lynx.sh
)"
echo "${CAMPAIGN_ROOT}" > "${HOME}/last_mna_nozzle_campaign_root.txt"
echo "${JOB_ID}" > "${HOME}/last_mna_nozzle_job_id.txt"
echo "CAMPAIGN_ROOT=${CAMPAIGN_ROOT}"
echo "JOB_ID=${JOB_ID}"
```

The success criteria are:

- case state reaches `Raw_delete_eligible`;
- `validation.json` reports raw and reduced outputs as valid;
- `post/mna_case_summary.csv` contains finite values for both objective
  columns;
- `post/carbon_probe_timeseries.csv` contains the last physical probe sample:
  near the configured stop time if the probe survives, or before a classified
  boundary loss; inspect terminal reason, position, and sampling gap;
- the required PNGs and `post/plots/mna_Ez_all_frames.mp4` are present and
  non-empty; workflow file validation alone does not prove visual correctness;
- the cleanup dry run writes a manifest/evidence and leaves every H5 file
  intact. Keep `CONFIRM_CLEANUP_EXECUTE` unset or `0`.

