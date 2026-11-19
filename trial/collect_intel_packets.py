"""Collect Intel official 2024+ quarterly earnings releases from its IR archive."""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from research_pipeline import PACKETS, ROOT

BASE = "https://www.intc.com/news-events/press-releases?category=financial&page={}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Magic7ResearchTrial/1.0)"}
ORDINAL = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4}


def soup(url: str) -> BeautifulSoup:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        return BeautifulSoup(response.read(2_000_000), "html.parser")


def main() -> None:
    links = {}
    for page in (1, 2, 3):
        for anchor in soup(BASE.format(page)).select("a[href]"):
            title = anchor.get_text(" ", strip=True)
            match = re.search(r"Intel Reports (First|Second|Third|Fourth)-Quarter(?: and Full-Year)? (20\d{2}) Financial Results", title)
            if match and int(match.group(2)) >= 2024:
                links[f"{match.group(2)}Q{ORDINAL[match.group(1)]}"] = anchor["href"].split("?")[0]
    status = {}
    for q, url in sorted(links.items()):
        path = PACKETS / "INTC" / q / "analysis.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("verification_status") == "official_release_text_collected":
            status[q] = "cached"
            continue
        try:
            page = soup(url)
            for tag in page(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            main = page.select_one("main") or page.body
            body = re.sub(r"\s+", " ", main.get_text(" ", strip=True))[:22_000]
            if len(body) < 1000 or "Financial Results" not in body:
                raise ValueError("release text failed validation")
            packet = {"ticker": "INTC", "calendar_quarter": q,
                      "cutoff": datetime.now(timezone.utc).isoformat(), "sources": [url],
                      "facts": [body], "official_release_confirmed": True,
                      "verification_status": "official_release_text_collected",
                      "note": "Official Intel earnings release. AI summary remains editorial-review pending."}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            status[q] = "official_release_text_collected"
        except Exception as exc:
            status[q] = f"fetch_failed: {exc}"
    (ROOT / "intel-source-coverage.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Intel source packets", status)


if __name__ == "__main__":
    main()
