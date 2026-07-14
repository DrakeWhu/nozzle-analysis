from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from mna_nozzle_analysis.carbon import (
    CARBON12_MASS_KG,
    C_LIGHT_M_S,
    ELEMENTARY_CHARGE_C,
    carbon_terminal_metric,
    read_particle_extrema_series,
)


class CarbonTests(unittest.TestCase):
    @staticmethod
    def _probe_rows(
        times_fs: list[float],
        energies_MeV: list[float],
        *,
        x_um: list[float] | None = None,
        z_um: list[float] | None = None,
    ) -> np.ndarray:
        rest_MeV = (
            CARBON12_MASS_KG * C_LIGHT_M_S**2 / ELEMENTARY_CHARGE_C / 1.0e6
        )
        energies = np.asarray(energies_MeV)
        gamma = 1.0 + energies / rest_MeV
        pz = CARBON12_MASS_KG * C_LIGHT_M_S * np.sqrt(gamma * gamma - 1.0)
        raw = np.zeros((len(times_fs), 18))
        raw[:, 0] = np.arange(len(times_fs)) * 10
        raw[:, 1] = np.asarray(times_fs) * 1.0e-15
        raw[:, 2] = raw[:, 3] = np.asarray(x_um or [0.0] * len(times_fs)) * 1.0e-6
        raw[:, 6] = raw[:, 7] = np.asarray(z_um or [10.9] * len(times_fs)) * 1.0e-6
        raw[:, 12] = raw[:, 13] = pz
        raw[:, 14] = raw[:, 15] = gamma
        raw[:, 16] = raw[:, 17] = 1.0
        return raw

    @staticmethod
    def _empty_probe_row(step: float, time_fs: float) -> np.ndarray:
        row = np.zeros(18)
        row[0] = step
        row[1] = time_fs * 1.0e-15
        for low, high in (
            (2, 3), (4, 5), (6, 7), (8, 9),
            (10, 11), (12, 13), (14, 15), (16, 17),
        ):
            row[low] = np.inf
            row[high] = -np.inf
        return row

    @staticmethod
    def _grid() -> dict[str, float]:
        return {
            "cell_size_m": 0.05e-6,
            "rmax_m": 20.0e-6,
            "zmin_m": -15.0e-6,
            "zmax_m": 85.0e-6,
        }

    def _read(self, raw: np.ndarray):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.txt"
            np.savetxt(path, raw, delimiter=",", fmt="%.17e")
            return read_particle_extrema_series(path)

    def test_terminal_metric_uses_last_physical_sample_at_simulation_end(self) -> None:
        series = self._read(
            self._probe_rows([0.0, 500.0, 1000.0], [0.005, 1.005, 4.005])
        )
        metric = carbon_terminal_metric(series, grid=self._grid())
        self.assertAlmostEqual(metric.delta_kz_MeV, 4.0, places=8)
        self.assertAlmostEqual(metric.terminal_time_fs, 1000.0, places=10)
        self.assertEqual(metric.terminal_reason, "simulation_end")
        self.assertEqual(metric.trailing_empty_rows, 0)

    def test_terminal_metric_classifies_radial_loss(self) -> None:
        raw = self._probe_rows(
            [0.0, 500.0, 512.0],
            [0.005, 100.0, 424.005],
            x_um=[0.0, 10.0, 19.964],
            z_um=[10.9, 25.0, 32.27],
        )
        raw = np.vstack([raw, self._empty_probe_row(30.0, 513.0)])
        metric = carbon_terminal_metric(self._read(raw), grid=self._grid())
        self.assertAlmostEqual(metric.delta_kz_MeV, 424.0, places=7)
        self.assertEqual(metric.terminal_reason, "radial_upper_loss")
        self.assertAlmostEqual(metric.terminal_r_um, 19.964, places=9)
        self.assertAlmostEqual(metric.terminal_sampling_gap_fs, 1.0, places=9)

    def test_unresolved_particle_loss_is_retained_as_qa(self) -> None:
        raw = self._probe_rows([0.0, 300.0], [0.005, 1.005], x_um=[0.0, 1.0])
        raw = np.vstack([raw, self._empty_probe_row(20.0, 301.0)])
        metric = carbon_terminal_metric(self._read(raw), grid=self._grid())
        self.assertEqual(metric.terminal_reason, "particle_loss_unresolved")

    def test_empty_probe_rows_must_be_trailing(self) -> None:
        raw = self._probe_rows([0.0, 500.0], [0.005, 1.005])
        raw = np.vstack([raw[:1], self._empty_probe_row(10.0, 250.0), raw[1:]])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.txt"
            np.savetxt(path, raw, delimiter=",", fmt="%.17e")
            with self.assertRaisesRegex(ValueError, "trailing suffix"):
                read_particle_extrema_series(path)


if __name__ == "__main__":
    unittest.main()
