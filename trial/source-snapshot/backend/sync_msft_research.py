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
    "sec_filings": {"label": "Microsoft SEC filings", "url": "https://www.microsoft.com/en-us/Investor/sec-filings.aspx", "type": "filing_index"},
    "market_yahoo": {"label": "Yahoo Finance price history", "url": "https://finance.yahoo.com/quote/MSFT/history/", "type": "market_data"},
}


def metric(name, expectation, actual=None, delta=None, assessment=None, sources=None, unit=None, tone="neutral"):
    return {"name": name, "expectation": expectation, "actual": actual, "delta": delta,
            "assessment": assessment, "source_ids": sources or [], "unit": unit, "tone": tone}


EVENTS = [
    {
        "id": "msft-2026-01-28", "period": "FY26 Q2", "date": "2026-01-28",
        "sample_role": "过往已发布样本", "status": "reported", "information_cutoff": "2026-01-27T23:59:59-05:00",
        "preview": {
            "title": "Microsoft FY26 Q2 · 财报前 Preview",
            "verdict": "收入和 EPS 门槛不算激进，真正决定市场反应的是 Azure 能否超过约 37% CC 指引，以及高强度 AI 投资能否维持云毛利率。",
            "summary": "市场一致预期收入约 803.1 亿美元、调整后 EPS 约 3.91 美元，公司收入指引为 795–806 亿美元。Headline 门槛并不极端，但市场真正定价的是 Azure 能否超过约 37% CC、AI 供给能否转化为收入，以及高资本开支下云毛利率与现金流是否守得住。Copilot 付费席位和 OpenAI 大合同对 RPO 的影响，则决定增长质量是否足够分散、可持续。",
            "summary_points": [
                {"title": "基础门槛", "text": "收入与 EPS 共识处于公司指引可覆盖范围，单纯小幅 beat 的信息量有限。", "tone": "neutral"},
                {"title": "核心上行", "text": "Azure 超过约 37% CC 且 Cloud GM 不低于约 66%，说明新增容量开始形成经营杠杆。", "tone": "positive"},
                {"title": "核心下行", "text": "Azure 仅达标、CapEx 继续上升而毛利率走弱，会强化市场对 AI 投资回报周期的担忧。", "tone": "negative"},
            ],
            "metrics_title": "关键指标与财报前门槛",
            "metrics": [
                metric("Revenue", "$80.31B consensus / $79.5–80.6B company guide", sources=["q2_consensus", "q1_call"]),
                metric("Adjusted EPS", "$3.91 FactSet consensus", sources=["q2_consensus"]),
                metric("Azure growth", "约 37% constant currency company guide", sources=["q1_call"]),
                metric("Intelligent Cloud revenue", "$32.25–32.55B company guide", sources=["q1_call"]),
                metric("Microsoft Cloud gross margin", "约 66% company guide", sources=["q1_call"]),
                metric("CapEx", "环比增加；FY26 增速预计高于 FY25", sources=["q1_call"]),
            ],
            "observations": [
                {"title": "Azure 兑现", "text": "关键不是单纯维持高增长，而是能否通过新增 GPU/CPU 供给和 fleet efficiency 超过约 37% CC 指引。", "source_ids": ["q1_call"]},
                {"title": "供给分配", "text": "需求持续高于可用供给，新增容量还要在 Azure、第一方 Copilot、研发和设备更新之间分配。", "source_ids": ["q1_call"]},
                {"title": "Copilot 商业化", "text": "应观察付费席位、ARPU 和大客户扩张，而不是只看产品发布数量。", "source_ids": ["q1_call"]},
                {"title": "RPO 质量", "text": "商业 bookings/RPO 可能受 OpenAI 大合同影响而失真，需要同时看剔除大单后的核心续约与消费趋势。", "source_ids": ["q1_call"]},
                {"title": "利润率约束", "text": "AI 基础设施折旧和产品使用成本会压低云毛利率；若 Azure 只达标而毛利率跌破约 66%，质量偏弱。", "source_ids": ["q1_call"]},
                {"title": "口径处理", "text": "GAAP EPS 会受 OpenAI 投资会计影响，跨期比较应优先使用剔除该影响后的 non-GAAP EPS。", "source_ids": ["q1_call"]},
            ],
            "market_focus": ["Azure 是否显著超过约 37% CC，而不只是达标", "CapEx 增长与自由现金流之间的剪刀差", "Copilot 付费席位与 RPO 中 OpenAI 集中度"],
            "risks": [
                {"title": "后见之明偏差", "text": "历史 Preview 只能使用 2026-01-27 前可获得的信息，不能用实际结果倒推当时应有判断。"},
                {"title": "口径错配", "text": "FactSet 共识、公司区间、reported growth 与 constant-currency growth 不是同一口径。"},
                {"title": "单一指标误判", "text": "Azure beat 若由提前确认或合同结构推动、同时毛利率和现金流恶化，不应直接判断为高质量超预期。"},
            ],
        },
        "analysis": {
            "title": "Microsoft FY26 Q2 · 财报后 Analysis",
            "verdict": "收入、调整后 EPS、Azure 和云毛利率均高于基准，经营结果偏超预期；但 375 亿美元 CapEx、自由现金流下滑及 OpenAI 集中度使市场更关注 AI 投资回报，属于“数字 beat、质量仍需验证”。",
            "summary": "收入 812.73 亿美元、调整后 EPS 4.14 美元，分别较 FactSet 共识高约 9.63 亿美元和 0.23 美元；Azure CC 增长 38%，较约 37% 指引高 1 个百分点，Cloud GM 67% 也好于约 66% 指引。经营数据本身偏超预期，但 375 亿美元 CapEx、自由现金流降至 59 亿美元、RPO 对 OpenAI 的高集中度，让市场把注意力从本季 beat 转向 AI 投资回报和下一季增长质量。",
            "summary_points": [
                {"title": "经营结果", "text": "收入、调整后 EPS、Azure 与云毛利率均越过基准，基本面判断偏正面。", "tone": "positive"},
                {"title": "质量争议", "text": "高 CapEx、低自由现金流和 RPO 集中度削弱了 headline beat 的含金量。", "tone": "negative"},
                {"title": "市场定价", "text": "次一交易日 MSFT 相对 QQQ 落后 9.39pct，显示市场更在意投入回报而非当季数字。", "tone": "negative"},
            ],
            "metrics_title": "实际结果 vs 财报前预期",
            "result_tone": "positive",
            "metrics": [
                metric("Revenue", "$80.31B", "$81.273B", "+$0.963B / +1.2%", "超预期", ["q2_consensus", "q2_release"], tone="positive"),
                metric("Adjusted EPS", "$3.91", "$4.14", "+$0.23 / +5.9%", "超预期", ["q2_consensus", "q2_release"], tone="positive"),
                metric("Azure growth (CC)", "约 37%", "38%", "+1 pct", "略超指引", ["q1_call", "q2_release", "q2_call"], tone="positive"),
                metric("Intelligent Cloud revenue", "$32.25–32.55B", "$32.907B", "+$0.357B vs high end", "超指引", ["q1_call", "q2_release"], tone="positive"),
                metric("Microsoft Cloud gross margin", "约 66%", "67%", "+1 pct", "好于指引", ["q1_call", "q2_call"], tone="positive"),
                metric("CapEx", "环比增加", "$37.5B", "约 +7.4% QoQ", "投入强度高", ["q1_call", "q2_call"], tone="negative"),
            ],
            "drivers": [
                {"title": "Azure", "text": "fleet efficiency 和容量重新分配推动 Azure 略超公司预期，说明供给缓解可以直接转化为收入。", "source_ids": ["q2_call"]},
                {"title": "云利润率", "text": "Microsoft Cloud 收入 515 亿美元、同比增长 26%，Cloud GM 67% 好于指引，暂时缓冲 AI 基建摊薄。", "source_ids": ["q2_release", "q2_call"]},
                {"title": "现金流", "text": "CapEx 375 亿美元、自由现金流仅 59 亿美元；投资兑现速度仍是最大负面争议。", "source_ids": ["q2_call"]},
                {"title": "集中度", "text": "商业 RPO 达 6250 亿美元，但约 45% 来自 OpenAI，headline backlog 的客户集中度较高。", "source_ids": ["q2_call"]},
                {"title": "Copilot", "text": "M365 Copilot 付费席位达到 1500 万，较单纯使用量更接近可验证的商业化证据。", "source_ids": ["q2_call"]},
            ],
            "guidance_changes": [
                {"title": "总收入", "text": "FY26 Q3 指引 806.5–817.5 亿美元，区间中点约 812 亿美元；增长预计 15%–17%。", "tone": "neutral", "source_ids": ["q2_call"]},
                {"title": "Azure", "text": "下一季指引 37%–38% CC，较本季实际 38% 大致持平，未给出明显再加速信号。", "tone": "neutral", "source_ids": ["q2_call"]},
                {"title": "Cloud GM / CapEx", "text": "Cloud GM 指引约 65%，较本季 67% 回落；CapEx 预计环比下降，但供需缺口仍在。", "tone": "negative", "source_ids": ["q2_call"]},
            ],
            "market_reaction": {"title": "财报后 MSFT vs QQQ", "method": "以财报日收盘价为基准；财报在盘后发布，比较随后 1 个及 5 个交易日收盘表现。", "source_ids": ["market_yahoo"], "metrics": [
                {"horizon": "次一交易日", "msft": "-9.99%", "qqq": "-0.60%", "relative": "-9.39 pct", "tone": "negative"},
                {"horizon": "5 个交易日", "msft": "-14.00%", "qqq": "-4.34%", "relative": "-9.66 pct", "tone": "negative"},
            ]},
            "risks": [
                {"title": "AI 投资回报周期继续拉长", "text": "375 亿美元 CapEx 已明显先于自由现金流兑现，若新增算力主要缓解内部产品和 OpenAI 需求、却不能转化为更高 Azure 消费收入，折旧会先进入利润表而收入滞后。", "transmission": "CapEx 上升 → 折旧与电力成本增加 → Cloud GM/FCF margin 承压 → 市场下调中期利润率与估值倍数。", "monitor": "Azure AI 收入与核心 Azure 增速、Cloud GM、经营现金流、现金 CapEx 与 finance lease、数据中心利用率。", "trigger": "未来两个季度 Azure 仅贴近指引，同时 Cloud GM 继续下行或自由现金流增长持续显著落后收入。", "horizon": "未来 2–4 个季度", "status": "正在上升；本季经营 beat 尚未消除回报周期争议。", "counter_signal": "Azure 持续显著超过指引、Cloud GM 稳定，并且自由现金流重新快于收入增长。", "source_ids": ["q2_call", "q2_release"]},
                {"title": "RPO 的客户集中与现金转化风险", "text": "商业 RPO 中约 45% 来自 OpenAI，headline backlog 不能等同于分散、可快速确认的企业云需求。单一客户的大额长期合同可能放大 bookings，同时延长收入和现金兑现时间。", "transmission": "客户集中度上升 → backlog 质量折价 → 收入可见性和现金回收的不确定性增加 → 市场降低对 RPO 的估值权重。", "monitor": "剔除 OpenAI 后的 commercial bookings/RPO 增速、合同期限、递延收入、应收账款及 Azure consumption 增速。", "trigger": "剔除 frontier-model 客户后订单明显减速，或 RPO 高增但递延收入和经营现金流没有同步改善。", "horizon": "未来 2–6 个季度", "status": "高关注；集中度已经成为可量化的质量折价因素。", "counter_signal": "非 OpenAI 客户订单重新加速，RPO 集中度下降且现金转化同步改善。", "source_ids": ["q2_call"]},
                {"title": "下一季利润率指引弱于本季质量", "text": "本季 Cloud GM 为 67%，但下一季指引约 65%。若下降主要来自折旧和推理成本，而非高增长业务组合，市场会认为本季利润率好于预期不可持续。", "transmission": "毛利率下修 → 增量 AI 收入利润贡献不足 → EPS 上修空间收窄 → 即使收入增长稳定，估值也可能压缩。", "monitor": "Microsoft Cloud GM、Intelligent Cloud operating margin、折旧增速、AI 产品单位推理成本及价格调整。", "trigger": "Cloud GM 跌至或低于指引，并且管理层继续下调后续季度利润率路径。", "horizon": "下一季度至 FY27", "status": "已进入指引；需要用后续实际数据确认幅度。", "counter_signal": "fleet efficiency 和规模效应抵消折旧，使 Cloud GM 高于指引并趋稳。", "source_ids": ["q2_call"]},
                {"title": "预期差而非会计 beat 主导股价", "text": "收入和调整后 EPS 均超共识，但次日相对 QQQ 落后 9.39pct，说明买方隐含门槛高于公开共识，市场正在交易资本效率和远期增速而非单季数字。", "transmission": "公开共识被击败但高阶预期未满足 → 盈利上修不足以覆盖估值溢价 → 拥挤仓位解除并放大下跌。", "monitor": "财报前一致预期修订、Azure buy-side whisper、远期 P/E/FCF yield、期权隐含波动与财报后盈利预测调整。", "trigger": "后续季度再次出现 headline beat、但远期 EPS/FCF 预测不上调且股价持续跑输 QQQ。", "horizon": "下一次财报前后", "status": "已经由负面相对价格反应验证。", "counter_signal": "远期盈利预测明显上修、估值保持稳定且相对 QQQ 重新转强。", "source_ids": ["q2_consensus", "market_yahoo"]},
                {"title": "非经营项目造成盈利质量误读", "text": "GAAP EPS 5.16 美元包含 OpenAI 投资会计影响；若把该收益与 3.91 美元调整后共识直接比较，会夸大核心经营超预期幅度。", "transmission": "一次性收益抬高 EPS → 错估持续盈利能力 → 后续不可重复时形成盈利下修。", "monitor": "GAAP 与 non-GAAP 调节表、权益法/公允价值投资损益、税率及数据中心寿命假设。", "trigger": "投资收益对 EPS 的贡献继续扩大，或公司口径与卖方可比口径差异持续增加。", "horizon": "每季复核", "status": "本季已发生，估值应基于可持续经营利润。", "counter_signal": "剔除投资损益后，核心 EPS 和现金流仍持续高于一致预期。", "source_ids": ["q2_release", "q2_call"]},
            ],
        },
    },
    {
        "id": "msft-2026-07-29", "period": "FY26 Q4", "date": "2026-07-29",
        "sample_role": "最近已发布样本", "status": "reported", "information_cutoff": "2026-07-28T23:59:59-04:00",
        "preview": {
            "title": "Microsoft FY26 Q4 · 财报前 Preview",
            "verdict": "市场门槛集中在 Azure 39–40% CC、约 876 亿美元收入和超过 400 亿美元 CapEx：只有增长加速同时维持云毛利率，才能证明 AI 投入正在转化为经营杠杆。",
            "summary": "FactSet 共识收入约 876.2 亿美元、调整后 EPS 约 4.24 美元，公司收入指引为 867–878 亿美元。市场门槛已经从“能否 beat”上移到 Azure 39–40% CC 能否显著超出、Cloud GM 能否守住约 64%，以及超过 400 亿美元 CapEx 是否带来更快的容量上线。FY27 的 Azure、总收入、资本开支和利润率指引，很可能比 FY26 Q4 的 headline 数字更能决定估值方向。",
            "summary_points": [
                {"title": "基础门槛", "text": "收入共识接近公司指引上沿，市场已经预期一个偏强季度。", "tone": "neutral"},
                {"title": "核心上行", "text": "Azure 明显超过 39–40% CC、Cloud GM 好于约 64%，可验证新增容量和效率改善。", "tone": "positive"},
                {"title": "核心下行", "text": "CapEx 超 400 亿美元但 Azure 只达标，或 FY27 利润率指引明显转弱，会压制估值。", "tone": "negative"},
            ],
            "metrics_title": "关键指标与财报前门槛",
            "metrics": [
                metric("Revenue", "$87.62B consensus / $86.7–87.8B company guide", sources=["q4_consensus", "q3_call"]),
                metric("Adjusted EPS", "$4.24 FactSet consensus", sources=["q4_consensus"]),
                metric("Azure growth", "39–40% constant currency company guide", sources=["q3_call"]),
                metric("Intelligent Cloud revenue", "$37.95–38.25B company guide", sources=["q3_call"]),
                metric("Microsoft Cloud gross margin", "约 64% company guide", sources=["q3_call"]),
                metric("CapEx", "> $40B；CY26 约 $190B", sources=["q3_call"]),
            ],
            "observations": [
                {"title": "Azure 加速度", "text": "需要明显超过 39–40% CC 指引，才能证明新容量交付和 fleet efficiency 正在加速收入。", "source_ids": ["q3_call"]},
                {"title": "GitHub Copilot", "text": "转向更贴近使用量和价值的计费后，需观察消费增长能否覆盖更高推理成本。", "source_ids": ["q3_call"]},
                {"title": "云毛利率", "text": "约 64% 是 AI 投入效率的硬约束；增长 beat 若伴随更差毛利率，质量有限。", "source_ids": ["q3_call"]},
                {"title": "投资回报", "text": "CapEx 超过 400 亿美元、CY26 约 1900 亿美元的路径要求 Azure、Copilot 与现金流共同验证回报。", "source_ids": ["q3_call"]},
                {"title": "Copilot 变现", "text": "应看净新增付费席位和 ARPU，Azure 应区分 AI 与核心基础设施贡献。", "source_ids": ["q3_call"]},
                {"title": "FY27 指引", "text": "收入、营业利润、CapEx 与利润率指引，重要性可能高于 FY26 Q4 的 headline beat。", "source_ids": ["q3_call"]},
            ],
            "market_focus": ["Azure 是否突破 40% CC 并延续至 FY27 Q1", "超过 400 亿美元 CapEx 对 Cloud GM 与 FCF 的影响", "M365 Copilot 席位、ARPU 与使用量计费", "FY27 收入、利润率和资本开支指引"],
            "risks": [
                {"title": "一次性项目", "text": "FactSet EPS 共识按调整后口径，需排除 OpenAI、Anthropic 投资和其他离散项目。"},
                {"title": "基准错配", "text": "公司指引区间与卖方共识不是同一基准，Azure reported 与 CC 口径也不能直接相减。"},
                {"title": "预期过高", "text": "即使全面 beat，若 FY27 指引只符合买方更高的隐含预期，股价反应仍可能有限。"},
            ],
        },
        "analysis": {
            "title": "Microsoft FY26 Q4 · 财报后 Analysis",
            "verdict": "全面超预期：收入、调整后 EPS、Azure、Intelligent Cloud 和云毛利率均越过关键门槛；Azure 容量更快上线使 AI 投资回报的可信度提高，但 410 亿美元 CapEx 与一次性收益仍需剔除。",
            "summary": "收入 900.07 亿美元、调整后 EPS 4.74 美元，分别较 FactSet 共识高约 23.87 亿美元和 0.50 美元。Azure 增长 43%，较 39–40% 指引高约 3–4 个百分点，Cloud GM 65% 也好于约 64% 指引；同时管理层给出 FY27 Q1 Azure 约 45% CC 和总收入 898.5–909.5 亿美元的强劲指引。尽管 410 亿美元 CapEx 与约 0.27 美元一次性收益需要剔除，容量兑现和前瞻加速使结果质量明显强于 FY26 Q2。",
            "summary_points": [
                {"title": "经营结果", "text": "收入、调整后 EPS、Azure、Intelligent Cloud 与 Cloud GM 全面越过关键门槛。", "tone": "positive"},
                {"title": "前瞻信号", "text": "FY27 Q1 Azure 约 45% CC 指引确认增长仍有加速度。", "tone": "positive"},
                {"title": "市场定价", "text": "次一交易日 MSFT 相对 QQQ 领先 12.21pct，市场把结果识别为高质量超预期。", "tone": "positive"},
            ],
            "metrics_title": "实际结果 vs 财报前预期",
            "result_tone": "positive",
            "metrics": [
                metric("Revenue", "$87.62B", "$90.007B", "+$2.387B / +2.7%", "超预期", ["q4_consensus", "q4_release"], tone="positive"),
                metric("Adjusted EPS", "$4.24", "$4.74", "+$0.50 / +11.8%", "超预期", ["q4_consensus", "q4_release"], tone="positive"),
                metric("Azure growth", "39–40% CC", "43% reported", "+3–4 pct（口径近似）", "明显超指引", ["q3_call", "q4_release", "q4_call"], tone="positive"),
                metric("Intelligent Cloud revenue", "$37.95–38.25B", "$39.3B", "+$1.05B vs high end", "超指引", ["q3_call", "q4_call"], tone="positive"),
                metric("Microsoft Cloud gross margin", "约 64%", "65%", "+1 pct", "好于指引", ["q3_call", "q4_call"], tone="positive"),
                metric("CapEx", "> $40B", "$41.0B", "符合高投入路径", "投入继续上升", ["q3_call", "q4_call"], tone="negative"),
            ],
            "drivers": [
                {"title": "Azure", "text": "43% 增长由 CPU/GPU fleet efficiency、流程改进和更早交付容量推动，新增供给迅速被需求吸收。", "source_ids": ["q4_call"]},
                {"title": "云规模", "text": "Microsoft Cloud 收入 593 亿美元、同比增长 27%；Azure 年收入首次超过 1000 亿美元。", "source_ids": ["q4_release", "q4_call"]},
                {"title": "Copilot", "text": "M365 Copilot 付费席位超过 3000 万，净新增环比翻倍，商业化证据较 FY26 Q2 明显增强。", "source_ids": ["q4_call"]},
                {"title": "现金流", "text": "CapEx 410 亿美元、自由现金流 196 亿美元；现金流仍被 AI 基建显著压低。", "source_ids": ["q4_call"]},
                {"title": "一次性收益", "text": "EPS 包含 Anthropic 投资收益和其他离散项目带来的约 0.27 美元好处，核心经营 beat 仍在，但幅度低于 headline。", "source_ids": ["q4_release", "q4_call"]},
                {"title": "前瞻", "text": "FY27 Q1 Azure 指引约 45% CC、总收入 898.5–909.5 亿美元，意味着管理层认为加速趋势可延续。", "source_ids": ["q4_call"]},
            ],
            "guidance_changes": [
                {"title": "Azure", "text": "FY27 Q1 指引约 45% CC，高于 FY26 Q4 实际 43% reported，方向上继续加速。", "tone": "positive", "source_ids": ["q4_call"]},
                {"title": "总收入", "text": "FY27 Q1 指引 898.5–909.5 亿美元，对应 16%–17% 增长，商业业务加速抵消 PC 压力。", "tone": "positive", "source_ids": ["q4_call"]},
                {"title": "利润率 / CapEx", "text": "Cloud GM 预计环比稳定，但 CapEx 将超过 500 亿美元；全年营业利润率预计下降不到 1pct。", "tone": "mixed", "source_ids": ["q4_call"]},
            ],
            "market_reaction": {"title": "财报后 MSFT vs QQQ", "method": "以财报日收盘价为基准；财报在盘后发布，比较随后 1 个及 5 个交易日收盘表现。", "source_ids": ["market_yahoo"], "metrics": [
                {"horizon": "次一交易日", "msft": "+15.51%", "qqq": "+3.30%", "relative": "+12.21 pct", "tone": "positive"},
                {"horizon": "5 个交易日", "msft": "+24.82%", "qqq": "+8.40%", "relative": "+16.42 pct", "tone": "positive"},
            ]},
            "risks": [
                {"title": "资本开支再上台阶后的现金回报压力", "text": "FY27 Q1 CapEx 指引将超过 500 亿美元，投入增速继续快于成熟软件业务。即使 Azure 保持高增，现金 CapEx、finance lease 和折旧的组合仍可能压低自由现金流转化率。", "transmission": "CapEx/租赁承诺增加 → 折旧和利息样成本上升 → FCF yield 下行 → 市场要求更高的 Azure 增速才能维持估值。", "monitor": "现金 CapEx、finance lease additions、FCF margin、Cloud GM、AI 数据中心投产周期及利用率。", "trigger": "Azure 增速开始回落，但 CapEx 仍继续上升且 FCF 增速连续两个季度低于收入。", "horizon": "FY27 全年", "status": "投入继续上升；强劲增长暂时提供缓冲，但尚未完成现金回报验证。", "counter_signal": "新增容量快速满载，Azure 与 Copilot 收入使 FCF margin 在高 CapEx 下保持稳定。", "source_ids": ["q4_call", "q4_release"]},
                {"title": "45% Azure 指引形成新的高基数风险", "text": "FY27 Q1 约 45% CC 指引把市场门槛再次上移。容量提前交付带来的加速可能存在时点效应，后续若供应扩张放缓或核心非 AI Azure 降速，增速持续性会受到挑战。", "transmission": "高指引被资本化进估值 → 后续仅达标也可能被视为减速 → 盈利预测与估值倍数同时承压。", "monitor": "Azure reported/CC 增速、AI 与核心基础设施贡献、供给约束、剩余履约义务及下一季指引。", "trigger": "Azure 低于约 45% CC 或下一季度指引出现明显降速，而 CapEx 路径没有同步下调。", "horizon": "未来 1–3 个季度", "status": "预期门槛显著提高，是下一次财报最重要的非对称风险。", "counter_signal": "Azure 连续超过高位指引，且非 AI 核心消费增速也保持稳定。", "source_ids": ["q4_call"]},
                {"title": "Copilot 商业化可能不足以覆盖推理成本", "text": "M365 Copilot 付费席位超过 3000 万是积极证据，但席位数不能直接等同于高质量利润。折扣、捆绑销售、使用量和推理成本决定真实 ARPU 与增量毛利。", "transmission": "席位增长但 ARPU/使用深度不足 → 单位推理成本难以下降 → Productivity 业务利润率被侵蚀 → AI 商业化估值溢价回吐。", "monitor": "净新增付费席位、ARPU、E5/E7 mix、usage-based billing、推理成本及 Productivity operating margin。", "trigger": "席位继续增长但 Productivity 收入或利润率没有相应改善，或管理层减少商业化指标披露。", "horizon": "未来 2–4 个季度", "status": "商业化证据改善，但单位经济性仍未被完整披露。", "counter_signal": "ARPU 和使用深度同步提高，Productivity 收入加速且利润率稳定。", "source_ids": ["q4_call"]},
                {"title": "一次性收益放大 headline EPS", "text": "调整后 EPS 仍包含约 0.27 美元投资收益和离散项目好处；若直接用 4.74 美元对比 4.24 美元共识，会高估核心经营 beat。", "transmission": "非经常性收益抬高 EPS → 市场高估可持续盈利 → 下一年度基数和预测回归造成下修。", "monitor": "投资公允价值变动、税率、股权投资收益、GAAP/non-GAAP 调节及卖方核心 EPS 修订。", "trigger": "剔除一次性项目后 EPS 超预期幅度显著收窄，且后续季度缺少经营利润率上修。", "horizon": "当前季度及未来同比基数", "status": "本季已发生；核心经营结果仍超预期，但幅度低于 headline。", "counter_signal": "剔除投资收益后，经营利润、Azure 和现金流仍持续超过预期。", "source_ids": ["q4_release", "q4_call"]},
                {"title": "强劲价格反应后的估值与仓位非对称", "text": "次日 MSFT 相对 QQQ 领先 12.21pct，表明市场已快速重估增长质量。正面信息被迅速计价后，下一季度对指引、毛利率或 CapEx 的小幅失误会产生更大的下行弹性。", "transmission": "盈利上修与估值扩张同步发生 → 安全边际下降 → 边际利空触发多重压缩和拥挤交易逆转。", "monitor": "远期 P/E、FCF yield、卖方目标价与盈利修订、期权偏度、相对 QQQ 强弱及机构仓位代理指标。", "trigger": "估值继续上升但盈利预测停止上修，或股价创新高而相对强弱和盈利修订开始背离。", "horizon": "下一次财报前后", "status": "市场确认基本面改善，同时提高了未来兑现门槛。", "counter_signal": "盈利和 FCF 预测持续上修，估值保持稳定且相对强势由基本面延续。", "source_ids": ["market_yahoo", "q4_consensus"]},
            ],
        },
    },
    {
        "id": "msft-2026-11-04", "period": "FY27 Q1", "date": "2026-11-04",
        "sample_role": "未来预计样本", "status": "estimated", "information_cutoff": "2026-10-03T23:59:59+08:00",
        "preview": {
            "title": "Microsoft FY27 Q1 · 财报前 Preview",
            "verdict": "公司给出的收入和 Azure 指引已经很强，核心问题不是能否保持双位数增长，而是约 45% Azure CC 增长和超过 500 亿美元 CapEx 能否同时保持云毛利率及现金流纪律。",
            "summary": "Nasdaq 当前预计日期为 2026-11-04、14 位分析师 EPS 预期约 4.70 美元，但 Microsoft IR 尚未确认日期。公司给出的总收入指引为 898.5–909.5 亿美元、Azure 约 45% CC、Intelligent Cloud 409.5–412.5 亿美元，增长门槛已经很高。市场将重点判断超过 500 亿美元 CapEx 是否继续换来 Azure 加速，同时 Cloud GM 能否环比稳定、Copilot 计费能否扩大 ARPU，并警惕 PC 需求和会计口径变化掩盖真实经营趋势。",
            "summary_points": [
                {"title": "强指引基准", "text": "收入区间中点约 904 亿美元，Azure 约 45% CC，基本面门槛明显高于前两期。", "tone": "positive"},
                {"title": "关键验证", "text": "Cloud GM 环比稳定且 Azure 达标，才能证明超过 500 亿美元 CapEx 仍有合理回报。", "tone": "neutral"},
                {"title": "主要下行", "text": "Azure 增长低于约 45%、利润率提前承压或 PC 弱于预期，都会放大高投入争议。", "tone": "negative"},
            ],
            "metrics_title": "关键指标与未来财报门槛",
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
                {"title": "Azure 构成", "text": "约 45% CC 是第一优先级；需要区分新增物理容量、fleet efficiency、合同结构和 AI 消费各自贡献。", "source_ids": ["q4_call"]},
                {"title": "收入质量", "text": "区间中点约 904 亿美元；若 Azure 达标但总收入靠低毛利业务支撑，结果质量有限。", "source_ids": ["q4_call"]},
                {"title": "云毛利率", "text": "环比稳定意味着效率改善需要抵消 AI 基础设施折旧和推理使用成本。", "source_ids": ["q4_call"]},
                {"title": "CapEx 口径", "text": "超过 500 亿美元是新的投资台阶；应同时核对现金 PP&E、finance lease 与 accounting reclassification。", "source_ids": ["q4_call"]},
                {"title": "Copilot ARPU", "text": "应继续跟踪付费席位、ARPU、使用量计费和 E5/E7 premium mix。", "source_ids": ["q4_call"]},
                {"title": "RPO 集中度", "text": "OpenAI 大合同会制造 bookings/RPO 波动，应优先看剔除 frontier model customers 后的核心增长。", "source_ids": ["q4_call"]},
                {"title": "PC 拖累", "text": "Windows OEM 面临组件涨价、库存和高基数；消费业务可能部分抵消商业云加速。", "source_ids": ["q4_call"]},
                {"title": "全年余量", "text": "FY27 营业利润率指引为全年下降不到 1 个百分点，若 Q1 已明显承压，后续容错空间会缩小。", "source_ids": ["q4_call"]},
            ],
            "market_focus": ["Azure 约 45% CC 是否兑现及其容量/AI 构成", "超过 500 亿美元 CapEx 与 Cloud GM 的组合", "M365 Copilot 的席位、ARPU 和 usage-based billing", "FY27 全年营业利润率下降是否仍控制在 1pct 内"],
            "risks": [
                {"title": "日期不确定", "text": "2026-11-04 仅为 Nasdaq estimated，必须等待 Microsoft IR 正式确认。"},
                {"title": "共识漂移", "text": "4.70 美元 EPS 来自当前 14 位分析师快照，临近财报仍会调整，不能当作固定门槛。"},
                {"title": "会计口径", "text": "数据中心寿命延长和租赁重分类会改变 CapEx、折旧与利润率的同比可比性。"},
                {"title": "高基数误判", "text": "Azure 接近 45% 仍可能因市场隐含预期更高而被视为不够；应同时观察指引、利润率和市场反应。"},
            ],
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
        "analysis_verdict": event["analysis"]["verdict"] if event["analysis"] else None,
    }
    brief = {
        "event": {k: event[k] for k in ("period", "date", "status", "information_cutoff")},
        "drafts": drafts,
    }
    prompt = (
        "不要展示推理过程，直接返回 JSON。只压缩和润色下列已核验草稿，不得增加或修改任何数字或事实，"
        "不得把预计写成事实。只返回 JSON：preview_verdict, analysis_verdict；"
        "未来未发布事件的 analysis_verdict 必须为 null。每个 verdict 不超过110字。证据："
        + json.dumps(brief, ensure_ascii=False, separators=(",", ":"))
    )
    payload = {"model": model, "messages": [
        {"role": "system", "content": "你是谨慎的美股财报研究编辑。事实、口径和时间边界优先。"},
        {"role": "user", "content": prompt},
    ], "temperature": 0.1, "max_tokens": 1100, "stream": False,
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
        event["preview"]["verdict"],
        event["analysis"]["verdict"] if event["analysis"] else None,
    )))
    allowed_numbers = set(re.findall(r"\d+(?:\.\d+)?", original_text))
    candidate_text = " ".join(str(value.get(key) or "") for key in ("preview_verdict", "analysis_verdict"))
    new_numbers = set(re.findall(r"\d+(?:\.\d+)?", candidate_text)) - allowed_numbers
    if new_numbers:
        raise ValueError(f"model introduced numbers not in draft: {sorted(new_numbers)}")
    if not isinstance(value.get("preview_verdict"), str) or not value["preview_verdict"].strip():
        raise ValueError("invalid preview_verdict")
    event["preview"]["verdict"] = value["preview_verdict"].strip()
    if event["analysis"]:
        if not isinstance(value.get("analysis_verdict"), str) or not value["analysis_verdict"].strip():
            raise ValueError("invalid analysis_verdict")
        event["analysis"]["verdict"] = value["analysis_verdict"].strip()


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
        "analysis_verdict": prior["analysis"]["verdict"] if prior.get("analysis") else None,
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
            if not restore_previous_narrative(event, previous):
                event["generation"] = {"mode": "verified_snapshot", "model": None}
    return {"schema_version": 3, "generated_at": now_iso(), "ticker": "MSFT", "company": "Microsoft",
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
