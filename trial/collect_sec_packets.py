"""Fetch US first-tier official 10-Q/10-K filing text into quarterly packets.

This uses SEC's public submissions API. It records failures without replacing
existing packets. Annual 10-K filings are leads only until quarter-specific
earnings materials establish Q4 values.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from research_pipeline import PACKETS, ROOT

CIKS = {"MSFT": 789019, "AMZN": 1018724, "META": 1326801, "GOOGL": 1652044,
        "ORCL": 1341439, "NVDA": 1045810, "AVGO": 1730168, "AMD": 2488,
        "MU": 723125, "INTC": 50863}
STATUS = ROOT / "sec-source-coverage.json"


def request_json(url: str, agent: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def filing_rows(recent: dict):
    keys = ("form", "accessionNumber", "primaryDocument", "reportDate", "filingDate")
    count = len(recent.get("form", []))
    for i in range(count):
        yield {key: recent.get(key, [None] * count)[i] for key in keys}


def official_text(url: str, agent: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read(3_000_000)
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    if len(text) < 2000:
        raise ValueError("filing text too short")
    return text[:28_000]


def gather(ticker: str, cik: int, agent: str, status: dict, max_quarters: int | None) -> None:
    url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    try:
        submissions = request_json(url, agent)
    except Exception as exc:
        status[ticker] = {"status": "submissions_fetch_failed", "error": str(exc), "url": url}
        return
    all_rows = list(filing_rows(submissions["filings"]["recent"]))
    for older in submissions["filings"].get("files", []):
        if older.get("filingFrom", "9999") > "2026-12-31" or older.get("filingTo", "0000") < "2024-01-01":
            continue
        try:
            all_rows += list(filing_rows(request_json("https://data.sec.gov/submissions/" + older["name"], agent)))
        except Exception as exc:
            status[f"{ticker}/archive/{older['name']}"] = {"status": "archive_fetch_failed", "error": str(exc)}
        time.sleep(0.12)
    chosen = {}
    for row in all_rows:
        if row["form"] not in ("10-Q", "10-K") or not row.get("reportDate") or not row.get("primaryDocument"):
            continue
        end = row["reportDate"]
        if end < "2024-01-01" or end > datetime.now().date().isoformat():
            continue
        q = f"{end[:4]}Q{(int(end[5:7]) - 1) // 3 + 1}"
        if q not in chosen or row["filingDate"] < chosen[q]["filingDate"]:
            chosen[q] = row
    selected = sorted(chosen.items(), reverse=True)
    if max_quarters:
        selected = selected[:max_quarters]
    for q, row in selected:
        accession = row["accessionNumber"].replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{row['primaryDocument']}"
        path = PACKETS / ticker / q / "analysis.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if existing.get("verification_status") in ("official_filing_text_collected", "manual_verified"):
            status[f"{ticker}/{q}"] = {"status": existing["verification_status"], "url": filing_url}
            continue
        try:
            body = official_text(filing_url, agent)
            annual_only = row["form"] == "10-K"
            packet = {"ticker": ticker, "calendar_quarter": q, "quarter_end": row["reportDate"],
                      "filing_date": row["filingDate"], "form": row["form"],
                      "cutoff": datetime.now(timezone.utc).isoformat(), "sources": [filing_url],
                      "facts": [body], "official_release_confirmed": not annual_only,
                      "verification_status": "official_filing_text_collected" if not annual_only else "annual_filing_q4_review_needed",
                      "note": "Primary SEC filing text; AI summary remains editorial-review pending."
                              if not annual_only else "10-K has annual figures; Q4 earnings release needed for quarter-only analysis."}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            status[f"{ticker}/{q}"] = {"status": packet["verification_status"], "url": filing_url}
        except Exception as exc:
            status[f"{ticker}/{q}"] = {"status": "filing_fetch_failed", "error": str(exc), "url": filing_url}
        time.sleep(0.12)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest-only", type=int, default=None, help="Limit to this many newest quarters per company")
    args = parser.parse_args()
    agent = os.getenv("SEC_USER_AGENT", "Magic7ResearchTrial zanehuang666@users.noreply.github.com")
    status = {}
    for ticker, cik in CIKS.items():
        gather(ticker, cik, agent, status, args.latest_only)
    STATUS.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "quarters": status},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SEC packets", dict(Counter(x["status"] for x in status.values())))


if __name__ == "__main__":
    main()
