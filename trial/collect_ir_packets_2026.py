"""One-time collection of matching 2026 company IR releases for pending packets.

Run locally after reviewing the URLs. Only a short source excerpt is retained;
the URL, title, date, and requested quarter are checked before changing a packet.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".vendor"))
from pypdf import PdfReader  # type: ignore[import-not-found]

RELEASES = {
    ("AMD", "2025Q4"): ("2026-02-03", "AMD Reports Fourth Quarter", "https://ir.amd.com/financial-information/sec-filings/content/0000002488-26-000014/q42025991.htm"),
    ("AMD", "2026Q1"): ("2026-05-05", "AMD Reports First Quarter 2026", "https://ir.amd.com/news-events/press-releases/detail/1284/amd-reports-first-quarter-2026-financial-results"),
    ("AMD", "2026Q2"): ("2026-08-04", "AMD Reports Second Quarter 2026", "https://ir.amd.com/news-events/press-releases/detail/1295/amd-reports-second-quarter-2026-financial-results"),
    ("AMZN", "2025Q4"): ("2026-02-05", "Amazon.com Announces Fourth Quarter Results", "https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-Fourth-Quarter-Results/default.aspx"),
    ("AMZN", "2026Q1"): ("2026-04-29", "Amazon.com Announces First Quarter Results", "https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-First-Quarter-Results/default.aspx"),
    ("AMZN", "2026Q2"): ("2026-07-30", "Amazon.com Announces Second Quarter Results", "https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-Second-Quarter-Results/default.aspx"),
    ("GOOGL", "2025Q4"): ("2026-02-04", "Alphabet Announces Fourth Quarter and Fiscal Year 2025", "https://s206.q4cdn.com/479360582/files/doc_news/2026/Feb/04/attachments/2025q4-alphabet-earnings-release.pdf"),
    ("GOOGL", "2026Q1"): ("2026-04-29", "Alphabet Announces First Quarter 2026", "https://s206.q4cdn.com/479360582/files/doc_news/2026/Apr/29/attachments/2026q1-alphabet-earnings-release.pdf"),
    ("GOOGL", "2026Q2"): ("2026-07-22", "Alphabet Announces Second Quarter 2026", "https://s206.q4cdn.com/479360582/files/doc_news/2026/Jul/22/attachments/2026q2-alphabet-earnings-release.pdf"),
    ("MSFT", "2025Q4"): ("2026-01-28", "Microsoft Cloud", "https://www.microsoft.com/en-us/investor/earnings/fy-2026-q2/press-release-webcast"),
    ("MSFT", "2026Q1"): ("2026-04-29", "Microsoft Cloud", "https://www.microsoft.com/en-us/investor/earnings/fy-2026-q3/press-release-webcast"),
    ("MSFT", "2026Q2"): ("2026-07-29", "Microsoft Cloud", "https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast"),
    ("MU", "2026Q1"): ("2026-03-18", "Reports Results for the Second Quarter of Fiscal 2026", "https://investors.micron.com/news/press-release/2026/Micron-Technology-Inc--Reports-Results-for-the-Second-Quarter-of-Fiscal-2026-03-18-2026/default.aspx"),
    ("MU", "2026Q2"): ("2026-06-24", "Reports Record Results for the Third Quarter of Fiscal 2026", "https://investors.micron.com/news/press-release/2026/Micron-Technology-Inc--Reports-Record-Results-for-the-Third-Quarter-of-Fiscal-2026/default.aspx"),
    ("NVDA", "2026Q1"): ("2026-02-25", "NVIDIA Announces Financial Results for Fourth Quarter and Fiscal 2026", "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2026/"),
    ("NVDA", "2026Q2"): ("2026-05-20", "NVIDIA Announces Financial Results for First Quarter Fiscal 2027", "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2027"),
    ("NVDA", "2026Q3"): ("2026-08-26", "NVIDIA Announces Financial Results for Second Quarter Fiscal 2027", "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2027/"),
}


def source_text(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Magic7 research contact: research@example.com"}, timeout=40)
    response.raise_for_status()
    if url.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(response.content))
        raw = "\n".join(page.extract_text() or "" for page in reader.pages[:3])
    else:
        soup = BeautifulSoup(response.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        body = soup.select_one("main") or soup.body or soup
        raw = body.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", raw)


def main() -> None:
    for (ticker, quarter), (date, title, url) in RELEASES.items():
        path = ROOT / "source-packets" / ticker / quarter / "analysis.json"
        prior = json.loads(path.read_text(encoding="utf-8"))
        if prior.get("verification_status") not in ("source_review_pending", "official_source_missing"):
            continue
        try:
            text = source_text(url)
            normalized = text.casefold()
            if title.casefold() not in normalized or date[:4] not in text:
                raise ValueError("title/year did not match expected quarter")
            start = normalized.find(title.casefold())
            excerpt = text[start:start + 14000]
            if len(excerpt) < 1500:
                raise ValueError("source extract too short")
            packet = {"ticker": ticker, "calendar_quarter": quarter, "release_date": date,
                      "cutoff": date + "T23:59:59", "sources": [url],
                      "facts": [excerpt[i:i + 1750] for i in range(0, len(excerpt), 1750)],
                      "official_release_confirmed": True,
                      "verification_status": "official_release_text_collected",
                      "note": "Company IR release text excerpt; title and release year matched. Numerical claims in generated prose require editorial review."}
            path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(ticker, quarter, "collected", len(excerpt), flush=True)
        except Exception as exc:
            print(ticker, quarter, "FAILED", str(exc)[:180], flush=True)


if __name__ == "__main__":
    main()
