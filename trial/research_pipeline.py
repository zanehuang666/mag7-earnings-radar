"""Isolated first-tier quarterly Markdown index and optional sourced generation.

Without model credentials or an explicit official source packet, this records
pending work and never fabricates a historical Preview or completed Analysis.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "v13-based" / "data" / "mag7.json"
RESEARCH = ROOT / "research"
PACKETS = ROOT / "source-packets"
PROMPT = ROOT / "prompts" / "quarterly-research.txt"
FIRST = {"MSFT", "AMZN", "META", "GOOGL", "ORCL", "SPACEX", "NVDA", "AVGO", "AMD", "MU", "INTC", "SKHX", "SMSN"}


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def quarter(event: dict) -> str:
    """Calendar quarter in which the fiscal period ended, not fiscal FY/Q."""
    period = str(event.get("fiscal_period") or "")
    direct = re.search(r"\b(20\d{2})Q([1-4])\b", period)
    if direct:
        return f"{direct.group(1)}Q{direct.group(2)}"
    month = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[ /-]?(20\d{2})\b", period)
    if month:
        m = datetime.strptime(month.group(1), "%b").month
        return f"{month.group(2)}Q{(m - 1) // 3 + 1}"
    day = datetime.fromisoformat(event["date"]).date()
    year, zero_month = divmod(day.year * 12 + day.month - 1 - 2, 12)
    return f"{year}Q{zero_month // 3 + 1}"


def advance(q: str, count: int) -> str:
    year, number = int(q[:4]), int(q[-1])
    year, index = divmod(year * 4 + number - 1 + count, 4)
    return f"{year}Q{index + 1}"


def event_quarters(events: list[dict]) -> dict[str, str]:
    by_company = defaultdict(list)
    for event in events:
        if event["ticker"] in FIRST:
            by_company[event["ticker"]].append(event)
    result = {}
    for company_events in by_company.values():
        ordered = sorted(company_events, key=lambda e: e["date"])
        reported = [e for e in ordered if e["status"] == "reported"]
        for event in reported:
            result[event["id"]] = quarter(event)
        if reported:
            last = max(reported, key=lambda e: e["date"])
            future = [e for e in ordered if e["status"] != "reported" and e["date"] > last["date"]]
            for index, event in enumerate(future, 1):
                result[event["id"]] = advance(result[last["id"]], index)
    return result


def official_packet(ticker: str, q: str, stage: str):
    path = PACKETS / ticker / q / f"{stage}.json"
    packet = load(path, None)
    if not packet or not packet.get("sources") or not packet.get("facts"):
        return None
    if packet.get("verification_status") in ("source_review_pending", "annual_filing_q4_review_needed"):
        return None
    if stage == "analysis" and not packet.get("official_release_confirmed"):
        return None
    return packet


def call_model(prompt: str, packet: dict) -> dict:
    key, base, model = (os.getenv(name, "").strip() for name in ("PARATERA_API_KEY", "PARATERA_BASE_URL", "PARATERA_MODEL"))
    if not all((key, base, model)):
        raise RuntimeError("model credentials unavailable")
    endpoint = base.rstrip("/") + ("/chat/completions" if base.rstrip("/").endswith("/v1") else "/v1/chat/completions")
    body = {"model": model, "temperature": 0.1, "max_tokens": 6000,
            "enable_thinking": False,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}]}
    req = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=240) as response:
                result = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
        except (TimeoutError, socket.timeout):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    message = result["choices"][0]["message"]
    content = message.get("content") or message.get("reasoning_content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("model returned no JSON content")
    return json.loads(content)


def main() -> None:
    data = load(DATA, None)
    if not data:
        raise RuntimeError("build trial before research index")
    prompt_template = PROMPT.read_text(encoding="utf-8")
    index = {}
    errors = {}
    now = datetime.now(timezone.utc).isoformat()
    quarter_ids = event_quarters(data["calendar"]["formal"]["events"])
    call_limit = max(0, int(os.getenv("RESEARCH_CALL_LIMIT", "3")))
    from_date = os.getenv("RESEARCH_FROM_DATE", "2026-01-01")
    through_date = os.getenv("RESEARCH_THROUGH_DATE", "2026-12-31")
    calls = 0
    all_events = data["calendar"]["formal"]["events"]
    today = datetime.now().date().isoformat()
    prioritized = sorted(all_events, key=lambda e: (
        0 if e["ticker"] in FIRST and e["status"] != "reported" and e["date"] >= today else
        1 if e["ticker"] in FIRST and e["status"] == "reported" else 2,
        int(e["date"].replace("-", "")) if e["status"] != "reported" else -int(e["date"].replace("-", ""))))
    for event in prioritized:
        ticker = event["ticker"]
        if ticker not in FIRST:
            continue
        q = quarter_ids.get(event["id"], quarter(event))
        record = {"ticker": ticker, "quarter": q, "date": event["date"], "stages": {}}
        for stage in ("preview", "analysis"):
            folder = RESEARCH / ticker / q
            path = folder / f"{stage}.md"
            meta_path = folder / f"{stage}.meta.json"
            meta = load(meta_path, {})
            raw_packet = load(PACKETS / ticker / q / f"{stage}.json", None)
            packet = official_packet(ticker, q, stage)
            in_scope = from_date <= event["date"] <= through_date
            eligible = in_scope and (
                stage == "preview" and (event["status"] != "reported" or bool(raw_packet and raw_packet.get("historical_reconstruction")))
                or stage == "analysis" and event["status"] == "reported")
            status = ("unavailable" if not eligible else
                      "source_review_pending" if raw_packet and not packet else
                      "awaiting_model_credentials" if packet and not all(os.getenv(n) for n in ("PARATERA_API_KEY", "PARATERA_BASE_URL", "PARATERA_MODEL")) else
                      "awaiting_official_source_packet")
            existing = path.exists() and path.stat().st_size > 20
            if existing and in_scope:
                status = meta.get("status", "manual")
            can_refresh = not existing or meta.get("status") in ("generated_review_pending", "baseline_source_limited")
            if eligible and can_refresh and packet and all(os.getenv(n) for n in ("PARATERA_API_KEY", "PARATERA_BASE_URL", "PARATERA_MODEL")):
                preview_packet = load(PACKETS / ticker / q / "preview.json", {}) if stage == "analysis" else {}
                preview_meta = load(folder / "preview.meta.json", {}) if stage == "analysis" else {}
                if stage == "analysis" and (preview_packet.get("historical_reconstruction") or preview_meta.get("status") == "baseline_source_limited"):
                    packet["preview_status"] = "无同期 Preview；另有事后历史资料重建稿，不可当作当时预测复核"
                elif stage == "analysis" and not (folder / "preview.md").exists():
                    packet["preview_status"] = "无同期 Preview"
                elif stage == "analysis":
                    packet["frozen_preview"] = (folder / "preview.md").read_text(encoding="utf-8")
                cutoff = packet.get("cutoff", now)
                if stage == "preview" and cutoff[:10] >= event["date"]:
                    status = "cutoff_after_event_date"
                else:
                    digest = hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    if meta.get("source_digest") != digest:
                        if calls >= call_limit:
                            status = "queued_call_limit"
                            record["stages"][stage] = {"status": status, "path": f"research/{ticker}/{q}/{stage}.md" if path.exists() else None,
                                                        "source_packet": f"source-packets/{ticker}/{q}/{stage}.json", "cutoff": meta.get("cutoff"),
                                                        "source_digest": meta.get("source_digest"),
                                                        "historical_reconstruction": bool(raw_packet and raw_packet.get("historical_reconstruction"))}
                            continue
                        try:
                            calls += 1
                            prompt = prompt_template.format(company=event["company"], ticker=ticker, quarter=q,
                                                            stage=stage, cutoff=cutoff)
                            if packet.get("historical_reconstruction"):
                                prompt += "\n这是事后重建的历史前瞻，不是当时真实发表的预测。正文标题和开头必须明确写‘历史资料重建’，且只能使用资料截止日前已公开的来源；不得暗示本稿写于财报公布前。"
                            for draft_attempt in range(2):
                                result = call_model(prompt, packet)
                                md = result.get("markdown", "").strip()
                                valid = (md.startswith("# ") and len(result.get("reader_questions", [])) == 3
                                         and bool(result.get("english_draft")) and bool(result.get("fact_checks"))
                                         and (not packet.get("historical_reconstruction") or "历史资料重建" in md[:250])
                                         and any(url in md for url in packet["sources"]))
                                if valid:
                                    break
                                if draft_attempt == 0:
                                    prompt += "\n上次格式或来源核验未通过。请严格输出完整 JSON、恰好三条读者问题，并在 Markdown 中直接链接所附官方来源。"
                            if not valid:
                                raise ValueError("invalid draft, reader check, reconstruction label, or citation after retry")
                            folder.mkdir(parents=True, exist_ok=True)
                            if existing:
                                history = folder / "history"
                                history.mkdir(exist_ok=True)
                                label = re.sub(r"[^0-9]", "", now)[:14]
                                shutil.copyfile(path, history / f"{stage}-{label}.md")
                            path.write_text(md + "\n", encoding="utf-8")
                            meta = {"status": "generated_review_pending", "source_digest": digest,
                                    "cutoff": cutoff, "generated_at": now, "sources": packet["sources"]}
                            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                            (folder / f"{stage}.checks.json").write_text(json.dumps({k: result.get(k) for k in ("english_draft", "reader_questions", "fact_checks")}, ensure_ascii=False, indent=2), encoding="utf-8")
                            status = meta["status"]
                        except Exception as exc:
                            errors[f"{ticker}/{q}/{stage}"] = str(exc)
                            status = "generation_failed"
            record["stages"][stage] = {"status": status, "path": f"research/{ticker}/{q}/{stage}.md" if in_scope and path.exists() else None,
                                        "source_packet": f"source-packets/{ticker}/{q}/{stage}.json" if raw_packet else None,
                                        "cutoff": meta.get("cutoff"), "source_digest": meta.get("source_digest"),
                                        "historical_reconstruction": bool(raw_packet and raw_packet.get("historical_reconstruction"))}
        index[event["id"]] = record
    out = {"generated_at": now, "events": index, "errors": errors, "model_calls": calls, "call_limit": call_limit,
           "note": "Drafts need source and editorial review; old structured summaries are not used for first-tier reading."}
    (ROOT / "research-index.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"research index: {len(index)} events, {len(errors)} generation errors")
    if errors:
        print(json.dumps(errors, ensure_ascii=False), file=sys.stderr)
        if os.getenv("RESEARCH_FAIL_ON_ERROR") == "1":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
