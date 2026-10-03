"""Build three source-grounded Microsoft research snapshots.

Numbers, deltas and citations are deterministic.  Paratera is optional and is
only allowed to tighten verdict/summary prose; it cannot rewrite the evidence.
"""
from __future__ import annotations

import copy
import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "data" / "msft_research.json"

SOURCES = {
    "q1_call": {"label": "Microsoft FY26 Q1 earnings call（Q2 前瞻指引）", "url": "https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q1", "type": "company_call"},
    "q2_release": {"label": "Microsoft FY26 Q2 official results", "url": "https://www.microsoft.com/en-us/investor/earnings/fy-2026-q2/press-release-webcast", "type": "company_release"},
    "q2_call": {"label": "Microsoft FY26 Q2 earnings call", "url": "https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q2", "type": "company_call"},
    "q2_consensus": {"label": "AP / FactSet FY26 Q2 consensus", "url": "https://apnews.com/article/db920987a30c23ccc6b50e698897902a", "type": "consensus"},
    "q3_call": {"label": "Microsoft FY26 Q3 earnings call（Q4 前瞻指引）", "url": "https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q3", "type": "company_call"},
    "q4_release": {"label": "Microsoft FY26 Q4 official results", "url": "https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast", "type": "company_release"},
    "q4_call": {"label": "Microsoft FY26 Q4 earnings call and FY27 Q1 guidance", "url": "https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4", "type": "company_call"},
    "q4_consensus": {"label": "AP / FactSet FY26 Q4 consensus", "url": "https://apnews.com/article/microsoft-earnings-results-ai-f7dff4fb9d51a2bdec56a13e5da1053d", "type": "consensus"},
    "nasdaq_future": {"label": "Nasdaq earnings calendar（date and EPS forecast）", "url": "https://api.nasdaq.com/api/calendar/earnings?date=2026-11-04", "type": "calendar"},
}


def metric(name, expectation, actual=None, delta=None, assessment=None, sources=None, unit=None):
    return {"name": name, "expectation": expectation, "actual": actual, "delta": delta,
            "assessment": assessment, "source_ids": sources or [], "unit": unit}


EVENTS = [
    {
        "id": "msft-2026-01-28", "period": "FY26 Q2", "date": "2026-01-28",
        "sample_role": "过往已发布样本", "status": "reported", "information_cutoff": "2026-01-27T23:59:59-05:00",
        "preview": {
            "title": "Microsoft FY26 Q2 · 财报前 Preview",
            "verdict": "收入和 EPS 门槛不算激进，真正决定市场反应的是 Azure 能否超过约 37% CC 指引，以及高强度 AI 投资能否维持云毛利率。",
            "summary": "市场一致预期收入约 803.1 亿美元、调整后 EPS 约 3.91 美元；公司给出的收入区间为 795–806 亿美元。应把 Azure、供给约束、Copilot 商业化和资本开支回报放在 headline beat 之前。",
            "metrics": [
                metric("Revenue", "$80.31B consensus / $79.5–80.6B company guide", sources=["q2_consensus", "q1_call"]),
                metric("Adjusted EPS", "$3.91 FactSet consensus", sources=["q2_consensus"]),
                metric("Azure growth", "约 37% constant currency company guide", sources=["q1_call"]),
                metric("Intelligent Cloud revenue", "$32.25–32.55B company guide", sources=["q1_call"]),
                metric("Microsoft Cloud gross margin", "约 66% company guide", sources=["q1_call"]),
                metric("CapEx", "环比增加；FY26 增速预计高于 FY25", sources=["q1_call"]),
            ],
            "observations": [
                {"text": "Azure 的关键不是单纯维持高增长，而是能否通过新增 GPU/CPU 供给和 fleet efficiency 超过约 37% CC 指引。", "source_ids": ["q1_call"]},
                {"text": "需求持续高于可用供给，新增容量还要在 Azure、第一方 Copilot、研发和设备更新之间分配。", "source_ids": ["q1_call"]},
                {"text": "Microsoft 365 Copilot 应观察付费席位、ARPU 和大客户扩张，而不是只看产品发布数量。", "source_ids": ["q1_call"]},
                {"text": "商业 bookings/RPO 可能受 OpenAI 大合同影响而失真，需要同时看剔除大单后的核心续约与消费趋势。", "source_ids": ["q1_call"]},
                {"text": "AI 基础设施折旧和产品使用成本会压低云毛利率；若 Azure 只达标而毛利率跌破约 66%，质量偏弱。", "source_ids": ["q1_call"]},
                {"text": "GAAP EPS 会受 OpenAI 投资会计影响，跨期比较应优先使用剔除该影响后的 non-GAAP EPS。", "source_ids": ["q1_call"]},
            ],
            "risks": ["历史回放严格使用发布前资料，不能用实际结果反推判断。", "FactSet 共识与公司指引口径不同；Azure 指引为 constant currency。"],
        },
        "analysis": {
            "title": "Microsoft FY26 Q2 · 财报后 Analysis",
            "verdict": "收入、调整后 EPS、Azure 和云毛利率均高于基准，经营结果偏超预期；但 375 亿美元 CapEx、自由现金流下滑及 OpenAI 集中度使市场更关注 AI 投资回报，属于“数字 beat、质量仍需验证”。",
            "summary": "收入 812.73 亿美元，较 FactSet 共识高约 9.63 亿美元；调整后 EPS 4.14 美元，高约 0.23 美元。Azure CC 增长 38%，较公司约 37% 指引高 1 个百分点，Microsoft Cloud 毛利率 67% 也高于约 66% 指引。",
            "metrics": [
                metric("Revenue", "$80.31B", "$81.273B", "+$0.963B / +1.2%", "超预期", ["q2_consensus", "q2_release"]),
                metric("Adjusted EPS", "$3.91", "$4.14", "+$0.23 / +5.9%", "超预期", ["q2_consensus", "q2_release"]),
                metric("Azure growth (CC)", "约 37%", "38%", "+1 pct", "略超指引", ["q1_call", "q2_release", "q2_call"]),
                metric("Intelligent Cloud revenue", "$32.25–32.55B", "$32.907B", "+$0.357B vs high end", "超指引", ["q1_call", "q2_release"]),
                metric("Microsoft Cloud gross margin", "约 66%", "67%", "+1 pct", "好于指引", ["q1_call", "q2_call"]),
                metric("CapEx", "环比增加", "$37.5B", "约 +7.4% QoQ", "投入强度高", ["q1_call", "q2_call"]),
            ],
            "drivers": [
                {"text": "Azure 因 fleet efficiency 和容量重新分配而略超公司预期，说明供给约束缓解可以直接转化为收入。", "source_ids": ["q2_call"]},
                {"text": "Microsoft Cloud 收入 515 亿美元、同比增长 26%，Cloud GM 67% 好于指引，暂时缓冲 AI 基建摊薄。", "source_ids": ["q2_release", "q2_call"]},
                {"text": "CapEx 375 亿美元、自由现金流仅 59 亿美元；投资兑现速度仍是结果中最主要的负面争议。", "source_ids": ["q2_call"]},
                {"text": "商业 RPO 达 6250 亿美元，但约 45% 来自 OpenAI，headline backlog 的客户集中度较高。", "source_ids": ["q2_call"]},
                {"text": "M365 Copilot 付费席位达到 1500 万，较单纯使用量更接近可验证的商业化证据。", "source_ids": ["q2_call"]},
            ],
            "risks": ["GAAP EPS 5.16 美元包含 OpenAI 投资会计收益，不应与 3.91 美元调整后共识直接比较。", "Azure reported growth 39% 与 constant-currency 38% 不可混用。"],
        },
    },
    {
        "id": "msft-2026-07-29", "period": "FY26 Q4", "date": "2026-07-29",
        "sample_role": "最近已发布样本", "status": "reported", "information_cutoff": "2026-07-28T23:59:59-04:00",
        "preview": {
            "title": "Microsoft FY26 Q4 · 财报前 Preview",
            "verdict": "市场门槛集中在 Azure 39–40% CC、约 876 亿美元收入和超过 400 亿美元 CapEx：只有增长加速同时维持云毛利率，才能证明 AI 投入正在转化为经营杠杆。",
            "summary": "FactSet 共识收入约 876.2 亿美元、EPS 约 4.24 美元；公司收入指引 867–878 亿美元。重点应从单季 beat 扩展到 Azure 容量兑现、Copilot 使用计费、FY27 指引和自由现金流。",
            "metrics": [
                metric("Revenue", "$87.62B consensus / $86.7–87.8B company guide", sources=["q4_consensus", "q3_call"]),
                metric("Adjusted EPS", "$4.24 FactSet consensus", sources=["q4_consensus"]),
                metric("Azure growth", "39–40% constant currency company guide", sources=["q3_call"]),
                metric("Intelligent Cloud revenue", "$37.95–38.25B company guide", sources=["q3_call"]),
                metric("Microsoft Cloud gross margin", "约 64% company guide", sources=["q3_call"]),
                metric("CapEx", "> $40B；CY26 约 $190B", sources=["q3_call"]),
            ],
            "observations": [
                {"text": "Azure 需要明显超过 39–40% CC 指引，才能证明新容量交付和 fleet efficiency 正在加速收入。", "source_ids": ["q3_call"]},
                {"text": "GitHub Copilot 转向更贴近使用量和价值的计费，需观察消费增长能否覆盖更高推理成本。", "source_ids": ["q3_call"]},
                {"text": "Microsoft Cloud GM 约 64% 是 AI 投入效率的硬约束；增长 beat 若伴随更差毛利率，质量有限。", "source_ids": ["q3_call"]},
                {"text": "CapEx 超过 400 亿美元、CY26 约 1900 亿美元的路径要求 Azure、Copilot 与现金流共同验证回报。", "source_ids": ["q3_call"]},
                {"text": "M365 Copilot 应看净新增付费席位和 ARPU，Azure 应区分 AI 与核心基础设施贡献。", "source_ids": ["q3_call"]},
                {"text": "FY27 的收入、营业利润、CapEx 与利润率指引，重要性可能高于 FY26 Q4 的 headline beat。", "source_ids": ["q3_call"]},
            ],
            "risks": ["FactSet EPS 共识按调整后口径，需排除 OpenAI 投资与一次性项目。", "公司指引区间与卖方共识不是同一基准，应分别比较。"],
        },
        "analysis": {
            "title": "Microsoft FY26 Q4 · 财报后 Analysis",
            "verdict": "全面超预期：收入、调整后 EPS、Azure、Intelligent Cloud 和云毛利率均越过关键门槛；Azure 容量更快上线使 AI 投资回报的可信度提高，但 410 亿美元 CapEx 与一次性收益仍需剔除。",
            "summary": "收入 900.07 亿美元，较 FactSet 共识高约 23.87 亿美元；调整后 EPS 4.74 美元，高 0.50 美元。Azure 增长 43%，较 39–40% 指引高约 3–4 个百分点，Cloud GM 65% 也高于约 64% 指引。",
            "metrics": [
                metric("Revenue", "$87.62B", "$90.007B", "+$2.387B / +2.7%", "超预期", ["q4_consensus", "q4_release"]),
                metric("Adjusted EPS", "$4.24", "$4.74", "+$0.50 / +11.8%", "超预期", ["q4_consensus", "q4_release"]),
                metric("Azure growth", "39–40% CC", "43% reported", "+3–4 pct（口径近似）", "明显超指引", ["q3_call", "q4_release", "q4_call"]),
                metric("Intelligent Cloud revenue", "$37.95–38.25B", "$39.3B", "+$1.05B vs high end", "超指引", ["q3_call", "q4_call"]),
                metric("Microsoft Cloud gross margin", "约 64%", "65%", "+1 pct", "好于指引", ["q3_call", "q4_call"]),
                metric("CapEx", "> $40B", "$41.0B", "符合高投入路径", "投入继续上升", ["q3_call", "q4_call"]),
            ],
            "drivers": [
                {"text": "Azure 43% 增长由 CPU/GPU fleet efficiency、流程改进和更早交付容量推动，新增供给迅速被需求吸收。", "source_ids": ["q4_call"]},
                {"text": "Microsoft Cloud 收入 593 亿美元、同比增长 27%；Azure 年收入首次超过 1000 亿美元。", "source_ids": ["q4_release", "q4_call"]},
                {"text": "M365 Copilot 付费席位超过 3000 万，净新增环比翻倍，商业化证据较 FY26 Q2 明显增强。", "source_ids": ["q4_call"]},
                {"text": "CapEx 410 亿美元、自由现金流 196 亿美元；现金流仍被 AI 基建显著压低。", "source_ids": ["q4_call"]},
                {"text": "EPS 包含 Anthropic 投资收益和其他离散项目带来的约 0.27 美元好处，核心经营 beat 仍在，但幅度低于 headline。", "source_ids": ["q4_release", "q4_call"]},
                {"text": "FY27 Q1 Azure 指引约 45% CC、总收入 898.5–909.5 亿美元，意味着管理层认为加速趋势可延续。", "source_ids": ["q4_call"]},
            ],
            "risks": ["Azure 实际值为 reported growth，而前瞻为 constant currency，3–4pct 差值为近似比较。", "一次性投资收益、会计寿命调整和租赁分类会影响 EPS、折旧与 CapEx 可比性。"],
        },
    },
    {
        "id": "msft-2026-11-04", "period": "FY27 Q1", "date": "2026-11-04",
        "sample_role": "未来预计样本", "status": "estimated", "information_cutoff": "2026-10-03T23:59:59+08:00",
        "preview": {
            "title": "Microsoft FY27 Q1 · 财报前 Preview",
            "verdict": "公司给出的收入和 Azure 指引已经很强，核心问题不是能否保持双位数增长，而是约 45% Azure CC 增长和超过 500 亿美元 CapEx 能否同时保持云毛利率及现金流纪律。",
            "summary": "Nasdaq 当前预计日期为 2026-11-04、14 位分析师 EPS 预期约 4.70 美元；Microsoft IR 尚未确认日期。公司收入指引 898.5–909.5 亿美元，Azure 约 45% CC，CapEx 超过 500 亿美元。",
            "metrics": [
                metric("Expected date", "2026-11-04 Nasdaq estimated；IR 未确认", sources=["nasdaq_future"]),
                metric("EPS consensus", "$4.70 / 14 analysts (Nasdaq snapshot)", sources=["nasdaq_future"]),
                metric("Revenue", "$89.85–90.95B company guide", sources=["q4_call"]),
                metric("Azure growth", "约 45% constant currency company guide", sources=["q4_call"]),
                metric("Intelligent Cloud revenue", "$40.95–41.25B company guide", sources=["q4_call"]),
                metric("Productivity & Business Processes", "$36.7–37.0B company guide", sources=["q4_call"]),
                metric("More Personal Computing", "$12.2–12.7B company guide", sources=["q4_call"]),
                metric("Microsoft Cloud gross margin", "环比大致稳定（FY26 Q4 为 65%）", sources=["q4_call"]),
                metric("CapEx", "> $50B company guide", sources=["q4_call"]),
            ],
            "observations": [
                {"text": "Azure 约 45% CC 是第一优先级；需要区分新增物理容量、fleet efficiency、合同结构和 AI 消费各自贡献。", "source_ids": ["q4_call"]},
                {"text": "收入区间中点约 904 亿美元；若 Azure 达标但总收入靠低毛利业务支撑，结果质量有限。", "source_ids": ["q4_call"]},
                {"text": "Cloud GM 指引环比稳定，意味着效率改善需要抵消 AI 基础设施折旧和推理使用成本。", "source_ids": ["q4_call"]},
                {"text": "超过 500 亿美元 CapEx 是新的投资台阶；应同时核对现金 PP&E、finance lease 与 accounting reclassification。", "source_ids": ["q4_call"]},
                {"text": "M365 Copilot 应继续跟踪付费席位、ARPU、使用量计费和 E5/E7 premium mix。", "source_ids": ["q4_call"]},
                {"text": "OpenAI 大合同会制造 bookings/RPO 波动，应优先看剔除 frontier model customers 后的核心增长。", "source_ids": ["q4_call"]},
                {"text": "Windows OEM 面临组件涨价、库存和高基数；消费业务可能部分抵消商业云加速。", "source_ids": ["q4_call"]},
                {"text": "FY27 营业利润率指引为全年下降不到 1 个百分点，若 Q1 已明显承压，后续容错空间会缩小。", "source_ids": ["q4_call"]},
            ],
            "risks": ["财报日期仅为 Nasdaq estimated，必须等待 Microsoft IR 确认。", "EPS 共识可能继续变化；页面应保留抓取时间和分析师数量。", "公司延长数据中心寿命并调整租赁分类，CapEx 与折旧的同比可比性下降。"],
        },
        "analysis": None,
    },
]


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_json_object(text: str) -> dict:
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as original:
        decoder = json.JSONDecoder()
        for index, char in enumerate(cleaned):
            if char == "{":
                try:
                    value, _ = decoder.raw_decode(cleaned[index:])
                    break
                except json.JSONDecodeError:
                    pass
        else:
            raise original
    if not isinstance(value, dict):
        raise ValueError("model output is not an object")
    return value


def call_paratera(event: dict) -> dict:
    key = os.environ["PARATERA_API_KEY"].strip()
    base = os.environ["PARATERA_BASE_URL"].strip().rstrip("/")
    model = os.environ.get("PARATERA_MODEL", "DeepSeek-V4-Flash").strip()
    drafts = {
        "preview_verdict": event["preview"]["verdict"],
        "preview_summary": event["preview"]["summary"],
        "analysis_verdict": event["analysis"]["verdict"] if event["analysis"] else None,
        "analysis_summary": event["analysis"]["summary"] if event["analysis"] else None,
    }
    brief = {
        "event": {k: event[k] for k in ("period", "date", "status", "information_cutoff")},
        "drafts": drafts,
    }
    prompt = (
        "不要展示推理过程，直接返回 JSON。只压缩和润色下列已核验草稿，不得增加或修改任何数字或事实，"
        "不得把预计写成事实。只返回 JSON：preview_verdict, preview_summary, analysis_verdict, analysis_summary；"
        "未来未发布事件的 analysis 两字段必须为 null。每个 verdict 不超过90字，summary 不超过180字。证据："
        + json.dumps(brief, ensure_ascii=False, separators=(",", ":"))
    )
    payload = {"model": model, "messages": [
        {"role": "system", "content": "你是谨慎的美股财报研究编辑。事实、口径和时间边界优先。"},
        {"role": "user", "content": prompt},
    ], "temperature": 0.1, "max_tokens": 1800, "stream": False,
        "response_format": {"type": "json_object"},
        # Paratera's official API documents this top-level switch.  Disabling
        # reasoning prevents a short editing task from spending the output
        # budget on reasoning_content and returning an empty answer string.
        "enable_thinking": False}
    endpoint = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = json.loads(response.read().decode())
    message = raw["choices"][0]["message"]
    content = message.get("content")
    # Some Paratera-hosted reasoning models return the only textual payload in
    # reasoning_content even when enable_thinking=false.  We still pass it
    # through the exact same strict JSON/field validation before accepting it.
    if not isinstance(content, str) or not content.strip():
        content = message.get("reasoning_content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Paratera returned empty content and reasoning_content")
    return parse_json_object(content)


def apply_narrative(event: dict, value: dict) -> None:
    original_text = " ".join(filter(None, (
        event["preview"]["verdict"], event["preview"]["summary"],
        event["analysis"]["verdict"] if event["analysis"] else None,
        event["analysis"]["summary"] if event["analysis"] else None,
    )))
    allowed_numbers = set(re.findall(r"\d+(?:\.\d+)?", original_text))
    candidate_text = " ".join(str(value.get(key) or "") for key in (
        "preview_verdict", "preview_summary", "analysis_verdict", "analysis_summary"
    ))
    new_numbers = set(re.findall(r"\d+(?:\.\d+)?", candidate_text)) - allowed_numbers
    if new_numbers:
        raise ValueError(f"model introduced numbers not in draft: {sorted(new_numbers)}")
    for key in ("preview_verdict", "preview_summary"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValueError(f"invalid {key}")
    event["preview"]["verdict"] = value["preview_verdict"].strip()
    event["preview"]["summary"] = value["preview_summary"].strip()
    if event["analysis"]:
        for key in ("analysis_verdict", "analysis_summary"):
            if not isinstance(value.get(key), str) or not value[key].strip():
                raise ValueError(f"invalid {key}")
        event["analysis"]["verdict"] = value["analysis_verdict"].strip()
        event["analysis"]["summary"] = value["analysis_summary"].strip()


def due_tomorrow() -> bool:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    return any(event["status"] != "reported" and event["date"] == tomorrow for event in EVENTS)


def previous_paratera_events() -> dict:
    if not OUTPUT.exists():
        return {}
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        return {
            event["id"]: event for event in data.get("events", [])
            if event.get("generation", {}).get("mode") == "paratera"
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def restore_previous_narrative(event: dict, previous: dict) -> bool:
    prior = previous.get(event["id"])
    if not prior:
        return False
    value = {
        "preview_verdict": prior["preview"]["verdict"],
        "preview_summary": prior["preview"]["summary"],
        "analysis_verdict": prior["analysis"]["verdict"] if prior.get("analysis") else None,
        "analysis_summary": prior["analysis"]["summary"] if prior.get("analysis") else None,
    }
    apply_narrative(event, value)
    event["generation"] = {"mode": "paratera", "model": prior["generation"].get("model"), "cached": True}
    return True


def build(force: bool = False) -> dict:
    events = copy.deepcopy(EVENTS)
    previous = previous_paratera_events()
    configured = all(os.getenv(name, "").strip() for name in ("PARATERA_API_KEY", "PARATERA_BASE_URL", "PARATERA_MODEL"))
    should_call = configured and (force or due_tomorrow())
    selected_id = os.getenv("MSFT_RESEARCH_EVENT_ID", "").strip()
    try:
        call_limit = max(0, min(3, int(os.getenv("MSFT_RESEARCH_CALL_LIMIT", "3"))))
    except ValueError:
        call_limit = 3
    errors, calls = [], 0
    if should_call:
        attempted = 0
        for event in events:
            restored = restore_previous_narrative(event, previous)
            if selected_id and event["id"] != selected_id:
                if not restored:
                    event["generation"] = {"mode": "verified_snapshot", "warning": "not_selected"}
                continue
            if attempted >= call_limit:
                if not restored:
                    event["generation"] = {"mode": "verified_snapshot", "warning": "call_limit"}
                continue
            attempted += 1
            try:
                apply_narrative(event, call_paratera(event))
                event["generation"] = {"mode": "paratera", "model": os.environ["PARATERA_MODEL"], "cached": False}
                calls += 1
            except Exception as exc:
                if restored:
                    event["generation"]["warning"] = type(exc).__name__
                else:
                    event["generation"] = {"mode": "verified_snapshot", "warning": type(exc).__name__}
                detail = " ".join(str(exc).split())[:160]
                errors.append(f"{event['period']}: {type(exc).__name__}: {detail}")
    else:
        for event in events:
            event["generation"] = {"mode": "verified_snapshot", "model": None}
    return {"schema_version": 2, "generated_at": now_iso(), "ticker": "MSFT", "company": "Microsoft",
            "strategy": "deterministic evidence + optional low-token LLM narrative", "events": events,
            "sources": SOURCES, "generation": {"paratera_calls": calls, "call_limit": call_limit,
            "selected_event_id": selected_id or None, "errors": errors},
            "disclaimer": "Research demo only. Estimated dates and consensus may change. Not investment advice."}


if __name__ == "__main__":
    force = os.getenv("MSFT_RESEARCH_FORCE", "").lower() in {"1", "true", "yes"}
    if OUTPUT.exists() and not force and not due_tomorrow():
        print("Microsoft research unchanged: no force and no T-1 event")
    else:
        data = build(force=force)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUTPUT}: {len(data['events'])} events, {data['generation']['paratera_calls']} Paratera calls")
