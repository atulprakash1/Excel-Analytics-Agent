---
id: liquidity_management
title: Liquidity management
parent: treasury_common
applies_when: Bank balances, cash positions, cash pooling, cash forecasts, liquidity buffers, liquidity ratios (LCR, NSFR), liquidity gaps and headroom.
signals:
  keywords: [liquidity, cash, balance, balances, buffer, hqla, lcr, nsfr, outflow, inflow, forecast, headroom, pool, pooling, sweep, overdraft, survival, stress, available, ledger]
  columns: [closing balance, opening balance, available balance, ledger balance, account, account no, account number, iban, bank, hqla, level 1, level 2a, level 2b, haircut, outflow, inflow, forecast, actual, variance, headroom, undrawn]
  file_patterns: [*balance*, *cash*, *liquidity*, *lcr*, *nsfr*, *forecast*, *pool*]
---
# Liquidity management (starter pack)

Status: **starter content** - confirm with the Liquidity / Cash Management team.

## Typical data
| Looks like | Usually means | Additivity | Always confirm |
|---|---|---|---|
| Closing / ledger balance | Booked balance at end of day | semi-additive over time | Book vs value-dated; end-of-day time and time zone |
| Available balance | Balance usable today (after holds, float) | semi-additive over time | Includes overdraft limit or not? |
| Opening balance | Previous day's closing | semi-additive over time | Equals prior closing? |
| Account, IBAN, account no | Bank account | identifier (keep as text) | Header vs sub-account in a pool |
| Bank, entity, currency | Dimensions | - | Entity level used for reporting |
| Inflow / outflow, receipts / payments | Cash flows | additive | Sign convention; category list |
| Forecast / actual | Cash forecast vs realised | additive (flows) | Forecast version / cut-off date |
| HQLA, Level 1 / 2A / 2B, haircut | Liquid asset buffer | semi-additive; haircut non-additive | Pre- or post-haircut values |
| Undrawn committed facility | Contingent liquidity | semi-additive | Committed only? Conditions? |

## Starter definitions (confirm locally before adding to the glossary)
- **Cash position** (as of date D) = sum of closing balances of in-scope accounts on D,
  converted to reporting currency at D's closing rate.
- **Liquidity headroom** (corporate) = available cash + undrawn committed facilities
  - minimum cash requirement.
- **Forecast accuracy / variance** = actual net flow - forecast net flow for the same period and
  forecast version; variance % = variance / |forecast|.
- **LCR** (banks, Basel III) = stock of HQLA after haircuts / total net cash outflows over the
  next 30 calendar days under stress; regulatory minimum 100%.
- **NSFR** (banks) = available stable funding / required stable funding; minimum 100%.
- **Liquidity gap** by time bucket = inflows - outflows in the bucket; cumulative gap is the
  running sum from the shortest bucket.
- **Survival horizon** = days until cumulative stressed net outflows exceed the liquidity buffer.

## Known traps
- Summing daily balances over a month gives a meaningless number - use month-end or average.
- Cash pools: header accounts may already include sub-account balances (double counting),
  or notional pools show gross balances that net for interest only.
- Negative balances are overdrafts - keep the sign; don't drop them.
- Weekends and holidays: missing rows vs repeated balances change averages.
- Balances from different banks may be captured at different times of day.
- Forecast files often hold several versions (weekly re-forecasts) - pick one explicitly.
- Regulatory ratios (LCR, NSFR) have jurisdiction-specific rules; never recompute them from
  a simplified file without Treasury sign-off.

## Questions to ask
1. Which balance is the reporting measure: ledger, value-dated or available?
2. Are there pooled accounts, and should header or sub-accounts be counted?
3. Which forecast version and horizon should be compared with actuals?
4. Which accounts or entities are in scope (restricted cash, trapped cash excluded?)
5. Reporting currency and FX rate source for consolidation?

## Typical analyses
Daily cash position by entity / bank / currency; average vs month-end balances; cash
concentration by bank (counterparty risk); forecast vs actual variance; liquidity headroom
trend; liquidity gap ladder; buffer composition by HQLA level.

## Extra validation checks
- Position totals use a single as-of date (or an explicit average).
- Opening balance of day D equals closing balance of day D-1 (per account), where both exist.
- Pool: header balance vs sum of sub-accounts reconciles, or only one level is used.
