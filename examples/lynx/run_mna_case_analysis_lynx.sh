#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[MNA-ANALYSIS] ERROR at line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 CASE_DIR" >&2
    exit 2
fi
CASE_DIR="$(cd "$1" && pwd -P)"
if [[ ! -f "${CASE_DIR}/case.env" ]]; then
    echo "[MNA-ANALYSIS] missing case.env in ${CASE_DIR}" >&2
    exit 1
fi
set -a
source "${CASE_DIR}/case.env"
set +a

if [[ -n "${MNA_ANALYSIS_ENV_SCRIPT:-}" ]]; then
    if [[ ! -f "${MNA_ANALYSIS_ENV_SCRIPT}" ]]; then
        echo "[MNA-ANALYSIS] missing MNA_ANALYSIS_ENV_SCRIPT" >&2
        exit 1
    fi
    source "${MNA_ANALYSIS_ENV_SCRIPT}"
else
    if ! type module >/dev/null 2>&1; then
        source /etc/profile.d/modules.sh 2>/dev/null || true
    fi
    module purge
    module use "${HOME}/apps/modules"
    module load WarpX/26.03_lynx_cpu_rz_yee_openpmd_py311
    ANALYSIS_VENV="${MNA_ANALYSIS_VENV:-${HOME}/apps/venvs/warpx-26.03-py311}"
    if [[ ! -f "${ANALYSIS_VENV}/bin/activate" ]]; then
        echo "[MNA-ANALYSIS] missing analysis venv: ${ANALYSIS_VENV}" >&2
        exit 1
    fi
    source "${ANALYSIS_VENV}/bin/activate"
fi

python - <<'PY'
import mna_nozzle_analysis
import openpmd_viewer
print(f"mna-nozzle-analysis={mna_nozzle_analysis.__version__}")
print(f"openPMD-viewer={getattr(openpmd_viewer, '__version__', 'unknown')}")
PY

animation_args=()
if [[ "${MNA_MAKE_ANIMATION:-0}" == "1" ]]; then
    animation_args+=(--make-animation)
fi
python -m mna_nozzle_analysis.cli analyze-case "${CASE_DIR}" \
    --diagnostics-dir diags \
    --reduced-diagnostic diags/reduced/carbon_probe_extrema.txt \
    --parameters resolved_parameters.json \
    --output-dir post \
    --theta-rad 0.0 \
    --target-time-fs 1000 \
    --target-tolerance-fs 25 \
    --field-window-start-fs 100 \
    --field-window-end-fs 300 \
    --near-wall-um 0.5 \
    --exit-band-um 5.0 \
    "${animation_args[@]}"

test -s "${CASE_DIR}/post/mna_case_summary.csv"
test -s "${CASE_DIR}/post/carbon_probe_timeseries.csv"
test -s "${CASE_DIR}/post/mna_field_timeseries.csv"
echo "[MNA-ANALYSIS] DONE: ${CASE_DIR}/post/mna_case_summary.csv"
