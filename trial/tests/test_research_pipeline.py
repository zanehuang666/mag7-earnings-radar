import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_pipeline as pipeline
import prepare_previews


class ResearchPipelineTest(unittest.TestCase):
    def test_historical_preview_uses_prior_release_and_is_not_original_forecast(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packets = root / "packets"
            prior = packets / "INTC" / "2024Q1" / "analysis.json"
            prior.parent.mkdir(parents=True)
            prior.write_text(json.dumps({"sources": ["https://example.com/q1"],
                "facts": ["Q1 revenue 12.7bn. Related content Q3 2026 results"],
                "release_date": "2024-04-25", "verification_status": "official_release_text_collected"}), encoding="utf-8")
            events = [
                {"id": "q1", "ticker": "INTC", "company": "Intel", "date": "2024-04-25", "status": "reported", "fiscal_period": "Mar 2024"},
                {"id": "q2", "ticker": "INTC", "company": "Intel", "date": "2024-08-01", "status": "reported", "fiscal_period": "Jun 2024"},
            ]
            with patch.object(prepare_previews, "PACKETS", packets):
                self.assertEqual(prepare_previews.seed_historical(events, {"q1": "2024Q1", "q2": "2024Q2"}, "INTC"), 1)
            packet = json.loads((packets / "INTC/2024Q2/preview.json").read_text(encoding="utf-8"))
            self.assertTrue(packet["historical_reconstruction"])
            self.assertLess(packet["cutoff"][:10], events[1]["date"])
            self.assertNotIn("Q3 2026", packet["facts"][0])
            data = root / "mag7.json"
            data.write_text(json.dumps({"calendar": {"formal": {"events": events}}}), encoding="utf-8")
            prompt = root / "prompt.txt"
            prompt.write_text("{company} {ticker} {quarter} {stage} {cutoff}", encoding="utf-8")
            answer = {"english_draft": "Prior-quarter revenue increased.", "reader_questions": ["a", "b", "c"],
                      "fact_checks": ["verified"], "markdown": "# 历史资料重建：Intel 前瞻\n\n[Source](https://example.com/q1)"}
            with patch.multiple(pipeline, ROOT=root, DATA=data, RESEARCH=root / "research", PACKETS=packets, PROMPT=prompt), \
                 patch.dict(os.environ, {"PARATERA_API_KEY": "test", "PARATERA_BASE_URL": "https://example.com", "PARATERA_MODEL": "test", "RESEARCH_CALL_LIMIT": "1"}), \
                 patch.object(pipeline, "call_model", return_value=answer):
                pipeline.main()
            index = json.loads((root / "research-index.json").read_text(encoding="utf-8"))
            self.assertTrue(index["events"]["q2"]["stages"]["preview"]["historical_reconstruction"])
            self.assertTrue((root / "research/INTC/2024Q2/preview.md").exists())

    def test_preview_is_frozen_and_analysis_is_incremental(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "mag7.json"
            events = [
                {"id": "googl-2024-10-20", "ticker": "GOOGL", "company": "Alphabet", "date": "2024-10-20", "fiscal_period": "Sep 2024", "status": "reported"},
                {"id": "googl-2030-02-01", "ticker": "GOOGL", "company": "Alphabet", "date": "2030-02-01", "fiscal_period": "Projected quarter +1", "status": "estimated"},
            ]
            data.write_text(json.dumps({"calendar": {"formal": {"events": events}}}), encoding="utf-8")
            packets = root / "packets"
            for q, stage, confirmed in (("2024Q3", "analysis", True), ("2024Q4", "preview", False)):
                path = packets / "GOOGL" / q / f"{stage}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"sources": ["https://example.com/official"], "facts": ["Revenue 1 USD"],
                                            "cutoff": "2029-12-01", "official_release_confirmed": confirmed}), encoding="utf-8")
            prompt = root / "prompt.txt"
            prompt.write_text("{company} {ticker} {quarter} {stage} {cutoff}", encoding="utf-8")
            answer = {"english_draft": "Revenue increased.", "reader_questions": ["a", "b", "c"],
                      "fact_checks": ["checked"], "markdown": "# Report\n\n[Source](https://example.com/official)"}
            with patch.multiple(pipeline, ROOT=root, DATA=data, RESEARCH=root / "research", PACKETS=packets, PROMPT=prompt), \
                 patch.dict(os.environ, {"PARATERA_API_KEY": "test", "PARATERA_BASE_URL": "https://example.com", "PARATERA_MODEL": "test", "RESEARCH_CALL_LIMIT": "1"}), \
                 patch.object(pipeline, "call_model", return_value=answer) as model:
                pipeline.main()
                first = json.loads((root / "research-index.json").read_text(encoding="utf-8"))
                self.assertEqual(first["model_calls"], 1)
                self.assertEqual(first["events"]["googl-2024-10-20"]["stages"]["preview"]["status"], "unavailable")
                self.assertTrue((root / "research/GOOGL/2024Q4/preview.md").exists())
                pipeline.main()
                second = json.loads((root / "research-index.json").read_text(encoding="utf-8"))
                self.assertEqual(second["model_calls"], 1)
                self.assertTrue((root / "research/GOOGL/2024Q3/analysis.md").exists())
                pipeline.main()
                self.assertEqual(model.call_count, 2)


if __name__ == "__main__":
    unittest.main()
