"""Build cached, source-linked Preview and Analysis for every Mag 7 release.

The baseline research layer is deterministic and makes no LLM calls.  Nasdaq's
historical daily calendar supplies the EPS consensus and actual result; the
cached market snapshot supplies 1-day and 5-day performance versus QQQ.  Once
an event is generated it is retained on later runs, so scheduled refreshes only
need to create records for newly reported events.  The three manually verified
Microsoft deep-dive records remain authoritative overrides.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALENDAR_PATH = ROOT / "frontend" / "data" / "mag7.json"
MARKET_PATH = ROOT / "frontend" / "data" / "market_qqq.json"
MSFT_PATH = ROOT / "frontend" / "data" / "msft_research.json"
OUTPUT = ROOT / "frontend" / "data" / "mag7_research.json"
NASDAQ = "https://api.nasdaq.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Mag7-Earnings-Radar/1.0)", "Accept": "application/json"}

PROFILES = {
    "MSFT": {
        "company": "Microsoft", "ir": "https://www.microsoft.com/en-us/Investor/",
        "focus": ["Azure 增速与 AI 工作负载构成", "Microsoft Cloud 毛利率与资本开支", "Copilot 商业化、RPO 质量与现金转化"],
        "risk": "AI 基础设施投入先于收入和现金回报兑现",
        "monitor": "Azure 增速、Cloud GM、CapEx、FCF margin、Copilot 付费席位与剔除大客户后的 RPO",
    },
    "AAPL": {
        "company": "Apple", "ir": "https://investor.apple.com/",
        "focus": ["iPhone 收入、产品组合与换机周期", "Services 增速和毛利率", "大中华区需求、渠道库存与资本回报"],
        "risk": "硬件周期、区域需求与高利润服务业务的增长错配",
        "monitor": "iPhone/Services 收入、GM 指引、大中华区、活跃设备、回购和经营现金流",
    },
    "GOOGL": {
        "company": "Alphabet", "ir": "https://abc.xyz/investor/",
        "focus": ["Search 广告增长及 AI 对变现的影响", "Google Cloud 增速与营业利润率", "AI CapEx、流量获取成本与监管风险"],
        "risk": "生成式 AI 投入提高成本，同时搜索份额和广告变现承压",
        "monitor": "Search/YouTube 广告、Cloud 收入和利润、TAC、CapEx、AI Overviews 变现指标",
    },
    "AMZN": {
        "company": "Amazon", "ir": "https://ir.aboutamazon.com/",
        "focus": ["AWS 增速、积压订单与 AI 容量", "北美及国际零售利润率", "CapEx、履约效率与自由现金流"],
        "risk": "云和物流资本开支上升快于 AWS 与零售利润兑现",
        "monitor": "AWS 增速/利润率、零售营业利润、广告收入、CapEx、FCF 和下一季收入指引",
    },
    "NVDA": {
        "company": "NVIDIA", "ir": "https://investor.nvidia.com/",
        "focus": ["Data Center 增速和大型客户需求", "Blackwell 等新品供给、交付与产品切换", "毛利率、出口限制与客户集中度"],
        "risk": "极高市场预期、产品切换和客户集中放大任何供给或需求偏差",
        "monitor": "Data Center 收入、GM 指引、库存/预付款、供应周期、网络业务和区域限制",
    },
    "META": {
        "company": "Meta", "ir": "https://investor.atmeta.com/",
        "focus": ["广告展示量、价格和推荐效率", "Family of Apps 用户参与度与利润率", "AI CapEx、Reality Labs 亏损和监管"],
        "risk": "AI 投入和 Reality Labs 支出快于广告效率及新产品收入兑现",
        "monitor": "广告价格/展示量、DAP、FoA margin、CapEx 指引、Reality Labs 亏损和 Reels 变现",
    },
    "TSLA": {
        "company": "Tesla", "ir": "https://ir.tesla.com/",
        "focus": ["汽车收入、交付量和平均售价", "汽车毛利率、降价与成本下降", "储能、FSD/Robotaxi 进展与现金流"],
        "risk": "价格竞争和需求弹性压低汽车利润，同时自动驾驶预期提前计价",
        "monitor": "交付/产量、ASP、汽车 GM ex-credits、库存、FCF、储能部署与 FSD 监管里程碑",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def fetch_day(day: str) -> tuple[str, list[dict], str | None]:
    url = f"{NASDAQ}/calendar/earnings?date={day}"
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return day, (payload.get("data") or {}).get("rows") or [], None
    except Exception as exc:
        return day, [], type(exc).__name__


def fetch_surprises(ticker: str) -> tuple[str, list[dict], str | None]:
    """Fetch Nasdaq's latest company table as the preferred recent EPS source."""
    url = f"{NASDAQ}/company/{ticker}/earnings-surprise"
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = ((payload.get("data") or {}).get("earningsSurpriseTable") or {}).get("rows") or []
        return ticker, rows, None
    except Exception as exc:
        return ticker, [], type(exc).__name__


def parse_number(value):
    if value is None or value == "" or str(value).upper() == "N/A":
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        number = float(text)
        return -number if negative else number
    except ValueError:
        return None


def fmt_money(value):
    return "—" if value is None else f"${value:.2f}"


def market_reaction(ticker: str, event_date: str, market: dict) -> tuple[dict | None, float | None]:
    series = market.get("series", {})
    if ticker not in series or "QQQ" not in series:
        return None, None
    by_symbol = {symbol: item["points"] for symbol, item in ((ticker, series[ticker]), ("QQQ", series["QQQ"]))}
    returns = {}
    for symbol, points in by_symbol.items():
        index = next((i for i, point in enumerate(points) if point["date"] >= event_date), None)
        if index is None or index + 5 >= len(points):
            return None, None
        base = points[index]["close"]
        returns[symbol] = {offset: (points[index + offset]["close"] / base - 1) * 100 for offset in (1, 5)}
    metrics = []
    for offset, label in ((1, "次一交易日"), (5, "5 个交易日")):
        relative = returns[ticker][offset] - returns["QQQ"][offset]
        metrics.append({
            "horizon": label, "ticker": f"{returns[ticker][offset]:+.2f}%",
            "msft": f"{returns[ticker][offset]:+.2f}%", "qqq": f"{returns['QQQ'][offset]:+.2f}%",
            "relative": f"{relative:+.2f} pct", "tone": "positive" if relative > 1 else "negative" if relative < -1 else "neutral",
        })
    return {
        "title": f"财报后 {ticker} vs QQQ",
        "method": "以财报日（或其后首个交易日）收盘为基准，比较随后 1 个及 5 个交易日；不等同于因果归因。",
        "source_ids": [f"market_{ticker.lower()}"], "metrics": metrics,
    }, returns[ticker][1] - returns["QQQ"][1]


def result_tone(surprise: float | None, relative: float | None) -> str:
    eps = "positive" if surprise is not None and surprise > 1 else "negative" if surprise is not None and surprise < -1 else "neutral"
    price = "positive" if relative is not None and relative > 1 else "negative" if relative is not None and relative < -1 else "neutral"
    if eps == price and eps in {"positive", "negative"}:
        return eps
    return "mixed"


def risk_items(ticker: str, source_ids: list[str]) -> list[dict]:
    profile = PROFILES[ticker]
    return [
        {
            "title": "核心经营变量未被单一 EPS 完整覆盖",
            "text": f"EPS 预期差不能替代对收入、分部增速、利润率和管理层指引的判断；{profile['risk']}是该公司的主要质量风险。",
            "transmission": "单项 EPS beat/miss → 市场重新检查收入质量和指引 → 盈利预测与估值可能朝相反方向调整。",
            "monitor": profile["monitor"], "trigger": "EPS 与收入、分部趋势或下一季指引明显背离。",
            "horizon": "当前财报至下一季度", "status": "需要结合公司正式材料复核。",
            "counter_signal": "核心业务、利润率、现金流和下一季指引与 EPS 方向一致。", "source_ids": source_ids,
        },
        {
            "title": "市场预期高于公开一致预期",
            "text": "Nasdaq EPS consensus 是公开卖方样本，不包含全部买方 whisper、期权定价和仓位，因此击败公开共识仍可能对应负面股价反应。",
            "transmission": "隐含门槛高于公开共识 → headline beat 无法推动盈利继续上修 → 拥挤交易解除并压缩估值。",
            "monitor": "财报前盈利修订、期权隐含波动、估值、财报后远期 EPS 修订和相对 QQQ 表现。",
            "trigger": "EPS beat 但次日和 5 日持续跑输 QQQ。", "horizon": "财报后 1–5 个交易日",
            "status": "通过相对价格反应进行交叉验证。", "counter_signal": "盈利预测上修且相对 QQQ 持续走强。", "source_ids": source_ids,
        },
        {
            "title": "历史回放与口径风险",
            "text": "历史 Preview 只能使用发布日期前可获得的共识；不同来源可能混合 GAAP、non-GAAP、拆股调整和后续修订口径。",
            "transmission": "口径错配或后见信息进入 Preview → 夸大可预测性 → 回测结论失真。",
            "monitor": "原始发布日期、EPS 注释、公司 reconciliation、拆股与会计政策变化。",
            "trigger": "Nasdaq 数值与公司正式稿口径无法对齐。", "horizon": "每次历史复核",
            "status": "免费数据链保留这一限制，不自动补写缺失指标。", "counter_signal": "公司原始材料和共识来源能够逐项对账。", "source_ids": source_ids,
        },
    ]


def build_future_record(event: dict) -> dict:
    """Build a source-linked Preview for every future Mag 7 event.

    Estimated dates may carry a live Nasdaq EPS consensus. Projected dates are
    deliberately limited to a cadence range and never inherit a made-up EPS.
    """
    ticker, event_date = event["ticker"], event["date"]
    profile = PROFILES[ticker]
    forecast = event.get("forecast") or {}
    status = event.get("status", "projected")
    source_id = f"calendar_{ticker.lower()}_{event_date.replace('-', '_')}"
    ir_id = f"ir_{ticker.lower()}"
    eps = forecast.get("eps") or "不可得"
    analysts = forecast.get("analyst_count") or "未披露"
    session = forecast.get("session") or "发布时间未提供"
    date_range = event.get("date_range") or {}
    if status == "confirmed":
        confidence = "公司 IR 已正式确认"
        date_note = event_date
    elif status == "estimated":
        confidence = "Nasdaq 市场日历预计，等待公司 IR 确认"
        date_note = event_date
    else:
        confidence = "依据历史披露节奏推算，属于低置信度日期区间"
        date_note = f"{date_range.get('from', event_date)} 至 {date_range.get('to', event_date)}"
        eps = "不可得（推算日期不生成 EPS 预期）"
        analysts = "不适用"
    preview = {
        "title": f"{profile['company']} · {event_date} 财报前 Preview",
        "verdict": f"当前日期状态：{confidence}。研究重点为{profile['focus'][0]}、{profile['focus'][1]}。",
        "summary": f"这是 {profile['company']} 下一次财报的确定性研究清单。日期状态由日历同步流程控制，不由模型判断；当前为“{confidence}”。可获得的 EPS 一致预期为 {eps}，分析师样本为 {analysts}。在正式结果发布前，页面只展示需要核验的业务指标、市场关注点和风险，不提前生成 Analysis，也不把市场预计写成公司确认。",
        "summary_points": [
            {"title": "日期可信度", "text": confidence, "tone": "neutral"},
            {"title": "当前量化锚点", "text": f"EPS {eps}；分析师样本 {analysts}", "tone": "neutral"},
            {"title": "首要验证项", "text": f"{profile['focus'][0]}；{profile['focus'][1]}", "tone": "mixed"},
        ],
        "metrics_title": "财报前已知信息与待验证指标",
        "metrics": [
            {"name": "日期状态", "expectation": confidence, "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
            {"name": "日期 / 区间", "expectation": date_note, "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
            {"name": "EPS consensus", "expectation": str(eps), "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
            {"name": "Analyst sample", "expectation": str(analysts), "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
            {"name": "Fiscal period", "expectation": event.get("fiscal_period") or "未披露", "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
            {"name": "Release session", "expectation": session, "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
        ],
        "observations": [
            {"title": f"核心观察 {index + 1}", "text": text, "source_ids": [ir_id]}
            for index, text in enumerate(profile["focus"])
        ],
        "market_focus": [
            *profile["focus"],
            f"财报发布后核对 {ticker} 相对 QQQ 的 1 日与 5 日表现",
        ],
        "risks": [
            {"title": "日期风险", "text": "预计或推算日期可能调整；只有公司 IR 公告才能升级为正式确认。", "source_ids": [source_id, ir_id]},
            {"title": "预期口径", "text": "公开 EPS consensus 不等于完整市场预期，也不能替代收入、分部指标和管理层指引。", "source_ids": [source_id]},
            {"title": "公司特定风险", "text": profile["risk"], "source_ids": [ir_id]},
        ],
    }
    return {
        "id": event["id"], "ticker": ticker, "company": profile["company"],
        "period": event.get("fiscal_period"), "date": event_date,
        "sample_role": "全量未来 Preview", "status": status,
        "information_cutoff": f"{now_iso()} · 自动日历快照",
        "preview": preview, "analysis": None,
        "generation": {"mode": "deterministic_future_preview", "model": None, "cached": False},
    }


def build_record(event: dict, row: dict | None, market: dict) -> dict:
    ticker, event_date = event["ticker"], event["date"]
    profile = PROFILES[ticker]
    source_id, ir_id = f"nasdaq_{event_date.replace('-', '_')}", f"ir_{ticker.lower()}"
    actual = parse_number((row or {}).get("eps"))
    expected = parse_number((row or {}).get("epsForecast"))
    surprise = parse_number((row or {}).get("surprise"))
    if surprise is None and actual is not None and expected not in (None, 0):
        surprise = (actual / expected - 1) * 100
    delta = actual - expected if actual is not None and expected is not None else None
    eps_tone = "positive" if surprise is not None and surprise > 1 else "negative" if surprise is not None and surprise < -1 else "neutral"
    reaction, relative = market_reaction(ticker, event_date, market)
    tone = result_tone(surprise, relative)
    price_text = "尚无完整行情窗口" if relative is None else f"次日相对 QQQ {relative:+.2f}pct"
    eps_text = "EPS 数据不可得" if surprise is None else f"EPS 较公开一致预期 {surprise:+.2f}%"
    assessment = "超预期" if eps_tone == "positive" else "不及预期" if eps_tone == "negative" else "大致符合/差异有限"
    source_ids = [source_id, ir_id]
    preview = {
        "title": f"{profile['company']} · {event_date} 财报前 Preview",
        "verdict": f"公开 EPS 共识为 {fmt_money(expected)}；真正需要同时验证的是{profile['focus'][0]}、{profile['focus'][1]}。",
        "summary": f"这是一份冻结在财报发布前的确定性历史 Preview。Nasdaq 当日历记录的 EPS 共识为 {fmt_money(expected)}，覆盖 {(row or {}).get('noOfEsts') or '未披露'} 位分析师。公开 EPS 只是基础门槛，不能替代公司分部数据和指引；对 {profile['company']}，市场更关注{profile['focus'][0]}、{profile['focus'][1]}以及{profile['focus'][2]}。本页不会把财报后的实际结果倒灌到 Preview。",
        "summary_points": [
            {"title": "基础门槛", "text": f"EPS consensus {fmt_money(expected)}；分析师数量 {(row or {}).get('noOfEsts') or '未披露'}。", "tone": "neutral"},
            {"title": "核心上行", "text": f"{profile['focus'][0]}与{profile['focus'][1]}同时强于市场门槛。", "tone": "positive"},
            {"title": "核心下行", "text": f"{profile['risk']}，即使 EPS 达标也可能压制估值。", "tone": "negative"},
        ],
        "metrics_title": "财报前公开门槛与研究范围",
        "metrics": [
            {"name": "EPS consensus", "expectation": fmt_money(expected), "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
            {"name": "Analyst sample", "expectation": str((row or {}).get("noOfEsts") or "未披露"), "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
            {"name": "Fiscal quarter", "expectation": (row or {}).get("fiscalQuarterEnding") or event.get("fiscal_period") or "未披露", "actual": None, "delta": None, "assessment": None, "source_ids": [source_id], "tone": "neutral"},
        ],
        "observations": [{"title": f"观察 {i+1}", "text": text, "source_ids": [ir_id]} for i, text in enumerate(profile["focus"])],
        "market_focus": profile["focus"],
        "risks": [
            {"title": "信息边界", "text": "仅使用历史日历中的财报前 EPS 共识，不使用发布后结果倒推当时观点。"},
            {"title": "共识覆盖", "text": "免费公开共识不等于完整买方预期，也不能代表收入和分部指标门槛。"},
            {"title": "口径差异", "text": "需用公司正式财报核对 GAAP/non-GAAP、拆股及一次性项目。"},
        ],
    }
    analysis = {
        "title": f"{profile['company']} · {event_date} 财报后 Analysis",
        "verdict": f"{eps_text}，{price_text}；综合判断为{'偏正面' if tone == 'positive' else '偏负面' if tone == 'negative' else '结果有分歧'}。",
        "summary": f"Nasdaq 历史日历记录实际 EPS {fmt_money(actual)}、公开一致预期 {fmt_money(expected)}，对应预期差 {surprise:+.2f}%" if surprise is not None else "免费历史日历未返回可核验 EPS 预期差，因此不生成数值结论。",
        "summary_points": [
            {"title": "EPS 结果", "text": eps_text, "tone": eps_tone},
            {"title": "市场确认", "text": price_text, "tone": "positive" if relative is not None and relative > 1 else "negative" if relative is not None and relative < -1 else "neutral"},
            {"title": "综合边界", "text": "整体判断由 EPS 与相对价格共同约束；收入、分部和指引仍需查看公司原始材料。", "tone": "mixed"},
        ],
        "metrics_title": "实际结果 vs 财报前公开门槛",
        "result_tone": tone,
        "metrics": [
            {"name": "EPS", "expectation": fmt_money(expected), "actual": fmt_money(actual), "delta": "—" if delta is None else f"{delta:+.2f} / {surprise:+.2f}%", "assessment": assessment, "source_ids": [source_id], "tone": eps_tone},
            {"name": "次日相对 QQQ", "expectation": "0.00 pct（市场基准）", "actual": "—" if reaction is None else reaction["metrics"][0]["ticker"], "delta": "—" if relative is None else f"{relative:+.2f} pct", "assessment": "市场正向确认" if relative is not None and relative > 1 else "市场负向确认" if relative is not None and relative < -1 else "相对表现中性", "source_ids": [f"market_{ticker.lower()}"], "tone": "positive" if relative is not None and relative > 1 else "negative" if relative is not None and relative < -1 else "neutral"},
        ],
        "drivers": [
            {"title": "公开预期差", "text": eps_text, "source_ids": [source_id]},
            {"title": "价格交叉验证", "text": f"{price_text}；价格反应用于识别隐含门槛，不证明单一因果。", "source_ids": [f"market_{ticker.lower()}"]},
            {"title": "业务质量", "text": f"仍需回到公司材料核对{profile['focus'][0]}、{profile['focus'][1]}和{profile['focus'][2]}。", "source_ids": [ir_id]},
        ],
        "guidance_changes": [{"title": "管理层指引", "text": "免费结构化基线未自动抽取本季指引变化；保留 IR 入口供逐项复核，避免模型补写。", "tone": "neutral", "source_ids": [ir_id]}],
        "market_reaction": reaction,
        "risks": risk_items(ticker, source_ids + [f"market_{ticker.lower()}"]),
    }
    return {
        "id": event["id"], "ticker": ticker, "company": profile["company"], "period": (row or {}).get("fiscalQuarterEnding") or event.get("fiscal_period"),
        "date": event_date, "sample_role": "全量历史确定性研究", "status": "reported",
        "information_cutoff": f"{event_date}T00:00:00-05:00（Preview 使用发布前共识快照）",
        "preview": preview, "analysis": analysis,
        "generation": {"mode": "deterministic_cached", "model": None, "cached": True},
    }


def build() -> dict:
    calendar = load(CALENDAR_PATH, {})
    market = load(MARKET_PATH, {})
    msft = load(MSFT_PATH, {"events": [], "sources": {}})
    previous = load(OUTPUT, {"events": [], "sources": {}})
    force = os.getenv("MAG7_RESEARCH_FORCE", "").lower() == "true"
    reported = [event for event in calendar.get("calendar", {}).get("formal", {}).get("events", []) if event.get("status") == "reported" and event.get("ticker") in PROFILES and event.get("date") >= "2024-01-01"]
    future = [event for event in calendar.get("calendar", {}).get("formal", {}).get("events", []) if event.get("status") != "reported" and event.get("ticker") in PROFILES]
    existing = {} if force else {event["id"]: event for event in previous.get("events", []) if event.get("sample_role") == "全量历史确定性研究"}
    deep = {
        event["id"]: {"ticker": "MSFT", "company": "Microsoft", **event}
        for event in msft.get("events", [])
    }
    # A newly released event may not yet have a complete 5-trading-day market
    # window.  Rebuild only those pending records until the reaction exists;
    # mature history remains byte-for-byte cached.
    pending_ids = {
        event_id for event_id, record in existing.items()
        if not (record.get("analysis") or {}).get("market_reaction")
    }
    missing = [
        event for event in reported
        if (event["id"] not in existing or event["id"] in pending_ids) and event["id"] not in deep
    ]
    dates = sorted({event["date"] for event in missing})
    rows_by_date, errors = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for day, rows, error in executor.map(fetch_day, dates):
            rows_by_date[day] = rows
            if error:
                errors.append(f"{day}: {error}")
    recent_by_id = {}
    missing_tickers = sorted({event["ticker"] for event in missing})
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for ticker, rows, error in executor.map(fetch_surprises, missing_tickers):
            if error:
                errors.append(f"{ticker} surprise: {error}")
            for row in rows:
                try:
                    day = datetime.strptime(row["dateReported"], "%m/%d/%Y").date().isoformat()
                except (KeyError, TypeError, ValueError):
                    continue
                recent_by_id[f"{ticker.lower()}-{day}"] = {
                    "symbol": ticker, "eps": row.get("eps"),
                    "epsForecast": row.get("consensusForecast"),
                    "surprise": row.get("percentageSurprise"),
                    "fiscalQuarterEnding": row.get("fiscalQtrEnd"),
                    "noOfEsts": None,
                }
    generated, preserved = [], 0
    for event in sorted(reported, key=lambda item: (item["date"], item["ticker"])):
        if event["id"] in deep:
            generated.append(deep[event["id"]])
            continue
        if event["id"] in existing and event["id"] not in pending_ids:
            generated.append(existing[event["id"]])
            preserved += 1
            continue
        aliases = {"GOOGL": {"GOOGL", "GOOG"}}.get(event["ticker"], {event["ticker"]})
        row = recent_by_id.get(event["id"]) or next((item for item in rows_by_date.get(event["date"], []) if (item.get("symbol") or "").upper() in aliases), None)
        generated.append(build_record(event, row, market))
    # Keep the verified future Microsoft Preview as the exemplar for T-1 behavior.
    for event in deep.values():
        if event["id"] not in {item["id"] for item in generated}:
            generated.append(event)
    generated_ids = {item["id"] for item in generated}
    for event in sorted(future, key=lambda item: (item["date"], item["ticker"])):
        if event["id"] not in generated_ids:
            generated.append(build_future_record(event))
            generated_ids.add(event["id"])
    sources = dict(msft.get("sources", {}))
    for event in reported:
        ticker, day = event["ticker"], event["date"]
        sources.setdefault(f"nasdaq_{day.replace('-', '_')}", {"label": f"Nasdaq earnings calendar · {day}", "url": f"{NASDAQ}/calendar/earnings?date={day}", "type": "consensus_and_actual"})
        sources.setdefault(f"ir_{ticker.lower()}", {"label": f"{PROFILES[ticker]['company']} Investor Relations", "url": PROFILES[ticker]["ir"], "type": "company_ir"})
        sources.setdefault(f"market_{ticker.lower()}", {"label": f"{ticker} / QQQ price history", "url": f"https://finance.yahoo.com/quote/{ticker}/history/", "type": "market_data"})
    for event in future:
        ticker, day = event["ticker"], event["date"]
        sources.setdefault(
            f"calendar_{ticker.lower()}_{day.replace('-', '_')}",
            {"label": event["source"]["label"], "url": event["source"]["url"], "type": "calendar"},
        )
        sources.setdefault(f"ir_{ticker.lower()}", {"label": f"{PROFILES[ticker]['company']} Investor Relations", "url": PROFILES[ticker]["ir"], "type": "company_ir"})
    return {
        "schema_version": 1, "version": "2026-10-04_V13", "generated_at": now_iso(),
        "coverage": {"from": "2024-01-01", "reported_events": len(reported), "future_previews": len(future), "tickers": sorted(PROFILES)},
        "events": sorted(generated, key=lambda item: (item["date"], item["ticker"])), "sources": sources,
        "generation": {"mode": "deterministic_incremental_cache", "llm_calls": 0, "new_records": len(missing), "preserved_records": preserved, "errors": errors},
        "methodology": "EPS actual/consensus from Nasdaq historical daily calendar; 1D/5D relative reaction from cached market series; company-specific lenses from deterministic profiles; verified Microsoft deep dives override baseline.",
        "disclaimer": "Research demo only. EPS and price reaction do not replace review of revenue, segment results, guidance and official filings. Not investment advice.",
    }


if __name__ == "__main__":
    output = build()
    if output["coverage"]["reported_events"] < 77:
        raise RuntimeError("reported Mag 7 coverage unexpectedly below 77 events")
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}: {output['coverage']['reported_events']} reported events, {output['generation']['new_records']} generated, {output['generation']['preserved_records']} preserved, 0 LLM calls")
