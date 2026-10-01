"""Refresh Microsoft earnings status and publish frontend JSON.

Stdlib-only by design so GitHub Actions needs no package installation.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "data" / "microsoft.json"
IR_URL = "https://www.microsoft.com/en-us/investor/default"
ARCHIVE_URL = "https://news.microsoft.com/source/tag/investor-relations/"

HISTORY = [
    {"period": "FY26 Q1", "date": "2025-10-29", "status": "reported"},
    {"period": "FY26 Q2", "date": "2026-01-28", "status": "reported"},
    {"period": "FY26 Q3", "date": "2026-04-29", "status": "reported"},
    {"period": "FY26 Q4", "date": "2026-07-29", "status": "reported"},
]

SOURCES = [
    {"label": "Microsoft Investor Relations", "url": IR_URL},
    {"label": "Microsoft IR archive", "url": ARCHIVE_URL},
    {"label": "FY26 Q2 official results", "url": "https://www.microsoft.com/en-us/investor/earnings/fy-2026-q2/press-release-webcast"},
    {"label": "FY26 Q2 earnings call", "url": "https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q2"},
]

FALLBACK = {
    "preview": {
        "title": "Microsoft FY26 Q2 · Preview",
        "verdict": "历史流程演示：重点观察 Azure 增速、AI 资本开支与云业务利润率",
        "summary": "这是历史验证快照，不代表当前完整市场一致预期。正式流程必须严格使用事件发生前已存在的资料。",
        "points": [
            "Azure 增速是判断 AI 需求兑现程度的核心。",
            "AI 基础设施资本开支上升，需要同步观察收入增长和毛利率。",
            "Microsoft 365 Copilot 席位及 ARPU 反映商业化进度。",
        ],
        "risks": [
            "未使用付费一致预期数据库，不能代表完整华尔街共识。",
            "历史回放必须避免使用财报发布后才出现的信息。",
        ],
    },
    "aftercheck": {
        "title": "Microsoft FY26 Q2 · Aftercheck",
        "verdict": "公司称 Revenue、Operating Income 和 EPS 均超过预期，整体偏正面",
        "summary": "收入 813 亿美元，同比增长 17%；Microsoft Cloud 收入 515 亿美元，同比增长 26%；Azure 及其他云服务增长 39%。",
        "points": [
            "Revenue 为 813 亿美元，同比增长 17%。",
            "Operating Income 为 383 亿美元，同比增长 21%。",
            "GAAP diluted EPS 为 5.16 美元，non-GAAP EPS 为 4.14 美元。",
            "Azure 及其他云服务增长 39%，略高于公司预期。",
        ],
        "risks": [
            "AI 基础设施投资继续压低云业务毛利率。",
            "GAAP 与 non-GAAP EPS 口径必须同时标注。",
        ],
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mag7-Earnings-Radar/0.3 educational-research",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def probe_ir() -> dict:
    try:
        html = fetch(IR_URL)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        waiting = bool(re.search(r"next earnings release (?:will be )?announced soon", text, re.I))
        return {
            "date": None,
            "status": "not_announced" if waiting else "review_required",
            "message": "Microsoft IR 尚未公布 FY27 Q1 日期" if waiting else "IR 页面发生变化，等待解析器复核",
            "source": IR_URL,
            "checked_at": now_iso(),
        }
    except Exception as exc:
        return {
            "date": None, "status": "source_error",
            "message": f"IR 检查失败：{type(exc).__name__}",
            "source": IR_URL, "checked_at": now_iso(),
        }


def strip_fence(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())


def parse_json_object(text: str) -> dict:
    """Accept strict JSON, fenced JSON, or a JSON object after brief model prose."""
    cleaned = strip_fence(text)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as original_error:
        decoder = json.JSONDecoder()
        for index, character in enumerate(cleaned):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(cleaned[index:])
                break
            except json.JSONDecodeError:
                continue
        else:
            raise original_error
    if not isinstance(value, dict):
        raise ValueError("model response must contain a JSON object")
    return value


def validate_research(value: dict) -> None:
    required = {"title", "verdict", "summary", "points", "risks"}
    if not required.issubset(value):
        raise ValueError(f"missing fields: {sorted(required - set(value))}")
    if not isinstance(value["points"], list) or not isinstance(value["risks"], list):
        raise ValueError("points and risks must be arrays")


def generate(kind: str) -> dict:
    key = os.getenv("PARATERA_API_KEY", "").strip()
    base = os.getenv("PARATERA_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("PARATERA_MODEL", "").strip()
    if not (key and base and model):
        return {"mode": "verified_snapshot", "model": None, "data": FALLBACK[kind]}

    evidence = {"event": HISTORY[1], "sources": SOURCES,
                "verified_aftercheck_facts": FALLBACK["aftercheck"]["points"]}
    boundary = "只能使用财报发布前可获得的信息" if kind == "preview" else "基于正式财报结果进行事后检查"
    prompt = (
        f"生成 Microsoft FY26 Q2 的 {kind}。{boundary}。事实与判断分开，不得虚构数字。"
        "只返回 JSON，字段严格为 title, verdict, summary, points, risks。资料："
        + json.dumps(evidence, ensure_ascii=False)
    )
    payload = {"model": model, "messages": [
        {"role": "system", "content": "你是谨慎的美股财报研究助手。"},
        {"role": "user", "content": prompt},
    ], "temperature": 0.2, "max_tokens": 1600, "stream": False}
    request = urllib.request.Request(
        f"{base}/v1/chat/completions" if not base.endswith("/v1") else f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
        value = parse_json_object(raw["choices"][0]["message"]["content"])
        validate_research(value)
        return {"mode": "paratera", "model": model, "data": value}
    except Exception as exc:
        return {"mode": "verified_snapshot", "model": model,
                "warning": f"Paratera failed: {type(exc).__name__}", "data": FALLBACK[kind]}


def build() -> dict:
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "company": "Microsoft", "ticker": "MSFT",
        "formal": {"next_event": {"period": "FY27 Q1", **probe_ir()}, "history": HISTORY},
        "demo": {"event": HISTORY[1], "preview": generate("preview"),
                 "aftercheck": generate("aftercheck")},
        "sources": SOURCES,
        "disclaimer": "Research demo only. Not investment advice.",
    }


if __name__ == "__main__":
    output = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
