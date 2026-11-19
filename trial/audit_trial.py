"""Audit event provenance and report coverage for the isolated trial."""
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "v13-based"
FIRST = ["MSFT", "AMZN", "META", "GOOGL", "ORCL", "SPACEX", "NVDA", "AVGO", "AMD", "MU", "INTC", "SKHX", "SMSN"]
EXTENDED_US = ["ORCL", "AVGO", "AMD", "MU", "INTC", "CRWV", "NBIS", "SNDK", "WDC", "STX", "AMAT", "CSCO", "LRCX", "ASML"]


def main():
    calendar = json.loads((SITE / "data/mag7.json").read_text(encoding="utf-8"))
    reports = json.loads((SITE / "data/report_index.json").read_text(encoding="utf-8"))
    ledger = json.loads((ROOT / "nasdaq-history-2024.json").read_text(encoding="utf-8"))
    foreign = json.loads((ROOT / "foreign-history-2024.json").read_text(encoding="utf-8"))
    events = calendar["calendar"]["formal"]["events"]
    ids = [e["id"] for e in events]
    problems = []
    if len(ids) != len(set(ids)):
        problems.append("duplicate event IDs")
    today = date.today().isoformat()
    for e in events:
        if e["status"] == "reported" and e["date"] > today:
            problems.append(f"future reported: {e['id']}")
        if e["status"] != "reported" and e["date"] < today:
            problems.append(f"past not reported: {e['id']}")
    sourced = {(row["ticker"], day) for day, rows in ledger["days"].items() for row in rows}
    for e in events:
        if e["ticker"] in EXTENDED_US and e["status"] == "reported" and (e["ticker"], e["date"]) not in sourced:
            problems.append(f"unsourced reported: {e['id']}")
    official = {(key.split("-")[0], item["date"]) for key, item in foreign.items() if item}
    for e in events:
        if e["ticker"] in {"SKHX", "SMSN"} and e["status"] == "reported" and (e["ticker"], e["date"]) not in official:
            problems.append(f"unsourced foreign result: {e['id']}")
    coverage = {}
    for ticker in FIRST:
        company = [e for e in events if e["ticker"] == ticker]
        reported = sorted((e for e in company if e["status"] == "reported"), key=lambda e: e["date"])
        future = [e for e in company if e["status"] != "reported"]
        coverage[ticker] = {"reported_count": len(reported), "first_reported": reported[0]["date"] if reported else None,
                            "last_reported": reported[-1]["date"] if reported else None,
                            "future_count": len(future), "report_status": reports.get(ticker, {}).get("status", "missing")}
    output = {"as_of": today, "scanned_weekdays": len(ledger["days"]), "scan_errors": ledger["errors"],
              "problems": problems, "first_tier": coverage}
    (ROOT / "trial-audit.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if problems or ledger["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
