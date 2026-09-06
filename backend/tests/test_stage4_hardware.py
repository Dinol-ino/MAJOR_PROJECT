import unittest
from app.system.hardware_detector import HardwareDetector, HardwareProfile
from fastapi.testclient import TestClient
from app.main import app


class TestStage4Hardware(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_auto_tier_selection_low_ram(self):
        profile_low = HardwareProfile(
            cpu_cores=4,
            cpu_name="Mock CPU",
            ram_total_gb=6.0,
            ram_available_gb=4.0,
            gpu_available=False,
            gpu_name=None,
            gpu_vram_gb=None,
            gpu_backend=None,
            storage_free_gb=20.0,
            platform_name="windows",
            supports_avx2=True
        )
        tier_info = HardwareDetector.get_auto_selected_tier(profile_low)
        self.assertEqual(tier_info["tier"], 0)
        self.assertEqual(tier_info["default_model"], "qwen2.5:3b")
        self.assertFalse(tier_info["upgrade_opt_in"])

    def test_auto_tier_selection_high_vram(self):
        profile_high = HardwareProfile(
            cpu_cores=16,
            cpu_name="Mock CPU High",
            ram_total_gb=32.0,
            ram_available_gb=24.0,
            gpu_available=True,
            gpu_name="NVIDIA RTX 4090",
            gpu_vram_gb=24.0,
            gpu_backend="cuda",
            storage_free_gb=100.0,
            platform_name="windows",
            supports_avx2=True
        )
        tier_info = HardwareDetector.get_auto_selected_tier(profile_high)
        self.assertEqual(tier_info["tier"], 2)
        self.assertEqual(tier_info["default_model"], "qwen2.5:14b")
        self.assertTrue(tier_info["upgrade_opt_in"])

    def test_override_validation_warning(self):
        # Claiming impossible VRAM (100GB) should produce validation warning
        res = HardwareDetector.validate_override(claimed_vram_gb=100.0)
        # On systems with <100GB VRAM, warnings list should contain at least 1 warning
        if res["detected_profile"]["gpu_vram_gb"] is not None and res["detected_profile"]["gpu_vram_gb"] < 100.0:
            self.assertFalse(res["valid"])
            self.assertTrue(len(res["warnings"]) > 0)

    def test_auto_select_endpoint(self):
        response = self.client.get("/models/auto-select")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("hardware", data)
        self.assertIn("tier_selection", data)
        self.assertIn("tier", data["tier_selection"])

    def test_override_endpoint(self):
        response = self.client.post("/models/override", json={"claimed_vram_gb": 4.0})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("valid", data)
        self.assertIn("warnings", data)


if __name__ == "__main__":
    unittest.main()
