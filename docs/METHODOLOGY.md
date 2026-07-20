# China LGB Issuance Schedule — Pipeline, Methodology & Findings

*A study of how well China's official local-government-bond issuance schedules
predict actual issuance. Data through 2026-06; all figures reproducible from
this repository.*

---

## 1. Question and motivation

Chinese provinces disclose **forward monthly issuance schedules** (发行安排) for
local government bonds (LGB, 地方政府债券) on the Ministry of Finance's official
platform. If those schedules are reliable, they are a **leading indicator of
bond supply** that is available days-to-weeks before issuance — earlier than
commercial terminals, which surface per-deal documents only ~5 working days
before tender. This study measures, per province and in aggregate:

1. **Lead time** — how far ahead of actual issuance the schedule is published;
2. **Timeliness** — compliance with the regulatory deadline;
3. **Coverage** — how much actual issuance was scheduled at all;
4. **Amount fidelity** — whether provinces issue *what they scheduled*.

**Regulatory frame.** 财库〔2020〕36号 requires each province to disclose its
next-month schedule by the **20th of the prior month** (and next-quarter
schedules by 20 Mar/Jun/Sep/Dec). Schedules are explicitly provisional
("以届时公布的发行文件为准") — quantifying that provisionality is the point of
this study. Results must be uploaded within 3 working days of issuance
(《地方政府债券信息公开平台管理办法》, 2021).

## 2. Data source

**celma.org.cn** (中国地方政府债券信息公开平台) — designated by MOF as the *sole*
official disclosure window, aggregating all **37 issuers** (31 provinces +
5 计划单列市 + 新疆生产建设兵团). Two datasets are used:

| Dataset | celma column | Mechanism (identified by one-time network capture, 2026-06) |
|---|---|---|
| **Schedule** (planned) | 发行安排 | Server-rendered article list `zqsclb_<page>.jhtml?ad_code=87&channelId=192`; one article per issuer-month at `/dfzfxjh/<id>.jhtml`; planned amounts in the standard MOF tables **表2-1** (再融资债券计划发行规模) and **表2-2** (新增一般债券 / 新增专项债券), unit 亿元, usually inside a linked PDF |
| **Realized** (actual) | 发行结果 | JSON API `loadBondData.action` (`dataType=ZQFXLISTBYAD`, `adCode=87` = nationwide): per-bond amount `FX_AMT`, split into new (`XZZQ_AMT`), refinancing (`ZRZZQ_AMT`), swap (`ZHZQ_AMT`), plus coupon, tenor, dates, 一般/专项 type |

Only **factual fields** are stored (amounts, dates, codes, types) — never
document prose. Every schedule row retains its source URL for direct
comparison against the website.

## 3. Pipeline

```
scrape_realized.py   JSON feed  -> data/raw/realized_json/          (full re-pull each refresh)
scrape_schedule.py   list scrape (loops until count == site 共N条)
                     + per-article planned amounts (cached, incremental)
parse_realized.py    -> data/clean/realized.csv
parse_schedule.py    -> data/clean/schedule.csv   (list + amounts joined on article_id)
verify.py            -> VERIFICATION.md           (checks below; hard-fails the run)
analyze.py           -> reconciliation.csv, scorecard.csv, national_monthly.csv,
                        outputs/celma_lgb_analysis.xlsx + charts
build_dashboard.py   -> docs/index.html           (self-contained, data embedded)
```

`run_all.py` chains the steps; `publish.py` commits refreshed data to GitHub
via the API (no git needed on the operator machine).

## 4. Completeness & fidelity verification

Scraping a live, newest-first list can silently drop rows at page boundaries as
new articles post mid-scrape. The pipeline therefore **proves completeness
against the source's own published figures** on every run:

| Check | Invariant | Current result |
|---|---|---|
| R1 | realized rows pulled = the API's own `total` | 19,487 = 19,487 |
| R2 | raw amount sum ≈ the API's own `sumCount` (±0.1%) | 805,364 vs 805,363 亿 |
| R3 | clean total ≈ `sumCount` after removing exact-duplicate rows; 37/37 issuers | 805,296 亿 (0.008%) |
| S1 | unique schedule articles = the site's own "共 N 条" | 2,150 = 共2150条 |
| S2 | 37/37 issuers present; amount-parse coverage reported | 95.4% of schedules parsed |

The schedule scraper fetches list pages concurrently (near-instant snapshot)
and repeats, unioning unique article ids, until the S1 target is met.
Realized **dedup removes only exact-identical rows**: the same bond code
legitimately recurs for re-taps (续发), which are distinct issuance events —
deduping on code was tested and undercounts by ~12,000 亿.

## 5. Reconciliation definitions

Unit of analysis: **issuer × calendar month**. Where an issuer posted multiple
schedule articles for one month (revisions, ~4% of cases), the **earliest**
publication is used — that is the leading signal.

| Metric | Definition |
|---|---|
| `lead_wd` | Working days (China calendar incl. 调休, via `chinesecalendar`) from schedule publication to the issuer's **first issuance** of that month. Negative = published after issuance began (retroactive). |
| `on_time` | Publication date ≤ the **20th of the prior month** (财库〔2020〕36号). |
| `coverage` | Share of issuer-months **with issuance** for which a schedule existed. |
| `planned total` | 表2-2 新增一般 + 新增专项 + 表2-1 再融资 (亿元). |
| `realized_comparable` | Realized new + refinancing, **excluding swap** (置换 is not scheduled; it is ~0 in recent years). |
| `delivery_ratio` | realized_comparable ÷ planned total (both > 0; ratios ≥5 excluded as data-quality outliers). |
| `score` (0–100) | `100 × (0.5 × min(max(lead_med,0)/20, 1) + 0.5 × coverage × on_time)` — a transparent blend of how *early* and how *dependable* the schedule is. Parameters are conventions, not estimates. |

## 6. Findings (data through 2026-06)

**F1 — When a schedule exists, it is executed almost exactly.**
Median delivery ratio is **1.00 in every year 2019–2026**; **71%** of scheduled
issuer-months execute within **±1%** of the planned amount (77% within ±10%;
11% under-deliver <0.9, 12% over-deliver >1.1). Amount risk is *not* the main
uncertainty in the schedule.

**F2 — The uncertainty is whether and when the schedule appears.**
Only **53%** of issuer-months with issuance had a schedule; **49%** of schedules
met the regulatory deadline; **51%** genuinely led issuance (median lead
**11 working days** overall, ~18 among plans that led). The indicator's
weakness is coverage and timing, not accuracy.

**F3 — The disclosure regime matured sharply around 2023.**
Scheduled amounts as a share of realized (new + refinancing) issuance:
6% (2019) → ~40% (2020–21) → 69% (2022) → **88% (2023) → 78% (2024) → 88%
(2025) → 95% (2026 YTD)**. Since 2023 the national schedule aggregate tracks
realized issuance closely (the 2024 dip coincides with the ad-hoc 特殊再融资
wave, which bypassed normal scheduling). **Practical implication: treat the
schedule as a usable national supply indicator from 2023 onward.**

**F4 — Provinces split into a usable tier and an unusable tier.**
Top of the scorecard (lead ≈ 20–30 wd, on-time ≥ 87%, delivery ≈ 1.00):
**吉林, 山东, 深圳, 广西, 贵州**. Bottom (negative lead — schedules published
*after* issuance; on-time ≈ 0%): **青岛, 辽宁, 天津, 新疆兵团, 大连**. For the
bottom tier the schedule has no forward value; monitor their issuance through
results only.

**Conclusion.** China's LGB issuance schedule is a **high-fidelity but
incomplete** leading indicator: amounts are executed nearly verbatim (F1), so
the schedule's value hinges on *existence and timing*, which improved
decisively from 2023 (F3) and varies sharply by province (F4). Used with the
scorecard as a province filter, it provides days-to-weeks of genuine lead over
deal-document-based sources.

## 7. Limitations

1. **Amount-parse coverage is 95.4%** — 99 schedule articles (4.6%) don't follow
   the standard tables (odd layouts, image PDFs); they carry dates but no
   amounts. Re-tried on each refresh.
2. **Monthly granularity.** Reconciliation is issuer×month; within-month
   re-scheduling is invisible. Quarterly/annual schedule articles (19 of 2,150)
   carry no month and are excluded from reconciliation.
3. **Schedule vintage.** Only the earliest article per issuer-month is used;
   revisions are not tracked as separate vintages (the raw articles are kept,
   so a vintage study is possible later).
4. **Working-day calendar** requires the annual `chinesecalendar` update;
   out-of-range dates fall back to Mon–Fri.
5. **Comparability.** Swap (置换) bonds are excluded from the realized side;
   pre-2019 realized issuance predates the schedule regime entirely.
6. The 发行前公告 (pre-deal notice) layer is **out of scope** by design; earlier
   exploration showed it adds ~no lead over the ~5-working-day baseline.

## 8. Reproducing / refreshing

See `docs/SETUP_HK.md` (operator machine) and `README.md`. Every refresh:
scrape → parse → **verify (hard gate)** → analyze → dashboard → publish. The
dashboard badge and `VERIFICATION.md` always reflect the latest run.
