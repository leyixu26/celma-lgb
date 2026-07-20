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

## Headline findings (through 2026-06)

1. **Schedules are executed almost exactly** — 71% of scheduled issuer-months
   issue within ±1% of the planned amount (median delivery ratio 1.00).
2. **The risk is coverage/timing, not amounts** — only 53% of issuing months had
   a schedule; 49% met the regulatory deadline; median lead 11 working days.
3. **Usable as a national supply indicator since 2023** — scheduled amounts now
   cover ~90% of realized issuance (vs 6% in 2019).
4. **Provinces split sharply** — 吉林/山东/深圳/广西/贵州 schedules lead by
   20–30 working days; 青岛/辽宁/天津/兵团/大连 post retroactively.

## Refresh (operator)

One click on any machine that reaches celma: see
[`docs/SETUP_HK.md`](docs/SETUP_HK.md). Pipeline:
`scrape → parse → verify (hard gate) → analyze → dashboard → publish`.
Raw scrape snapshots are attached to [Releases](../../releases).

## Notes

- Source is a public government disclosure platform; only factual fields
  (amounts, dates, codes, types) are stored — no document text.
- Code: MIT. Data: 中华人民共和国财政部 / celma.org.cn public disclosures.
