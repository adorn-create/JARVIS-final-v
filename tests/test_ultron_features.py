import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ultron_features

from ultron_features import (
    capability_report, strategic_plan, review_improvement,
    simulate_fleet,
)


class UltronFeatureTests(unittest.TestCase):
    def test_capabilities_include_all_requested_areas(self):
        report = capability_report()
        self.assertIn("robot_army", report["capabilities"])
        self.assertIn("self_improvement", report["capabilities"])

    def test_plan_is_advisory(self):
        result = strategic_plan("Improve local security monitoring")
        self.assertEqual(len(result["plan"]), 6)
        self.assertIn("does not execute", result["safety"])

    def test_saved_plan_is_local_and_manual_progress_only(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder) / "ultron_plans.json"
            with patch.object(ultron_features, "_plan_store_path", return_value=store):
                saved = ultron_features.save_strategy_plan("Improve JARVIS diagnostics")
                plan_id = saved["saved_plan"]["plan_id"]
                self.assertEqual(saved["saved_plan"]["status"], "proposed")
                updated = ultron_features.update_saved_plan_step(plan_id, 0, "completed")
                listed = ultron_features.list_saved_plans()
        self.assertEqual(updated["step_status"], "completed")
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["plans"][0]["completed_steps"], 1)
        self.assertIn("no background execution", listed["note"])

    def test_saved_plan_step_update_rejects_invalid_state(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder) / "ultron_plans.json"
            with patch.object(ultron_features, "_plan_store_path", return_value=store):
                saved = ultron_features.save_strategy_plan("Test safe plan")
                with self.assertRaises(ValueError):
                    ultron_features.update_saved_plan_step(
                        saved["saved_plan"]["plan_id"], 0, "execute"
                    )

    def test_improvement_is_proposal_only(self):
        result = review_improvement("voice", "Recognition misses short commands")
        self.assertIn("PROPOSAL ONLY", result["status"])

    def test_fleet_is_simulated(self):
        result = simulate_fleet("formation_demo", 4)
        self.assertTrue(result["simulation"])
        self.assertFalse(result["physical_devices_contacted"])
        self.assertEqual(len(result["units"]), 4)

    def test_rejects_unsafe_fleet_command(self):
        with self.assertRaises(ValueError):
            simulate_fleet("launch_weapons", 2)


if __name__ == "__main__":
    unittest.main()
