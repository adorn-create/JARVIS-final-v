import unittest

from module_router import route_request


class ModuleRouterTests(unittest.TestCase):
    def test_security_routes_to_morpheus(self):
        self.assertIn("MORPHEUS", route_request("check TLS certificate and firewall")["modules"])

    def test_sensor_routes_to_ev(self):
        self.assertIn("E.V.", route_request("read wearable heart rate")["modules"])

    def test_navigation_routes_to_friday(self):
        self.assertIn("F.R.I.D.A.Y.", route_request("give me navigation bearing guidance")["modules"])

    def test_desktop_routes_to_jarvis(self):
        self.assertIn("JARVIS", route_request("open notepad and type hello")["modules"])

    def test_combined_request_routes_multiple_modules(self):
        modules = route_request("check camera motion and scan for malware")["modules"]
        self.assertIn("E.V.", modules)
        self.assertIn("MORPHEUS", modules)


if __name__ == "__main__":
    unittest.main()
