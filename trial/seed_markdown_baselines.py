"""Port the live site's deterministic research layer to first-tier Markdown.

Every event gets a readable, explicitly limited Markdown record. These are
indexes/baselines, not model-written or source-verified buy-side articles.
Paratera may replace a baseline when a qualified source packet is available.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from research_pipeline import DATA, FIRST, PACKETS, RESEARCH, ROOT, event_quarters

LIVE = ROOT / "v13-based" / "data" / "mag7_research.json"

FOCUS = {
    "MSFT": ["Azure 增速", "云业务利润率", "AI 资本开支与现金流"],
    "AMZN": ["AWS 增速", "零售利润率", "资本开支与自由现金流"],
    "META": ["广告价格和展示量", "应用家族利润率", "AI 资本开支"],
    "GOOGL": ["搜索与 YouTube 广告", "Google Cloud 收入和利润", "AI 投入与现金流"],
    "ORCL": ["云基础设施收入", "剩余履约义务与转化", "资本开支与现金流"],
    "NVDA": ["数据中心收入", "新品交付与供给", "毛利率和客户集中"],
    "AVGO": ["AI 半导体收入", "软件业务利润", "现金流与客户集中"],
    "AMD": ["数据中心收入", "GPU 与 CPU 产品组合", "毛利率和指引"],
    "MU": ["DRAM 与 NAND 定价", "HBM 出货与供给", "毛利率和资本开支"],
    "INTC": ["客户端计算", "数据中心和 AI", "晶圆代工亏损与现金流"],
    "SKHX": ["HBM 产品供给", "DRAM 与 NAND 定价", "营业利润和资本开支"],
    "SMSN": ["存储业务与 HBM", "晶圆代工表现", "利润和资本开支"],
}


def read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def source_link(event: dict) -> str:
    source = event.get("source") or {}
    return source.get("url") or ""


def stage_text(event: dict, quarter: str, stage: str, live: dict | None, packet: dict | None) -> str:
    ticker, company, day = event["ticker"], event["company"], event["date"]
    reported = event["status"] == "reported"
    historical = reported and stage == "preview"
    title = "历史前瞻资料索引" if historical else "财报前观察底稿" if stage == "preview" else "财报后资料索引"
    lines = [f"# {company}（{ticker}）{quarter}｜{title}", "",
             "> 自动整理的资料索引，尚不是经逐季财报核对的完整研究文章。"
             + ("此稿为事后整理，不能视为当时发表的预测。" if historical else ""), "",
             f"- 财报日：{day}" + ("（已发布）" if reported else f"（{event['status']}，非公司确认日期）"),
             f"- 财报期：{event.get('fiscal_period') or '待核'}", ""]
    focus = FOCUS.get(ticker, [])
    packet_sources = (packet or {}).get("sources") or []
    if stage == "preview":
        lines += ["## 已知信息与研究问题", ""]
        if packet and packet.get("historical_reconstruction"):
            lines.append(f"本节只引用上一季 {packet.get('prior_quarter')} 在 {packet.get('prior_release_date')} 已公开的资料；目标季度结果未用于构造前瞻。")
        elif historical:
            lines.append("目前没有可证明在本次财报前已公开的完整资料包；因此不填写当时的数字预期。")
        else:
            lines.append("日期和研究范围来自日历快照；实际预期须在官方公告和有时间戳的市场数据核实后补入。")
        lines += ["", *[f"- 本次需核对：{item}。" for item in focus], ""]
    else:
        lines += ["## 已核实资料与待复核判断", ""]
        if packet and packet.get("verification_status") in {"manual_verified", "official_release_text_collected", "official_filing_text_collected"}:
            facts = packet.get("facts") or []
            if packet["verification_status"] == "manual_verified":
                lines += [f"- {fact}" for fact in facts[:5]]
            elif facts:
                lines.append("已采集公司官方正文；具体业务、利润和现金流数字仍需逐项核对后写成研究判断。")
        else:
            lines.append("尚无逐项核实的公司官方财报资料，因此不推断收入、利润或指引的表现。")
        forecast = event.get("forecast") or {}
        if forecast.get("actual_eps") is not None and forecast.get("consensus_eps") is not None:
            lines += ["", "### Nasdaq EPS 线索（尚待核对财报口径）", "",
                      f"Nasdaq 快照记录实际 EPS {forecast['actual_eps']}、公开一致预期 {forecast['consensus_eps']}"
                      + (f"、差异 {forecast['surprise_pct']}%。" if forecast.get("surprise_pct") is not None else "。"),
                      "此处不推断 GAAP、非 GAAP或拆股调整口径，也不据此单独判断财报质量。"]
        legacy = (live or {}).get("analysis") or {}
        if legacy.get("summary"):
            lines += ["", "### 正式版确定性摘要（Nasdaq / 行情口径）", "", legacy["summary"],
                      "", "该摘要只提供公开 EPS 或价格反应线索，不能代替公司财报正文。"]
        lines += ["", "### 后续核对", "", *[f"- {item}：实际结果、指引与下季变化。" for item in focus], ""]
    eps_url = (f"https://api.nasdaq.com/api/company/{ticker}/earnings-surprise"
               if stage == "analysis" and (event.get("forecast") or {}).get("actual_eps") is not None else "")
    links = list(dict.fromkeys([*packet_sources, source_link(event), eps_url]))
    lines += ["## 来源与状态", ""]
    lines += [f"- [原始资料 {i + 1}]({url})" for i, url in enumerate(links) if url]
    if not links:
        lines.append("- 尚无可引用的原始资料链接。")
    lines += ["", "资料齐备后，由 Paratera 按双重事实检查与读者互检提示词生成完整稿；人工编辑稿不会被覆盖。", ""]
    return "\n".join(lines)


def main() -> None:
    events = read(DATA, {})["calendar"]["formal"]["events"]
    from_date = os.getenv("RESEARCH_FROM_DATE", "2026-01-01")
    through_date = os.getenv("RESEARCH_THROUGH_DATE", "2026-12-31")
    quarters = event_quarters(events)
    legacy = {row["id"]: row for row in read(LIVE, {}).get("events", [])}
    made = 0
    for event in events:
        if event["ticker"] not in FIRST or event["ticker"] == "SPACEX" or not from_date <= event["date"] <= through_date:
            continue
        quarter = quarters.get(event["id"])
        if not quarter:
            continue
        stages = ("preview", "analysis") if event["status"] == "reported" else ("preview",)
        for stage in stages:
            folder = RESEARCH / event["ticker"] / quarter
            path, meta = folder / f"{stage}.md", folder / f"{stage}.meta.json"
            old_meta = read(meta, {})
            if path.exists() and old_meta.get("status") != "baseline_source_limited":
                continue
            packet = read(PACKETS / event["ticker"] / quarter / f"{stage}.json", None)
            body = stage_text(event, quarter, stage, legacy.get(event["id"]), packet)
            if path.exists() and path.read_text(encoding="utf-8") == body:
                continue
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            meta.write_text(json.dumps({"status": "baseline_source_limited", "kind": "deterministic_index",
                                   "source_packet_status": (packet or {}).get("verification_status"),
                                   "historical_reconstruction": bool(packet and packet.get("historical_reconstruction"))},
                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            made += 1
    print(f"deterministic Markdown baselines written: {made}")


if __name__ == "__main__":
    main()
