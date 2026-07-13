#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[MNA-WARPX] ERROR at line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 CASE_DIR" >&2
    exit 2
fi
if [[ -z "${SLURM_JOB_ID:-}" || -z "${SLURM_NTASKS:-}" ]]; then
    echo "[MNA-WARPX] SLURM_JOB_ID and SLURM_NTASKS are required" >&2
    exit 1
fi
if [[ "${SLURM_JOB_PARTITION:-}" != "novas" ]]; then
    echo "[MNA-WARPX] this runner is restricted to partition novas" >&2
    exit 1
fi

CASE_DIR="$(cd "$1" && pwd -P)"
cd "${CASE_DIR}"
if [[ ! -f case.env || ! -f input.py ]]; then
    echo "[MNA-WARPX] missing case.env or input.py in ${CASE_DIR}" >&2
    exit 1
fi
set -a
source ./case.env
set +a
mkdir -p logs post diags/reduced

shopt -s nullglob
existing_raw=(diags/*.h5 diags/*.hdf5)
if [[ -e diags/reduced/carbon_probe_extrema.txt ]]; then
    existing_raw+=(diags/reduced/carbon_probe_extrema.txt)
fi
if (( ${#existing_raw[@]} > 0 )); then
    echo "[MNA-WARPX] refusing to mix a new run with existing diagnostics:" >&2
    printf '  %s\n' "${existing_raw[@]}" >&2
    exit 1
fi

if ! type module >/dev/null 2>&1; then
    source /etc/profile.d/modules.sh 2>/dev/null || true
fi
module purge
module use "${HOME}/apps/modules"
module load WarpX/26.03_lynx_cpu_rz_yee_openpmd_py311

WARPX_VENV="${MNA_WARPX_VENV:-${HOME}/apps/venvs/warpx-26.03-py311}"
if [[ ! -f "${WARPX_VENV}/bin/activate" ]]; then
    echo "[MNA-WARPX] missing WarpX venv: ${WARPX_VENV}" >&2
    exit 1
fi
source "${WARPX_VENV}/bin/activate"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

{
    echo "=== MNA RUN INFO ==="
    date --iso-8601=seconds
    echo "CASE_DIR=${CASE_DIR}"
    echo "SLURM_JOB_ID=${SLURM_JOB_ID}"
    echo "SLURM_JOB_PARTITION=${SLURM_JOB_PARTITION}"
    echo "SLURM_NTASKS=${SLURM_NTASKS}"
    echo "python=$(command -v python)"
    python --version
    { env | grep '^MNA_' || true; } | sort
} | tee run_info.txt

echo "[MNA-WARPX] PICMI write-only preflight"
MNA_DRY_RUN=1 python -u input.py
test -s inputs_rz_nozzle_preionized
test -s resolved_parameters.json
python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("resolved_parameters.json").read_text(encoding="utf-8"))
if payload.get("geometry_model") != "rz_circle_head_quarter_ellipse_skirt":
    raise SystemExit("unexpected geometry model")
if int(payload.get("n_azimuthal_modes", 0)) != 2:
    raise SystemExit("RZ campaign requires exactly two azimuthal modes")
if float(payload["run"]["stop_time_s"]) < 1.0e-12:
    raise SystemExit("stop time does not reach the 1 ps objective")
if payload["field_diagnostic"].get("data") != ["Ez"]:
    raise SystemExit("objective diagnostic must contain Ez only")
if payload["field_diagnostic"].get("dump_all_rz_modes") is not True:
    raise SystemExit("objective diagnostic must dump every RZ mode")
print("[MNA-WARPX] resolved-parameter preflight OK")
PY

echo "[MNA-WARPX] srun -n ${SLURM_NTASKS} python -u input.py"
srun -n "${SLURM_NTASKS}" python -u input.py

shopt -s nullglob
produced_h5=(diags/*.h5 diags/*.hdf5)
if (( ${#produced_h5[@]} == 0 )); then
    echo "[MNA-WARPX] simulation produced no openPMD HDF5 files" >&2
    exit 1
fi
test -s diags/reduced/carbon_probe_extrema.txt
date --iso-8601=seconds
echo "[MNA-WARPX] DONE"
