"""Cache keyless QQQ + Mag 7 market series for the static Pages demo.

QQQ is used as a transparent Nasdaq-100 market proxy.  The browser never calls
Yahoo directly; GitHub Actions writes a versioned JSON snapshot instead.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "data" / "market_qqq.json"
SYMBOLS = {
    "QQQ": "QQQ · Nasdaq-100 ETF proxy", "MSFT": "Microsoft", "AAPL": "Apple",
    "GOOGL": "Alphabet", "AMZN": "Amazon", "NVDA": "NVIDIA", "META": "Meta", "TSLA": "Tesla",
}
START = date(2024, 1, 1)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Mag7-Earnings-Radar/1.0; research demo)"}


def unix(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())


def fetch_symbol(symbol: str, attempts: int = 3) -> dict:
    end = date.today() + timedelta(days=2)
    query = urllib.parse.urlencode({
        "period1": unix(START), "period2": unix(end), "interval": "1d", "events": "history",
    })
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}"
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            result = payload["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]
            points = []
            for stamp, close in zip(timestamps, quote["close"]):
                if close is None:
                    continue
                day = datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
                points.append({"date": day, "close": round(float(close), 2)})
            if len(points) < 100:
                raise RuntimeError("market series unexpectedly short")
            return {
                "symbol": symbol, "label": SYMBOLS[symbol],
                "currency": result.get("meta", {}).get("currency", "USD"),
                "points": points,
            }
        except (KeyError, TypeError, ValueError, RuntimeError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"{symbol} market source failed: {type(last_error).__name__}")


def fetch() -> dict:
    series, errors = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_symbol, symbol): symbol for symbol in SYMBOLS}
        for future in concurrent.futures.as_completed(futures):
            symbol = futures[future]
            try:
                series[symbol] = future.result()
            except RuntimeError as exc:
                errors.append(str(exc))
    if "QQQ" not in series or len(series) < len(SYMBOLS):
        raise RuntimeError("; ".join(errors) or "market series incomplete")
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "refresh_schedule": "GitHub Actions weekdays at approximately 09:37 and 21:37 Asia/Shanghai",
        "source": {
            "label": "Yahoo Finance chart (keyless cached snapshot)",
            "url": "https://finance.yahoo.com/quote/QQQ/history/",
        },
        "series": series,
        "disclaimer": "Indexed market context only; earnings markers show timing, not causation.",
    }


def main() -> None:
    try:
        data = fetch()
    except RuntimeError as exc:
        if OUTPUT.exists():
            print(f"warning: {exc}; preserved previous {OUTPUT}")
            return
        raise
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    count = sum(len(item["points"]) for item in data["series"].values())
    print(f"wrote {OUTPUT}: {len(data['series'])} series, {count} daily closes")


if __name__ == "__main__":
    main()
