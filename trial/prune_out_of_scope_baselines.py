"""Remove only generated index Markdown outside the selected report dates."""
from __future__ import annotations

import json
import os

from research_pipeline import DATA, RESEARCH, event_quarters


def main() -> None:
    start = os.getenv("RESEARCH_FROM_DATE", "2026-01-01")
    end = os.getenv("RESEARCH_THROUGH_DATE", "2026-12-31")
    events = json.loads(DATA.read_text(encoding="utf-8"))["calendar"]["formal"]["events"]
    quarters = event_quarters(events)
    removed = 0
    for event in events:
        if start <= event["date"] <= end or event["id"] not in quarters:
            continue
        folder = RESEARCH / event["ticker"] / quarters[event["id"]]
        for stage in ("preview", "analysis"):
            meta = folder / f"{stage}.meta.json"
            if not meta.exists():
                continue
            item = json.loads(meta.read_text(encoding="utf-8"))
            if item.get("status") != "baseline_source_limited":
                continue
            doc = folder / f"{stage}.md"
            if doc.exists():
                doc.unlink()
                removed += 1
            meta.unlink()
    print(f"out-of-scope generated baselines removed: {removed}")


if __name__ == "__main__":
    main()
