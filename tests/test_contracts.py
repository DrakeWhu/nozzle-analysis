from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_nominal_case_contains_materialization_columns(self) -> None:
        campaign = json.loads(
            (ROOT / "examples/lynx/campaign.json").read_text(encoding="utf-8")
        )
        with (ROOT / "examples/lynx/cases.tsv").open(
            encoding="utf-8", newline=""
        ) as stream:
            row = next(csv.DictReader(stream, delimiter="\t"))
        required = {
            rule["column"]
            for rule in campaign["case_materialization"]["env_columns"]
            if rule.get("required")
        }
        self.assertFalse(required.difference(row))
        self.assertEqual(row["Z_NECK_UM"], "0.00")

    def test_optimizer_box_guarantees_geometry_constraints(self) -> None:
        optimizer = json.loads(
            (ROOT / "examples/lynx/optimizer.json").read_text(encoding="utf-8")
        )
        bounds = {
            item["name"]: item["bounds"]
            for item in optimizer["parameter_space"]["parameters"]
        }
        self.assertLess(bounds["r_neck_um"][1], bounds["r_head_um"][0])
        self.assertLess(bounds["r_head_um"][1], bounds["r_exit_um"][0])
        self.assertLessEqual(
            bounds["r_head_um"][1] - bounds["r_neck_um"][0],
            bounds["L1_um"][0],
        )
        self.assertLessEqual(
            bounds["r_exit_um"][1] - bounds["r_neck_um"][0],
            bounds["L2_um"][0],
        )

    def test_campaign_and_optimizer_share_objective_columns(self) -> None:
        campaign = json.loads(
            (ROOT / "examples/lynx/campaign.json").read_text(encoding="utf-8")
        )
        optimizer = json.loads(
            (ROOT / "examples/lynx/optimizer.json").read_text(encoding="utf-8")
        )
        summary = next(
            item
            for item in campaign["analysis"]["outputs"]
            if item["name"] == "mna_case_summary"
        )
        objective_metrics = {
            item["metric"] for item in optimizer["objective"]["objectives"]
        }
        self.assertTrue(objective_metrics.issubset(summary["required_columns"]))

    def test_lynx_stale_diagnostic_literal_is_checked_explicitly(self) -> None:
        script = (
            ROOT / "examples/lynx/run_warpx_mna_case_lynx.sh"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "existing_raw=(diags/*.h5 diags/*.hdf5 "
            "diags/reduced/carbon_probe_extrema.txt)",
            script,
        )
        self.assertIn(
            "if [[ -e diags/reduced/carbon_probe_extrema.txt ]]; then",
            script,
        )

    def test_lynx_case_env_is_exported_to_python(self) -> None:
        runner = (
            ROOT / "examples/lynx/run_warpx_mna_case_lynx.sh"
        ).read_text(encoding="utf-8")
        analysis = (
            ROOT / "examples/lynx/run_mna_case_analysis_lynx.sh"
        ).read_text(encoding="utf-8")
        for script in (runner, analysis):
            self.assertIn("set -a\nsource", script)
            self.assertIn("set +a", script)
        self.assertIn("{ env | grep '^MNA_' || true; } | sort", runner)

    def test_lynx_warpx_runner_uses_mpirun_by_default(self) -> None:
        runner = (
            ROOT / "examples/lynx/run_warpx_mna_case_lynx.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('MPI_LAUNCHER="${MNA_MPI_LAUNCHER:-mpirun}"', runner)
        self.assertIn('mpirun|mpiexec)', runner)
        self.assertIn('srun)', runner)
        self.assertNotIn('srun -n "${SLURM_NTASKS}" python -u input.py', runner)

    def test_picmi_analytic_distribution_constants_are_expression_inputs_only(
        self,
    ) -> None:
        source = (ROOT / "examples/lynx/input_template.py").read_text(
            encoding="utf-8"
        )
        module = ast.parse(source)
        geometry_constants = None
        for node in module.body:
            if isinstance(node, ast.Assign):
                targets = [
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                ]
                if targets == ["geometry_constants"] and isinstance(
                    node.value, ast.Dict
                ):
                    geometry_constants = {
                        key.value
                        for key in node.value.keys
                        if isinstance(key, ast.Constant)
                    }
                    break
        self.assertIsNotNone(geometry_constants)
        self.assertNotIn("L1", geometry_constants)
        self.assertNotIn("r_head", geometry_constants)


if __name__ == "__main__":
    unittest.main()
