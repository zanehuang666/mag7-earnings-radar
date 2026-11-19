"""Seed the next-quarter Preview packet from the last official results.

This is a first draft source set. It never uses an already-published target
quarter to write a historical Preview, and it never overwrites manual packets.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from research_pipeline import DATA, FIRST, PACKETS, event_quarters


def prior_release_date(packet: dict, event: dict) -> str:
    """The prior release must be dated before the target earnings event."""
    return str(packet.get("release_date") or packet.get("filing_date") or event["date"])[:10]


def prior_facts(packet: dict) -> list[str]:
    # Some newsroom pages add today's related-article links to old releases.
    return [str(fact).split(" Related content ", 1)[0] for fact in packet.get("facts", [])]


def seed_historical(reported: list[dict], mapped: dict[str, str], ticker: str) -> int:
    """Create clearly labelled reconstructions from a *previous* official release."""
    created = 0
    for prior, target in zip(reported, reported[1:]):
        prior_q, target_q = mapped[prior["id"]], mapped[target["id"]]
        source_path = PACKETS / ticker / prior_q / "analysis.json"
        new_path = PACKETS / ticker / target_q / "preview.json"
        if not source_path.exists() or new_path.exists():
            continue
        source = json.loads(source_path.read_text(encoding="utf-8"))
        if source.get("verification_status") not in {"manual_verified", "official_release_text_collected", "official_filing_text_collected"}:
            continue
        published = prior_release_date(source, prior)
        if not published or published >= target["date"] or not source.get("sources") or not source.get("facts"):
            continue
        packet = {"ticker": ticker, "calendar_quarter": target_q,
                  "target_event_date": target["date"], "prior_quarter": prior_q,
                  "prior_release_date": published, "cutoff": published + "T23:59:59",
                  "sources": source["sources"], "facts": prior_facts(source),
                  "verification_status": source["verification_status"],
                  "historical_reconstruction": True,
                  "note": "Retrospective reconstruction using only the previous official release. "
                          "It was not actually written before target-quarter earnings. "
                          "Do not describe it as a contemporaneous forecast."}
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created += 1
    return created


def main() -> None:
    events = json.loads(DATA.read_text(encoding="utf-8"))["calendar"]["formal"]["events"]
    mapped = event_quarters(events)
    created = 0
    for ticker in FIRST - {"SPACEX"}:
        reported = sorted((e for e in events if e["ticker"] == ticker and e["status"] == "reported"), key=lambda e: e["date"])
        future = sorted((e for e in events if e["ticker"] == ticker and e["status"] != "reported"), key=lambda e: e["date"])
        created += seed_historical(reported, mapped, ticker)
        if not reported or not future:
            continue
        prior, target = reported[-1], future[0]
        prior_q, target_q = mapped[prior["id"]], mapped[target["id"]]
        prior_packet = PACKETS / ticker / prior_q / "analysis.json"
        new_packet = PACKETS / ticker / target_q / "preview.json"
        if not prior_packet.exists():
            continue
        source = json.loads(prior_packet.read_text(encoding="utf-8"))
        if not source.get("sources") or not source.get("facts"):
            continue
        previous = json.loads(new_packet.read_text(encoding="utf-8")) if new_packet.exists() else {}
        if previous and (previous.get("prior_quarter") != prior_q or previous.get("historical_reconstruction")):
            continue
        changed = any(previous.get(key) != source.get(key) for key in ("sources", "facts", "verification_status"))
        if previous and not changed:
            continue
        packet = {"ticker": ticker, "calendar_quarter": target_q,
                  "target_event_date": target["date"], "date_status": target["status"],
                  "cutoff": datetime.now(timezone.utc).isoformat(),
                  "sources": source["sources"], "facts": source["facts"],
                  "prior_quarter": prior_q,
                  "verification_status": source.get("verification_status", "source_review_pending"),
                  "note": "Only prior-quarter materials are provided. Target-quarter results are not yet public. "
                          "Date is projected or estimated unless company IR confirms it."}
        new_packet.parent.mkdir(parents=True, exist_ok=True)
        new_packet.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created += 1
    print(f"preview packets created: {created}")


if __name__ == "__main__":
    main()
