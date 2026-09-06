import os
import unittest
import yaml
from app.system.installer_helper import DesktopInstallerHelper


class TestStage6Deployment(unittest.TestCase):
    def test_docker_compose_config(self):
        compose_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "docker-compose.yml")
        self.assertTrue(os.path.exists(compose_path))

        with open(compose_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        services = data.get("services", {})
        self.assertIn("backend", services)
        self.assertIn("frontend", services)
        self.assertIn("postgres", services)
        self.assertIn("redis", services)

    def test_desktop_installer_helper(self):
        helper = DesktopInstallerHelper()
        res = helper.run_first_launch_check()
        self.assertTrue(res["standalone_ready"])
        self.assertIn("hardware_tier", res)
        self.assertIn("recommended_model", res)


if __name__ == "__main__":
    unittest.main()
