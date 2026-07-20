# Data verification

Run 2026-07-20 · data through **2026-06-16** · overall: ✅ **ALL CHECKS PASS**

Every check compares our scrape against the **source's own published figures** (the API's `total`/`sumCount`; the list's `共 N 条` count).

| # | Check | Result | Detail |
|---|-------|--------|--------|
| R1 | rows pulled == API total | ✅ | 19487 vs 19487 |
| R2 | raw amount sum ≈ API sumCount | ✅ | 805,364.3 vs 805,362.9 亿 |
| R3 | clean total ≈ API sumCount after dedup; 37 issuers | ✅ | 19480 rows (7 dup/sum rows removed), 805,295.8 vs 805,362.9 亿, 37/37 issuers |
| S1 | unique articles == site 共N条 | ✅ | 2150 vs 共2150条 (COMPLETE) |
| S2 | 37 issuers; amount coverage | ✅ | 37/37 issuers; amounts on 2051/2150 plans (95.4%) |

Row-level spot-checking: every schedule row in `data/clean/schedule.csv` carries its source `url` — open it on celma and compare title/date/amounts directly.
