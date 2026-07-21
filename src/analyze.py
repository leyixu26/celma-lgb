"""
Reconcile the SCHEDULE (planned) against REALIZED issuance and score each issuer.
Definitions and formulas: docs/METHODOLOGY.md §5.

Outputs (data/clean/): reconciliation.csv (issuer × month), scorecard.csv,
national_monthly.csv. Plus outputs/: celma_lgb_analysis.xlsx and two charts.

Comparability note: planned = 新增一般 + 新增专项 + 再融资 (the schedule tables);
realized_comparable = new + refinance, EXCLUDING swap (置换, not scheduled).

    python src/analyze.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from celma import DATA_CLEAN, OUTPUTS

try:
    from chinese_calendar import is_workday as _cc_workday
except Exception:  # noqa: BLE001
    _cc_workday = None


# ---------------------------------------------------------------- calendar
def is_workday(d: date) -> bool:
    if _cc_workday:
        try:
            return _cc_workday(d)
        except (NotImplementedError, ValueError, KeyError):
            pass
    return d.weekday() < 5


def working_days(a: date, b: date) -> int:
    """Signed working days from a to b (China calendar incl. 调休 where covered)."""
    if a == b:
        return 0
    lo, hi = (a, b) if b > a else (b, a)
    n, d = 0, lo + timedelta(days=1)
    while d <= hi:
        n += is_workday(d)
        d += timedelta(days=1)
    return n if b > a else -n


def plan_due_date(period: str) -> date:
    """财库〔2020〕36号: next-month plan due by the 20th of the PRIOR month."""
    y, m = map(int, period.split("-"))
    return date(y - 1, 12, 20) if m == 1 else date(y, m - 1, 20)


# ---------------------------------------------------------------- build tables
def build() -> dict:
    sched = pd.read_csv(DATA_CLEAN / "schedule.csv", parse_dates=["publish_date"])
    real = pd.read_csv(DATA_CLEAN / "realized.csv", parse_dates=["issue_date"])

    # one plan per issuer-month: earliest publish (= the leading signal), amounts from that article
    s = sched.dropna(subset=["issuer", "plan_period", "publish_date"]).sort_values("publish_date")
    plans = s.groupby(["issuer", "plan_period"], as_index=False).first()[
        ["issuer", "plan_period", "publish_date", "new_general_yi", "new_special_yi",
         "refinance_yi", "total_planned_yi", "url"]].rename(columns={"plan_period": "period"})

    r = real.dropna(subset=["issuer", "issue_date"]).copy()
    r["period"] = r["issue_date"].dt.strftime("%Y-%m")
    r["_ng"] = r["new_amount_yi"].where(r["bond_type_en"] == "general", 0.0)
    r["_ns"] = r["new_amount_yi"].where(r["bond_type_en"] == "special", 0.0)
    ragg = r.groupby(["issuer", "period"], as_index=False).agg(
        realized_gross_yi=("amount_yi", "sum"),
        realized_new_general_yi=("_ng", "sum"),
        realized_new_special_yi=("_ns", "sum"),
        realized_refinance_yi=("refinance_amount_yi", "sum"),
        realized_swap_yi=("swap_amount_yi", "sum"),
        n_bonds=("bond_code", "size"),
        first_issue=("issue_date", "min"))

    m = plans.merge(ragg, on=["issuer", "period"], how="outer")
    m["has_plan"] = m["publish_date"].notna()
    m["has_issuance"] = m["n_bonds"].fillna(0) > 0
    m["realized_comparable_yi"] = m[["realized_new_general_yi", "realized_new_special_yi",
                                     "realized_refinance_yi"]].sum(axis=1, min_count=1)
    m["lead_wd"] = [working_days(p.date(), f.date()) if pd.notna(p) and pd.notna(f) else np.nan
                    for p, f in zip(m["publish_date"], m["first_issue"])]
    m["on_time"] = [bool(p.date() <= plan_due_date(per)) if pd.notna(p) else np.nan
                    for p, per in zip(m["publish_date"], m["period"])]
    both = m["total_planned_yi"].notna() & m["has_issuance"]
    m["amount_slippage_yi"] = np.where(both, m["realized_comparable_yi"].fillna(0) - m["total_planned_yi"], np.nan)
    m["delivery_ratio"] = np.where(both & (m["total_planned_yi"] > 0),
                                   m["realized_comparable_yi"].fillna(0) / m["total_planned_yi"], np.nan)
    recon = m.sort_values(["period", "issuer"]).reset_index(drop=True)

    # ---- per-issuer scorecard
    rows = []
    for iss, g in recon.groupby("issuer"):
        issued = g[g["has_issuance"]]
        planned = g[g["has_plan"]]
        pr = planned[planned["delivery_ratio"].notna() & (planned["delivery_ratio"] > 0)
                     & (planned["delivery_ratio"] < 5)]["delivery_ratio"]
        lead_med = planned["lead_wd"].median()
        cov = issued["has_plan"].mean() if len(issued) else np.nan
        ont = planned["on_time"].mean() if len(planned) else np.nan
        score = 100 * (0.5 * min(max(lead_med, 0) / 20, 1) + 0.5 * (cov or 0) * (ont or 0)) \
            if pd.notna(lead_med) else 0.0
        rows.append({"issuer": iss,
                     "months_planned": int(len(planned)), "months_issued": int(len(issued)),
                     "coverage_pct": round(100 * cov, 1) if pd.notna(cov) else None,
                     "on_time_pct": round(100 * ont, 1) if pd.notna(ont) else None,
                     "median_lead_wd": round(lead_med, 1) if pd.notna(lead_med) else None,
                     "median_delivery_ratio": round(pr.median(), 2) if len(pr) else None,
                     "score": round(score, 1)})
    scorecard = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)

    # ---- national monthly
    nat = recon.groupby("period", as_index=False).agg(
        planned_total_yi=("total_planned_yi", "sum"),
        realized_gross_yi=("realized_gross_yi", "sum"),
        realized_comparable_yi=("realized_comparable_yi", "sum"),
        n_plans=("has_plan", "sum"), n_bonds=("n_bonds", "sum")).sort_values("period")

    num = recon.select_dtypes("number").columns
    recon[num] = recon[num].round(2)
    nat[[c for c in nat.columns if c != "period"]] = nat[[c for c in nat.columns if c != "period"]].round(2)
    return {"reconciliation": recon, "scorecard": scorecard, "national_monthly": nat,
            "schedule": sched, "realized": real}


# ---------------------------------------------------------------- outputs
def charts(t: dict) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for fp in ["/System/Library/Fonts/STHeiti Light.ttc", "/System/Library/Fonts/PingFang.ttc",
               "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", r"C:\Windows\Fonts\msyh.ttc",
               r"C:\Windows\Fonts\simhei.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
        if Path(fp).exists():
            try:
                font_manager.fontManager.addfont(fp)
                name = font_manager.FontProperties(fname=fp).get_name()
                plt.rcParams["font.family"] = name
                if any(g.name == name for g in font_manager.fontManager.ttflist):
                    break
            except Exception:  # noqa: BLE001
                continue
    plt.rcParams["axes.unicode_minus"] = False
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    paths = []

    nat = t["national_monthly"]
    nat2 = nat[nat["period"] >= "2021-01"].copy()
    nat2["dt"] = pd.to_datetime(nat2["period"] + "-01")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.fill_between(nat2["dt"], nat2["realized_comparable_yi"], color="#1D66A0", alpha=0.30,
                    label="Realized (new + refinancing, 亿元)")
    ax.plot(nat2["dt"], nat2["planned_total_yi"], color="#C8922A", lw=1.8, label="Scheduled (发行安排, 亿元)")
    ax.set_title("Scheduled vs realized LGB issuance, monthly")
    ax.legend(fontsize=9)
    fig.tight_layout()
    p = OUTPUTS / "national_scheduled_vs_realized.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    paths.append(p)

    sc = t["scorecard"].dropna(subset=["median_lead_wd"]).sort_values("score")
    fig, ax = plt.subplots(figsize=(7.5, 10))
    colors = ["#1D66A0" if v >= 50 else ("#C8922A" if v >= 25 else "#9aa3ad") for v in sc["score"]]
    ax.barh(sc["issuer"], sc["score"], color=colors)
    ax.set_xlabel("Schedule usability score (0–100)")
    ax.set_title("Whose issuance schedule is a usable leading indicator?")
    fig.tight_layout()
    p = OUTPUTS / "issuer_score.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    paths.append(p)
    return paths


def excel(t: dict, chart_paths: list[Path]) -> Path:
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Font
    recon, sc, nat = t["reconciliation"], t["scorecard"], t["national_monthly"]
    pm = recon[recon["has_plan"]]
    summary = pd.DataFrame([
        ("Realized bonds", f"{len(t['realized']):,}"),
        ("Realized range", f"{t['realized']['issue_date'].min():%Y-%m-%d} .. {t['realized']['issue_date'].max():%Y-%m-%d}"),
        ("Schedule articles", f"{len(t['schedule']):,}"),
        ("Issuer-months with a plan", f"{len(pm):,}"),
        ("Median lead, plan → first issuance (working days)", f"{pm['lead_wd'].median():.0f}"),
        ("Plans on time (≤20th of prior month)", f"{100 * pm['on_time'].mean():.0f}%"),
        ("Coverage (issued months that had a plan)", f"{100 * recon[recon['has_issuance']]['has_plan'].mean():.0f}%"),
        ("Median delivery ratio (realized ÷ planned)", f"{pm['delivery_ratio'].median():.2f}"),
    ], columns=["metric", "value"])
    out = OUTPUTS / "celma_lgb_analysis.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Summary", index=False)
        sc.to_excel(xw, sheet_name="Scorecard", index=False)
        recon.to_excel(xw, sheet_name="Reconciliation", index=False)
        nat.to_excel(xw, sheet_name="National_Monthly", index=False)
        t["schedule"].to_excel(xw, sheet_name="Schedule_raw", index=False)
        t["realized"].to_excel(xw, sheet_name="Realized_raw", index=False)
        wb = xw.book
        for name in ("Summary", "Scorecard"):
            for cell in wb[name][1]:
                cell.font = Font(bold=True)
        wb["Summary"].column_dimensions["A"].width = 46
        wb["Summary"].column_dimensions["B"].width = 30
        ws = wb.create_sheet("Charts")
        row = 1
        for cp in chart_paths:
            ws.add_image(XLImage(str(cp)), f"A{row}")
            row += 26
    return out


def main() -> None:
    if _cc_workday is None:
        print("NOTE: chinesecalendar not installed — working-day metrics (lead_wd) use a "
              "Mon-Fri fallback that ignores CN holidays/调休. Install it for full precision "
              "(see requirements.txt).")
    t = build()
    for name in ("reconciliation", "scorecard", "national_monthly"):
        t[name].to_csv(DATA_CLEAN / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"{name}.csv: {len(t[name])} rows")
    cps = charts(t)
    xp = excel(t, cps)
    print("outputs:", xp.name, "+", ", ".join(p.name for p in cps))


if __name__ == "__main__":
    main()
