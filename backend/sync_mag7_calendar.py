"""Build the auditable Mag 7 earnings calendar without an API key or LLM.

Sources:
- Nasdaq daily earnings calendar: historical verification + forward estimates.
- Nasdaq earnings surprise table: latest reported dates and EPS surprise.

The historical seed was individually checked against Nasdaq daily calendar rows.
Future rows remain `estimated`; the job never promotes them to `confirmed` by itself.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "data" / "mag7.json"
NASDAQ = "https://api.nasdaq.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Mag7-Earnings-Radar/1.0; research demo)",
    "Accept": "application/json, text/plain, */*",
}

COMPANIES = {
    "MSFT": ("Microsoft", "https://www.microsoft.com/en-us/Investor/", ["Azure 增速", "AI 资本开支", "云业务利润率"]),
    "AAPL": ("Apple", "https://investor.apple.com/", ["iPhone 产品周期", "服务收入", "大中华区需求"]),
    "GOOGL": ("Alphabet", "https://abc.xyz/investor/", ["搜索广告", "Google Cloud", "AI 投入回报"]),
    "AMZN": ("Amazon", "https://ir.aboutamazon.com/", ["AWS 增速", "零售利润率", "资本开支"]),
    "NVDA": ("NVIDIA", "https://investor.nvidia.com/", ["数据中心需求", "新品供给", "毛利率路径"]),
    "META": ("Meta", "https://investor.atmeta.com/", ["广告效率", "用户参与度", "AI 基础设施投入"]),
    "TSLA": ("Tesla", "https://ir.tesla.com/", ["汽车毛利率", "交付与需求", "储能和自动驾驶"]),
}

# Individually verified against Nasdaq daily earnings-calendar rows on 2026-10-02.
HISTORICAL_SEED = {
    "MSFT": ["2024-01-30", "2024-04-25", "2024-07-30", "2024-10-30", "2025-01-29", "2025-04-30", "2025-07-30"],
    "AAPL": ["2024-02-01", "2024-05-02", "2024-08-01", "2024-10-31", "2025-01-30", "2025-05-01", "2025-07-31"],
    "GOOGL": ["2024-01-30", "2024-04-25", "2024-07-23", "2024-10-29", "2025-02-04", "2025-04-24", "2025-07-23"],
    "AMZN": ["2024-02-01", "2024-04-30", "2024-08-01", "2024-10-31", "2025-02-06", "2025-05-01", "2025-07-31"],
    "NVDA": ["2024-02-21", "2024-05-22", "2024-08-28", "2024-11-20", "2025-02-26", "2025-05-28", "2025-08-27"],
    "META": ["2024-02-01", "2024-04-24", "2024-07-31", "2024-10-30", "2025-01-29", "2025-04-30", "2025-07-30"],
    "TSLA": ["2024-01-24", "2024-04-23", "2024-07-23", "2024-10-23", "2025-01-29", "2025-04-22", "2025-07-23"],
}


def fetch_json(url: str, attempts: int = 3) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"source failed after {attempts} attempts: {type(last_error).__name__}")


def normalize_us_date(value: str) -> str:
    return datetime.strptime(value, "%m/%d/%Y").date().isoformat()


def research_blocks(ticker: str, status: str, surprise: dict | None = None) -> tuple[dict, dict]:
    name, _, focus = COMPANIES[ticker]
    preview = {
        "verdict": f"{name} 财报前检查清单（简版）",
        "summary": "本阶段先验证日期与流程；研究内容将在下一阶段扩充。",
        "points": focus,
        "risks": ["预计日期可能调整，应以公司 IR 最终公告为准", "简版内容不代表完整卖方一致预期"],
    }
    if status != "reported":
        analysis = {
            "verdict": "尚未发布，Analysis 将在财报后生成",
            "summary": "当前仅保留结构化占位，不提前生成事后结论。",
            "points": focus,
            "risks": ["不得把预测写成已发生事实", "等待正式结果和来源验证"],
        }
    elif surprise:
        pct = float(surprise.get("percentageSurprise") or 0)
        direction = "高于" if pct > 0 else "低于" if pct < 0 else "符合"
        analysis = {
            "verdict": f"已发布：EPS {direction} Nasdaq 一致预期 {abs(pct):.2f}%",
            "summary": f"报告 EPS {surprise.get('eps')}，一致预期 {surprise.get('consensusForecast')}。当前仅用于日期层验收。",
            "points": [f"报告 EPS：{surprise.get('eps')}", f"一致预期：{surprise.get('consensusForecast')}", f"惊喜幅度：{pct:.2f}%"],
            "risks": ["EPS 不能替代收入、指引和分部分析", "不同数据源的 GAAP/调整后口径可能不同"],
        }
    else:
        analysis = {
            "verdict": "已发布；详细 Analysis 待下一阶段补充",
            "summary": "日期已经数据源核验，本版本不使用模型补写缺失的历史数字。",
            "points": focus,
            "risks": ["尚未接入该季度完整财报指标", "需在后续研究层补充原始财报来源"],
        }
    return preview, analysis


def make_event(ticker: str, event_date: str, status: str, period: str, source_url: str,
               source_label: str, surprise: dict | None = None, forecast: dict | None = None) -> dict:
    name, ir_url, _ = COMPANIES[ticker]
    preview, analysis = research_blocks(ticker, status, surprise)
    return {
        "id": f"{ticker.lower()}-{event_date}", "ticker": ticker, "company": name,
        "date": event_date, "fiscal_period": period, "status": status,
        "date_confidence": "reported" if status == "reported" else "estimated",
        "source": {"label": source_label, "url": source_url},
        "ir_source": {"label": f"{name} IR", "url": ir_url},
        "forecast": forecast or {}, "preview": preview, "aftercheck": analysis,
    }


def latest_reported() -> tuple[list[dict], list[str]]:
    events, errors = [], []
    for ticker in COMPANIES:
        url = f"{NASDAQ}/company/{ticker}/earnings-surprise"
        try:
            payload = fetch_json(url)
            rows = payload["data"]["earningsSurpriseTable"]["rows"] or []
            for row in rows:
                event_date = normalize_us_date(row["dateReported"])
                events.append(make_event(ticker, event_date, "reported", row.get("fiscalQtrEnd") or "Reported quarter",
                                         url, "Nasdaq earnings surprise", surprise=row))
        except Exception as exc:
            errors.append(f"{ticker} latest: {type(exc).__name__}")
    return events, errors


def scan_day(day: date) -> tuple[str, list[dict], str | None]:
    key = day.isoformat()
    url = f"{NASDAQ}/calendar/earnings?date={key}"
    try:
        payload = fetch_json(url, attempts=2)
        rows = (payload.get("data") or {}).get("rows") or []
        return key, [row for row in rows if row.get("symbol") in COMPANIES], None
    except Exception as exc:
        return key, [], type(exc).__name__


def upcoming(days: int = 120) -> tuple[list[dict], list[str]]:
    start = date.today()
    dates = [start + timedelta(days=i) for i in range(days + 1) if (start + timedelta(days=i)).weekday() < 5]
    events, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for key, rows, error in executor.map(scan_day, dates):
            if error:
                errors.append(f"{key}: {error}")
            for row in rows:
                ticker = row["symbol"]
                forecast = {"eps": row.get("epsForecast"), "analyst_count": row.get("noOfEsts"), "session": row.get("time")}
                events.append(make_event(ticker, key, "estimated", row.get("fiscalQuarterEnding") or "Upcoming quarter",
                                         f"{NASDAQ}/calendar/earnings?date={key}", "Nasdaq earnings calendar",
                                         forecast=forecast))
    return events, errors


def build() -> dict:
    by_id: dict[str, dict] = {}
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
            for event in previous.get("calendar", {}).get("formal", {}).get("events", []):
                if event.get("status") == "reported" or event.get("date", "") >= date.today().isoformat():
                    by_id[event["id"]] = event
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    for ticker, dates in HISTORICAL_SEED.items():
        for event_date in dates:
            event = make_event(ticker, event_date, "reported", "Historical earnings",
                               f"{NASDAQ}/calendar/earnings?date={event_date}", "Nasdaq historical earnings calendar")
            by_id[event["id"]] = event

    recent, recent_errors = latest_reported()
    for event in recent:
        by_id[event["id"]] = event
    future, future_errors = upcoming(int(os.getenv("MAG7_FORWARD_DAYS", "120")))
    for event in future:
        by_id[event["id"]] = event

    events = sorted(by_id.values(), key=lambda item: (item["date"], item["ticker"]))
    reported = [event for event in events if event["status"] == "reported" and event["date"] >= "2024-01-01"]
    estimated = [event for event in events if event["status"] == "estimated"]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": 3, "generated_at": now,
        "companies": [{"ticker": ticker, "company": values[0], "ir_url": values[1]} for ticker, values in COMPANIES.items()],
        "calendar": {
            "formal": {
                "label": "正式日历", "as_of": date.today().isoformat(),
                "message": "历史日期来自 Nasdaq 日历并由最近四季接口自动校准；未来日期明确标记为预计，最终以公司 IR 为准。",
                "events": reported + estimated,
            },
            "replay": {
                "label": "历史验证", "as_of": "2024-10-22", "month": "2024-10",
                "message": "模拟时间停在 2024-10-22；所有历史事件同时保留当时的简版 Preview 与财报后的 Analysis。",
                "events": reported,
            },
        },
        "sync": {
            "reported_count": len(reported), "estimated_count": len(estimated),
            "source": "Nasdaq public earnings endpoints", "errors": recent_errors + future_errors,
            "forward_days": int(os.getenv("MAG7_FORWARD_DAYS", "120")),
        },
        "disclaimer": "Calendar research demo only. Estimated dates may change. Not investment advice.",
    }


if __name__ == "__main__":
    output = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}: {output['sync']['reported_count']} reported, {output['sync']['estimated_count']} estimated, {len(output['sync']['errors'])} errors")
