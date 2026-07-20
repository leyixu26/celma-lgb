# celma-lgb — China Local Government Bond Issuance Monitor

Scheduled vs. actual issuance for all 37 Chinese LGB issuers, scraped from the
Ministry of Finance's official disclosure platform (**celma.org.cn**), verified
against the source's own record counts on every refresh, and served as a
one-page dashboard.

**📊 Dashboard: https://leyixu26.github.io/celma-lgb/** — latest monthly
issuance schedule (发行安排, with planned amounts), full realized history
(发行结果), and the schedule-reliability analysis. Data is embedded in the page;
no login, nothing to install.

## Data (in `data/clean/`, CSV)

| File | Contents |
|---|---|
| `schedule.csv` | 发行安排 — one row per schedule article: issuer, plan month, publish date, planned 新增一般/新增专项/再融资 amounts (亿元), source URL |
| `realized.csv` | 发行结果 — one row per bond issued (2009–): amount, new/refinance/swap split, type, tenor, coupon, date |
| `reconciliation.csv` | issuer × month: planned vs realized, lead time (working days), on-time flag, delivery ratio |
| `scorecard.csv` | per-issuer reliability: lead, coverage, timeliness, delivery ratio, usability score |
| `national_monthly.csv` | national monthly planned vs realized totals |

Verification proof for the current data: [`VERIFICATION.md`](VERIFICATION.md).
Methodology, definitions, and findings: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Headline findings (data through 2026-07-17)

| Question | Answer |
|---|---|
| Do provinces issue **what** they schedule? | **Yes, almost exactly** — median delivery ratio **1.00**; 70% of scheduled issuer-months execute within **±1%** of plan (77% within ±10%) |
| Do they issue **when** they schedule? | The weak spot: only **53%** of issuing months had a schedule at all, **49%** met the regulatory deadline (20th of prior month), median lead **11 working days** |
| Is the schedule usable as a **national supply indicator**? | **Since 2023, yes** — scheduled amounts cover **88–97%** of realized issuance (2023: 88% · 2024: 78% · 2025: 88% · 2026 YTD: **97%**), vs just 6% in 2019 |
| Which provinces' schedules can you **trust**? | **Usable:** 山东, 吉林, 深圳, 广西, 贵州 (lead 20–34 wd, ~90%+ on time). **Not usable:** 青岛, 辽宁, 天津, 新疆兵团, 大连 (post retroactively — negative lead, ~0% on time) |

**Bottom line:** the schedule is a *high-fidelity but incomplete* leading
indicator — amounts are executed nearly verbatim, so its value hinges on
existence and timing, which matured decisively from 2023 and varies sharply by
province. Full analysis: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## External validation vs Ministry of Finance

Bottom-up per-deal totals cross-checked against MOF's official aggregates
(details: [`docs/EXTERNAL_VALIDATION.md`](docs/EXTERNAL_VALIDATION.md)):

| Series | Ours | MOF official | Diff |
|---|---:|---:|---:|
| 2025 FY refinancing | 49,282 亿 | 49,284 亿 | **−0.004%** |
| 2025 FY new bonds | 53,633 亿 | 53,817 亿 | −0.34% |
| 2025 FY total | 102,917 亿 | 103,101 亿 | −0.18% |
| 2026 Jan new / refi | 4,285 / 4,349 亿 | 4,284.55 / 4,348.94 亿 | **exact (0.00%)** |
| 2021 FY total | 74,898 亿 | 74,898 亿 | exact |
| 2026 Q1 total | 32,777 亿 | 31,059 亿 | +5.5% ⚠ open item¹ |

¹ Gap sits in Feb–Mar 2026 only; our side audited clean (zero duplicate bonds,
completeness proven vs the platform's own totals) — likely MOF preliminary
figures / 化债-related classification; being reconciled against MOF's monthly
cumulative tables.

## Refresh (operator)

One click on any machine that reaches celma: see
[`docs/SETUP_HK.md`](docs/SETUP_HK.md). Pipeline:
`scrape → parse → verify (hard gate) → analyze → dashboard → publish`.
Raw scrape snapshots are attached to [Releases](../../releases).

## Notes

- Source is a public government disclosure platform; only factual fields
  (amounts, dates, codes, types) are stored — no document text.
- Code: MIT. Data: 中华人民共和国财政部 / celma.org.cn public disclosures.
