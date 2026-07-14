#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[MNA-ITERATION-ARRAY] ERROR at line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

: "${CW_WORKFLOW_ROOT:?missing CW_WORKFLOW_ROOT}"

MNA_REPO="${MNA_REPO:-${HOME}/apps/src/mna-nozzle-analysis}"
CASE_RUNNER="${MNA_REPO}/examples/lynx/run_warpx_mna_case_lynx.sh"
GENERIC_ARRAY="${CW_WORKFLOW_ROOT}/examples/lynx/run_iteration_array_lynx.sh"

if [[ ! -x "${CASE_RUNNER}" ]]; then
    echo "[MNA-ITERATION-ARRAY] missing MNA case runner: ${CASE_RUNNER}" >&2
    exit 1
fi

if [[ ! -f "${GENERIC_ARRAY}" ]]; then
    echo "[MNA-ITERATION-ARRAY] missing generic Lynx array: ${GENERIC_ARRAY}" >&2
    exit 1
fi

export CASE_RUNNER

exec bash "${GENERIC_ARRAY}"
