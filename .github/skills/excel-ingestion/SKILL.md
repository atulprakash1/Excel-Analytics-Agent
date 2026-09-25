---
name: excel-ingestion
description: Rules for loading profiled data into pandas and aggregating Treasury measures correctly - load_source/load_sheet, stocks vs flows, weighted rates, currencies, dates, joins. Use when writing analysis.py or checks.py.
---
# Loading and aggregating data

## Loading (the only way)
```python
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))                 # workspace root
from tools.load_data import load_source, load_sheet, load_source_profile

df, log = load_source("<source_id>", "<sheet>")          # recurring input: the current file
df, log = load_sheet("<profile_name>", "<sheet>")        # one-off file
```
- Header row and confirmed cleaning rules come from the profile. Keep every `log` in
  `output/data_log.json`. A `WARNING` in a log means stop and check.
- Preview: `python tools/load_data.py <source_id or profile> <sheet>`.
- Sources: `python tools/knowledge.py sources`.

## Aggregating Treasury measures (check `column_additivity` first)
| Measure | Correct | Wrong |
|---|---|---|
| Stock (balance, outstanding, position) | value at ONE as-of date; or average over dates | sum across dates |
| Stock trend | one value per date (a time series) | cumulative sum |
| Flow (interest, payments, volumes) | sum over the period | - |
| Rate (deal rate, yield) | `(amount * rate).sum() / amount.sum()` | `rate.mean()` or `rate.sum()` |
| Ratio (utilisation, LCR, NIM) | recompute from summed numerator and denominator | average of ratios |
| Amounts in several currencies | per currency, or convert first (state rate source and date) | one mixed total |

## Dates
- Outstanding on D: `(value_date <= D) & (maturity_date > D)` (confirm the maturity-day rule).
- Periods: `.dt.to_period("M")`; windows with explicit `>= start` and `< end`.
- Unpivoted period labels need parsing (e.g. `format="%b-%y"`); tenor buckets need an explicit
  sort order (O/N, 0-1M, 1-3M, ...), not alphabetical.

## Joins
- Keys from `profiles/_relationships.json` and annotations; right side unique on the key.
- `how="left"` from the main table; count unmatched rows; assert the row count is unchanged.

## Output conventions (`analysis/<report>/output/`)
- `kpis.json`: flat dict, headline numbers, `rows_in_scope`, and `as_of` for stocks.
- One CSV per table; business column names; first column is the label (or the date for trends).
- Ratios as 0-1 floats, amounts as plain floats; no symbols or separators.
- Print KPIs and main tables at the end of the script.
