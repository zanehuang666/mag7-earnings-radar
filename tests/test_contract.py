import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.sync_msft_research import EVENTS as MSFT_RESEARCH_EVENTS, apply_narrative, parse_json_object


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
        events = self.data["calendar"]["formal"]["events"]
        for event in events:
            self.assertIn(event["status"], {"reported", "projected", "estimated", "confirmed"})
            if event["status"] == "estimated":
                self.assertEqual(event["date_confidence"], "estimated")
            if event["status"] == "projected":
                self.assertEqual(event["date_confidence"], "projected")
                self.assertTrue({"from", "to"}.issubset(event["date_range"]))

    def test_history_is_complete_from_2024(self):
        reported = [event for event in self.data["calendar"]["formal"]["events"] if event["status"] == "reported"]
        counts = {}
        for event in reported:
            self.assertGreaterEqual(event["date"], "2024-01-01")
            counts[event["ticker"]] = counts.get(event["ticker"], 0) + 1
        self.assertEqual(len(reported), 77)
        self.assertEqual(set(counts.values()), {11})
        self.assertEqual(len({event["id"] for event in reported}), len(reported))

    def test_forward_calendar_covers_every_company(self):
        estimated = [event for event in self.data["calendar"]["formal"]["events"] if event["status"] == "estimated"]
        self.assertEqual({event["ticker"] for event in estimated}, {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"})

    def test_four_future_periods_per_company(self):
        future = [event for event in self.data["calendar"]["formal"]["events"] if event["status"] != "reported"]
        counts = {}
        for event in future:
            counts[event["ticker"]] = counts.get(event["ticker"], 0) + 1
        self.assertEqual(set(counts.values()), {4})
        self.assertEqual(len(future), 28)
        self.assertEqual(sum(event["status"] == "projected" for event in future), 21)

    def test_calendar_ui_has_required_controls(self):
        html = (ROOT / "frontend" / "calendar.html").read_text(encoding="utf-8")
        for required in ("正式追踪", "历史验证", "运行完整时间模拟", "Preview", "Analysis", "showDate", "selectCompany", "setSimOffset", "2024 起点", "下一次预计", "stockForm", "removeStock", "companyClose", "eventBack", "eventClose", "未发布"):
            self.assertIn(required, html)

    def test_replay_has_two_auditable_system_snapshots(self):
        replay = self.data["calendar"]["replay"]
        self.assertEqual(replay["as_of"], "2026-01-27")
        self.assertEqual(replay["month"], "2026-01")
        html = (ROOT / "frontend" / "calendar.html").read_text(encoding="utf-8")
        for required in ("snapshotBefore", "snapshotAfter", "SNAPSHOT A · T-1",
                         "SNAPSHOT B · T+1", "runSnapshotDemo", "2026-01-29"):
            self.assertIn(required, html)

    def test_default_page_opens_calendar(self):
        html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn('content="0;url=calendar.html"', html)

    def test_search_candidate_index(self):
        candidates = json.loads((ROOT / "frontend" / "data" / "us_earnings_candidates.json").read_text(encoding="utf-8"))
        self.assertGreater(len(candidates["events"]), 1000)
        for event in candidates["events"]:
            self.assertTrue({"ticker", "company", "date", "fiscal_period"}.issubset(event))

    def test_public_sync_audit_and_real_verification_sample(self):
        sync = self.data["sync"]
        self.assertTrue(sync["automatic"])
        self.assertEqual(sync["schedule_timezone"], "Asia/Shanghai")
        self.assertTrue(any("周末" in item for item in sync["schedule"]))
        self.assertTrue({"previous_generated_at", "current_generated_at", "heartbeat_changed"}
                        .issubset(sync["audit"]))
        candidates = json.loads((ROOT / "frontend" / "data" / "us_earnings_candidates.json").read_text(encoding="utf-8"))
        sample = candidates["verification_sample"]
        self.assertEqual(sample["ticker"], "AEHR")
        self.assertEqual(sample["date"], "2026-10-05")
        self.assertIn(sample["status"], {"estimated", "reported"})
        self.assertTrue(sample["calendar_source"].startswith("https://api.nasdaq.com/"))
        self.assertTrue(sample["result_source"].startswith("https://api.nasdaq.com/"))

    def test_chart_colors_require_structured_research(self):
        html = (ROOT / "frontend" / "calendar.html").read_text(encoding="utf-8")
        self.assertIn("e.research?.analysis?.result_tone", html)
        self.assertIn("尚无完整研究结论", html)
        self.assertIn("空心灰＝尚无完整研究", html)
        self.assertIn("mag7-custom-cache", html)
        self.assertIn("checkLatestData", html)
        workflow = (ROOT / ".github" / "workflows" / "sync-and-deploy.yml").read_text(encoding="utf-8")
        self.assertIn('37 1 * * 0,6', workflow)

    def test_mu_search_fallback_has_history_and_four_projections(self):
        candidates = json.loads((ROOT / "frontend" / "data" / "us_earnings_candidates.json").read_text(encoding="utf-8"))
        profile = candidates["profiles"]["MU"]
        reported = [event for event in profile["events"] if event["status"] == "reported"]
        projected = [event for event in profile["events"] if event["status"] == "projected"]
        self.assertEqual(profile["company"], "Micron Technology")
        self.assertGreaterEqual(len(reported), 4)
        self.assertEqual(len(projected), 4)
        self.assertTrue(all({"from", "to"}.issubset(event["date_range"]) for event in projected))

    def test_market_snapshot_is_usable(self):
        market = json.loads((ROOT / "frontend" / "data" / "market_qqq.json").read_text(encoding="utf-8"))
        expected = {"QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"}
        self.assertEqual(set(market["series"]), expected)
        self.assertIn("09:37", market["refresh_schedule"])
        self.assertIn("21:37", market["refresh_schedule"])
        for series in market["series"].values():
            self.assertGreater(len(series["points"]), 500)
            self.assertGreaterEqual(series["points"][0]["date"], "2024-01-01")
            self.assertTrue(all({"date", "close"}.issubset(point) for point in series["points"]))

    def test_released_macro_events_are_auditable(self):
        macro = json.loads((ROOT / "frontend" / "data" / "macro_events.json").read_text(encoding="utf-8"))
        self.assertEqual(macro["consensus_policy"], "unavailable_not_inferred")
        self.assertEqual(set(macro["supported"]), {"FOMC", "CPI", "NFP", "PCE"})
        self.assertGreaterEqual(len(macro["events"]), 12)
        self.assertEqual({event["code"] for event in macro["events"]}, {"FOMC", "CPI", "NFP", "PCE"})
        for event in macro["events"]:
            self.assertIsNotNone(event["actual"])
            self.assertIsNone(event["forecast"])
            self.assertIn("不是市场预期差", event["comparison_basis"])
            self.assertTrue(event["source"]["url"].startswith("https://"))
            self.assertTrue(event["official_source"]["url"].startswith("https://"))
        html = (ROOT / "frontend" / "calendar.html").read_text(encoding="utf-8")
        for required in ("macro_events.json", "selectMacro", "macroPanel", "市场一致预期",
                         "不会把前值冒充预期"):
            self.assertIn(required, html)
        workflow = (ROOT / ".github" / "workflows" / "sync-and-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("sync_macro_events.py", workflow)


class Mag7ResearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "frontend" / "data" / "mag7_research.json").read_text(encoding="utf-8"))
        cls.reported = [event for event in cls.data["events"] if event["status"] == "reported"]

    def test_all_reported_mag7_events_have_research(self):
        self.assertEqual(self.data["coverage"]["reported_events"], 77)
        self.assertEqual(len(self.reported), 77)
        counts = {}
        for event in self.reported:
            counts[event["ticker"]] = counts.get(event["ticker"], 0) + 1
            self.assertIsNotNone(event["preview"])
            self.assertIsNotNone(event["analysis"])
            self.assertIn(event["analysis"]["result_tone"], {"positive", "negative", "mixed"})
            self.assertGreaterEqual(len(event["preview"]["market_focus"]), 3)
            self.assertGreaterEqual(len(event["analysis"]["risks"]), 3)
        self.assertEqual(set(counts.values()), {11})

    def test_baseline_has_real_eps_and_market_comparison(self):
        for event in self.reported:
            eps = next(metric for metric in event["analysis"]["metrics"] if metric["name"] in {"EPS", "Adjusted EPS"})
            self.assertNotEqual(eps["expectation"], "—")
            self.assertNotEqual(eps["actual"], "—")
            self.assertTrue(eps["source_ids"])
            reaction = event["analysis"].get("market_reaction")
            self.assertIsNotNone(reaction)
            self.assertEqual({item["horizon"] for item in reaction["metrics"]}, {"次一交易日", "5 个交易日"})

    def test_sources_and_low_token_incremental_policy(self):
        sources = self.data["sources"]
        for event in self.reported:
            for section_name, item_name in (("preview", "observations"), ("analysis", "drivers")):
                section = event[section_name]
                for metric in section["metrics"]:
                    self.assertTrue(set(metric["source_ids"]).issubset(sources))
                for item in section[item_name]:
                    self.assertTrue(set(item["source_ids"]).issubset(sources))
        self.assertEqual(self.data["generation"]["mode"], "deterministic_incremental_cache")
        self.assertEqual(self.data["generation"]["llm_calls"], 0)
        workflow = (ROOT / ".github" / "workflows" / "sync-and-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("sync_mag7_research.py", workflow)
        html = (ROOT / "frontend" / "calendar.html").read_text(encoding="utf-8")
        self.assertIn("mag7_research.json", html)


class MicrosoftResearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "frontend" / "data" / "msft_research.json").read_text(encoding="utf-8"))
        cls.events = {event["id"]: event for event in cls.data["events"]}

    def test_three_deliberate_samples(self):
        self.assertEqual(set(self.events), {
            "msft-2026-01-28", "msft-2026-07-29", "msft-2026-11-04",
        })
        self.assertEqual(
            [event["sample_role"] for event in self.data["events"]],
            ["过往已发布样本", "最近已发布样本", "未来预计样本"],
        )

    def test_model_json_can_follow_brief_prose(self):
        parsed = parse_json_object('以下是结果：\n```json\n{"preview_verdict":"ok"}\n```')
        self.assertEqual(parsed, {"preview_verdict": "ok"})

    def test_reported_analysis_has_expected_actual_and_delta(self):
        for event_id in ("msft-2026-01-28", "msft-2026-07-29"):
            event = self.events[event_id]
            self.assertEqual(event["status"], "reported")
            self.assertGreaterEqual(len(event["analysis"]["metrics"]), 6)
            for metric in event["analysis"]["metrics"]:
                self.assertTrue(metric["expectation"])
                self.assertTrue(metric["actual"])
                self.assertTrue(metric["delta"])
                self.assertTrue(metric["assessment"])

    def test_future_event_is_preview_only_and_unconfirmed(self):
        event = self.events["msft-2026-11-04"]
        self.assertEqual(event["status"], "estimated")
        self.assertIsNone(event["analysis"])
        self.assertGreaterEqual(len(event["preview"]["metrics"]), 8)
        self.assertIn("IR 未确认", event["preview"]["metrics"][0]["expectation"])

    def test_every_citation_resolves_to_https_source(self):
        sources = self.data["sources"]
        referenced = set()
        for event in self.data["events"]:
            for section_name in ("preview", "analysis"):
                section = event.get(section_name)
                if not section:
                    continue
                for metric in section["metrics"]:
                    referenced.update(metric["source_ids"])
                point_key = "observations" if section_name == "preview" else "drivers"
                for point in section[point_key]:
                    referenced.update(point["source_ids"])
        self.assertTrue(referenced)
        self.assertTrue(referenced.issubset(sources))
        self.assertTrue(all(source["url"].startswith("https://") for source in sources.values()))

    def test_low_token_guardrail_and_ui_hooks(self):
        self.assertLessEqual(self.data["generation"]["paratera_calls"], 3)
        html = (ROOT / "frontend" / "calendar.html").read_text(encoding="utf-8")
        for required in ("mag7_research.json", "metricBody", "sourceList", "information_cutoff",
                         "summaryBullets", "guidanceWrap", "reactionWrap", "chartVerdict"):
            self.assertIn(required, html)
        workflow = (ROOT / ".github" / "workflows" / "sync-and-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("refresh_research", workflow)
        self.assertIn("sync_msft_research.py", workflow)

    def test_model_cannot_introduce_new_numbers(self):
        event = json.loads(json.dumps(MSFT_RESEARCH_EVENTS[0]))
        value = {
            "preview_verdict": event["preview"]["verdict"] + " 新增 999%",
            "preview_summary": event["preview"]["summary"],
            "analysis_verdict": event["analysis"]["verdict"],
            "analysis_summary": event["analysis"]["summary"],
        }
        with self.assertRaisesRegex(ValueError, "introduced numbers"):
            apply_narrative(event, value)

    def test_expanded_preview_structure(self):
        for event in self.data["events"]:
            preview = event["preview"]
            self.assertGreaterEqual(len(preview["summary"]), 170)
            self.assertEqual(len(preview["summary_points"]), 3)
            self.assertGreaterEqual(len(preview["market_focus"]), 3)
            self.assertGreaterEqual(len(preview["risks"]), 3)
            self.assertTrue(all({"title", "text"}.issubset(item) for item in preview["observations"]))
            self.assertTrue(all(metric["tone"] in {"positive", "negative", "mixed", "neutral"}
                                for metric in preview["metrics"]))

    def test_analysis_guidance_and_market_reaction(self):
        market = json.loads((ROOT / "frontend" / "data" / "market_qqq.json").read_text(encoding="utf-8"))
        for event_id in ("msft-2026-01-28", "msft-2026-07-29"):
            event = self.events[event_id]
            analysis = event["analysis"]
            self.assertEqual(len(analysis["guidance_changes"]), 3)
            self.assertEqual(analysis["result_tone"], "positive")
            reported = {item["horizon"]: item for item in analysis["market_reaction"]["metrics"]}
            self.assertEqual(set(reported), {"次一交易日", "5 个交易日"})
            for offset, horizon in ((1, "次一交易日"), (5, "5 个交易日")):
                returns = {}
                for ticker in ("MSFT", "QQQ"):
                    points = market["series"][ticker]["points"]
                    index = next(i for i, point in enumerate(points) if point["date"] == event["date"])
                    returns[ticker] = (points[index + offset]["close"] / points[index]["close"] - 1) * 100
                relative = returns["MSFT"] - returns["QQQ"]
                self.assertEqual(reported[horizon]["msft"], f"{returns['MSFT']:+.2f}%")
                self.assertEqual(reported[horizon]["qqq"], f"{returns['QQQ']:+.2f}%")
                self.assertEqual(reported[horizon]["relative"], f"{relative:+.2f} pct")

    def test_analysis_risks_use_investment_validation_framework(self):
        required = {"title", "text", "transmission", "monitor", "trigger", "horizon",
                    "status", "counter_signal", "source_ids"}
        for event_id in ("msft-2026-01-28", "msft-2026-07-29"):
            risks = self.events[event_id]["analysis"]["risks"]
            self.assertGreaterEqual(len(risks), 5)
            self.assertTrue(all(required.issubset(risk) for risk in risks))
            self.assertTrue(all(risk["source_ids"] for risk in risks))


if __name__ == "__main__":
    unittest.main()
