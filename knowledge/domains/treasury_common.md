---
id: treasury_common
title: Treasury - common conventions
parent:
applies_when: Any Treasury data. Always read alongside the specific area pack.
signals:
  keywords: [treasury, entity, counterparty, currency, ccy, value, maturity, notional, principal, rate, bank, deal, trade, position, exposure, limit, bp, bps]
  columns: [value date, trade date, maturity date, settlement date, reporting date, as of date, currency, ccy, counterparty, legal entity, entity, deal id, trade id, notional, principal, rate, status]
  file_patterns: [*treasury*, *tms*, *position*]
---
# Treasury - common conventions (starter pack)

Status: **starter content**. General Treasury practice, not yet confirmed for this organisation.
Anything used from here must be confirmed with the data owner before it goes into the
glossary or the column catalog.

## 1. Measure types and additivity (the most important rule)
| Measure type | Examples | Additivity | Aggregate by |
|---|---|---|---|
| Stock / position | balances, outstanding principal, exposures, holdings, limits | **semi-additive over time** | sum across entities, banks, currencies (after conversion); take ONE as-of date, or average over dates |
| Flow | payments, interest paid/received, drawdowns, repayments, cash in/out | additive | sum across everything, including time |
| Rate / price / ratio | interest rate, yield, spread, FX rate, LCR, NIM, utilisation % | **non-additive** | recompute from totals, or weight by principal/balance; never sum or plain-average |
| Count | number of deals, accounts | additive (distinct counts are not) | count distinct identifiers |

## 2. Dates
- **Trade date** (agreed), **value / settlement date** (cash moves), **maturity date** (ends),
  **reporting / as-of date** (snapshot). Ask which one defines the reporting period.
- A position is **outstanding on date D** when `value_date <= D < maturity_date` (confirm whether
  the maturity day itself counts).
- Weekends and bank holidays: balances often repeat Friday's value, or rows are missing. Ask
  whether calendar-day or business-day averages are expected.
- Cut-off times differ by bank and region; "end of day" may not be the same moment everywhere.

## 3. Currencies and conversion
- Expect ISO 4217 codes (EUR, USD, GBP). Normalise case and spaces.
- **Never add amounts in different currencies** without conversion. Always confirm:
  reporting currency, rate source, rate date (spot at as-of date vs monthly average), and the
  quotation direction (EURUSD 1.08 = 1 EUR in USD).
- Stocks usually convert at the closing rate of the as-of date; flows often at average rates.

## 4. Signs and direction
Confirm the sign convention before any total:
- assets positive / liabilities negative, or both positive with a direction column;
- pay / receive, buy / sell, lend / borrow, deposit / placement / loan;
- debit / credit from ledgers.
Totals that net assets and liabilities must be labelled as net.

## 5. Units and scale
Amounts may be in units, thousands or millions - often stated only in a title row.
Rates may be in percent (3.25), decimals (0.0325) or basis points (325). Confirm each.

## 6. Day count conventions
Interest = principal x rate x days / basis. Common bases: ACT/360 (EUR, USD money markets),
ACT/365 (GBP), 30/360 (many bonds and swap fixed legs). Confirm per currency and instrument.

## 7. Entities, counterparties and intercompany
- Legal entity vs business unit vs cost centre: confirm the level used for reporting.
- Intercompany deals and balances must be eliminated for group totals. Look for an
  intercompany flag or counterparties that are group entities.
- Counterparty names vary in spelling; look for an identifier (LEI, internal ID).

## 8. Status and versions
- Deal status: live, matured, cancelled, amended. Cancelled and superseded rows usually must be excluded.
- Snapshots vs restated history: a figure for last month may change in a later file.

## Questions to ask for any Treasury file
1. What is the as-of / reporting date, and which date column defines the period?
2. What currency are amounts in, and how should they be converted (rate source and date)?
3. What is the sign convention?
4. What units are amounts and rates in?
5. Are intercompany items included, and should they be eliminated?
6. Which statuses count (live only)?

## Standard validation checks (Treasury)
- Stock measures are taken at one as-of date (or averaged), never summed across dates.
- No cross-currency total without an explicit conversion step and stated rate date.
- Rates recomputed as weighted averages (by principal or balance), never plain averages.
- Maturity date >= value date >= trade date for every deal.
- Rates within a plausible range (negative rates can be valid; confirm).
- Totals reconcile to the file's own totals or to the source system.

## Data sensitivity
Account numbers, counterparty names and deal details can be confidential. Mask account
numbers in reports (last 4 digits) and never copy raw rows into the knowledge base.
