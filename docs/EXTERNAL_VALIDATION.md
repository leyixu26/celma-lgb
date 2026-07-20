# External validation vs Ministry of Finance official figures

Independent sanity check of `data/clean/realized.csv` (bottom-up, per-deal from
celma) against MOF's published aggregate issuance statistics (top-down).
Compiled 2026-07-21; amounts in 亿元.

| Series | Ours (celma per-deal) | MOF official | Diff | Diff % |
|---|---:|---:|---:|---:|
| 2025 FY new bonds | 53,633 | 53,816.89 | −184 | −0.34% |
| 2025 FY refinancing | 49,282 | 49,284.07 | −2 | −0.004% |
| 2025 FY total | 102,917 | 103,100.96 | −184 | −0.18% |
| 2026 Jan new | 4,285 | 4,284.55 | 0 | 0.00% |
| 2026 Jan refinancing | 4,349 | 4,348.94 | 0 | 0.00% |
| 2026 Q1 new | 15,498 | 14,199 | +1,299 | +9.2% |
| 2026 Q1 refinancing | 17,280 | 16,860 | +420 | +2.5% |
| 2026 Q1 total | 32,777 | 31,059 | +1,718 | +5.5% |

Also: our 2021 gross (74,898) equals MOF's published 2021 total exactly.

**Reading.** Full-year 2025 and January 2026 agree essentially exactly — strong
evidence the per-deal scrape is complete and correctly classified. The Q1-2026
gap is concentrated in Feb–Mar (Jan is exact) and was investigated on our side:
zero near-duplicate rows (521 unique bond codes), completeness proven against
the platform's own `total`/`sumCount`, and re-bucketing by value date (起息日)
instead of tender date does not close it. Remaining explanations are on the
reporting side (preliminary vs revised MOF cumulative figures, and/or the
classification of 化债-related 特殊 bonds in early 2026). **Open item:**
compare against MOF's own monthly cumulative table (预算司 →
地方政府债务管理 → 数据统计, "地方政府债券发行和债务余额情况") from a
network that reaches mof.gov.cn.

**Sources.** MOF budget dept. monthly releases (yss.mof.gov.cn), MOF Government
Debt Research & Evaluation Center market reports (kjhx.mof.gov.cn), China News
Service report of MOF Q1-2026 figures (2026-05-08).
