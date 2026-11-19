"""Prepare 2024+ first-tier earnings source packets without inventing history.

Six company bundles supply provisional, source-linked numeric facts. Korean
official newsroom articles can be fetched to produce verified-release packets.
Existing hand-edited packets are never replaced.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from research_pipeline import DATA, FIRST, PACKETS, ROOT, event_quarters

REPORTS = ROOT / "v13-based" / "reports"
BUNDLES = ("MSFT", "AMZN", "GOOGL", "NVDA", "AMD", "MU", "AVGO", "SMSN")
FOREIGN = ROOT / "foreign-history-2024.json"
STATUS_FILE = ROOT / "source-packet-coverage.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Magic7ResearchTrial/1.0)"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, packet: dict) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def collect_bundles(status: dict) -> None:
    for ticker in BUNDLES:
        base = REPORTS / ticker / "data"
        if not all((base / name).exists() for name in ("periods.json", "facts.json", "sources.json")):
            continue
        periods = read(base / "periods.json")["records"]
        facts = defaultdict(list)
        for item in read(base / "facts.json")["records"]:
            if item.get("value") is not None and item.get("value_status") == "reported":
                facts[item.get("period_id")].append(item)
        sources = {item["source_id"]: item for item in read(base / "sources.json")["records"]}
        for period in periods:
            end = period.get("quarter_end")
            if not end or end < "2024-01-01" or end > datetime.now().date().isoformat():
                continue
            q = f"{end[:4]}Q{(int(end[5:7]) - 1) // 3 + 1}"
            rows = facts[period["period_id"]]
            if not rows:
                continue
            urls = sorted({sources[row["source_id"]]["url"] for row in rows
                           if row.get("source_id") in sources and sources[row["source_id"]].get("is_company_official")
                           and sources[row["source_id"]].get("url", "").startswith("https://")})
            if not urls:
                continue
            # The imported historical bundles are useful research leads, but
            # several source records explicitly say reference_only. Do not
            # silently promote them to verified facts or launch AI generation.
            digest = []
            for row in rows[:45]:
                digest.append(f"{row.get('original_metric_name') or row.get('metric_id')} | {row.get('entity_id')} | "
                              f"{row['value']} {row.get('unit_original') or ''} {row.get('currency') or ''} | "
                              f"{row.get('gaap_basis') or ''} | source_id={row.get('source_id')}")
            packet = {"ticker": ticker, "calendar_quarter": q, "fiscal_period": period["period_id"],
                      "quarter_end": end, "cutoff": datetime.now(timezone.utc).isoformat(),
                      "sources": urls, "facts": digest, "verification_status": "source_review_pending",
                      "official_release_confirmed": False,
                      "note": "Imported report bundle. Source URLs and individual numbers require independent review."}
            path = PACKETS / ticker / q / "analysis.json"
            write_new(path, packet)
            current = read(path)
            status[f"{ticker}/{q}"] = {"status": current.get("verification_status", "source_review_pending"), "source_count": len(urls),
                                        "fact_count": len(digest), "packet": str(path.relative_to(ROOT))}


def fetch_official(url: str) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(1_500_000)
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.select_one("main") or soup.select_one("article") or soup.body
    text = main.get_text(" ", strip=True) if main else ""
    text = re.sub(r"\s+", " ", text)
    if len(text) < 700:
        raise ValueError("official article text too short")
    return text[:18_000]


def collect_foreign(status: dict, fetch: bool) -> None:
    for key, item in read(FOREIGN).items():
        if not item:
            continue
        ticker, q = key.split("-", 1)
        path = PACKETS / ticker / q / "analysis.json"
        if path.exists() and read(path).get("verification_status") == "official_release_text_collected":
            status[f"{ticker}/{q}"] = {"status": "official_release_text_collected", "packet": str(path.relative_to(ROOT))}
            continue
        if not fetch:
            status[f"{ticker}/{q}"] = {"status": "official_url_known_text_not_fetched", "url": item["source"]}
            continue
        try:
            article = fetch_official(item["source"])
            packet = {"ticker": ticker, "calendar_quarter": q, "cutoff": datetime.now(timezone.utc).isoformat(),
                      "release_date": item["date"], "sources": [item["source"]], "facts": [article],
                      "official_release_confirmed": True, "verification_status": "official_release_text_collected",
                      "note": "Official newsroom text collected. AI article remains an unreviewed draft until edited."}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            status[f"{ticker}/{q}"] = {"status": "official_release_text_collected", "packet": str(path.relative_to(ROOT))}
        except Exception as exc:
            status[f"{ticker}/{q}"] = {"status": "fetch_failed", "error": str(exc), "url": item["source"]}


def mark_missing_releases() -> None:
    events = read(DATA)["calendar"]["formal"]["events"]
    quarters = event_quarters(events)
    for event in events:
        if event["ticker"] not in FIRST or event["status"] != "reported":
            continue
        ticker, q = event["ticker"], quarters[event["id"]]
        path = PACKETS / ticker / q / "analysis.json"
        if path.exists():
            continue
        links = [v["url"] for v in (event.get("ir_source"), event.get("source"))
                 if isinstance(v, dict) and v.get("url")]
        packet = {"ticker": ticker, "calendar_quarter": q, "release_date": event["date"],
                  "discovery_links": links, "sources": [], "facts": [],
                  "official_release_confirmed": False, "verification_status": "official_source_missing",
                  "note": "Calendar date is known. An official earnings release or filing text is still needed."}
        write_new(path, packet)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-official", action="store_true")
    args = parser.parse_args()
    status = {}
    collect_bundles(status)
    collect_foreign(status, args.fetch_official)
    mark_missing_releases()
    for path in PACKETS.glob("*/20*Q*/analysis.json"):
        ticker, q = path.parent.parent.name, path.parent.name
        if ticker in FIRST:
            packet = read(path)
            status[f"{ticker}/{q}"] = {"status": packet.get("verification_status", "manual_packet"),
                                        "source_count": len(packet.get("sources", [])),
                                        "packet": str(path.relative_to(ROOT))}
    STATUS_FILE.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                                       "quarters": status}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = defaultdict(int)
    for item in status.values():
        counts[item["status"]] += 1
    print("source packets", dict(counts))


if __name__ == "__main__":
    main()
