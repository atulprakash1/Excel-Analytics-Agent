---
id: fx_management
title: FX management
parent: treasury_common
applies_when: FX exposures, FX trades (spot, forward, swap, option), hedging of currency risk, open currency positions, FX rates and revaluation.
signals:
  keywords: [fx, foreign, exchange, currency, spot, forward, forwards, swap, option, hedge, hedging, exposure, exposures, revaluation, mtm, pair, cross, points, open, position]
  columns: [currency pair, ccy pair, buy currency, sell currency, buy amount, sell amount, bought, sold, spot rate, forward rate, forward points, deal rate, near leg, far leg, mtm, mark to market, exposure, hedge ratio, hedged amount, fx rate]
  file_patterns: [*fx*, *forex*, *currency*, *hedge*, *exposure*]
---
# FX management (starter pack)

Status: **starter content** - confirm with the FX / Currency Risk team.

## Typical data
| Looks like | Usually means | Additivity | Always confirm |
|---|---|---|---|
| Buy / sell currency and amount | The two legs of a trade | additive per currency only | Which side is "ours" |
| Currency pair (EURUSD) | Quote convention | dimension | Base / quote currency orientation |
| Deal / spot / forward rate, forward points | Prices | non-additive | Points scaling (pips); rate direction |
| Near / far leg | FX swap legs | per currency | Both legs present or one row per swap |
| MTM / mark to market | Current value | semi-additive over time | Valuation currency and date; sign |
| Exposure, hedged amount | Risk to hedge | semi-additive | Forecast vs balance sheet exposure |

## Starter definitions (confirm locally)
- **Open position** (currency C) = assets in C - liabilities in C + bought C - sold C.
- **Hedge ratio** = hedged amount / exposure (same currency, same horizon).
- **Forward rate** = spot rate + forward points / points scale.
- **Revaluation / MTM** = notional x (market forward rate - deal rate), discounted; use the system figure where available.
- **Weighted average deal rate** = sum(amount x rate) / sum(amount), per currency pair and direction.

## Known traps
- Adding buy and sell amounts across currencies without conversion.
- Pair orientation: EURUSD vs USDEUR inverts the rate; triangulation through a base currency.
- FX swaps have two legs in opposite directions; counting both as exposure double counts.
- Points scaling differs by pair (e.g. /10,000 for most, /100 for JPY pairs).
- MTM sign: gain/loss from whose perspective.
- Rate date: trade-date rate vs revaluation date rate.

## Questions to ask
1. Which currency is the reporting currency, and which rate source and date?
2. Are exposures forecast cash flows or balance sheet positions?
3. Are FX swaps shown as one row or two legs?
4. Sign convention for MTM and positions?

## Typical analyses
Open currency positions; hedge ratios by currency and horizon; forward book by maturity;
MTM by counterparty; average hedge rates vs budget rates.

## Extra validation checks
- Per-currency totals only; any cross-currency total has an explicit conversion.
- For each trade, buy amount / sell amount ≈ deal rate (in the pair's orientation).
