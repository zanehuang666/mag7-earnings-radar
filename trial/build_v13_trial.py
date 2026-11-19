from __future__ import annotations

import json
import base64
import shutil
import subprocess
import sys
from datetime import datetime
from datetime import date, timedelta
from statistics import median
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "source-snapshot"
SOURCE = SNAPSHOT / "frontend"
TARGET = ROOT / "v13-based"
SKILL = Path(r"C:\Users\黄政\.codex\skills\cloud-earnings-report")

COMPANIES = [
    ("ORCL", "Oracle"), ("SPACEX", "SpaceX"), ("AVGO", "Broadcom"),
    ("AMD", "AMD"), ("MU", "Micron"), ("INTC", "Intel"),
    ("SKHX", "SK hynix"), ("SMSN", "Samsung Electronics"),
    ("CRWV", "CoreWeave"), ("NBIS", "Nebius"), ("SNDK", "SanDisk"),
    ("WDC", "Western Digital"), ("STX", "Seagate"), ("AMAT", "Applied Materials"),
    ("CSCO", "Cisco"), ("LRCX", "Lam Research"), ("ASML", "ASML"),
]


def main() -> None:
    if not SOURCE.exists():
        origin = ROOT.parent / "mag7-earnings-radar-debug"
        shutil.copytree(origin / "frontend", SOURCE)
        shutil.copytree(origin / "backend", SNAPSHOT / "backend")
    assert TARGET.resolve().parent == ROOT.resolve()
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    shutil.copyfile(ROOT / "history-cache.json", TARGET / "data/history-cache.json")
    shutil.copyfile(ROOT / "nasdaq-history-2024.json", TARGET / "data/nasdaq-history-2024.json")
    shutil.copyfile(ROOT / "foreign-history-2024.json", TARGET / "data/foreign-history-2024.json")
    data_file = TARGET / "data/mag7.json"
    data = json.loads(data_file.read_text(encoding="utf-8"))
    # The isolated source snapshot can lag when Nasdaq is unreachable. An
    # official NVIDIA release confirms this one already-published event.
    nvda_release = "https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Third-Quarter-Fiscal-2027/"
    for event in data["calendar"]["formal"]["events"]:
        if event.get("id") == "nvda-2026-11-17" and date.today().isoformat() >= "2026-11-17":
            event["status"] = "reported"
            event["date_confidence"] = "reported"
            event["ir_source"] = {"url": nvda_release, "label": "NVIDIA 官方业绩公告"}
    candidates = json.loads((TARGET / "data/us_earnings_candidates.json").read_text(encoding="utf-8"))
    existing = {company["ticker"] for company in data["companies"]}
    for ticker, name in COMPANIES:
        if ticker not in existing:
            data["companies"].append({"ticker": ticker, "company": name, "ir_url": None})
    accepted = {ticker for ticker, _ in COMPANIES}
    history = json.loads((ROOT / "history-cache.json").read_text(encoding="utf-8"))["companies"]
    daily_history = json.loads((ROOT / "nasdaq-history-2024.json").read_text(encoding="utf-8"))["days"]
    foreign_history = json.loads((ROOT / "foreign-history-2024.json").read_text(encoding="utf-8"))
    names = dict(COMPANIES)
    added = []
    latest_results = {(ticker, datetime.strptime(row["dateReported"], "%m/%d/%Y").date().isoformat()): row
                      for ticker, bundle in history.items() for row in bundle["rows"]}
    for calendar_day, rows in daily_history.items():
        for calendar_row in rows:
            ticker = calendar_row["ticker"]
            day = calendar_day
            if ticker == "NBIS" and day < "2024-10-01":
                continue  # Pre-restructuring issuer; needs separate corporate-history review.
            result = latest_results.get((ticker, day), {})
            event = {
                "id": f"{ticker.lower()}-{day}", "ticker": ticker, "company": names[ticker],
                "date": day, "fiscal_period": result.get("fiscalQtrEnd") or calendar_row.get("fiscal_period") or "Reported quarter",
                "status": "reported", "date_confidence": "reported",
                "source": {"url": calendar_row["source"], "label": "Nasdaq 历史财报日历"},
                "ir_source": None,
                "forecast": {"actual_eps": result.get("eps"), "consensus_eps": result.get("consensusForecast"), "surprise_pct": result.get("percentageSurprise")},
                "date_range": None,
                "preview": {"verdict": "历史财报日期已收录", "summary": "此处等待经审阅的财报前 Preview Markdown。", "points": ["历史日期来自 Nasdaq"], "risks": ["不能用事后数据改写财报前判断"]},
                "aftercheck": {"verdict": "历史数据占位", "summary": "已收录 EPS 结果；完整 Analysis 尚待上传。", "points": ["查看 Nasdaq 原始数据来源"], "risks": ["EPS 差异不能代替完整财报分析"]},
            }
            data["calendar"]["formal"]["events"].append(event)
            added.append(event)
    for key, item in foreign_history.items():
        if not item:
            continue
        ticker, fiscal_period = key.split("-", 1)
        day = item["date"]
        event = {
            "id": f"{ticker.lower()}-{day}", "ticker": ticker, "company": names[ticker],
            "date": day, "fiscal_period": fiscal_period, "status": "reported", "date_confidence": "reported",
            "source": {"url": item["source"], "label": "公司官方季度业绩稿"}, "ir_source": {"url": item["source"], "label": "公司官方公告"},
            "forecast": {}, "date_range": None,
            "preview": {"verdict": "历史官方发布日期已收录", "summary": "财报前 Preview 尚待研究。", "points": ["查看公司官方公告"], "risks": ["不能用事后数据改写财报前判断"]},
            "aftercheck": {"verdict": "历史研究占位", "summary": "完整季度 Analysis 尚待上传。", "points": ["查看公司官方公告"], "risks": ["当前仅核验发布日期"]},
        }
        data["calendar"]["formal"]["events"].append(event)
        added.append(event)
    for item in candidates["events"]:
        if item["ticker"] not in accepted:
            continue
        event = {
            "id": f"{item['ticker'].lower()}-{item['date']}",
            "ticker": item["ticker"], "company": item["company"],
            "date": item["date"], "fiscal_period": item["fiscal_period"],
            "status": "estimated", "date_confidence": "estimated",
            "source": {"url": f"https://api.nasdaq.com/api/calendar/earnings?date={item['date']}", "label": "Nasdaq 预计财报日历"},
            "ir_source": None, "forecast": {"eps": item.get("eps"), "analyst_count": item.get("analyst_count")},
            "date_range": None,
            "preview": {"verdict": "等待完整季度 Preview", "summary": "Nasdaq 日历收录的预计日期；尚需公司 IR 确认。", "points": ["核对公司公告与财报日期", "核对一致预期及主要业务指标", "财报前上传完整 Markdown"], "risks": ["预计日期可能变动", "当前没有已审阅的完整研究稿"]},
            "aftercheck": {"verdict": "尚未发布", "summary": "正式财报发布后再生成 Analysis。", "points": ["等待官方财报"], "risks": ["不可提前推断实际结果"]},
        }
        if any(e["id"] == event["id"] for e in data["calendar"]["formal"]["events"]):
            continue
        data["calendar"]["formal"]["events"].append(event)
        added.append(event)
    # Follow the original Mag 7 hierarchy: sourced estimates first, then
    # clearly labelled cadence projections to keep four upcoming slots.
    for ticker in list(history) + ["SKHX", "SMSN"]:
        company_events = [e for e in data["calendar"]["formal"]["events"] if e["ticker"] == ticker]
        known = sorted((e for e in company_events if e["status"] == "reported"), key=lambda e: e["date"])
        future = sorted((e for e in company_events if e["status"] != "reported" and e["date"] >= date.today().isoformat()), key=lambda e: e["date"])
        if len(known) < 2:
            continue
        gaps = [(date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days for a, b in zip(known, known[1:])]
        cadence = max(84, min(100, round(median(gaps))))
        anchor = date.fromisoformat((future[-1] if future else known[-1])["date"])
        while len(future) < 4:
            anchor += timedelta(days=cadence)
            while anchor <= date.today():
                anchor += timedelta(days=cadence)
            day = anchor.isoformat()
            if any(e["date"] == day and e["ticker"] == ticker for e in data["calendar"]["formal"]["events"]):
                anchor += timedelta(days=7)
                day = anchor.isoformat()
            projected = {
                "id": f"{ticker.lower()}-{day}", "ticker": ticker, "company": names[ticker],
                "date": day, "fiscal_period": "历史节奏推算季度", "status": "projected",
                "date_confidence": "projected",
                "source": {"url": history[ticker]["source"] if ticker in history else known[-1]["source"]["url"], "label": "历史结果；日期为节奏推算"},
                "ir_source": None, "forecast": {"method": "median_reported_gap", "cadence_days": cadence},
                "date_range": {"from": (anchor-timedelta(days=7)).isoformat(), "to": (anchor+timedelta(days=7)).isoformat()},
                "preview": {"verdict": "低置信度日期推算", "summary": "依历史发布间隔推算，不是公司或市场确认日期。", "points": ["等待公司 IR 确认", "等待 Nasdaq 预计日期"], "risks": ["日期可能显著变化"]},
                "aftercheck": {"verdict": "尚未发布", "summary": "待财报正式发布。", "points": [], "risks": []},
            }
            data["calendar"]["formal"]["events"].append(projected)
            future.append(projected)
            added.append(projected)
    data["calendar"]["formal"]["events"].sort(key=lambda e: (e["date"], e["ticker"]))
    data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reports = {}
    for ticker, folder in {"MSFT": "microsoft", "AMZN": "amazon", "GOOGL": "google"}.items():
        dest = TARGET / "reports" / ticker / "overview.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SKILL / "checks/reference-bundles" / folder / "draft.html", dest)
        reports[ticker] = {"path": f"reports/{ticker}/overview.html", "skill": "cloud-earnings-report", "status": "draft_unverified"}
        shutil.copytree(SKILL / "checks/reference-bundles" / folder,
                        TARGET / "reports" / ticker / "data", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("draft.html"))
        view_file = TARGET / "reports" / ticker / "data" / "report-view.json"
        view = json.loads(view_file.read_text(encoding="utf-8"))
        view["return_href"] = "../../calendar.html"
        view_file.write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    research_root = ROOT.parent / "美股跟踪"
    legacy = {
        "META": "Meta财报研究Demo_v2.html", "ORCL": "Oracle财报研究Demo_v2.html",
        "SPACEX": "SpaceX财报研究Demo_v2.html", "NBIS": "Nebius财报研究_草稿.html",
        "NVDA": "nvidia-financial-history-draft.html", "AMD": "amd-financial-history-draft.html",
        "MU": "micron-financial-history-draft.html", "INTC": "Intel财报研究Demo_v2.html",
        "SNDK": "SanDisk财报研究Demo_v2.html", "SKHX": "SK海力士财报研究Demo_v2.html",
    }
    for ticker, filename in legacy.items():
        matches = list(research_root.rglob(filename))
        if not matches:
            continue
        src = next((p for p in matches if "过程文档" not in str(p)), matches[0])
        dest = TARGET / "reports" / ticker / "overview.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        reports[ticker] = {"path": f"reports/{ticker}/overview.html",
                           "skill": "hardware-earnings-report" if ticker in {"NVDA", "AMD", "MU", "INTC", "SNDK", "SKHX"} else "cloud-earnings-report",
                           "status": "existing_draft_not_reverified", "source_file": str(src.relative_to(ROOT.parent))}
        sibling_data = src.parent / "data"
        if sibling_data.is_dir():
            shutil.copytree(sibling_data, TARGET / "reports" / ticker / "data", dirs_exist_ok=True)
    for ticker in ("AVGO", "SMSN"):
        source = ROOT / "diagnostic-inputs" / ticker
        dest = TARGET / "reports" / ticker
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / "overview.html", dest / "overview.html")
        shutil.copytree(source, dest / "data", dirs_exist_ok=True, ignore=shutil.ignore_patterns("overview.html"))
        reports[ticker] = {"path": f"reports/{ticker}/overview.html", "skill": "hardware-earnings-report",
                           "status": "diagnostic_one_quarter_only"}
    for ticker in ("GOOGL", "MSFT", "AMZN", "NVDA", "AMD", "MU"):
        skill_name = reports[ticker]["skill"]
        scripts = Path(r"C:\Users\黄政\.codex\skills") / skill_name / "scripts"
        company_data = TARGET / "reports" / ticker / "data"
        output = TARGET / "reports" / ticker / "overview.html"
        checks = TARGET / "reports" / ticker / "checks"
        checks.mkdir(exist_ok=True)
        validation = subprocess.run([sys.executable, str(scripts / "validate_data.py"), str(company_data)], capture_output=True, text=True)
        (checks / "data-validation.json").write_text(validation.stdout or validation.stderr, encoding="utf-8")
        if validation.returncode:
            reports[ticker]["status"] = "data_validation_failed"
            continue
        build = subprocess.run([sys.executable, str(scripts / "build_report.py"), str(company_data), "--output", str(output)], capture_output=True, text=True)
        (checks / "build.json").write_text(build.stdout or build.stderr, encoding="utf-8")
        if build.returncode:
            reports[ticker]["status"] = "build_failed"
            continue
        verify = subprocess.run([sys.executable, str(scripts / "verify_report.py"), str(output)], capture_output=True, text=True)
        (checks / "static-verification.json").write_text(verify.stdout or verify.stderr, encoding="utf-8")
        reports[ticker]["status"] = "static_pass_source_review_pending" if verify.returncode == 0 else "static_verification_failed"
    (TARGET / "data/report_index.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "add_latest_official_packets.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "collect_official_packets.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "prepare_previews.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "prune_out_of_scope_baselines.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "seed_markdown_baselines.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "research_pipeline.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "coverage_report.py")], check=True, capture_output=True)
    shutil.copyfile(ROOT / "research-index.json", TARGET / "data/research_index.json")
    shutil.copyfile(ROOT / "source-packet-coverage.json", TARGET / "data/source_packet_coverage.json")
    shutil.copyfile(ROOT / "research-coverage.md", TARGET / "data/research-coverage.md")
    if (ROOT / "research").exists():
        shutil.copytree(ROOT / "research", TARGET / "research", dirs_exist_ok=True)
    if (ROOT / "source-packets").exists():
        shutil.copytree(ROOT / "source-packets", TARGET / "source-packets", dirs_exist_ok=True)
    page = TARGET / "calendar.html"
    content = page.read_text(encoding="utf-8")
    content = content.replace('<span class="company-tag">M7</span>', '')
    content = content.replace('const r=(MSFT_RESEARCH?.events||[]).find(x=>x.id===e.id);if(!r)return e;', 'if(FIRST_TIER_TICKERS.has(e.ticker))return e;const r=(MSFT_RESEARCH?.events||[]).find(x=>x.id===e.id);if(!r)return e;', 1)
    content = content.replace("$('companies').innerHTML=fixed.concat(custom).join('');", '''const groups=[['第一梯队 · 云与平台',['MSFT','AMZN','META','GOOGL','ORCL','SPACEX']],['第一梯队 · 芯片与硬件',['NVDA','AVGO','AMD','MU','INTC','SKHX','SMSN']],['第二梯队 · 云与平台',['CRWV','NBIS']],['第二梯队 · 芯片与硬件',['SNDK','WDC','STX','AMAT','CSCO','LRCX','ASML']],['原有其他',['AAPL','TSLA']]];const groupHtml=groups.map(([label,tickers],i)=>`<details class="company-group" ${i===0?'open':''}><summary>${label} <span>${tickers.length}</span></summary><div class="group-items">${tickers.map(t=>fixed[DATA.companies.findIndex(c=>c.ticker===t)]||'').join('')}</div></details>`).join('');$('companies').innerHTML=groupHtml+custom.join('');''')
    content = content.replace('</style>', '''.company-row{display:flex;gap:7px;align-items:flex-start}.company-group{border:1px solid var(--line);border-radius:9px;background:#fff;padding:4px 8px}.company-group summary{cursor:pointer;font-size:11px;font-weight:800;color:var(--blue);white-space:nowrap}.company-group summary span{color:var(--muted);font-weight:500}.group-items{display:flex;flex-wrap:wrap;gap:5px;padding:8px 0;max-width:340px}.company-wrap.core{border-color:var(--line);background:#fff}.company-wrap .company{padding:4px 7px}#databaseLinks{display:flex;gap:10px;margin:10px 0;font-size:11px;flex-wrap:wrap}#databaseLinks a{color:var(--green)}#macroPanel .macro-value,#macroPanel .macro-compare,#macroPanel #macroImplications,#macroPanel .notice{display:none}#macroPanel .macro-comment strong:before{content:'Analysis · '}#quarterMarkdown{font-size:13px;line-height:1.8;color:var(--ink)}#quarterMarkdown .md-body{margin-top:14px}#quarterMarkdown h2{font-size:18px;margin:16px 0 8px}#quarterMarkdown h3{font-size:14px;margin:14px 0 6px}#quarterMarkdown p{margin:8px 0}#quarterMarkdown .md-item{margin:5px 0 5px 12px}
</style>''', 1)
    content = content.replace('<div class="company-row" id="companies"></div>', '<div class="company-row" id="companies"></div><nav id="databaseLinks"><a href="./data/mag7.json" target="_blank">日历数据库 JSON ↗</a><a href="./data/nasdaq-history-2024.json" target="_blank">2024 起 Nasdaq 历史 ↗</a><a href="./data/foreign-history-2024.json" target="_blank">韩国官方发布日期 ↗</a><a href="./data/us_earnings_candidates.json" target="_blank">未来候选日期 ↗</a><a href="./data/report_index.json" target="_blank">公司报告索引 ↗</a><a href="./data/research_index.json" target="_blank">季度研究索引 ↗</a><a href="./data/research-coverage.md" target="_blank">研究覆盖表 ↗</a><a href="./data/source_packet_coverage.json" target="_blank">资料覆盖 ↗</a></nav>')
    content = content.replace('<div id="eventList" class="event-list"></div>', '<div id="companyReport" class="notice"></div><div id="eventList" class="event-list"></div>')
    report_meta = {ticker: {"path": item["path"], "status": item["status"]} for ticker, item in reports.items()}
    content = content.replace('renderCalendar()}\nfunction selectEvent(id)', '''const report=REPORT_META[ticker];const reportStatus=report?.status==='existing_draft_not_reverified'?'旧版草稿':report?.status==='diagnostic_one_quarter_only'?'单季度诊断稿':report?.status==='static_pass_source_review_pending'?'研究草稿 · 来源待逐值核验':'研究草稿';$('companyReport').innerHTML=report?`<strong>公司时间序列研究 · ${reportStatus}</strong><p>HTML 已归档在研究数据库中；状态及来源见报告索引。</p><a href="./${report.path}" target="_blank">打开完整 HTML 报告 ↗</a><iframe title="${esc(company.company)} 时间序列研究" src="./${report.path}" style="width:100%;height:380px;border:1px solid #dce3dd;border-radius:9px;margin-top:10px"></iframe>`:'<strong>公司时间序列研究</strong><p>HTML 尚未接入；后续由对应 Skill 生成。</p>';renderCalendar()}\nfunction selectEvent(id)''', 1)
    content = content.replace('const $=id=>', 'const FIRST_TIER_TICKERS=new Set('+json.dumps(["MSFT","AMZN","META","GOOGL","ORCL","SPACEX","NVDA","AVGO","AMD","MU","INTC","SKHX","SMSN"])+');const REPORT_META='+json.dumps(report_meta, ensure_ascii=False)+';const $=id=>', 1)
    viewer = (ROOT / "research_viewer.js").read_text(encoding="utf-8")
    content = content.replace('</body>', '<script>const QUARTER_RESEARCH='+json.dumps(json.loads((ROOT / "research-index.json").read_text(encoding="utf-8"))["events"], ensure_ascii=False)+';'+viewer+'</script></body>')
    page.write_text(content, encoding="utf-8")
    payload = {path.name: path.read_text(encoding="utf-8") for path in (TARGET / "data").glob("*.json")}
    payload.update({"./" + path.relative_to(TARGET).as_posix(): path.read_text(encoding="utf-8") for path in (TARGET / "research").rglob("*.md")})
    payload.update({"./" + path.relative_to(TARGET).as_posix(): path.read_text(encoding="utf-8") for path in (TARGET / "source-packets").rglob("*.json")})
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    shim = ("<script>const embedded=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('" + encoded +
            "'),c=>c.charCodeAt(0))));const originalFetch=window.fetch.bind(window);" +
            "window.fetch=(input,options)=>{const path=String(input).split('?')[0],key=embedded[path]!==undefined?path:path.split('/').pop();" +
            "return embedded[key]===undefined?originalFetch(input,options):Promise.resolve(new Response(embedded[key],{status:200}));};</script>")
    (TARGET / "trial-offline.html").write_text(content.replace("<script>", shim + "<script>", 1), encoding="utf-8")
    print(f"V13-based trial: {len(data['companies'])} companies, {len(added)} sourced new calendar events")


if __name__ == "__main__":
    main()
