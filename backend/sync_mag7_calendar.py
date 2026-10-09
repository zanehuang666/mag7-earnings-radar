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
import statistics
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "data" / "mag7.json"
CANDIDATES_OUTPUT = ROOT / "frontend" / "data" / "us_earnings_candidates.json"
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

# Small, explicitly supported extension set.  These are not promoted to the
# fixed Mag 7 universe; they only make the search useful when Nasdaq has not
# yet published a symbol's next date in its forward calendar.
EXTRA_COMPANIES = {
    "MU": ("Micron Technology", "https://investors.micron.com/", ["DRAM / NAND 定价", "HBM 需求与供给", "毛利率与资本开支"]),
}
ALL_COMPANIES = {**COMPANIES, **EXTRA_COMPANIES}

# A single, deliberately small public verification sample.  It lets the UI
# prove that a scheduled run can move a real event from estimated to reported
# without spending LLM tokens or pretending that a Mag 7 release is imminent.
VERIFICATION_SAMPLE = {
    "ticker": "AEHR",
    "company": "Aehr Test Systems",
    "expected_date": "2026-10-05",
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

# Add an item only after an IR announcement is verified. A confirmed row replaces
# an estimate/projection for the same company and nearby quarter.
CONFIRMED_EVENTS: list[dict] = []


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
    name, _, focus = ALL_COMPANIES[ticker]
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
               source_label: str, surprise: dict | None = None, forecast: dict | None = None,
               date_range: dict | None = None) -> dict:
    name, ir_url, _ = ALL_COMPANIES[ticker]
    preview, analysis = research_blocks(ticker, status, surprise)
    return {
        "id": f"{ticker.lower()}-{event_date}", "ticker": ticker, "company": name,
        "date": event_date, "fiscal_period": period, "status": status,
        "date_confidence": status,
        "source": {"label": source_label, "url": source_url},
        "ir_source": {"label": f"{name} IR", "url": ir_url},
        "forecast": forecast or {}, "date_range": date_range or {},
        "preview": preview, "aftercheck": analysis,
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
        return key, rows, None
    except Exception as exc:
        return key, [], type(exc).__name__


def upcoming(days: int = 120) -> tuple[list[dict], list[str], list[dict]]:
    start = date.today()
    dates = [start + timedelta(days=i) for i in range(days + 1) if (start + timedelta(days=i)).weekday() < 5]
    events, errors, candidates = [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for key, rows, error in executor.map(scan_day, dates):
            if error:
                errors.append(f"{key}: {error}")
            for row in rows:
                ticker = (row.get("symbol") or "").upper().strip()
                if not ticker:
                    continue
                candidates.append({
                    "ticker": ticker, "company": (row.get("name") or ticker).strip(), "date": key,
                    "fiscal_period": row.get("fiscalQuarterEnding") or "Upcoming quarter",
                    "eps": row.get("epsForecast"), "analyst_count": row.get("noOfEsts"),
                    "session": row.get("time"),
                })
                if ticker not in COMPANIES:
                    continue
                forecast = {"eps": row.get("epsForecast"), "analyst_count": row.get("noOfEsts"), "session": row.get("time")}
                events.append(make_event(ticker, key, "estimated", row.get("fiscalQuarterEnding") or "Upcoming quarter",
                                         f"{NASDAQ}/calendar/earnings?date={key}", "Nasdaq earnings calendar",
                                         forecast=forecast))
    return events, errors, candidates


def weekday_near(value: date) -> date:
    if value.weekday() == 5:
        return value - timedelta(days=1)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def add_cadence_projections(by_id: dict[str, dict], periods_per_company: int = 4,
                            tickers=None) -> None:
    today = date.today()
    for ticker in tickers or COMPANIES:
        company_events = sorted((event for event in by_id.values() if event["ticker"] == ticker), key=lambda event: event["date"])
        reported_dates = [date.fromisoformat(event["date"]) for event in company_events if event["status"] == "reported"]
        future_events = [event for event in company_events if event["status"] in {"estimated", "confirmed"} and date.fromisoformat(event["date"]) >= today]
        gaps = [(right - left).days for left, right in zip(reported_dates[-9:-1], reported_dates[-8:])]
        cadence = max(84, min(100, round(statistics.median(gaps or [91]))))
        missing = periods_per_company - len(future_events)
        seasonal_sources = reported_dates[-missing:] if missing else []
        anchor = max((date.fromisoformat(event["date"]) for event in future_events), default=reported_dates[-1])
        for index in range(missing):
            if index < len(seasonal_sources):
                anchor = weekday_near(seasonal_sources[index] + timedelta(days=364))
                method = "same_quarter_plus_52_weeks"
            else:
                anchor = weekday_near(anchor + timedelta(days=cadence))
                method = "median_quarter_gap"
            while anchor < today:
                anchor = weekday_near(anchor + timedelta(days=364))
            event_date = anchor.isoformat()
            low = (anchor - timedelta(days=7)).isoformat()
            high = (anchor + timedelta(days=7)).isoformat()
            event = make_event(
                ticker, event_date, "projected", f"Projected quarter +{len(future_events) + index + 1}",
                "https://github.com/zanehuang666/mag7-earnings-radar#日期同步机制",
                "Historical cadence projection",
                forecast={"method": method, "cadence_days_fallback": cadence},
                date_range={"from": low, "to": high},
            )
            by_id[event["id"]] = event


def build_extra_profiles() -> tuple[dict[str, dict], list[str]]:
    """Build auditable history + projections for a small search fallback set."""
    profiles, errors = {}, []
    for ticker, (company, ir_url, _) in EXTRA_COMPANIES.items():
        by_id: dict[str, dict] = {}
        url = f"{NASDAQ}/company/{ticker}/earnings-surprise"
        try:
            payload = fetch_json(url)
            rows = payload["data"]["earningsSurpriseTable"]["rows"] or []
            for row in rows:
                event_date = normalize_us_date(row["dateReported"])
                event = make_event(ticker, event_date, "reported", row.get("fiscalQtrEnd") or "Reported quarter",
                                   url, "Nasdaq earnings surprise", surprise=row)
                by_id[event["id"]] = event
            if not by_id:
                raise RuntimeError("no reported rows")
            add_cadence_projections(by_id, tickers=[ticker])
            profiles[ticker] = {
                "ticker": ticker, "company": company, "ir_url": ir_url,
                "method": "Nasdaq reported history + deterministic cadence projection",
                "events": sorted(by_id.values(), key=lambda item: item["date"]),
            }
        except Exception as exc:
            errors.append(f"{ticker} profile: {type(exc).__name__}")
    return profiles, errors


def build_verification_sample(candidates: list[dict]) -> tuple[dict, str | None]:
    ticker = VERIFICATION_SAMPLE["ticker"]
    expected_date = VERIFICATION_SAMPLE["expected_date"]
    calendar_row = next(
        (item for item in candidates if item["ticker"] == ticker and item["date"] == expected_date),
        None,
    )
    previous = None
    if CANDIDATES_OUTPUT.exists():
        try:
            previous = json.loads(CANDIDATES_OUTPUT.read_text(encoding="utf-8")).get("verification_sample")
        except (OSError, json.JSONDecodeError):
            pass
    sample = {
        "ticker": ticker,
        "company": (calendar_row or previous or VERIFICATION_SAMPLE).get("company", VERIFICATION_SAMPLE["company"]),
        "date": expected_date,
        "status": "estimated",
        "session": (calendar_row or previous or {}).get("session", "time-not-supplied"),
        "eps_forecast": (calendar_row or previous or {}).get("eps", (previous or {}).get("eps_forecast")),
        "analyst_count": (calendar_row or previous or {}).get("analyst_count"),
        "actual_eps": None,
        "consensus_eps": None,
        "surprise_pct": None,
        "calendar_source": f"{NASDAQ}/calendar/earnings?date={expected_date}",
        "result_source": f"{NASDAQ}/company/{ticker}/earnings-surprise",
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "purpose": "公开验证定时同步是否把真实事件从预计更新为已发布；不调用 LLM。",
    }
    try:
        payload = fetch_json(sample["result_source"])
        rows = payload["data"]["earningsSurpriseTable"]["rows"] or []
        reported = next(
            (row for row in rows if normalize_us_date(row["dateReported"]) == expected_date),
            None,
        )
        if reported:
            actual = reported.get("eps")
            consensus = reported.get("consensusForecast")
            surprise = reported.get("percentageSurprise")
            sample.update({
                "status": "reported",
                "actual_eps": actual,
                "consensus_eps": consensus,
                "surprise_pct": float(surprise) if surprise not in (None, "") else None,
            })
        return sample, None
    except Exception as exc:
        # Keep the prior reported state if the upstream endpoint is temporarily
        # unavailable; a transient source failure must not reverse the demo.
        if previous and previous.get("status") == "reported":
            sample.update({key: previous.get(key) for key in ("status", "actual_eps", "consensus_eps", "surprise_pct")})
        return sample, f"{ticker} verification: {type(exc).__name__}"


def build() -> tuple[dict, dict]:
    by_id: dict[str, dict] = {}
    previous_future: list[dict] = []
    previous_generated_at = None
    previous_ids: set[str] = set()
    previous_statuses: dict[str, str] = {}
    previous_events: dict[str, dict] = {}
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
            previous_generated_at = previous.get("generated_at")
            for event in previous.get("calendar", {}).get("formal", {}).get("events", []):
                previous_ids.add(event.get("id", ""))
                previous_statuses[event.get("id", "")] = event.get("status", "")
                previous_events[event.get("id", "")] = event
                if event.get("status") == "reported":
                    by_id[event["id"]] = event
                elif event.get("status") in {"estimated", "confirmed"} and event.get("date", "") >= date.today().isoformat():
                    previous_future.append(event)
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
    future, future_errors, candidates = upcoming(int(os.getenv("MAG7_FORWARD_DAYS", "120")))
    fresh_future_tickers = {event["ticker"] for event in future}
    for event in previous_future:
        # A complete Nasdaq scan is authoritative: replace yesterday's estimates
        # so a moved date cannot survive beside its replacement.  During a partial
        # source outage, retain only companies for which no fresh row was observed.
        if event["status"] == "confirmed" or (future_errors and event["ticker"] not in fresh_future_tickers):
            by_id[event["id"]] = event
    for event in future:
        by_id[event["id"]] = event

    for item in CONFIRMED_EVENTS:
        event = make_event(item["ticker"], item["date"], "confirmed", item["period"],
                           item["source_url"], "Company IR confirmation")
        for key, candidate in list(by_id.items()):
            if candidate["ticker"] == item["ticker"] and candidate["status"] in {"estimated", "projected"}:
                if abs((date.fromisoformat(candidate["date"]) - date.fromisoformat(item["date"])).days) <= 30:
                    by_id.pop(key)
        by_id[event["id"]] = event

    add_cadence_projections(by_id)
    extra_profiles, profile_errors = build_extra_profiles()
    verification_sample, verification_error = build_verification_sample(candidates)
    if verification_error:
        profile_errors.append(verification_error)

    events = sorted(by_id.values(), key=lambda item: (item["date"], item["ticker"]))
    reported = [event for event in events if event["status"] == "reported" and event["date"] >= "2024-01-01"]
    estimated = [event for event in events if event["status"] == "estimated"]
    confirmed = [event for event in events if event["status"] == "confirmed"]
    projected = [event for event in events if event["status"] == "projected"]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    current_ids = {event["id"] for event in reported + projected + estimated + confirmed}
    current_events = {event["id"]: event for event in reported + projected + estimated + confirmed}
    added_ids = current_ids - previous_ids if previous_generated_at else set()
    removed_ids = previous_ids - current_ids if previous_generated_at else set()
    matched_added: set[str] = set()
    matched_removed: set[str] = set()
    date_changes = []
    for removed_id in sorted(removed_ids):
        before = previous_events.get(removed_id, {})
        migration_candidates = [
            current_events[event_id] for event_id in added_ids
            if event_id not in matched_added
            and current_events[event_id].get("ticker") == before.get("ticker")
            and current_events[event_id].get("fiscal_period") == before.get("fiscal_period")
            and current_events[event_id].get("status") != "reported"
            and before.get("status") != "reported"
        ]
        if not migration_candidates:
            continue
        after = min(migration_candidates, key=lambda event: abs((date.fromisoformat(event["date"]) - date.fromisoformat(before["date"])).days))
        matched_removed.add(removed_id)
        matched_added.add(after["id"])
        date_changes.append({
            "ticker": after["ticker"], "fiscal_period": after.get("fiscal_period"),
            "from_date": before.get("date"), "to_date": after.get("date"),
            "from_status": before.get("status"), "to_status": after.get("status"),
        })
    status_changes = [
        {
            "id": event_id,
            "ticker": current_events[event_id]["ticker"],
            "date": current_events[event_id]["date"],
            "fiscal_period": current_events[event_id].get("fiscal_period"),
            "from": previous_status,
            "to": current_events[event_id]["status"],
        }
        for event_id, previous_status in previous_statuses.items()
        if event_id in current_events and previous_status != current_events[event_id]["status"]
    ]
    field_changes = []
    tracked_fields = (
        ("eps_forecast", "EPS 预期"),
        ("analyst_count", "分析师数量"),
        ("session", "发布时间段"),
    )
    for event_id in sorted(current_ids & previous_ids):
        before, after = previous_events.get(event_id, {}), current_events[event_id]
        for field, label in tracked_fields:
            old_value = (before.get("forecast") or {}).get(field.replace("eps_forecast", "eps"))
            new_value = (after.get("forecast") or {}).get(field.replace("eps_forecast", "eps"))
            if old_value != new_value:
                field_changes.append({
                    "id": event_id, "ticker": after["ticker"], "date": after["date"],
                    "field": field, "label": label, "from": old_value, "to": new_value,
                })
    added_events = [
        {key: current_events[event_id].get(key) for key in ("id", "ticker", "date", "status", "fiscal_period")}
        for event_id in sorted(added_ids - matched_added)
    ]
    removed_events = [
        {key: previous_events[event_id].get(key) for key in ("id", "ticker", "date", "status", "fiscal_period")}
        for event_id in sorted(removed_ids - matched_removed) if event_id in previous_events
    ]
    run_id = os.getenv("GITHUB_RUN_ID", "")
    repository = os.getenv("GITHUB_REPOSITORY", "zanehuang666/mag7-earnings-radar")
    audit = {
        "previous_generated_at": previous_generated_at,
        "current_generated_at": now,
        "event_ids_added": len(added_ids),
        "event_ids_removed": len(removed_ids),
        "content_change_count": len(date_changes) + len(status_changes) + len(field_changes) + len(added_events) + len(removed_events),
        "date_changes": date_changes,
        "status_changes": status_changes,
        "field_changes": field_changes,
        "added_events": added_events,
        "removed_events": removed_events,
        "heartbeat_changed": previous_generated_at != now,
    }
    calendar = {
        "schema_version": 3, "generated_at": now,
        "companies": [{"ticker": ticker, "company": values[0], "ir_url": values[1]} for ticker, values in COMPANIES.items()],
        "calendar": {
            "formal": {
                "label": "正式日历", "as_of": date.today().isoformat(),
                "message": "历史日期来自 Nasdaq 日历并由最近四季接口自动校准；未来日期明确标记为预计，最终以公司 IR 为准。",
                "events": sorted(reported + projected + estimated + confirmed, key=lambda item: (item["date"], item["ticker"])),
            },
            "replay": {
                "label": "历史验证", "as_of": "2026-01-27", "month": "2026-01",
                "message": "模拟系统时间初始冻结在 Microsoft FY26 Q2 财报前一天；运行完整模拟后推进到 2026-01-29，并保留前后两个快照。",
                "events": reported,
            },
        },
        "sync": {
            "reported_count": len(reported), "projected_count": len(projected),
            "estimated_count": len(estimated), "confirmed_count": len(confirmed),
            "source": "Nasdaq public earnings endpoints", "errors": recent_errors + future_errors + profile_errors,
            "forward_days": int(os.getenv("MAG7_FORWARD_DAYS", "120")),
            "automatic": True,
            "schedule_timezone": "Asia/Shanghai",
            "schedule": ["工作日 09:37", "工作日 21:37", "周末 09:37 心跳验证"],
            "run": {
                "trigger": os.getenv("GITHUB_EVENT_NAME", "local"),
                "run_id": run_id or None,
                "url": f"https://github.com/{repository}/actions/runs/{run_id}" if run_id else None,
            },
            "source_check": {
                "checked_at": now,
                "provider": "Nasdaq public earnings endpoints",
                "successful": not bool(recent_errors + future_errors),
                "reported_observed": len(recent),
                "future_observed": len(future),
            },
            "audit": audit,
        },
        "disclaimer": "Calendar research demo only. Estimated dates may change. Not investment advice.",
    }
    candidate_index = {
        "generated_at": now, "forward_days": int(os.getenv("MAG7_FORWARD_DAYS", "120")),
        "source": "Nasdaq public earnings calendar plus supported historical profiles",
        "events": sorted(candidates, key=lambda item: (item["date"], item["ticker"])),
        "profiles": extra_profiles,
        "verification_sample": verification_sample,
    }
    return calendar, candidate_index


if __name__ == "__main__":
    output, candidates = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CANDIDATES_OUTPUT.write_text(json.dumps(candidates, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        f"wrote {OUTPUT}: {output['sync']['reported_count']} reported, "
        f"{output['sync']['projected_count']} projected, {output['sync']['estimated_count']} estimated, "
        f"{output['sync']['confirmed_count']} confirmed, {len(candidates['events'])} US candidates, "
        f"{len(output['sync']['errors'])} errors"
    )
