"""Refresh trial Markdown and its static/offline readers without report skills.

This is safe to run in GitHub Actions on an isolated trial branch. It does not
touch the live site's frontend or deploy Pages.
"""
from __future__ import annotations

import base64
import json
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
    run("seed_markdown_baselines.py")
    run("research_pipeline.py")
    run("coverage_report.py")
    for source, dest in ((ROOT / "research-index.json", SITE / "data/research_index.json"),
                         (ROOT / "research-coverage.md", SITE / "data/research-coverage.md")):
        shutil.copyfile(source, dest)
    shutil.copytree(ROOT / "research", SITE / "research", dirs_exist_ok=True)
    shutil.copytree(ROOT / "source-packets", SITE / "source-packets", dirs_exist_ok=True)
    page = SITE / "calendar.html"
    html = page.read_text(encoding="utf-8")
    marker = "<script>const QUARTER_RESEARCH="
    if html.count(marker) != 1:
        raise RuntimeError("trial page research marker changed")
    prefix, rest = html.split(marker, 1)
    _, suffix = rest.rsplit("</script></body>", 1)
    index = json.loads((ROOT / "research-index.json").read_text(encoding="utf-8"))["events"]
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
    (SITE / "trial-offline.html").write_text(html.replace("<script>", shim + "<script>", 1), encoding="utf-8")
    print(f"refreshed trial page and offline reader: {len(index)} events")


if __name__ == "__main__":
    main()
