"""One-time source packets for first 2026 historical Preview reconstructions.

Each packet uses the company's previous earnings release, published before the
2026 target event. These drafts must remain labelled as retrospective work.
"""
from __future__ import annotations

import json
from pathlib import Path

from collect_ir_packets_2026 import source_text

ROOT = Path(__file__).resolve().parent / "source-packets"
RELEASES = {
    ("AMD", "2025Q4", "2026-02-03"): ("2025-11-04", "AMD Reports Third Quarter 2025", "https://ir.amd.com/news-events/press-releases/detail/1265/amd-reports-third-quarter-2025-financial-results"),
    ("AMZN", "2025Q4", "2026-02-05"): ("2025-10-30", "Amazon.com Announces Third Quarter Results", "https://ir.aboutamazon.com/news-release/news-release-details/2025/Amazon-com-Announces-Third-Quarter-Results/default.aspx"),
    ("AVGO", "2026Q1", "2026-03-04"): ("2025-12-11", "Broadcom Inc. Announces Fourth Quarter and Fiscal Year 2025", "https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-fourth-quarter-and-fiscal-year-2025"),
    ("GOOGL", "2025Q4", "2026-02-04"): ("2025-10-29", "Alphabet Announces Third Quarter 2025", "https://s206.q4cdn.com/479360582/files/doc_news/2025/Oct/29/attachments/2025q3-alphabet-earnings-release.pdf"),
    ("META", "2025Q4", "2026-01-28"): ("2025-10-29", "Meta Reports Third Quarter 2025", "https://investor.atmeta.com/investor-news/press-release-details/2025/Meta-Reports-Third-Quarter-2025-Results/default.aspx"),
    ("MSFT", "2025Q4", "2026-01-28"): ("2025-10-29", "Microsoft Cloud", "https://www.microsoft.com/en-us/Investor/earnings/FY-2026-Q1/press-release-webcast"),
    ("MU", "2026Q1", "2026-03-18"): ("2025-12-17", "Reports Results for the First Quarter of Fiscal 2026", "https://investors.micron.com/news/press-release/2025/Micron-Technology-Inc--Reports-Results-for-the-First-Quarter-of-Fiscal-2026-12-17-2025/default.aspx"),
    ("NVDA", "2026Q1", "2026-02-25"): ("2025-11-19", "NVIDIA Announces Financial Results for Third Quarter Fiscal 2026", "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-third-quarter-fiscal-2026"),
    ("ORCL", "2026Q1", "2026-03-10"): ("2025-12-10", "Oracle Announces Fiscal Year 2026 Second Quarter", "https://investor.oracle.com/investor-news/news-details/2025/Oracle-Announces-Fiscal-Year-2026-Second-Quarter-Financial-Results/"),
}


def main() -> None:
    for (ticker, target_quarter, target_date), (date, title, url) in RELEASES.items():
        path = ROOT / ticker / target_quarter / "preview.json"
        if path.exists():
            continue
        try:
            text = source_text(url)
            start = text.casefold().find(title.casefold())
            if start < 0 or date[:4] not in text or date >= target_date:
                raise ValueError("prior release title/date did not match")
            excerpt = text[start:start + 14000]
            if len(excerpt) < 1500:
                raise ValueError("prior source extract too short")
            packet = {"ticker": ticker, "calendar_quarter": target_quarter,
                      "target_event_date": target_date, "prior_release_date": date,
                      "cutoff": date + "T23:59:59", "sources": [url],
                      "facts": [excerpt[i:i + 1750] for i in range(0, len(excerpt), 1750)],
                      "verification_status": "official_release_text_collected",
                      "historical_reconstruction": True,
                      "note": "Retrospective reconstruction using only the previous official release. Not a contemporaneous forecast."}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(ticker, target_quarter, "prior release collected", flush=True)
        except Exception as exc:
            print(ticker, target_quarter, "FAILED", str(exc)[:180], flush=True)


if __name__ == "__main__":
    main()
