---
id: money_market
title: Money market
parent: treasury_common
applies_when: Short-term deposits and placements, borrowings, call/notice accounts, CDs, commercial paper, repo and reverse repo, money market funds, deal blotters and maturity ladders.
signals:
  keywords: [deposit, deposits, placement, placements, borrowing, loan, mm, money, market, repo, reverse, cd, cp, commercial, paper, mmf, fund, tenor, overnight, call, notice, blotter, rollover, murex]
  columns: [deal id, deal no, trade date, value date, maturity date, tenor, principal, nominal, notional, rate, interest rate, all in rate, day count, basis, interest, interest amount, counterparty, direction, deal type, instrument, rating, limit, collateral, portfolio, murex id]
  file_patterns: [*mm*, *money*market*, *deposit*, *placement*, *repo*, *blotter*, *deal*, *deal*inventory*]
---
# Money market (starter pack)

Status: **starter content** - confirm with the Money Market / Front Office team.

## Typical data
| Looks like | Usually means | Additivity | Always confirm |
|---|---|---|---|
| Deal ID / deal no | One deal (or one leg) | identifier | Rollovers: new ID or same ID? |
| Trade / value / maturity date | Deal life | date | Which date defines "new business" in a period |
| Principal / nominal | Deal amount | semi-additive over time (outstanding) | Sign by direction? Face vs discounted (CP, CD) |
| Rate / all-in rate | Deal interest rate | non-additive | Percent vs decimal; fixed vs floating (+ spread) |
| Day count / basis | ACT/360, ACT/365, 30/360 | attribute | Per currency default if missing |
| Interest amount | Interest for the full term | additive (flow) | Full-term vs accrued to date |
| Direction / deal type | Deposit, placement, borrowing, loan, repo | dimension | Which are assets vs liabilities |
| Counterparty, rating, limit | Credit exposure | dimension / limit semi-additive | Group vs legal entity; rating source |

## Starter definitions (confirm locally)
- **Outstanding on date D**: deals with `value_date <= D < maturity_date` and live status.
- **Interest (simple)** = principal x rate x days / basis, with days = maturity - value date.
- **Accrued interest to D** = principal x rate x (D - value date) / basis.
- **Weighted average rate** = sum(principal x rate) / sum(principal), over outstanding deals.
- **Weighted average maturity (remaining days)** = sum(principal x (maturity - D)) / sum(principal).
- **Maturity ladder**: outstanding principal grouped by remaining term bucket (O/N, <1W, 1W-1M, 1-3M, 3-6M, 6-12M).
- **Limit utilisation** = outstanding exposure to counterparty / approved limit.

## Known traps
- Summing principal of all deals in a period mixes stock and flow: use outstanding-as-of for
  exposure, and sum of new deals (by trade or value date) for volumes.
- Overnight and call deals rolled daily can appear once per day - counting them as separate
  new deals overstates volumes.
- Rates in percent vs decimal; negative rates are possible in some currencies and periods.
- Day count differs by currency (GBP usually ACT/365, EUR and USD usually ACT/360).
- Discount instruments (CP, T-bills) quote a price or discount rate, not a coupon.
- Repo: the cash leg and the collateral are different amounts; don't add them.
- Cancelled, amended and matured deals may still be in the extract.

## Questions to ask
1. Should volumes count new deals by trade date or value date?
2. Are rollovers new deals or extensions of the same deal?
3. Is the interest column full-term or accrued to the report date?
4. Which statuses are in scope?
5. Which counterparty level do limits apply to (group or legal entity)?

## Typical analyses
Outstanding by counterparty / currency / tenor as of a date; weighted average rate and
maturity; maturity ladder; new business volumes and average rate by month; interest
income/expense (accrued and paid); counterparty limit utilisation; concentration.

## Extra validation checks
- maturity_date > value_date >= trade_date for every deal.
- Recomputed interest (principal x rate x days / basis) matches the interest column within rounding.
- Weighted average rate lies between the minimum and maximum deal rate.
- Outstanding principal on the as-of date reconciles to the position report, if one exists.
