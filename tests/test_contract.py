import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.sync import parse_json_object


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

    def test_model_json_can_follow_brief_prose(self):
        parsed = parse_json_object('以下是结果：\n```json\n{"title":"ok"}\n```')
        self.assertEqual(parsed, {"title": "ok"})


class Mag7CalendarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "frontend" / "data" / "mag7.json").read_text(encoding="utf-8"))
        cls.events = cls.data["calendar"]["replay"]["events"]

    def test_all_mag7_tickers_are_present(self):
        expected = {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"}
        self.assertEqual({event["ticker"] for event in self.events}, expected)

    def test_every_replay_event_is_auditable(self):
        for event in self.events:
            self.assertRegex(event["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(event["source"]["url"].startswith("https://"))
            for kind in ("preview", "aftercheck"):
                research = event[kind]
                self.assertTrue({"verdict", "summary", "points", "risks"}.issubset(research))
                self.assertGreaterEqual(len(research["points"]), 3)
                self.assertGreaterEqual(len(research["risks"]), 2)

    def test_formal_calendar_does_not_fake_dates(self):
        self.assertEqual(self.data["calendar"]["formal"]["events"], [])

    def test_calendar_ui_has_required_controls(self):
        html = (ROOT / "frontend" / "calendar.html").read_text(encoding="utf-8")
        for required in ("正式追踪", "历史验证", "推进模拟时间", "Preview", "Aftercheck"):
            self.assertIn(required, html)

    def test_default_page_opens_calendar(self):
        html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn('content="0;url=calendar.html"', html)


if __name__ == "__main__":
    unittest.main()
