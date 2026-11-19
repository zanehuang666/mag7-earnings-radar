"""Cache a small, auditable set of released US macro events.

The public feed aggregates release schedules and actuals from BLS, BEA, the
Federal Reserve and FRED.  It deliberately has no consensus field.  We retain
that limitation in the output instead of relabelling the previous print as a
market forecast.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "data" / "macro_events.json"
API_URL = "https://xoomar.com/api/markets/calendar?from=2024-01-01&to=2030-12-31"
DOCS_URL = "https://xoomar.com/markets/api/calendar"

EVENT_TYPES = {
    "FOMC Rate Decision": {
        "code": "FOMC", "name": "美联储利率决议", "category": "policy",
        "official_url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    },
    "CPI (Consumer Price Index)": {
        "code": "CPI", "name": "美国 CPI", "category": "inflation",
        "official_url": "https://www.bls.gov/cpi/",
    },
    "Nonfarm Payrolls (Employment Situation)": {
        "code": "NFP", "name": "美国非农就业", "category": "labor",
        "official_url": "https://www.bls.gov/ces/",
    },
    "Personal Income and Outlays (PCE)": {
        "code": "PCE", "name": "美国 PCE 通胀", "category": "inflation",
        "official_url": "https://www.bea.gov/data/personal-consumption-expenditures-price-index",
    },
}


def fetch() -> dict:
    request = urllib.request.Request(API_URL, headers={"User-Agent": "Mag7-Earnings-Radar/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def number(value):
    if value in (None, ""):
        return None
    return float(value)


def display(value, unit):
    if value is None:
        return "—"
    if "thousands" in (unit or ""):
        return f"{value:,.0f}K"
    if "%" in (unit or ""):
        return f"{value:g}%"
    return f"{value:g}"


def commentary(category: str, actual: float | None, previous: float | None) -> tuple[str, str]:
    if actual is None:
        return "数据待补充", "原始日程已发布，但实际值尚未进入免密钥数据链路。"
    if previous is None:
        return "缺少可比前值", "当前只能确认本次实际值，暂不做方向判断。"
    delta = actual - previous
    if category == "policy":
        if delta < 0:
            return "政策利率下调", "相较前次会议更宽松，通常有利于久期较长的成长资产估值，但也需判断降息是否反映增长风险。"
        if delta > 0:
            return "政策利率上调", "相较前次会议更紧缩，通常抬升无风险利率并压制高估值成长股的折现价值。"
        return "政策利率维持不变", "利率水平未变，市场影响更多取决于声明措辞、点阵图和主席对后续路径的表述。"
    if category == "inflation":
        if delta > 0:
            return "通胀较前值升温", "通胀黏性上升可能推迟宽松预期、推高长端收益率，并对高估值科技股形成折现率压力。"
        if delta < 0:
            return "通胀较前值降温", "通胀回落通常改善降息预期和实际利率环境，但仍需结合核心分项与服务通胀判断持续性。"
        return "通胀与前值持平", "方向没有进一步改善或恶化，市场更可能交易核心分项、修订值和后续政策表态。"
    if delta > 0:
        return "就业增长较前值增强", "劳动力需求改善支持经济软着陆，但也可能降低短期降息必要性并推高利率预期。"
    if delta < 0:
        return "就业增长较前值放缓", "就业降温有利于通胀再平衡和宽松预期，但若降幅过大也会增加盈利与衰退担忧。"
    return "就业增长与前值持平", "就业动能暂未变化，应结合失业率、工资增速和前期修订判断。"


def build(payload: dict) -> dict:
    now = datetime.now(timezone.utc)
    events = []
    for row in payload.get("data", []):
        config = EVENT_TYPES.get(row.get("eventName"))
        if not config:
            continue
        scheduled = datetime.fromisoformat(row["scheduledAt"].replace("Z", "+00:00"))
        actual, previous = number(row.get("actual")), number(row.get("previous"))
        # Formal mode intentionally shows releases only after an actual value is
        # available.  Future schedules are not imported into the calendar.
        if scheduled > now or actual is None:
            continue
        headline, impact = commentary(config["category"], actual, previous)
        unit = row.get("unit") or ""
        event = {
            "id": f"macro-{config['code'].lower()}-{scheduled.date().isoformat()}",
            "type": "macro", "code": config["code"], "name": config["name"],
            "category": config["category"], "date": scheduled.date().isoformat(),
            "scheduled_at": row["scheduledAt"], "period": row.get("periodLabel"),
            "actual": actual, "actual_display": display(actual, unit),
            "previous": previous, "previous_display": display(previous, unit),
            "forecast": None, "forecast_display": "免费官方链路不提供市场一致预期",
            "comparison_basis": "实际值 vs 前值（不是市场预期差）",
            "unit": unit, "headline": headline, "commentary": impact,
            "source": {"label": "官方数据聚合 / XOOMAR", "url": DOCS_URL},
            "official_source": {"label": row.get("source", "Official source"), "url": config["official_url"]},
        }
        if config["code"] == "FOMC":
            event["target_range"] = f"{actual - 0.125:g}%–{actual + 0.125:g}%"
        events.append(event)
    events.sort(key=lambda item: (item["date"], item["code"]))
    return {
        "schema_version": 1,
        "generated_at": now.replace(microsecond=0).isoformat(),
        "events": events,
        "supported": ["FOMC", "CPI", "NFP", "PCE"],
        "consensus_policy": "unavailable_not_inferred",
        "source": payload.get("source", "xoomar.com"),
        "source_updated_at": payload.get("updatedAt"),
        "attribution": payload.get("attribution"),
        "upstream_attribution": (payload.get("meta") or {}).get("sourceAttribution"),
        "disclaimer": "Released events only. Previous is not consensus. Not investment advice.",
    }


if __name__ == "__main__":
    try:
        data = build(fetch())
        if not data["events"]:
            raise RuntimeError("macro feed returned no supported released events")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUTPUT}: {len(data['events'])} released macro events")
    except Exception as exc:
        if OUTPUT.exists():
            print(f"macro sync failed ({type(exc).__name__}); retained previous snapshot")
        else:
            raise
