import os
import unittest
from app.config.settings import (
    Settings,
    ModelConfig,
    SecurityConfig,
    RetrievalConfig,
    MemoryConfig,
    MCPConfig,
    PerformanceConfig,
    NetworkModeConfig,
    settings,
)
from app.system.model_registry import ModelRegistry


class TestSettings(unittest.TestCase):
    def test_settings_default_instances(self):
        self.assertIsNotNone(settings.model)
        self.assertIsNotNone(settings.security)
        self.assertIsNotNone(settings.retrieval)
        self.assertIsNotNone(settings.memory)
        self.assertIsNotNone(settings.mcp)
        self.assertIsNotNone(settings.performance)
        self.assertIsNotNone(settings.network)

    def test_backward_compatible_aliases(self):
        self.assertEqual(settings.OLLAMA_URL, settings.model.ollama_url)
        self.assertEqual(settings.DEFAULT_MODEL, settings.model.default_model)
        self.assertEqual(settings.SQLITE_DB_PATH, settings.memory.sqlite_db_path)
        self.assertEqual(settings.CHROMA_PERSIST_DIR, settings.retrieval.chroma_persist_dir)
        self.assertEqual(settings.INJECTION_RISK_THRESHOLD, settings.security.injection_risk_threshold)

    def test_model_registry_loads_yaml(self):
        import yaml
        registry = ModelRegistry()
        with open(registry.yaml_path, encoding="utf-8") as f:
            declared = [m["model_id"] for m in (yaml.safe_load(f) or {}).get("models", [])]
        model_ids = [m.model_id for m in registry.all_models()]
        # The registry reflects exactly what the YAML declares (no code-side defaults mixed in).
        self.assertEqual(sorted(model_ids), sorted(declared))
        self.assertTrue(len(model_ids) >= 1)

    def test_security_config_thresholds(self):
        sec = SecurityConfig(injection_risk_threshold=0.85, grounding_overlap_threshold=0.1)
        self.assertEqual(sec.injection_risk_threshold, 0.85)
        self.assertEqual(sec.grounding_overlap_threshold, 0.1)
        self.assertTrue(sec.enable_pii_scanning)


if __name__ == "__main__":
    unittest.main()
