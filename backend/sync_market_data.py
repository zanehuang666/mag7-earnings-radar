"""Cache a small, keyless market series for the static GitHub Pages demo.

QQQ is used as a transparent Nasdaq-100 market proxy.  The browser never calls
Yahoo directly; GitHub Actions writes a versioned JSON snapshot instead.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "data" / "market_qqq.json"
SYMBOL = "QQQ"
START = date(2024, 1, 1)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Mag7-Earnings-Radar/1.0; research demo)"}


def unix(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())


def fetch(attempts: int = 3) -> dict:
    end = date.today() + timedelta(days=2)
    query = urllib.parse.urlencode({
        "period1": unix(START), "period2": unix(end), "interval": "1d", "events": "history",
    })
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?{query}"
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
                "schema_version": 1,
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "symbol": SYMBOL,
                "label": "QQQ · Nasdaq-100 ETF proxy",
                "currency": result.get("meta", {}).get("currency", "USD"),
                "source": {
                    "label": "Yahoo Finance chart (keyless cached snapshot)",
                    "url": "https://finance.yahoo.com/quote/QQQ/history/",
                },
                "points": points,
                "disclaimer": "Market context only; earnings markers show timing, not causation.",
            }
        except (KeyError, TypeError, ValueError, RuntimeError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"market source failed: {type(last_error).__name__}")


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
    print(f"wrote {OUTPUT}: {len(data['points'])} daily closes")


if __name__ == "__main__":
    main()
