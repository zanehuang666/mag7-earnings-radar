"""Refresh trial Markdown and its static/offline readers without report skills.

This is safe to run in GitHub Actions on an isolated trial branch. It does not
touch the live site's frontend or deploy Pages.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "v13-based"


def run(script: str) -> None:
    subprocess.run([sys.executable, str(ROOT / script)], check=True)


def main() -> None:
    run("prepare_previews.py")
    run("prune_out_of_scope_baselines.py")
    run("seed_markdown_baselines.py")
    run("research_pipeline.py")
    run("coverage_report.py")
    for source, dest in ((ROOT / "research-index.json", SITE / "data/research_index.json"),
                         (ROOT / "research-coverage.md", SITE / "data/research-coverage.md")):
        shutil.copyfile(source, dest)
    shutil.copytree(ROOT / "research", SITE / "research", dirs_exist_ok=True)
    for file in (SITE / "research").rglob("*.md"):
        if not (ROOT / "research" / file.relative_to(SITE / "research")).exists():
            file.unlink()
    shutil.copytree(ROOT / "source-packets", SITE / "source-packets", dirs_exist_ok=True)
    page = SITE / "calendar.html"
    html = re.sub(r"<!-- TRIAL_OFFLINE_SHIM_START -->.*?<!-- TRIAL_OFFLINE_SHIM_END -->", "", page.read_text(encoding="utf-8"), flags=re.S)
    for name in ("nasdaq-history-2024.json", "foreign-history-2024.json"):
        html = re.sub(rf'<a href="\./data/{name}"[^>]*>.*?</a>', '', html)
    marker = "<script>const QUARTER_RESEARCH="
    if html.count(marker) != 1:
        raise RuntimeError("trial page research marker changed")
    prefix, rest = html.split(marker, 1)
    _, suffix = rest.rsplit("</script></body>", 1)
    index = json.loads((ROOT / "research-index.json").read_text(encoding="utf-8"))["events"]
    source_status = {}
    for event in index.values():
        if not event["date"].startswith("2026-"):
            continue
        ticker, quarter = event["ticker"], event["quarter"]
        for stage in ("preview", "analysis"):
            packet_path = ROOT / "source-packets" / ticker / quarter / f"{stage}.json"
            packet = json.loads(packet_path.read_text(encoding="utf-8")) if packet_path.exists() else {}
            source_status[f"{ticker}/{quarter}/{stage}"] = {"status": packet.get("verification_status", "missing"),
                                                             "source_count": len(packet.get("sources", []))}
    (SITE / "data/source_packet_coverage.json").write_text(json.dumps(source_status, ensure_ascii=False, indent=2), encoding="utf-8")
    viewer = (ROOT / "research_viewer.js").read_text(encoding="utf-8")
    html = prefix + marker + json.dumps(index, ensure_ascii=False) + ";" + viewer + "</script></body>" + suffix
    page.write_text(html, encoding="utf-8")
    payload = {path.name: path.read_text(encoding="utf-8") for path in (SITE / "data").glob("*.json")}
    payload.update({"./" + path.relative_to(SITE).as_posix(): path.read_text(encoding="utf-8")
                    for path in (SITE / "research").rglob("*.md")})
    payload.update({"./" + path.relative_to(SITE).as_posix(): path.read_text(encoding="utf-8")
                    for path in (SITE / "source-packets").rglob("*.json")})
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    shim = ("<script>const embedded=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('" + encoded +
            "'),c=>c.charCodeAt(0))));const originalFetch=window.fetch.bind(window);" +
            "window.fetch=(input,options)=>{const path=String(input).split('?')[0],key=embedded[path]!==undefined?path:path.split('/').pop();" +
            "return embedded[key]===undefined?originalFetch(input,options):Promise.resolve(new Response(embedded[key],{status:200}));};</script>")
    offline = html.replace("<script>", "<!-- TRIAL_OFFLINE_SHIM_START -->" + shim + "<!-- TRIAL_OFFLINE_SHIM_END --><script>", 1)
    page.write_text(offline, encoding="utf-8")
    (SITE / "trial-offline.html").write_text(offline, encoding="utf-8")
    print(f"refreshed trial page and offline reader: {len(index)} events")


if __name__ == "__main__":
    main()
