from __future__ import annotations

import unittest

import numpy as np

from mna_nozzle_analysis.geometry import NozzleGeometry, region_masks


class GeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.geometry = NozzleGeometry(
            L1=3.1e-6,
            L2=9.9e-6,
            d_paper=0.6e-6,
            r_head=2.65e-6,
            r_neck=1.4e-6,
            r_exit=6.0e-6,
            z_neck_paper=0.0,
        )

    def test_canonical_surface_hits_all_three_apertures(self) -> None:
        radii = self.geometry.inner_radius(
            np.asarray(
                [self.geometry.z_head, self.geometry.z_neck_paper, self.geometry.z_exit]
            )
        )
        np.testing.assert_allclose(
            radii,
            [self.geometry.r_head, self.geometry.r_neck, self.geometry.r_exit],
            rtol=0.0,
            atol=1.0e-15,
        )

    def test_invalid_order_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "r_neck < r_head < r_exit"):
            NozzleGeometry(
                L1=3.1e-6,
                L2=9.9e-6,
                d_paper=0.6e-6,
                r_head=1.0e-6,
                r_neck=1.4e-6,
                r_exit=6.0e-6,
            )

    def test_exit_roi_is_nonempty(self) -> None:
        transverse = np.linspace(0.0, 10.0e-6, 101)
        z = np.linspace(-5.0e-6, 16.0e-6, 211)
        masks = region_masks(
            self.geometry,
            transverse,
            z,
            near_wall_m=0.5e-6,
            exit_band_m=5.0e-6,
        )
        self.assertGreater(int(masks["exit_downstream"].sum()), 0)
        self.assertGreater(int(masks["near_inner_wall"].sum()), 0)


if __name__ == "__main__":
    unittest.main()

