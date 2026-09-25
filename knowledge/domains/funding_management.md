---
id: funding_management
title: Funding and debt management
parent: treasury_common
applies_when: Credit facilities, loans and drawdowns, bonds and notes, debt maturity profiles, covenants, cost of debt, headroom.
signals:
  keywords: [funding, debt, facility, facilities, rcf, revolving, loan, loans, drawdown, drawn, undrawn, bond, bonds, note, notes, issuance, covenant, covenants, headroom, coupon, amortisation, repayment, commitment]
  columns: [facility, facility limit, commitment, drawn amount, undrawn amount, utilisation, lender, coupon, margin, all in cost, issue date, maturity date, face value, carrying amount, amortisation, repayment schedule, covenant, ratio, threshold]
  file_patterns: [*facility*, *facilities*, *debt*, *loan*, *bond*, *funding*, *covenant*]
---
# Funding and debt management (starter pack)

Status: **starter content** - confirm with the Funding / Capital Markets team.

## Typical data
| Looks like | Usually means | Additivity | Always confirm |
|---|---|---|---|
| Facility, lender, commitment / limit | Credit line | semi-additive over time | Committed vs uncommitted |
| Drawn amount | Used part of the facility | semi-additive | Includes letters of credit / guarantees? |
| Undrawn / headroom | Available part | semi-additive | Conditions precedent; ancillary use |
| Coupon, margin, all-in cost | Pricing | non-additive | Base rate + margin; fees included? |
| Face value vs carrying amount | Bond amounts | semi-additive | Which one reporting uses |
| Covenant ratio, threshold | Financial covenant | non-additive | Definition per agreement; test dates |

## Starter definitions (confirm locally)
- **Utilisation** = drawn amount / committed limit.
- **Undrawn committed headroom** = committed limit - drawn - ancillary utilisation.
- **Gross debt** = sum of drawn loans and bonds outstanding (face or carrying - confirm).
- **Net debt** = gross debt - cash and cash equivalents (definition varies by agreement).
- **Weighted average cost of debt** = sum(outstanding x all-in rate) / sum(outstanding).
- **Weighted average maturity** = sum(outstanding x years to maturity) / sum(outstanding).
- **Maturity profile**: outstanding repayments grouped by year of maturity.

## Known traps
- Covenant definitions come from each agreement (e.g. EBITDA adjustments); don't use a generic formula for compliance.
- Amortising loans: outstanding falls over time; the maturity date alone overstates late buckets.
- Face value vs carrying amount (discounts, fees) give different totals.
- Uncommitted lines should not count as headroom unless confirmed.
- Multi-currency facilities: limits in one currency, drawings in several.

## Questions to ask
1. Committed only, or all facilities? Which ancillary uses reduce headroom?
2. Face or carrying amount for debt totals?
3. Which net debt and covenant definitions apply, and on which test dates?
4. Are repayment schedules available for amortising loans?

## Typical analyses
Facility utilisation and headroom; debt maturity profile; fixed/floating mix; weighted average
cost and maturity; covenant headroom vs thresholds; refinancing needs by year.

## Extra validation checks
- Drawn <= committed limit per facility (flag breaches).
- Maturity profile buckets sum to total outstanding.
