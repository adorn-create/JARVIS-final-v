import unittest

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
