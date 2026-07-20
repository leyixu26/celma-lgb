# Data verification

Run 2026-07-21 · data through **2026-07-17** · overall: ✅ **ALL CHECKS PASS**

Every check compares our scrape against the **source's own published figures** (the API's `total`/`sumCount`; the list's `共 N 条` count).

| # | Check | Result | Detail |
|---|-------|--------|--------|
| R1 | rows pulled == API total | ✅ | 19708 vs 19708 |
| R2 | raw amount sum ≈ API sumCount | ✅ | 812,270.1 vs 812,268.7 亿 |
| R3 | clean total ≈ API sumCount after dedup; 37 issuers | ✅ | 19701 rows (7 dup/sum rows removed), 812,201.6 vs 812,268.7 亿, 37/37 issuers |
| S1 | unique articles == site 共N条 | ✅ | 2180 vs 共2180条 (COMPLETE) |
| S2 | 37 issuers; amount coverage | ✅ | 37/37 issuers; amounts on 2081/2180 plans (95.5%) |

Row-level spot-checking: every schedule row in `data/clean/schedule.csv` carries its source `url` — open it on celma and compare title/date/amounts directly.
