import os
import tempfile
import shutil
import unittest
from app.finetuning.dataset_generator import BehaviorDatasetGenerator
from app.finetuning.ollama_adapter_exporter import OllamaAdapterExporter


class TestStage5Finetuning(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_behavior_dataset_exporter(self):
        generator = BehaviorDatasetGenerator()
        jsonl_path = os.path.join(self.test_dir, "dataset.jsonl")
        
        exported = generator.export_jsonl(jsonl_path, num_repeats=2)
        self.assertTrue(os.path.exists(exported))

        # Check line count (3 samples * 2 repeats = 6 lines)
        with open(exported, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 6)

    def test_ollama_modelfile_exporter(self):
        exporter = OllamaAdapterExporter(base_model="qwen2.5:7b", adapter_path="./test_adapter")
        modelfile_path = os.path.join(self.test_dir, "Modelfile")

        generated = exporter.generate_modelfile(modelfile_path)
        self.assertTrue(os.path.exists(generated))

        with open(generated, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("FROM qwen2.5:7b", content)
        self.assertIn("ADAPTER ./test_adapter", content)
        self.assertIn("DFrag Enterprise Legal Assistant", content)


if __name__ == "__main__":
    unittest.main()
