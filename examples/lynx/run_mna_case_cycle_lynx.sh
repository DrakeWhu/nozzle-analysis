#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[MNA-CYCLE] ERROR at line ${LINENO}: ${BASH_COMMAND}" >&2' ERR
set -x

if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
    echo "[MNA-CYCLE] ERROR: SLURM_ARRAY_TASK_ID is not set." >&2
    exit 2
fi

CAMPAIGN_ROOT="${CAMPAIGN_ROOT:-${SLURM_SUBMIT_DIR}}"
WORKFLOW_ROOT="${WORKFLOW_ROOT:-${HOME}/apps/src/campaign-workflow}"
WORKFLOW_ENV="${WORKFLOW_ENV:-${HOME}/apps/env/campaign_workflow_lynx.sh}"
CASE_RUNNER="${CASE_RUNNER:-${CAMPAIGN_ROOT}/run_warpx_mna_case_lynx.sh}"
ANALYSIS_RUNNER="${ANALYSIS_RUNNER:-${CAMPAIGN_ROOT}/run_mna_case_analysis_lynx.sh}"

CAMPAIGN_ROOT="$(cd "${CAMPAIGN_ROOT}" && pwd -P)"
WORKFLOW_ROOT="$(cd "${WORKFLOW_ROOT}" && pwd -P)"

cd "${CAMPAIGN_ROOT}"
mkdir -p array_logs

if [[ ! -f campaign.json || ! -f cases.tsv ]]; then
    echo "[MNA-CYCLE] ERROR: campaign.json/cases.tsv missing in ${CAMPAIGN_ROOT}" >&2
    exit 1
fi
if [[ ! -f "${WORKFLOW_ENV}" ]]; then
    echo "[MNA-CYCLE] ERROR: missing workflow env: ${WORKFLOW_ENV}" >&2
    exit 1
fi
if [[ ! -x "${CASE_RUNNER}" ]]; then
    echo "[MNA-CYCLE] ERROR: missing/non-executable case runner: ${CASE_RUNNER}" >&2
    exit 1
fi
if [[ ! -x "${ANALYSIS_RUNNER}" ]]; then
    echo "[MNA-CYCLE] ERROR: missing/non-executable analysis runner: ${ANALYSIS_RUNNER}" >&2
    exit 1
fi

set +e
CASE_ROW="$(
    awk -v task_id="${SLURM_ARRAY_TASK_ID}" '
        BEGIN { FS = "\t"; case_id_col = 0; case_name_col = 0; found = 0 }
        NR == 1 {
            for (i = 1; i <= NF; i++) {
                if ($i == "CASE_ID") case_id_col = i
                if ($i == "CASE_NAME") case_name_col = i
            }
            if (case_id_col == 0 || case_name_col == 0) exit 3
            next
        }
        ($case_id_col + 0) == (task_id + 0) {
            print $case_id_col "\t" $case_name_col
            found = 1
            exit 0
        }
        END { if (case_id_col == 0 || case_name_col == 0 || found == 0) exit 4 }
    ' cases.tsv
)"
CASE_ROW_RC=$?
set -e

if [[ "${CASE_ROW_RC}" -ne 0 || -z "${CASE_ROW}" ]]; then
    echo "[MNA-CYCLE] ERROR: no CASE_ID/CASE_NAME row found for SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID}" >&2
    exit 1
fi

IFS=$'\t' read -r CASE_ID CASE_NAME <<< "${CASE_ROW}"
CASE_DIR="${CAMPAIGN_ROOT}/${CASE_NAME}"

if [[ ! -d "${CASE_DIR}" ]]; then
    echo "[MNA-CYCLE] ERROR: missing case directory: ${CASE_DIR}" >&2
    exit 1
fi

mkdir -p "${CASE_DIR}/logs" "${CASE_DIR}/post"

export CAMPAIGN_ROOT WORKFLOW_ROOT WORKFLOW_ENV
export CASE_ID CASE_NAME CASE_DIR
export CAMPAIGN_RUN_PARTICLE_ANALYSIS="${CAMPAIGN_RUN_PARTICLE_ANALYSIS:-auto}"

SCHEDULER_JOB_ID="${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-}}"
SCHEDULER_ARRAY_TASK_ID="${SLURM_ARRAY_TASK_ID}"
CASE_LOG_PREFIX="logs/${SLURM_JOB_NAME}_${SCHEDULER_JOB_ID}_${SCHEDULER_ARRAY_TASK_ID}_${CASE_ID}"
STDOUT_LOG="${CASE_LOG_PREFIX}.out"
STDERR_LOG="${CASE_LOG_PREFIX}.err"
RUN_COMMAND="bash ${CASE_RUNNER} ${CASE_DIR}"
SUBMIT_COMMAND="sbatch ${CAMPAIGN_ROOT}/submit_mna_smoke_lynx.sh"

phase_log_path() {
    local phase_name="$1"
    local stream_name="$2"
    printf '%s/logs/case_cycle_%s_%s.txt' "${CASE_DIR}" "${phase_name}" "${stream_name}"
}

run_phase() {
    local phase_name="$1"
    shift

    local stdout_log
    local stderr_log
    local rc
    stdout_log="$(phase_log_path "${phase_name}" stdout)"
    stderr_log="$(phase_log_path "${phase_name}" stderr)"

    echo "[MNA-CYCLE] BEGIN phase=${phase_name} case_id=${CASE_ID} case_name=${CASE_NAME}"
    echo "[MNA-CYCLE] stdout=${stdout_log}"
    echo "[MNA-CYCLE] stderr=${stderr_log}"

    set +e
    "$@" > >(tee -a "${stdout_log}") 2> >(tee -a "${stderr_log}" >&2)
    rc=$?

    if [[ "${rc}" -ne 0 ]]; then
        echo "[MNA-CYCLE] FAIL phase=${phase_name} return_code=${rc}" >&2
        return "${rc}"
    fi

    set -e
    echo "[MNA-CYCLE] END phase=${phase_name}"
    return 0
}

load_workflow_env() {
    source "${WORKFLOW_ENV}"
}

load_workflow_env

run_phase mark_sim_submitted \
    python -m campaign_workflow.cli.mark_sim_submitted \
        --campaign-root "${CAMPAIGN_ROOT}" \
        --case-id "${CASE_ID}" \
        --scheduler slurm \
        --scheduler-job-id "${SCHEDULER_JOB_ID}" \
        --scheduler-array-task-id "${SCHEDULER_ARRAY_TASK_ID}" \
        --submit-command "${SUBMIT_COMMAND}" \
        --environment-name "campaign-workflow-py311" \
        --verbose

run_phase mark_sim_running \
    python -m campaign_workflow.cli.mark_sim_running \
        --campaign-root "${CAMPAIGN_ROOT}" \
        --case-id "${CASE_ID}" \
        --scheduler slurm \
        --scheduler-job-id "${SCHEDULER_JOB_ID}" \
        --scheduler-array-task-id "${SCHEDULER_ARRAY_TASK_ID}" \
        --run-command "${RUN_COMMAND}" \
        --environment-name "warpx-26.03-py311" \
        --stdout-log "${STDOUT_LOG}" \
        --stderr-log "${STDERR_LOG}" \
        --verbose

set +e
run_phase run_external_simulation bash "${CASE_RUNNER}" "${CASE_DIR}"
SIM_RC=$?
set -e

load_workflow_env

if [[ "${SIM_RC}" -ne 0 ]]; then
    run_phase mark_sim_failed \
        python -m campaign_workflow.cli.mark_sim_failed \
            --campaign-root "${CAMPAIGN_ROOT}" \
            --case-id "${CASE_ID}" \
            --scheduler slurm \
            --scheduler-job-id "${SCHEDULER_JOB_ID}" \
            --scheduler-array-task-id "${SCHEDULER_ARRAY_TASK_ID}" \
            --run-command "${RUN_COMMAND}" \
            --environment-name "warpx-26.03-py311" \
            --stdout-log "${STDOUT_LOG}" \
            --stderr-log "${STDERR_LOG}" \
            --return-code "${SIM_RC}" \
            --error "case-local WarpX runner failed" \
            --verbose || true

    echo "[MNA-CYCLE] STOP: simulation failed for case_id=${CASE_ID} return_code=${SIM_RC}" >&2
    exit "${SIM_RC}"
fi

run_phase mark_sim_done \
    python -m campaign_workflow.cli.mark_sim_done \
        --campaign-root "${CAMPAIGN_ROOT}" \
        --case-id "${CASE_ID}" \
        --verbose

run_phase validate_raw_case \
    python -m campaign_workflow.cli.validate_raw_case \
        --campaign-root "${CAMPAIGN_ROOT}" \
        --case-id "${CASE_ID}" \
        --verbose

run_phase analyze_case \
    python -m campaign_workflow.cli.analyze_case \
        --campaign-root "${CAMPAIGN_ROOT}" \
        --case-id "${CASE_ID}" \
        --verbose

run_phase validate_reduced_case \
    python -m campaign_workflow.cli.validate_reduced_case \
        --campaign-root "${CAMPAIGN_ROOT}" \
        --case-id "${CASE_ID}" \
        --verbose

run_phase mark_raw_delete_eligible \
    python -m campaign_workflow.cli.mark_raw_delete_eligible \
        --campaign-root "${CAMPAIGN_ROOT}" \
        --case-id "${CASE_ID}" \
        --verbose

run_phase cleanup_raw_case_dry_run \
    python -m campaign_workflow.cli.cleanup_raw_case \
        --campaign-root "${CAMPAIGN_ROOT}" \
        --case-id "${CASE_ID}" \
        --dry-run \
        --verbose

if [[ "${CONFIRM_CLEANUP_EXECUTE:-0}" == "1" ]]; then
    run_phase cleanup_raw_case_execute \
        python -m campaign_workflow.cli.cleanup_raw_case \
            --campaign-root "${CAMPAIGN_ROOT}" \
            --case-id "${CASE_ID}" \
            --execute \
            --verbose
else
    echo "[MNA-CYCLE] SKIP: cleanup execute not requested. Set CONFIRM_CLEANUP_EXECUTE=1 to enable it."
fi

echo "[MNA-CYCLE] DONE: case_id=${CASE_ID} case_name=${CASE_NAME}"

