"""
Normalize the raw realized-issuance JSON into data/clean/realized.csv.

Dedup removes ONLY exact-identical rows (pagination overlap). The same bond
code (ZQ_CODE) legitimately recurs for re-taps (续发) — distinct issuance events
that must be kept; deduping on code would undercount (~¥12k亿 in testing).

    python src/parse_realized.py
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from celma import DATA_RAW, DATA_CLEAN, canonicalize_issuer

TYPE_EN = {"专项债券": "special", "一般债券": "general"}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _d(v):
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def main() -> None:
    files = sorted(glob.glob(str(DATA_RAW / "realized_json" / "page_*.json")))
    if not files:
        sys.exit("no data/raw/realized_json/*.json — run scrape_realized.py first")
    recs = []
    for fp in files:
        recs += json.loads(Path(fp).read_text(encoding="utf-8")).get("data", [])
    rows = []
    for r in recs:
        if r.get("newFlag") or r.get("ZQ_NAME") in (None, "", "合计"):
            continue
        rows.append({
            "issuer": canonicalize_issuer(r.get("AD_NAME", "")) or r.get("AD_NAME"),
            "set_year": r.get("SET_YEAR"),
            "bond_name": r.get("ZQ_NAME"),
            "bond_code": r.get("ZQ_CODE"),
            "issue_date": _d(r.get("ZQ_FXTIME")),
            "bond_type": r.get("ZQLX_NAME"),
            "bond_type_en": TYPE_EN.get(r.get("ZQLX_NAME")),
            "tenor_label": r.get("ZQQX_NAME"),
            "coupon_pct": _f(r.get("LL")),
            "amount_yi": _f(r.get("FX_AMT")),
            "new_amount_yi": _f(r.get("XZZQ_AMT")),
            "refinance_amount_yi": _f(r.get("ZRZZQ_AMT")),
            "swap_amount_yi": _f(r.get("ZHZQ_AMT")),
        })
    df = (pd.DataFrame(rows).drop_duplicates()
          .sort_values("issue_date", ascending=False, na_position="last").reset_index(drop=True))
    DATA_CLEAN.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_CLEAN / "realized.csv", index=False, encoding="utf-8-sig")
    print(f"realized.csv: {len(df)} bonds | {df['issuer'].nunique()} issuers | "
          f"{df['issue_date'].min()} .. {df['issue_date'].max()} | gross {df['amount_yi'].sum():,.0f} 亿")


if __name__ == "__main__":
    main()
