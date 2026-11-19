"""Run the existing twice-daily sync in an isolated trial snapshot, then rebuild UI."""
from __future__ import annotations

import subprocess
import sys
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "source-snapshot"


def main() -> None:
    if not (SNAPSHOT / "backend").exists():
        subprocess.run([sys.executable, str(ROOT / "build_v13_trial.py")], check=True)
    data_dir = SNAPSHOT / "frontend" / "data"
    backup = {path: path.read_bytes() for path in data_dir.glob("*.json")}
    previous_calendar = json.loads((data_dir / "mag7.json").read_text(encoding="utf-8"))
    previous_errors = set(previous_calendar.get("sync", {}).get("errors", []))
    try:
        for name in ("sync_mag7_calendar.py", "sync_market_data.py", "sync_macro_events.py", "sync_msft_research.py", "sync_mag7_research.py"):
            subprocess.run([sys.executable, str(SNAPSHOT / "backend" / name)], cwd=SNAPSHOT, check=True)
            if name == "sync_mag7_calendar.py":
                current = json.loads((data_dir / "mag7.json").read_text(encoding="utf-8"))
                new_errors = set(current.get("sync", {}).get("errors", [])) - previous_errors
                if new_errors:
                    raise RuntimeError(f"calendar upstream reported {len(new_errors)} new errors; keeping previous trial")
        subprocess.run([sys.executable, str(ROOT / "fetch_history.py")], check=True)
        subprocess.run([sys.executable, str(ROOT / "backfill_history.py")], check=True)
    except Exception:
        for path, content in backup.items():
            path.write_bytes(content)
        raise
    # Scan the Korean publishers only once a day; the daily calendar scan is
    # still performed on each of the two trial refreshes.
    foreign = ROOT / "foreign-history-2024.json"
    stamp = ROOT / "foreign-history-refresh.json"
    last = json.loads(stamp.read_text(encoding="utf-8")) if stamp.exists() else {}
    today = date.today().isoformat()
    if not foreign.exists() or last.get("date") != today:
        subprocess.run([sys.executable, str(ROOT / "foreign_history.py")], check=True)
        # These source collectors preserve existing packets and write per-company
        # failure states. A blocked IR site cannot erase the last good article.
        subprocess.run([sys.executable, str(ROOT / "collect_official_packets.py"), "--fetch-official"], check=True)
        subprocess.run([sys.executable, str(ROOT / "collect_intel_packets.py")], check=False)
        subprocess.run([sys.executable, str(ROOT / "collect_sec_packets.py"), "--latest-only", "2"], check=False)
        stamp.write_text(json.dumps({"date": today}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "build_v13_trial.py")], check=True)


if __name__ == "__main__":
    main()
