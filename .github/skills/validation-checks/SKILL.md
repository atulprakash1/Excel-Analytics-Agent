---
name: validation-checks
description: Checklist and helper for independently validating a Treasury analysis before reporting - reconciliation, stock vs flow, currencies, weighted rates, grain, joins, domain-pack checks. Use when reviewing analysis/<report> and writing checks.py and review.md.
---
# Validating an analysis

## Principle
Recompute, don't re-read. `checks.py` loads the source again and derives the key numbers a
*different* way from `analysis.py`. Agreement between two routes is the evidence.
Scaffolded reports already contain the standard checks; you add the question-specific ones.

## Helper ([validate.py](../../../tools/validate.py))
```python
from tools.validate import Validator
v = Validator("<report>")                        # review_level="quick" for fast-path reports
v.reconcile("Headline vs independent recompute", source_value, report_value)   # 0.5% tolerance
v.row_count("Rows in scope", expected, actual)
v.unique(df, ["<id column>", "<date column>"], label="Grain: one row per account per day")
v.no_nulls(df, ["<dimension>", "<measure>"])
v.shares_sum_to_one(table["Share"])
v.check("<name>", condition, "<detail>")
v.warn("<name>", "<detail>")                     # shown in the report, not a failure
v.save()                                         # writes validation.json; exits 1 on failure
```

## Mandatory checks
1. Headline reconciles to an independent recompute from source.
2. Breakdown tables sum to the headline; a stock's time-series table ends at the headline.
3. Reconcile to totals in the source file where they exist (total rows, total columns), explaining differences.
4. Row count in scope; grain uniqueness; no nulls in used columns.
5. **Stocks** are taken at one as-of date (or explicitly averaged).
6. **Currencies:** no total across currencies unless converted (rate source and date stated).
7. **Rates and ratios:** weighted by amount or recomputed from totals; weighted rate lies between min and max rate.
8. Joins: no rows gained or lost; unmatched keys counted.
9. Statuses in scope as planned (e.g. cancelled deals excluded).
10. Every profile `open_question` carried as `v.warn(...)`.
11. The domain packs' "Extra validation checks" that apply (e.g. maturity > value date,
    recomputed interest matches, assets = liabilities + equity, buckets sum to total).
12. Definitions match `knowledge/glossary.md` or are marked NEW; applicable decisions and lessons followed.

## review.md
```
# Review: <report>
Verdict: PASS | PASS WITH NOTES | FAIL
Checks: <passed>/<total> (validation.json)
## Issues
| Severity | Issue | Where | Suggested fix |
## Caveats for the report
## Lessons for next time
```
