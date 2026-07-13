#!/usr/bin/env bash
#SBATCH --job-name=mna_rz_smoke
#SBATCH --partition=novas
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=16
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --array=0-0
#SBATCH --output=array_logs/%x_%A_%a.out
#SBATCH --error=array_logs/%x_%A_%a.err

set -Eeuo pipefail
trap 'echo "[MNA-SMOKE] ERROR at line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

if [[ "${SLURM_JOB_PARTITION:-}" != "novas" ]]; then
    echo "[MNA-SMOKE] partition must be novas" >&2
    exit 1
fi
CAMPAIGN_ROOT="${CAMPAIGN_ROOT:-${SLURM_SUBMIT_DIR}}"
WORKFLOW_ROOT="${WORKFLOW_ROOT:-${HOME}/apps/src/campaign-workflow}"
export CAMPAIGN_ROOT WORKFLOW_ROOT
export CASE_RUNNER="${CAMPAIGN_ROOT}/run_warpx_mna_case_lynx.sh"
export CONFIRM_CLEANUP_EXECUTE=0
export MNA_MAKE_ANIMATION="${MNA_MAKE_ANIMATION:-0}"

exec bash "${WORKFLOW_ROOT}/examples/sunrise/submit_case_cycle_array.sh"

