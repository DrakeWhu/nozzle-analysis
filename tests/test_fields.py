from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from mna_nozzle_analysis.fields import (
    FieldFrame,
    _resolve_openpmd_h5_directory,
    frame_metrics,
    select_field_objective,
)
from mna_nozzle_analysis.geometry import NozzleGeometry


class OpenPMDDirectoryTests(unittest.TestCase):
    def test_direct_h5_files_take_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "openpmd_000000.h5").touch()
            nested = root / "nested"
            nested.mkdir()
            (nested / "openpmd_000100.h5").touch()
            self.assertEqual(_resolve_openpmd_h5_directory(root), root.resolve())

    def test_unique_nested_h5_directory_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "openpmd"
            nested.mkdir()
            (nested / "openpmd_000000.h5").touch()
            (nested / "openpmd_000100.h5").touch()
            self.assertEqual(_resolve_openpmd_h5_directory(root), nested.resolve())

    def test_multiple_nested_h5_directories_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("first", "second"):
                nested = root / name
                nested.mkdir()
                (nested / "openpmd_000000.h5").touch()
            with self.assertRaisesRegex(ValueError, "multiple directories"):
                _resolve_openpmd_h5_directory(root)

    def test_missing_h5_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "no openPMD .h5 files"):
                _resolve_openpmd_h5_directory(directory)


class FieldMetricTests(unittest.TestCase):
    def test_peak_frame_is_selected_inside_window_only(self) -> None:
        geometry = NozzleGeometry(
            L1=3.1e-6,
            L2=9.9e-6,
            d_paper=0.6e-6,
            r_head=2.65e-6,
            r_neck=1.4e-6,
            r_exit=6.0e-6,
        )
        transverse = np.linspace(0.0, 8.0e-6, 81)
        z = np.linspace(-4.0e-6, 16.0e-6, 201)
        base = np.zeros((transverse.size, z.size))
        rows = []
        for iteration, time_fs, amplitude in (
            (0, 50.0, 100.0),
            (100, 150.0, 10.0),
            (200, 200.0, 20.0),
            (300, 350.0, 200.0),
        ):
            field = base.copy()
            exit_mask = (
                (z[None, :] >= geometry.z_exit)
                & (z[None, :] <= geometry.z_exit + 5.0e-6)
                & (transverse[:, None] <= geometry.r_exit)
            )
            field[exit_mask] = amplitude
            rows.extend(
                frame_metrics(
                    FieldFrame(
                        iteration=iteration,
                        time_s=time_fs * 1.0e-15,
                        ez_v_m=field,
                        transverse_m=transverse,
                        z_m=z,
                        transverse_name="r",
                    ),
                    geometry,
                )
            )
        selected = select_field_objective(rows)
        self.assertEqual(selected["iteration"], 200)
        self.assertEqual(selected["p995_abs_Ez_V_m"], 20.0)


if __name__ == "__main__":
    unittest.main()
