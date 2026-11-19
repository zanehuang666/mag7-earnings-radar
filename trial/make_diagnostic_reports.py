"""Create deliberately narrow Skill diagnostic reports from official latest releases."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "diagnostic-inputs"
SPECS = {
    "AVGO": {
        "name": "Broadcom", "currency": "USD", "unit": "百万美元", "quarter_end": "2026-08-02",
        "source": "https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-third-quarter-fiscal-year-2026-financial",
        "revenue": 29591, "segments": [],
        "intro": "仅展示已定位的 FY2026Q3 官方收入。历史、利润、现金流、量价及指引尚未逐季研究。",
    },
    "SMSN": {
        "name": "Samsung Electronics", "currency": "KRW", "unit": "十亿韩元", "quarter_end": "2026-09-30",
        "source": "https://news.samsung.com/global/samsung-electronics-announces-third-quarter-2026-results",
        "revenue": 195300, "segments": [],
        "intro": "仅展示已定位的 2026Q3 集团收入。历史、业务拆分、利润、现金流、量价及指引尚未逐季研究。",
    },
}


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    for ticker, spec in SPECS.items():
        dest = OUT / ticker
        dest.mkdir(parents=True, exist_ok=True)
        period = "FY2026Q3"
        base = {"schema_version": "1", "company_id": ticker.lower(), "updated_at": "2026-11-19"}
        write(dest / "periods.json", {**base, "records": [{"period_id": period, "fiscal_year": 2026, "fiscal_quarter": 3,
                                                      "quarter_end": spec["quarter_end"], "status": "reported"}]})
        write(dest / "sources.json", {**base, "records": [{"source_id": "q3-release", "publisher": spec["name"],
                                                      "is_company_official": True, "url": spec["source"], "title": "2026 Q3 earnings release"}]})
        facts = [{"fact_id": "group-revenue", "period_id": period, "period_type": "quarter", "metric_id": "consolidated_revenue",
                  "original_metric_name": "Consolidated revenue", "entity_id": "group", "parent_entity_id": None,
                  "value": spec["revenue"], "value_status": "reported", "unit_original": "million" if ticker == "AVGO" else "billion",
                  "currency": spec["currency"], "scale_original": "million" if ticker == "AVGO" else "billion",
                  "source_id": "q3-release", "locator": "Quarterly revenue / Third Quarter Financial Highlights", "side": None}]
        classifications = []
        for entity, label, value in spec["segments"]:
            facts.append({"fact_id": f"{entity}-revenue", "period_id": period, "period_type": "quarter", "metric_id": "segment_revenue",
                          "original_metric_name": label, "entity_id": entity, "parent_entity_id": None,
                          "value": value, "value_status": "reported", "unit_original": "million", "currency": "USD",
                          "scale_original": "million", "source_id": "q3-release", "locator": "Net revenue by segment", "side": None})
            classifications.append({"classification_id": entity, "entity_id": entity, "official_name": label,
                                    "valid_from_period_id": period, "side": None, "source_id": "q3-release"})
        write(dest / "facts.json", {**base, "records": facts})
        write(dest / "classification.json", {**base, "records": classifications})
        write(dest / "guidance.json", {**base, "records": []})
        write(dest / "report-view.json", {"company_name": spec["name"], "currency": spec["currency"],
                                          "display_unit": spec["unit"], "display_divisor": 1,
                                          "research_status": "diagnostic", "return_href": "../../calendar.html",
                                          "traditional_intro": spec["intro"], "ai_intro": "AI 相关业务金额尚未逐季核实；不把混合分部全部视为纯 AI。"})
        print(ticker, dest)


if __name__ == "__main__":
    main()
