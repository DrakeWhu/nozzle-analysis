from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LynxCampaignAnimationTests(unittest.TestCase):
    def test_animation_is_enabled_and_required(self) -> None:
        campaign = json.loads(
            (
                ROOT / "examples/lynx/campaign.json"
            ).read_text(encoding="utf-8")
        )

        constants = campaign["case_materialization"]["env_constants"]
        self.assertEqual(constants["MNA_MAKE_ANIMATION"], "1")

        outputs = {
            item["name"]: item
            for item in campaign["analysis"]["outputs"]
        }
        self.assertTrue(outputs["ez_animation"]["required"])
        self.assertEqual(
            outputs["ez_animation"]["path"],
            "post/plots/mna_Ez_all_frames.mp4",
        )

        command = " ".join(campaign["analysis"]["command"])
        self.assertIn("run_mna_case_analysis_lynx.sh", command)
        self.assertIn("{case_dir}", command)


    def test_optimizer_requests_fields_for_all_candidates(self) -> None:
        optimizer = json.loads(
            (
                ROOT / "examples/lynx/optimizer.json"
            ).read_text(encoding="utf-8")
        )

        batch = optimizer["candidate_batch"]
        self.assertTrue(batch["write_fields_for_all"])

    def test_iteration_wrapper_selects_mna_runner(self) -> None:
        wrapper = (
            ROOT / "examples/lynx/run_mna_iteration_array_lynx.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("run_warpx_mna_case_lynx.sh", wrapper)
        self.assertIn("run_iteration_array_lynx.sh", wrapper)
        self.assertIn("export CASE_RUNNER", wrapper)
        self.assertNotIn("sbatch ", wrapper)


if __name__ == "__main__":
    unittest.main()
