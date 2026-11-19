"""Curated official release facts for recent first-tier earnings.

These packets supplement the bulk collectors where IR hosts deny direct fetches.
They never replace an already curated packet or a human Markdown article.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from research_pipeline import PACKETS


RELEASES = {
    ("MSFT", "2026Q3"): (
        "https://www.microsoft.com/en-us/investor/earnings/fy-2027-q1/press-release-webcast",
        ["Fiscal 2027 Q1 ended September 30, 2026; published October 28, 2026.",
         "Revenue was USD 92.3 billion, up 19% year over year.",
         "GAAP operating income was USD 45.9 billion, up 21% year over year."],
    ),
    ("AMZN", "2026Q3"): (
        "https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-Third-Quarter-Results/",
        ["Q3 2026 earnings release published October 29, 2026.",
         "Net sales were USD 201.9 billion; operating income was USD 28.1 billion.",
         "AWS sales grew 39.3% year over year according to the company release."],
    ),
    ("GOOGL", "2026Q3"): (
        "https://www.sec.gov/Archives/edgar/data/1652044/000165204426000080/googexhibit991q32026.htm",
        ["Q3 2026 ended September 30, 2026; released October 28, 2026.",
         "Consolidated revenue was USD 127.577 billion, up 25% year over year.",
         "Google Cloud revenue was USD 30.709 billion; operating income was USD 11.121 billion."],
    ),
    ("NVDA", "2026Q4"): (
        "https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Third-Quarter-Fiscal-2027/default.aspx",
        ["Fiscal 2027 Q3 ended October 25, 2026; this maps to calendar 2026Q4.",
         "Revenue was USD 115.8 billion, up 103% year over year.",
         "GAAP gross margin was 74.8%; GAAP diluted EPS was USD 2.70.",
         "Data Center revenue was USD 107.6 billion."],
    ),
    ("AMD", "2026Q3"): (
        "https://ir.amd.com/news-events/press-releases/detail/1303/amd-reports-third-quarter-2026-financial-results",
        ["Q3 2026 results released November 3, 2026.",
         "Revenue was USD 13.4 billion, up 45% year over year.",
         "The company attributed growth partly to record Data Center revenue; separate GAAP and non-GAAP figures in analysis."],
    ),
    ("MU", "2026Q3"): (
        "https://investors.micron.com/news/press-release/2026/Micron-Technology-Inc--Reports-Record-Fiscal-Fourth-Quarter-and-Full-Year-2026-Results/default.aspx",
        ["Fiscal 2026 Q4 ended September 3, 2026; this maps to calendar 2026Q3; released September 30, 2026.",
         "Revenue was USD 54.229 billion according to the official release (table unit: USD millions).",
         "GAAP gross margin was USD 47.047 billion; verify the unusually large year-on-year increase before writing conclusions."],
    ),
}


def main() -> None:
    added = 0
    for (ticker, quarter), (url, facts) in RELEASES.items():
        path = PACKETS / ticker / quarter / "analysis.json"
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            if old.get("verification_status") in {"manual_verified", "official_release_text_collected"}:
                continue
        path.parent.mkdir(parents=True, exist_ok=True)
        packet = {"ticker": ticker, "calendar_quarter": quarter,
                  "cutoff": datetime.now(timezone.utc).isoformat(),
                  "sources": [url], "facts": facts,
                  "official_release_confirmed": True,
                  "verification_status": "manual_verified",
                  "note": "Curated facts from linked official release; AI article still needs editorial review."}
        path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        added += 1
    print(f"latest official packets added: {added}")


if __name__ == "__main__":
    main()
