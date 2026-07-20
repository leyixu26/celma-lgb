"""
One-command refresh: scrape -> parse -> verify -> analyze -> dashboard [-> publish].

    python run_all.py                # refresh everything locally
    python run_all.py --publish      # ... then push data+outputs+dashboard to GitHub
    python run_all.py --skip-scrape  # rebuild analysis/dashboard from cached raw data

verify.py is a HARD GATE: if any completeness check fails, the run stops and
nothing is published.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def run(script: str, *args: str) -> None:
    print(f"\n=== {script} {' '.join(args)} ===")
    r = subprocess.run([sys.executable, str(SRC / script), *args], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"STOPPED: {script} failed (exit {r.returncode}).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true", help="push refreshed data to GitHub (needs GITHUB_TOKEN)")
    ap.add_argument("--skip-scrape", action="store_true", help="rebuild from cached raw data only")
    args = ap.parse_args()

    if not args.skip_scrape:
        run("scrape_realized.py")
        run("scrape_schedule.py")
    run("parse_realized.py")
    run("parse_schedule.py")
    run("verify.py")            # hard gate
    run("analyze.py")
    run("build_dashboard.py")
    if args.publish:
        print("\n=== publish.py ===")
        r = subprocess.run([sys.executable, str(ROOT / "publish.py")], cwd=ROOT)
        if r.returncode != 0:
            sys.exit("publish failed — data is refreshed locally but NOT pushed.")
    print("\nDONE.")


if __name__ == "__main__":
    main()
