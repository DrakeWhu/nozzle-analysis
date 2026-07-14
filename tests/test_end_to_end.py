from __future__ import annotations

import csv
import tempfile
import unittest

from mna_nozzle_analysis.analysis import analyze_case
from mna_nozzle_analysis.synthetic import write_synthetic_case


class EndToEndTests(unittest.TestCase):
    def test_synthetic_case_satisfies_csv_and_plot_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = write_synthetic_case(directory)
            summary = analyze_case(
                root,
                field_npz="synthetic_fields.npz",
            )
            self.assertEqual(summary["analysis_status"], "ok")
            self.assertAlmostEqual(
                summary["objective_carbon_terminal_delta_kz_MeV"], 4.0, places=7
            )
            self.assertEqual(summary["carbon_terminal_reason"], "simulation_end")
            self.assertEqual(summary["exit_ez_peak_time_fs"], 200.0)
            required = (
                "post/mna_case_summary.csv",
                "post/carbon_probe_timeseries.csv",
                "post/mna_field_timeseries.csv",
                "post/plots/carbon_probe_energy_vs_time.png",
                "post/plots/mna_field_metrics_vs_time.png",
                "post/plots/mna_peak_exit_Ez.png",
                "post/analysis_report.json",
            )
            for relative in required:
                self.assertGreater((root / relative).stat().st_size, 0, relative)
            with (root / "post/mna_case_summary.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                row = next(csv.DictReader(stream))
            self.assertTrue(row["objective_carbon_terminal_delta_kz_MeV"])
            self.assertTrue(row["carbon_terminal_reason"])
            self.assertTrue(row["objective_exit_ez_p995_peak_100_300fs_V_m"])


if __name__ == "__main__":
    unittest.main()
