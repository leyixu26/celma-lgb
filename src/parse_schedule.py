"""
Build data/clean/schedule.csv: the 发行安排 article list enriched from titles
(issuer, plan period) and joined to the parsed planned amounts on article_id.

    python src/parse_schedule.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from celma import DATA_RAW, DATA_CLEAN, enrich_schedule_row

AMOUNT_FIELDS = ["new_general_yi", "new_special_yi", "refinance_yi"]


def main() -> None:
    src = DATA_RAW / "schedule_list.jsonl"
    if not src.exists():
        sys.exit("no data/raw/schedule_list.jsonl — run scrape_schedule.py first")
    rows = [enrich_schedule_row(json.loads(ln)) for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    df = pd.DataFrame(rows)

    amt_path = DATA_RAW / "schedule_amounts.csv"
    if amt_path.exists():
        amt = pd.read_csv(amt_path, dtype={"article_id": str})
        keep = ["article_id"] + [c for c in AMOUNT_FIELDS if c in amt.columns]
        df = df.merge(amt[keep].drop_duplicates("article_id"), on="article_id", how="left")
        df["total_planned_yi"] = df[[c for c in AMOUNT_FIELDS if c in df.columns]].sum(axis=1, min_count=1)

    df = df.sort_values("publish_date", ascending=False, na_position="last").reset_index(drop=True)
    DATA_CLEAN.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_CLEAN / "schedule.csv", index=False, encoding="utf-8-sig")
    with_amt = int(df[AMOUNT_FIELDS].notna().any(axis=1).sum()) if AMOUNT_FIELDS[0] in df.columns else 0
    print(f"schedule.csv: {len(df)} plans | {df['issuer'].nunique()} issuers | "
          f"amounts on {with_amt}/{len(df)} | periods {df['plan_period'].dropna().min()} .. {df['plan_period'].dropna().max()}")


if __name__ == "__main__":
    main()
