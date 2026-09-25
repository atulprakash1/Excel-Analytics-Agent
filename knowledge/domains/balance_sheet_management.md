---
id: balance_sheet_management
title: Balance sheet management
parent: treasury_common
applies_when: Balance sheet structure and mix, asset-liability management (ALM), funding structure, net interest margin, cost of funds, funds transfer pricing (FTP), capital and leverage ratios, average balances.
signals:
  keywords: [balance, sheet, alm, asset, assets, liability, liabilities, equity, funding, structure, nim, margin, yield, cost, ftp, transfer, pricing, capital, cet1, rwa, leverage, ldr, average, gl, ledger]
  columns: [balance sheet line, line item, gl account, account code, assets, liabilities, equity, average balance, month end balance, yield, cost of funds, interest income, interest expense, nim, ftp rate, rwa, cet1, tier 1, leverage exposure, hierarchy, parent line]
  file_patterns: [*balance*sheet*, *alm*, *bs*, *nim*, *ftp*, *capital*, *funding*structure*]
---
# Balance sheet management (starter pack)

Status: **starter content** - confirm with the ALM / Balance Sheet Management team.

## Typical data
| Looks like | Usually means | Additivity | Always confirm |
|---|---|---|---|
| Balance sheet line, GL account, line item | Row dimension, often hierarchical | - | Which rows are subtotals / parents |
| Month-end balance | Stock at period end | semi-additive over time | Book vs average |
| Average balance | Daily or monthly average | non-additive over time (re-average) | Daily vs month-end average method |
| Interest income / expense | Flow for the period | additive | Accrual basis; includes fees? |
| Yield, cost of funds, NIM, FTP rate | Rates | non-additive | Annualised? Day count? |
| RWA, CET1, leverage exposure | Capital metrics | RWA additive across portfolios; ratios non-additive | Regulatory vs internal basis |

## Starter definitions (confirm locally)
- **Net interest income (NII)** = interest income - interest expense for the period.
- **Net interest margin (NIM)** = annualised NII / average interest-earning assets.
- **Yield on assets** = annualised interest income / average interest-earning assets.
- **Cost of funds** = annualised interest expense / average interest-bearing liabilities.
- **Loan-to-deposit ratio** = customer loans / customer deposits.
- **Funding mix** = each funding source / total funding (share of total).
- **CET1 ratio** = CET1 capital / RWA; **leverage ratio** = Tier 1 capital / leverage exposure.
- **FTP margin** = customer rate - FTP rate (per product), weighted by balance.

## Known traps
- Hierarchies: summing parent and child lines double counts. Use leaf lines only, or one level.
- Liabilities may be negative in ledger extracts; balance sheet reports often show both positive.
- Average balance vs month-end balance give different NIMs - always state which.
- Ratios must be annualised consistently (days in period / days in year).
- Reclassifications between periods break trends; check line mappings per period.
- Regulatory figures (capital, LCR) follow specific rules - use the official figure, don't rebuild it.

## Questions to ask
1. Which rows are leaf lines, and which are subtotals?
2. Month-end or average balances for margins and mix?
3. Sign convention for liabilities and equity?
4. Annualisation method (actual days vs 12 x monthly)?
5. Is this regulatory or management reporting basis?

## Typical analyses
Balance sheet composition and trend; asset and funding mix; NII, NIM, yield and cost-of-funds
trends; FTP margins by product; loan-to-deposit ratio; capital ratio trend vs targets.

## Extra validation checks
- Total assets = total liabilities + equity for each date (within rounding).
- Leaf lines sum to their parent lines where the file includes both.
- Ratios recomputed from totals match the file's stated ratios, if present.
