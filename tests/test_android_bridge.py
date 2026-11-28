import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import android_bridge


class AndroidBridgeTests(unittest.TestCase):
    def test_lists_authorized_and_unauthorized_devices_without_control(self):
        output = (
            "List of devices attached\n"
            "R58M1234567 device product:demo model:Pixel_8 device:husky\n"
            "emulator-5554 unauthorized\n"
        )
        with patch.object(android_bridge, "_run", return_value=output), \
             patch.object(android_bridge, "_load_device_aliases", return_value={"R58M1234567": "Main phone"}):
            result = android_bridge.list_android_devices()
        self.assertEqual(result["ready_count"], 1)
        self.assertEqual(result["devices"][0]["alias"], "Main phone")
        self.assertEqual(result["devices"][1]["state"], "unauthorized")

    def test_launches_allowlisted_app_for_each_selected_device(self):
        with patch.object(android_bridge, "_validated_targets", return_value=["PHONE_A", "PHONE_B"]), \
             patch.object(android_bridge, "_per_device", side_effect=lambda serial, args, timeout=12: "ok") as run:
            result = android_bridge.launch_android_app(["PHONE_A", "PHONE_B"], "youtube")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(run.call_count, 2)

    def test_unknown_android_app_is_rejected(self):
        with patch.object(android_bridge, "_validated_targets") as validate:
            result = android_bridge.launch_android_app(["PHONE_A"], "unknown-app")
        self.assertFalse(result["ok"])
        validate.assert_not_called()

    def test_wireless_connect_rejects_public_addresses(self):
        with patch.object(android_bridge, "_run") as run:
            with self.assertRaisesRegex(ValueError, "private LAN"):
                android_bridge.connect_wireless_android_device("8.8.8.8:5555")
        run.assert_not_called()

    def test_wireless_pair_requires_six_digit_code(self):
        with patch.object(android_bridge, "_run") as run:
            with self.assertRaisesRegex(ValueError, "six-digit"):
                android_bridge.pair_wireless_android_device("192.168.1.20:37123", "123")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
