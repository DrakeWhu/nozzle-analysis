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
    def test_longitudinal_gain_at_one_ps(self) -> None:
        rest_MeV = (
            CARBON12_MASS_KG * C_LIGHT_M_S**2 / ELEMENTARY_CHARGE_C / 1.0e6
        )
        energies = np.asarray([0.005, 1.005, 4.005])
        gamma = 1.0 + energies / rest_MeV
        pz = CARBON12_MASS_KG * C_LIGHT_M_S * np.sqrt(gamma * gamma - 1.0)
        raw = np.zeros((3, 18))
        raw[:, 0] = [0, 10, 20]
        raw[:, 1] = np.asarray([0.0, 500.0, 1000.0]) * 1.0e-15
        raw[:, 6] = raw[:, 7] = 10.9e-6
        raw[:, 12] = raw[:, 13] = pz
        raw[:, 14] = raw[:, 15] = gamma
        raw[:, 16] = raw[:, 17] = 1.0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.txt"
            np.savetxt(path, raw, delimiter=",", fmt="%.17e")
            rows = read_particle_extrema(path)
        metric = carbon_target_metric(rows)
        self.assertAlmostEqual(metric.delta_kz_MeV, 4.0, places=8)
        self.assertAlmostEqual(metric.actual_time_fs, 1000.0, places=10)

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

