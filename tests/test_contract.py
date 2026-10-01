import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "frontend" / "data" / "microsoft.json").read_text(encoding="utf-8"))

    def test_required_top_level_fields(self):
        self.assertTrue({"company", "ticker", "formal", "demo", "sources"}.issubset(self.data))

    def test_supported_date_status(self):
        allowed = {"estimated", "confirmed", "reported", "not_announced", "source_error", "review_required"}
        self.assertIn(self.data["formal"]["next_event"]["status"], allowed)

    def test_no_fake_confirmed_date(self):
        event = self.data["formal"]["next_event"]
        if event["status"] == "not_announced":
            self.assertIsNone(event["date"])

    def test_research_contract(self):
        required = {"title", "verdict", "summary", "points", "risks"}
        for kind in ("preview", "aftercheck"):
            self.assertTrue(required.issubset(self.data["demo"][kind]["data"]))


if __name__ == "__main__":
    unittest.main()
