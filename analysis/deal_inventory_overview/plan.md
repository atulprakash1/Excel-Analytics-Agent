# Analysis plan: IAM Deal Inventory Overview

**Type:** Full review
**Requested by:** user
**Date:** 2026-09-25
**Question:** What is the total notional by deal type, maturity profile, currency exposure, and portfolio split?
**Domain packs:** money_market

## Data (from confirmed profiles)
| Source | Sheet | Grain |
|---|---|---|
| IAM_Deal_Inventory_DUMMY_2026-08-01.xlsx | IAM Deal Inventory | one deal (Murex ID) as of the single Reporting Date |

## Measures (cite knowledge/glossary.md; if missing, a domain pack starter definition marked NEW)
- Notional in CCY: semi_additive over time - outstanding notional per deal, in EUR (single-currency
  file). Confirmed with user: summed across deals at the one reporting date for all totals/splits
  below, never summed across dates. NEW - no glossary entry yet; profiled and confirmed directly
  with the user for this report (see `profiles/IAM_Deal_Inventory_DUMMY_2026-08-01.profile.json`).

## Filters, as-of date / time window, currency, joins
- As-of date: the file's single Reporting Date, 2026-08-01 (confirmed with user as "today" for
  maturity bucketing, since the file is a snapshot dated in the past relative to the current date).
- No row filters: all 1,019 deals are in scope (no cancelled/void status column present).
- Currency: single currency, EUR, for every row - confirmed with user, no conversion needed.
- No joins - single source, single sheet.
- Maturity windows are cumulative from the as-of date, not mutually-exclusive buckets: "next 7 days"
  is a subset of "next 30 days", which is a subset of "next 90 days", etc. - matching the question
  as asked ("total amount maturing in next 7, 30, 90, and 365 days").

## Outputs (output/)
- `kpis.json` - total notional, Loan/Deposit totals, maturity-window totals, as-of date
- `by_deal_type.csv` - notional, deal count and share by Deal Type (Loan / Deposit)
- `maturity_windows.csv` - notional, deal count and share maturing within 7 / 30 / 90 / 365 days
- `maturity_by_year.csv` - notional, deal count and share by calendar year of Maturity Date
- `by_currency.csv` - notional, deal count and share by currency (single EUR row)
- `portfolio_split.csv` - Loan, Deposit and Total notional by Murex Portfolio

## Decisions, lessons and domain traps applied (cite knowledge/)
- Treated "Notional in CCY" as a stock per the `money_market` domain pack convention (never summed
  over time); the single Reporting Date makes this a straightforward single-snapshot position.
- No knowledge-base entries existed yet for this file (0 recognised / 18 unknown at profiling); all
  column meanings were confirmed directly with the user rather than assumed.
