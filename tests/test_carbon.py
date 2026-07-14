from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from mna_nozzle_analysis.carbon import (
    CARBON12_MASS_KG,
    C_LIGHT_M_S,
    ELEMENTARY_CHARGE_C,
    carbon_target_metric,
    read_particle_extrema,
)


class CarbonTests(unittest.TestCase):
    @staticmethod
    def _probe_rows(times_fs: list[float], energies_MeV: list[float]) -> np.ndarray:
        rest_MeV = (
            CARBON12_MASS_KG * C_LIGHT_M_S**2 / ELEMENTARY_CHARGE_C / 1.0e6
        )
        energies = np.asarray(energies_MeV)
        gamma = 1.0 + energies / rest_MeV
        pz = CARBON12_MASS_KG * C_LIGHT_M_S * np.sqrt(gamma * gamma - 1.0)
        raw = np.zeros((len(times_fs), 18))
        raw[:, 0] = np.arange(len(times_fs)) * 10
        raw[:, 1] = np.asarray(times_fs) * 1.0e-15
        raw[:, 6] = raw[:, 7] = 10.9e-6
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
            (2, 3),
            (4, 5),
            (6, 7),
            (8, 9),
            (10, 11),
            (12, 13),
            (14, 15),
            (16, 17),
        ):
            row[low] = np.inf
            row[high] = -np.inf
        return row

    def test_longitudinal_gain_at_one_ps(self) -> None:
        raw = self._probe_rows([0.0, 500.0, 1000.0], [0.005, 1.005, 4.005])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.txt"
            np.savetxt(path, raw, delimiter=",", fmt="%.17e")
            rows = read_particle_extrema(path)
        metric = carbon_target_metric(rows)
        self.assertAlmostEqual(metric.delta_kz_MeV, 4.0, places=8)
        self.assertAlmostEqual(metric.actual_time_fs, 1000.0, places=10)

    def test_trailing_empty_probe_rows_are_ignored(self) -> None:
        raw = self._probe_rows([0.0, 500.0, 990.0], [0.005, 1.005, 4.005])
        raw = np.vstack(
            [
                raw,
                self._empty_probe_row(30.0, 995.0),
                self._empty_probe_row(40.0, 1000.0),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.txt"
            np.savetxt(path, raw, delimiter=",", fmt="%.17e")
            rows = read_particle_extrema(path)
        self.assertEqual(len(rows), 3)
        metric = carbon_target_metric(rows)
        self.assertAlmostEqual(metric.actual_time_fs, 990.0, places=10)
        self.assertAlmostEqual(metric.delta_kz_MeV, 4.0, places=8)

    def test_empty_probe_rows_must_be_trailing(self) -> None:
        raw = self._probe_rows([0.0, 500.0], [0.005, 1.005])
        raw = np.vstack(
            [raw[:1], self._empty_probe_row(10.0, 250.0), raw[1:]]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.txt"
            np.savetxt(path, raw, delimiter=",", fmt="%.17e")
            with self.assertRaisesRegex(ValueError, "trailing suffix"):
                read_particle_extrema(path)

    def test_target_must_be_sampled(self) -> None:
        rows = [
            {
                "time_fs": 0.0,
                "kinetic_energy_from_pz_MeV": 0.005,
                "kinetic_energy_MeV": 0.005,
                "pz_over_mc": 0.0,
            },
            {
                "time_fs": 300.0,
                "kinetic_energy_from_pz_MeV": 1.0,
                "kinetic_energy_MeV": 1.0,
                "pz_over_mc": 0.01,
            },
        ]
        with self.assertRaisesRegex(ValueError, "no carbon sample"):
            carbon_target_metric(rows, target_time_fs=1000.0, tolerance_fs=25.0)


if __name__ == "__main__":
    unittest.main()
