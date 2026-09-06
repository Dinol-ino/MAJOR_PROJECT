import unittest
from app.mcp.permission_layer import permission_layer


class TestMCPPermissionLayer(unittest.TestCase):

    def test_valid_payload_passes_validation(self):
        valid_args = {"query": "murder punishment Section 302", "top_k": 3}
        is_valid, err, validated = permission_layer.validate_request("local_statute_search", valid_args)
        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertEqual(validated["query"], "murder punishment Section 302")
        self.assertEqual(validated["top_k"], 3)

    def test_missing_required_arguments_rejected(self):
        # query is required
        invalid_args = {"top_k": 3}
        is_valid, err, validated = permission_layer.validate_request("local_statute_search", invalid_args)
        self.assertFalse(is_valid)
        self.assertIn("query", err)

    def test_out_of_bounds_parameters_rejected(self):
        # top_k max is 20
        invalid_args = {"query": "valid query", "top_k": 500}
        is_valid, err, validated = permission_layer.validate_request("local_statute_search", invalid_args)
        self.assertFalse(is_valid)
        self.assertIn("top_k", err)

    def test_unknown_tool_rejected(self):
        is_valid, err, validated = permission_layer.validate_request("non_existent_tool", {})
        self.assertFalse(is_valid)
        self.assertIn("Unknown tool", err)


if __name__ == "__main__":
    unittest.main()
