"""Summarize first-tier 2024+ research article and official-source coverage."""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "research-index.json"
ORDER = ("MSFT", "AMZN", "META", "GOOGL", "ORCL", "SPACEX", "NVDA", "AVGO", "AMD", "MU", "INTC", "SKHX", "SMSN")


def main() -> None:
    events = json.loads(INDEX.read_text(encoding="utf-8"))["events"]
    from_date = os.getenv("RESEARCH_FROM_DATE", "2026-01-01")
    through_date = os.getenv("RESEARCH_THROUGH_DATE", "2026-12-31")
    source = {}
    for packet_path in (ROOT / "source-packets").glob("*/*/analysis.json"):
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        key = f"{packet_path.parent.parent.name}/{packet_path.parent.name}"
        source[key] = {"status": packet.get("verification_status", "official_source_missing")}
    by_ticker = defaultdict(list)
    for event in events.values():
        if from_date <= event["date"] <= through_date:
            by_ticker[event["ticker"]].append(event)
    lines = ["# 第一梯队 2026 年财报研究覆盖", "", "状态按本地试用版资料统计。官方资料包不等于已经完成 Markdown 文章。", "",
             "| 公司 | 已发布季度 | 官方正文已采 | 官方关键事实已核 | 旧数据待逐值复核 | 官方正文待补 | 历史 Preview 资料包 | Analysis MD 索引/研究 | 历史 Preview MD 索引/研究 | 未来 Preview MD 索引/研究 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for ticker in ORDER:
        rows = by_ticker[ticker]
        reported = [r for r in rows if r["stages"]["analysis"]["status"] != "unavailable"]
        future = [r for r in rows if r["stages"]["analysis"]["status"] == "unavailable"]
        statuses = Counter(source.get(f"{ticker}/{r['quarter']}", {}).get("status", "official_source_missing") for r in reported)
        official = sum(v for k, v in statuses.items() if k in ("official_release_text_collected", "official_filing_text_collected"))
        manual = statuses["manual_verified"]
        pending = statuses["source_review_pending"]
        missing = len(reported) - official - manual - pending
        analysis = sum(bool(r["stages"]["analysis"]["path"]) for r in reported)
        analysis_research = sum(bool(r["stages"]["analysis"]["path"]) and r["stages"]["analysis"]["status"] != "baseline_source_limited" for r in reported)
        historical_packets = sum(bool(r["stages"]["preview"].get("historical_reconstruction")) for r in reported)
        historical_preview = sum(bool(r["stages"]["preview"]["path"]) for r in reported)
        historical_research = sum(bool(r["stages"]["preview"]["path"]) and r["stages"]["preview"]["status"] != "baseline_source_limited" for r in reported)
        future_preview = sum(bool(r["stages"]["preview"]["path"]) for r in future)
        future_research = sum(bool(r["stages"]["preview"]["path"]) and r["stages"]["preview"]["status"] != "baseline_source_limited" for r in future)
        lines.append(f"| {ticker} | {len(reported)} | {official} | {manual} | {pending} | {missing} | {historical_packets} | {analysis}/{analysis_research} | {historical_preview}/{historical_research} | {future_preview}/{future_research} |")
    lines += ["", "说明：SpaceX 没有公开的标准季度财报，保留公司 HTML 旧版草稿，不创建季度研究事件。",
              "历史 Preview 资料包只使用上一季已发布的官方资料，生成稿须标明‘历史资料重建’，不能冒充当时发表的预测。2024 年首季如无 2023 年同期前资料，仍保持空缺。"]
    lines += ["MD 表中的‘索引’包含资料不足时的确定性 Markdown 底稿；‘研究’仅统计人工样稿或模型生成的完整草稿。"]
    (ROOT / "research-coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
