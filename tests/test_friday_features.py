import unittest

from friday_features import (
    analyze_movement, assess_safety_signals, navigation_guidance, emergency_guidance,
    fuse_environmental_observations
)


class FridayFeaturesTests(unittest.TestCase):
    def test_movement_prediction(self):
        result = analyze_movement([
            {"x": 0, "y": 0, "t": 0},
            {"x": 10, "y": 0, "t": 1},
            {"x": 20, "y": 0, "t": 2},
        ])
        self.assertEqual(result["direction"], "right")
        self.assertEqual(result["predicted_position"], {"x": 30.0, "y": 0.0})

    def test_reject_non_monotonic_samples(self):
        with self.assertRaises(ValueError):
            analyze_movement([{"x": 0, "y": 0, "t": 1}, {"x": 1, "y": 1, "t": 1}])

    def test_safety_score(self):
        result = assess_safety_signals(["smoke", "fire"])
        self.assertEqual(result["level"], "high")

    def test_sensor_fusion_reports_corroboration_without_declaring_emergency(self):
        result = fuse_environmental_observations(
            camera_motion_detected=True,
            acoustic_classification="strong transient or very loud sound",
            reported_signals=[],
        )
        self.assertEqual(result["corroboration"], "multiple_sources_observed")
        self.assertEqual(result["decision"], "review_observations")
        self.assertIn("does not contact responders", result["limitations"])

    def test_sensor_fusion_requires_explicit_supported_safety_signals(self):
        result = fuse_environmental_observations(reported_signals=["fire"])
        self.assertEqual(result["reported_signal_advisory"]["level"], "moderate")
        with self.assertRaises(ValueError):
            fuse_environmental_observations(acoustic_classification="speech detected")

    def test_navigation_wraparound(self):
        result = navigation_guidance(350, 10)
        self.assertEqual(result["guidance"], "turn right")
        self.assertEqual(result["relative_turn_deg"], 20.0)

    def test_emergency_guidance(self):
        result = emergency_guidance("fire")
        self.assertTrue(result["recommended_steps"])


if __name__ == "__main__":
    unittest.main()
