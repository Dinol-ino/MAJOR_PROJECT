import unittest
from unittest.mock import patch
from app.retrieval.fusion_router import filter_superseded_provisions
from app.config import settings


class TestSupersededFilter(unittest.TestCase):

    def test_filter_superseded_provisions(self):
        chunks = [
            {
                "act": "Indian Penal Code, 1860",
                "section": "Section 302",
                "text": "Punishment for murder.",
                "metadata": {"superseded_by": "Bharatiya Nyaya Sanhita, 2023 Section 103"}
            },
            {
                "act": "Bharatiya Nyaya Sanhita, 2023",
                "section": "Section 103",
                "text": "Punishment for murder under BNS.",
                "metadata": {"superseded_by": None}
            },
            {
                "act": "Code of Criminal Procedure, 1973",
                "section": "Section 154",
                "text": "Information in cognizable cases.",
                "metadata": {"is_superseded": True}
            }
        ]

        # With exclude_superseded = True (Default)
        valid = filter_superseded_provisions(chunks)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["act"], "Bharatiya Nyaya Sanhita, 2023")

    def test_superseded_filter_bypass_when_disabled(self):
        chunks = [
            {
                "act": "Old Act",
                "section": "Sec 1",
                "text": "Old provision",
                "metadata": {"superseded_by": "New Act"}
            }
        ]
        with patch.object(settings.retrieval, "exclude_superseded", False):
            result = filter_superseded_provisions(chunks)
            self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
