from __future__ import annotations

import html
import base64
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "mag7-earnings-radar-debug"
SKILL = Path(r"C:\Users\黄政\.codex\skills\cloud-earnings-report")
OUT = ROOT / "site"

COMPANIES = [
    ("MSFT", "Microsoft", 1), ("AMZN", "Amazon", 1), ("META", "Meta", 1),
    ("GOOGL", "Alphabet", 1), ("ORCL", "Oracle", 1), ("SPACEX", "SpaceX", 1),
    ("NVDA", "NVIDIA", 1), ("AVGO", "Broadcom", 1), ("AMD", "AMD", 1),
    ("MU", "Micron", 1), ("INTC", "Intel", 1), ("SKHX", "SK hynix", 1),
    ("SMSN", "Samsung Electronics", 1), ("CRWV", "CoreWeave", 2),
    ("NBIS", "Nebius", 2), ("SNDK", "SanDisk", 2), ("WDC", "Western Digital", 2),
    ("STX", "Seagate", 2), ("AMAT", "Applied Materials", 2),
    ("CSCO", "Cisco", 2), ("LRCX", "Lam Research", 2), ("ASML", "ASML", 2),
]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    data = json.loads((SOURCE / "frontend/data/mag7.json").read_text(encoding="utf-8"))
    research = json.loads((SOURCE / "frontend/data/mag7_research.json").read_text(encoding="utf-8"))
    reports = {"MSFT": "microsoft", "AMZN": "amazon", "GOOGL": "google"}
    for ticker, folder in reports.items():
        dest = OUT / "reports" / ticker / "overview.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SKILL / "checks/reference-bundles" / folder / "draft.html", dest)

    index = {}
    for record in research["events"]:
        ticker = record["ticker"]
        event_id = record["id"]
        index[event_id] = {}
        for stage, block in (("preview", record.get("preview")), ("analysis", record.get("analysis"))):
            if not block:
                continue
            lines = [f"# {block.get('title') or ticker + ' ' + stage}", "",
                     f"> 试用版迁移稿｜信息截止：{record.get('information_cutoff', '未记录')}｜来源：现有 V13 研究缓存。", "",
                     f"**结论：** {block.get('verdict', '')}", "", block.get("summary", ""), ""]
            points = block.get("summary_points") or []
            if points:
                lines += ["## 核心要点", ""] + ["- " + str(x) for x in points] + [""]
            for heading, key in (("观察与驱动", "observations" if stage == "preview" else "drivers"),
                                 ("风险", "risks")):
                values = block.get(key) or []
                if values:
                    lines += ["## " + heading, ""]
                    for value in values:
                        lines.append("- " + str(value.get("text", value.get("title", "")) if isinstance(value, dict) else value))
                    lines.append("")
            path = OUT / "research" / ticker / event_id / f"{stage}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            index[event_id][stage] = path.relative_to(OUT).as_posix()

    (OUT / "data.json").write_text(json.dumps({
        "companies": [{"ticker": t, "name": n, "tier": tier,
                       "report": f"reports/{t}/overview.html" if t in reports else None} for t, n, tier in COMPANIES],
        "events": data["calendar"]["formal"]["events"], "articles": index,
        "snapshot": data.get("generated_at"),
    }, ensure_ascii=False), encoding="utf-8")
    payload = {"data.json": (OUT / "data.json").read_text(encoding="utf-8")}
    for folder in index.values():
        for rel in folder.values():
            payload[rel] = (OUT / rel).read_text(encoding="utf-8")
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    shim = ("<script>const trialFiles=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('" + encoded +
            "'),c=>c.charCodeAt(0))));const nativeFetch=window.fetch.bind(window);" +
            "window.fetch=(url,options)=>trialFiles[url]===undefined?nativeFetch(url,options):" +
            "Promise.resolve(new Response(trialFiles[url],{status:200}));</script>")
    page = (OUT / "index.html").read_text(encoding="utf-8")
    (OUT / "trial-offline.html").write_text(page.replace("<script>", shim + "<script>", 1), encoding="utf-8")
    print(f"Built {OUT}: {len(COMPANIES)} companies, {len(index)} event folders, 3 report drafts")


if __name__ == "__main__":
    main()
