"""Add manually checked 2026 earnings facts from company investor-relations releases."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "source-packets"

RELEASES = {
    ("AVGO", "2026Q1"): (
        "2026-03-04",
        "https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-first-quarter-fiscal-year-2026-financial",
        ["Fiscal Q1 2026 ended February 1, 2026; revenue USD 19.311 billion, up 29% year over year.",
         "AI semiconductor revenue USD 8.4 billion, up 106% year over year; this is the CEO's stated AI measure.",
         "Adjusted EBITDA USD 13.128 billion, 68% of revenue; GAAP diluted EPS USD 1.50 and non-GAAP diluted EPS USD 2.05.",
         "Operating cash flow USD 8.260 billion, capex USD 0.250 billion, free cash flow USD 8.010 billion.",
         "Next-quarter company guidance: total revenue approximately USD 22.0 billion and AI semiconductor revenue USD 10.7 billion; these are forecasts."],
    ),
    ("AVGO", "2026Q2"): (
        "2026-06-03",
        "https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-second-quarter-fiscal-year-2026-financial",
        ["Fiscal Q2 2026 ended May 3, 2026; revenue USD 22.187 billion, up 48% year over year.",
         "AI semiconductor revenue USD 10.8 billion, up 143% year over year; this is the CEO's stated AI measure.",
         "Adjusted EBITDA USD 15.244 billion, 69% of revenue; GAAP diluted EPS USD 1.91 and non-GAAP diluted EPS USD 2.44.",
         "Operating cash flow USD 10.493 billion, capex USD 0.231 billion, free cash flow USD 10.262 billion.",
         "Next-quarter company guidance: total revenue approximately USD 29.4 billion; this is a forecast."],
    ),
    ("META", "2025Q4"): (
        "2026-01-28",
        "https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-Fourth-Quarter-and-Full-Year-2025-Results/default.aspx",
        ["Quarter ended December 31, 2025; quarterly revenue USD 59.893 billion, up 24% year over year.",
         "Quarterly operating income USD 24.745 billion and operating margin 41%; diluted EPS USD 8.88.",
         "Family daily active people averaged 3.58 billion in December 2025, up 7% year over year.",
         "Quarterly capital expenditure including finance leases USD 22.14 billion; operating cash flow USD 36.21 billion; free cash flow USD 14.08 billion.",
         "Company Q1 2026 revenue outlook USD 53.5–56.5 billion; this is a forecast."],
    ),
    ("META", "2026Q1"): (
        "2026-04-29",
        "https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-First-Quarter-2026-Results/default.aspx",
        ["Quarter ended March 31, 2026; revenue USD 56.311 billion, up 33% year over year.",
         "Operating income USD 22.872 billion; operating margin 41%; diluted EPS USD 10.44.",
         "Reported net income includes an USD 8.03 billion income tax benefit; excluding it would reduce diluted EPS by USD 3.13, per company release.",
         "Family daily active people averaged 3.56 billion in March 2026, up 4% year over year; ad impressions increased 19% year over year."],
    ),
    ("META", "2026Q2"): (
        "2026-07-29",
        "https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-Second-Quarter-2026-Results/default.aspx",
        ["Quarter ended June 30, 2026; revenue USD 60.801 billion, up 28% year over year.",
         "Operating income USD 18.775 billion, down 8% year over year; operating margin 31%, versus 43% a year earlier; diluted EPS USD 6.18.",
         "Costs and expenses USD 42.026 billion include USD 2.40 billion of legal charges and USD 1.18 billion of severance from May 2026 headcount reduction.",
         "Family daily active people averaged 3.60 billion in June 2026; ad impressions grew 14% and average ad price grew 12% year over year.",
         "Capital expenditure including finance leases USD 31.08 billion; company Q3 revenue outlook USD 61–64 billion is a forecast."],
    ),
    ("ORCL", "2026Q1"): (
        "2026-03-10",
        "https://investor.oracle.com/investor-news/news-details/2026/Oracle-Announces-Fiscal-Year-2026-Third-Quarter-Financial-Results/default.aspx",
        ["Oracle fiscal Q3 2026 released March 10, 2026; total revenue USD 17.2 billion, up 22% year over year in USD.",
         "Cloud revenue (IaaS plus SaaS) USD 8.9 billion, up 44%; cloud infrastructure revenue USD 4.9 billion, up 84%; cloud applications USD 4.0 billion, up 13%.",
         "Remaining performance obligations USD 553 billion, up 325% year over year; this is contracted backlog, not recognized revenue.",
         "GAAP EPS USD 1.27 and non-GAAP EPS USD 1.79; do not conflate the two measures."],
    ),
    ("ORCL", "2026Q2"): (
        "2026-06-10",
        "https://investor.oracle.com/investor-news/news-details/2026/Oracle-Announces-Record-Q4-and-FY-2026-Results-Driven-by-Cloud-Infrastructure--Cloud-Applications/default.aspx",
        ["Oracle fiscal Q4 2026 released June 10, 2026; total quarterly revenue USD 19.2 billion, up 21% year over year.",
         "Quarterly cloud revenue (IaaS plus SaaS) USD 9.9 billion, up 47%; cloud infrastructure USD 5.8 billion, up 93%; cloud applications USD 4.1 billion, up 10%.",
         "Remaining performance obligations increased from USD 553 billion to USD 638 billion during the quarter; this is contracted backlog, not recognized revenue.",
         "Quarterly GAAP operating income USD 6.1 billion and non-GAAP operating income USD 8.6 billion; GAAP EPS USD 1.45 and non-GAAP EPS USD 2.11."],
    ),
}


def main() -> None:
    created = 0
    for (ticker, quarter), (date, url, facts) in RELEASES.items():
        path = ROOT / ticker / quarter / "analysis.json"
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if previous.get("verification_status") not in (None, "official_source_missing"):
            continue
        packet = {"ticker": ticker, "calendar_quarter": quarter, "release_date": date,
                  "cutoff": date + "T23:59:59", "sources": [url], "facts": facts,
                  "official_release_confirmed": True, "verification_status": "manual_verified",
                  "note": "Selected facts checked against the linked company release; generated prose still requires editorial review."}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created += 1
    print(f"verified 2026 source packets added: {created}")


if __name__ == "__main__":
    main()
