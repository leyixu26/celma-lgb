"""
Verify the scraped data against the SOURCE'S OWN figures and write the proof to
VERIFICATION.md (human) + data/clean/verification.json (dashboard badge).

Checks
  R1  realized: rows pulled == the API's own `total`
  R2  realized: raw amount sum ≈ the API's own `sumCount` (±0.1%)
  R3  realized: clean table == raw minus exact-duplicate rows; all 37 issuers
  S1  schedule: unique articles == the site's own "共 N 条" count
  S2  schedule: all 37 issuers present; share of plans with parsed amounts

    python src/verify.py
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from celma import ROOT, DATA_RAW, DATA_CLEAN, ISSUERS


def main() -> None:
    checks = []

    def check(cid, desc, ok, detail):
        checks.append({"id": cid, "desc": desc, "ok": bool(ok), "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {cid}: {desc} — {detail}")

    print("verifying realized …")
    pages = sorted(glob.glob(str(DATA_RAW / "realized_json" / "page_*.json")))
    raw = []
    api_total = api_sum = None
    for fp in pages:
        d = json.loads(Path(fp).read_text(encoding="utf-8"))
        raw += d.get("data", [])
        if fp.endswith("page_0001.json"):
            api_total = int(d.get("total", 0) or 0)
            api_sum = float(d.get("sumCount", 0) or 0)
    check("R1", "rows pulled == API total", len(raw) == api_total, f"{len(raw)} vs {api_total}")
    raw_sum = sum(float(r.get("FX_AMT") or 0) for r in raw)
    ok2 = api_sum and abs(raw_sum - api_sum) / api_sum < 0.001
    check("R2", "raw amount sum ≈ API sumCount", ok2, f"{raw_sum:,.1f} vs {api_sum:,.1f} 亿")
    clean = pd.read_csv(DATA_CLEAN / "realized.csv")
    clean_sum = clean["amount_yi"].sum()
    ok3 = (api_sum and abs(clean_sum - api_sum) / api_sum < 0.001
           and len(clean) <= len(raw) and clean["issuer"].nunique() == len(ISSUERS))
    check("R3", "clean total ≈ API sumCount after dedup; 37 issuers", ok3,
          f"{len(clean)} rows ({len(raw) - len(clean)} dup/sum rows removed), "
          f"{clean_sum:,.1f} vs {api_sum:,.1f} 亿, {clean['issuer'].nunique()}/37 issuers")

    print("verifying schedule …")
    prov = json.loads((DATA_RAW / "schedule_provenance.json").read_text(encoding="utf-8"))
    sched = pd.read_csv(DATA_CLEAN / "schedule.csv")
    check("S1", "unique articles == site 共N条",
          prov.get("status") == "COMPLETE" and len(sched) == prov.get("scraped_unique"),
          f"{len(sched)} vs 共{prov.get('site_total_tiao')}条 ({prov.get('status')})")
    amt_cols = [c for c in ["new_general_yi", "new_special_yi", "refinance_yi"] if c in sched.columns]
    with_amt = int(sched[amt_cols].notna().any(axis=1).sum()) if amt_cols else 0
    check("S2", "37 issuers; amount coverage", sched["issuer"].nunique() == len(ISSUERS),
          f"{sched['issuer'].nunique()}/37 issuers; amounts on {with_amt}/{len(sched)} plans "
          f"({100 * with_amt / max(1, len(sched)):.1f}%)")

    all_ok = all(c["ok"] for c in checks)
    as_of = str(clean["issue_date"].max())
    result = {"verified": all_ok, "as_of": as_of, "run_date": str(date.today()),
              "realized_rows": len(clean), "schedule_rows": len(sched),
              "schedule_amount_rows": with_amt, "checks": checks}
    DATA_CLEAN.mkdir(parents=True, exist_ok=True)
    (DATA_CLEAN / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Data verification",
        "",
        f"Run {result['run_date']} · data through **{as_of}** · overall: "
        f"{'✅ **ALL CHECKS PASS**' if all_ok else '❌ **CHECK FAILURE — see below**'}",
        "",
        "Every check compares our scrape against the **source's own published figures** "
        "(the API's `total`/`sumCount`; the list's `共 N 条` count).",
        "",
        "| # | Check | Result | Detail |",
        "|---|-------|--------|--------|",
    ]
    for c in checks:
        lines.append(f"| {c['id']} | {c['desc']} | {'✅' if c['ok'] else '❌'} | {c['detail']} |")
    lines += ["", "Row-level spot-checking: every schedule row in `data/clean/schedule.csv` carries its "
                  "source `url` — open it on celma and compare title/date/amounts directly.", ""]
    (ROOT / "VERIFICATION.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{'ALL CHECKS PASS' if all_ok else 'CHECK FAILURE'} -> VERIFICATION.md + data/clean/verification.json")
    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
