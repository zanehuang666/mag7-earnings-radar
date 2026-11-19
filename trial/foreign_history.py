"""Collect official Samsung and SK hynix quarterly announcement dates."""
import concurrent.futures
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent / "foreign-history-2024.json"
ORDINAL = {1: "first", 2: "second", 3: "third", 4: "fourth"}
VERIFIED_OVERRIDES = {
    "SMSN-2024Q2": ("2024-07-31", "https://news.samsung.com/global/samsung-electronics-announces-results-for-second-quarter-of-2024"),
    "SMSN-2024Q3": ("2024-10-31", "https://news.samsung.com/global/samsung-electronics-announces-results-for-third-quarter-of-2024"),
    "SMSN-2024Q4": ("2025-01-31", "https://news.samsung.com/global/samsung-electronics-announces-fourth-quarter-and-fy-2024-results"),
    "SMSN-2025Q3": ("2025-10-30", "https://news.samsung.com/global/samsung-electronics-announces-third-quarter-2025-results"),
    "SMSN-2026Q1": ("2026-04-30", "https://news.samsung.com/global/samsung-electronics-announces-first-quarter-2026-results"),
    "SKHX-2024Q3": ("2024-10-24", "https://news.skhynix.com/en/sk-hynix-announces-3q24-financial-results/"),
    "SKHX-2024Q4": ("2025-01-23", "https://news.skhynix.com/en/sk-hynix-announces-4q24-financial-results/"),
    "SKHX-2025Q1": ("2025-04-24", "https://news.skhynix.com/en/sk-hynix-announces-1q25-financial-results/"),
    "SKHX-2025Q4": ("2026-01-28", "https://news.skhynix.com/en/sk-hynix-announces-fy25-financial-results/"),
}


def urls(ticker, year, quarter):
    if ticker == "SMSN":
        base = f"https://news.samsung.com/global/samsung-electronics-announces-{ORDINAL[quarter]}-quarter-"
        return [base + f"{year}-results", base + f"and-fy-{year}-results"] if quarter == 4 else [base + f"{year}-results"]
    base = "https://news.skhynix.com/en/"
    return [base + f"sk-hynix-announces-{quarter}q{str(year)[-2:]}-financial-results/",
            base + f"sk-hynix-announces-{quarter}q{str(year)[-2:]}-earnings/",
            base + f"q{quarter}-{year}-business-results/"]


def fetch(ticker, year, quarter):
    for url in urls(ticker, year, quarter):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=18) as response:
                page = response.read().decode("utf-8", "ignore")
            if ticker == "SMSN":
                match = re.search(r'"datePublished":"(\d{4}-\d{2}-\d{2})', page)
                # Samsung newsroom's page heading provides the Korean local date.
                local = re.search(r'Korea on\s+([A-Z][a-z]+ \d{1,2}, \d{4})', page)
                day = datetime.strptime(local.group(1), "%B %d, %Y").date().isoformat() if local else (match.group(1) if match else None)
            else:
                local = re.search(r'Seoul,?\s+([A-Z][a-z]+ \d{1,2}, \d{4})', page)
                day = datetime.strptime(local.group(1), "%B %d, %Y").date().isoformat() if local else None
            if day:
                return ticker, year, quarter, {"date": day, "source": url, "status": "reported"}
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass
    return ticker, year, quarter, None


def main():
    current_year = datetime.now().year
    records = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    tasks = [(t, y, q) for t in ("SMSN", "SKHX") for y in range(2024, current_year + 1)
             for q in range(1, 5) if not records.get(f"{t}-{y}Q{q}")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        for ticker, year, quarter, item in executor.map(lambda args: fetch(*args), tasks):
            key = f"{ticker}-{year}Q{quarter}"
            if item:
                records[key] = item
            print(key, item["date"] if item else "missing", flush=True)
    for key, (day, url) in VERIFIED_OVERRIDES.items():
        if records.get(key) is None:
            records[key] = {"date": day, "source": url, "status": "reported", "method": "official_release_manual_review"}
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
