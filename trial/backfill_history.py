"""Build an auditable 2024+ earnings-date ledger from Nasdaq daily calendars."""
from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "nasdaq-history-2024.json"
TICKERS = {"ORCL", "AVGO", "AMD", "MU", "INTC", "CRWV", "NBIS", "SNDK", "WDC", "STX", "AMAT", "CSCO", "LRCX", "ASML"}


def scan(day: str):
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={day}"
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.load(response)
            rows = (payload.get("data") or {}).get("rows") or []
            found = [{"ticker": str(row.get("symbol", "")).upper().strip(), "company": row.get("name"),
                      "date": day, "fiscal_period": row.get("fiscalQuarterEnding"),
                      "source": url} for row in rows if str(row.get("symbol", "")).upper().strip() in TICKERS]
            return day, found, None
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(attempt + 1)
    return day, [], last


def main():
    state = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"days": {}, "errors": {}}
    all_days = []
    day = date(2024, 1, 1)
    while day <= date.today():
        if day.weekday() < 5:
            all_days.append(day.isoformat())
        day += timedelta(days=1)
    pending = [day for day in all_days if day not in state["days"]]
    print("historical days to check:", len(pending), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for index, (day, rows, error) in enumerate(executor.map(scan, pending), 1):
            if error:
                state["errors"][day] = error
            else:
                state["days"][day] = rows
                state["errors"].pop(day, None)
            if index % 50 == 0 or index == len(pending):
                OUT.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                print(index, "/", len(pending), "checked; errors", len(state["errors"]), flush=True)
    OUT.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    print("matched dates:", sum(len(rows) for rows in state["days"].values()))


if __name__ == "__main__":
    main()
