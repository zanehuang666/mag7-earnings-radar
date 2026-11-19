"""Refresh sourced US earnings history once per day for the trial universe."""
import concurrent.futures
import json
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "history-cache.json"
TICKERS = ["ORCL", "AVGO", "AMD", "MU", "INTC", "CRWV", "NBIS", "SNDK", "WDC", "STX", "AMAT", "CSCO", "LRCX", "ASML"]


def fetch(ticker):
    url = f"https://api.nasdaq.com/api/company/{ticker}/earnings-surprise"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    rows = ((payload.get("data") or {}).get("earningsSurpriseTable") or {}).get("rows") or []
    return ticker, {"source": url, "rows": rows}


def main():
    previous = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"companies": {}}
    if previous.get("checked_on") == date.today().isoformat():
        print("history cache fresh; no upstream requests")
        return
    companies = previous.get("companies", {})
    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch, ticker): ticker for ticker in TICKERS}
        for future in concurrent.futures.as_completed(futures):
            ticker = futures[future]
            try:
                key, value = future.result()
                companies[key] = value
            except Exception as exc:
                errors.append(f"{ticker}: {type(exc).__name__}: {exc}")
    OUT.write_text(json.dumps({"checked_on": date.today().isoformat(), "companies": companies, "errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("history rows:", {ticker: len(item["rows"]) for ticker, item in companies.items()}, "errors:", errors)


if __name__ == "__main__":
    main()
