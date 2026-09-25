---
id: interest_rate_management
title: Interest rate management
parent: treasury_common
applies_when: Interest rate risk (IRRBB), repricing gaps, NII and EVE sensitivity, duration, PV01/DV01, interest rate swaps and hedges, fixed/floating mix, benchmark rates.
signals:
  keywords: [interest, rate, risk, irrbb, repricing, gap, nii, eve, duration, pv01, dv01, bpv, sensitivity, shock, swap, swaps, irs, hedge, fixed, floating, benchmark, sofr, estr, sonia, euribor, tenor, bucket]
  columns: [repricing date, next reset, reset date, fixed rate, floating rate, index, spread, notional, pay leg, receive leg, pay receive, duration, modified duration, pv01, dv01, nii, eve, shock, scenario, bucket, o/n, 0-1m, 1-3m, 3-6m, 6-12m, 1-2y, 2-5y, >5y]
  file_patterns: [*irr*, *irrbb*, *gap*, *repricing*, *swap*, *sensitivity*, *duration*, *nii*, *eve*]
---
# Interest rate management (starter pack)

Status: **starter content** - confirm with the ALM / Interest Rate Risk team.

## Typical data
| Looks like | Usually means | Additivity | Always confirm |
|---|---|---|---|
| Tenor bucket columns (O/N, 0-1M ... >5Y) | Repricing or maturity gap report (wide) | semi-additive over time; additive across buckets | Repricing vs contractual maturity; bucket boundaries |
| Balance sheet line, product | Row dimension | - | Hierarchy: are subtotal lines included? |
| Notional | Swap / hedge size | semi-additive | Not an exposure amount; per leg or per trade |
| Fixed rate, index, spread, reset date | Swap / loan terms | non-additive | Index name and tenor (e.g. 3M EURIBOR, SOFR compounded) |
| Pay / receive | Swap direction | dimension | Pay-fixed or receive-fixed from whose view |
| NII / EVE, shock, scenario | Sensitivity results | additive across portfolios within one scenario | Shock size (bp), scenario definitions, horizon |
| Duration, PV01 / DV01 | Price sensitivity | PV01 additive; duration non-additive | Sign convention; per 1bp; currency |

## Starter definitions (confirm locally)
- **Repricing gap** (bucket b) = rate-sensitive assets - rate-sensitive liabilities (+/- derivatives) repricing in b.
- **Cumulative gap** = running sum of bucket gaps from the shortest bucket.
- **ΔNII (parallel shock s)** ≈ sum over buckets within the horizon of gap_b x s x (time from bucket midpoint to horizon) - use the risk system's figure if available.
- **ΔEVE** = change in present value of assets - liabilities under a rate shock.
- **PV01 / DV01** = change in value for a 1bp move; portfolio PV01 is the sum of position PV01s.
- **Portfolio duration** = value-weighted average of position durations (never a plain average).
- **Fixed / floating mix** = fixed-rate principal / total principal (after hedges, if stated).
- **Hedge ratio** = hedged notional / hedged item exposure.

## Known traps
- Gap reports are wide: bucket columns must be unpivoted, and "Total" rows and columns removed
  before summing.
- Subtotal lines (Total assets, Total liabilities, Gap) sit inside the data.
- Periodic vs cumulative gap columns look alike - confirm which.
- Non-maturity deposits use behavioural (modelled) repricing, not contractual; state the assumption.
- Swap notionals are not exposures; netting pay and receive legs requires the sign convention.
- Rates and shocks in bp vs percent.
- Multiple scenarios in one file: never add results across scenarios.

## Questions to ask
1. Repricing or contractual maturity buckets? Which bucket boundaries?
2. Are derivatives included in the gap, and with what sign?
3. Which shock scenarios and horizon apply to NII / EVE figures?
4. Behavioural assumptions for non-maturity deposits and prepayments?
5. Which index and tenor do floating legs reference?

## Typical analyses
Repricing gap and cumulative gap by currency; NII and EVE sensitivity by scenario vs limits;
PV01 by tenor bucket; fixed/floating mix before and after hedging; swap portfolio by maturity
and direction; hedge coverage.

## Extra validation checks
- Bucket values sum to the row's total column (where present).
- Gap = assets - liabilities (+/- derivatives) per bucket, matching any gap row in the file.
- Results are never summed across scenarios.
