---
name: data-profiling
description: How to profile Treasury Excel/CSV files and write profile annotations (grain, roles, additivity, cleaning rules, feasible analyses). Use when new or changed files arrive in data/raw, or a profile is draft or needs_review.
---
# Data profiling

The script **measures**; you **interpret**. Never estimate what the script measures.

## 1. Measure
```
python tools/profile_excel.py                  # all files; unchanged files are cached
python tools/profile_excel.py data/raw/<file>  # one file
python tools/profile_excel.py --html-only      # re-render HTML after editing annotations
python tools/profile_excel.py data/raw/<file> --prefill   # also draft the annotations (below)
```
`--prefill` fills gaps in unconfirmed annotations (catalog matches and existing entries win):
roles from `suggested_role`, additivity guessed from column names (rate/%/price -> non_additive;
balance/notional/outstanding -> semi_additive over time; amount/payment/interest -> additive),
`cleaning_rules` from the suggestions, a draft grain from a unique identifier, and a meaning for
single-value columns. Every guess, outlier, unclear numeric column, wide period block and
"dated name without a logical source - recurring?" becomes an `open_questions` item. Status stays
`draft`. It never interprets business meaning: that part is yours.
It detects: header row and title rows, hidden sheets, merged cells, formulas, subtotal/total
rows, blank rows, duplicates, wide layouts (period columns like `Sep-26` and tenor buckets like
`O/N`, `1-3M`, `>5Y`, plus total columns), per-column type, nulls, distinct values, numbers or
dates stored as text, codes with leading zeros (kept as text), inconsistent spellings, outliers,
a suggested role, candidate joins, catalog matches (`knowledge-base` skill) and ranked domain
packs (`domain-packs` skill).

## 2. Interpret - `annotations` in `profiles/<file>.profile.json`
| Field | What to write |
|---|---|
| `domains` | Confirmed packs (`python tools/domains.py set ...`) |
| `sheets.<s>.include` | `false` for helper, lookup or empty sheets |
| `sheets.<s>.description` | One sentence in business terms |
| `sheets.<s>.grain` | What ONE row is after cleaning - e.g. "one account on one value date", "one deal", "one balance sheet line x currency x tenor bucket" |
| `sheets.<s>.column_roles` | `dimension`, `measure`, `date`, `identifier`, `attribute`, `unused` |
| `sheets.<s>.column_meanings` | Units, currency, sign convention, rate format (% / decimal / bp), date meaning |
| `sheets.<s>.column_additivity` | Every measure: `additive` (flows), `semi_additive over time` (balances, positions, outstanding), `non_additive` (rates, ratios, prices) |
| `sheets.<s>.column_units` | Every measure's unit: `"EUR"`, `"%"`, `"bp"`, `"days"` (carried into the catalog) |
| `sheets.<s>.cleaning_rules` | Reviewed copy of `suggested_cleaning_rules` |
| `feasible_analyses` / `not_feasible` | What the data supports, and what it can't (e.g. "group total - no FX rates") |
| `open_questions` | Anything a human must confirm |
| `answers` | Each answered question, moved here (never deleted): `{"question", "answer", "by", "on"}`. The Curator proposes decisions from these |

Grain test: the identifier columns (plus the date for daily stocks) are unique after cleaning.

## 3. Cleaning rules (executed in order by `tools/load_data.py`)
Ops: `drop_blank_rows`, `drop_rows_matching`, `drop_columns`, `strip_whitespace`,
`canonical_values`, `map_values`, `to_numeric`, `to_datetime`, `drop_duplicates`, `rename`,
`unpivot`, `filter`.
- Drop junk rows first (totals, subtotals, "Gap" rows), then fix types, then reshape, then rename.
- `canonical_values` (list of correct spellings, e.g. currency codes) beats `map_values`: it also
  absorbs future case/space variants, and values outside the list are flagged.
- Wide sheets: drop total columns, then `unpivot` with `"value_columns": "periods"` so new
  period or bucket columns are picked up automatically.
- `drop_duplicates`, `map_values`, `canonical_values`, `unpivot`: confirm with the user; remove
  `needs_confirmation` only after they agree.
- `filter` for status (e.g. exclude cancelled deals) only when the user confirms it.

## 4. Recurring files and drift
- A new file matching a logical source inherits the previous file's confirmed annotations
  (including domains) when the structure matches; new period/bucket columns don't count as drift.
- Values outside confirmed value rules (a new currency or entity) set `needs_review` with
  `review_reasons`. Confirm the new value with the user, update the rule, re-confirm.
- Structure changes: explain the `drift` block, update annotations, re-confirm.

## 5. Checklist before `status: confirmed`
- [ ] Domain packs recorded (or the user chose none)
- [ ] Each included sheet: description, grain, roles, additivity for every measure, rules
- [ ] Unknown / ambiguous columns resolved with the user
- [ ] `python tools/load_data.py <profile> <sheet>` runs; row counts explained
- [ ] Grain uniqueness holds
- [ ] All `needs_confirmation` rules confirmed or removed; open questions answered or accepted,
      and every answer recorded under `answers`
- [ ] Recurring or one-off answered; a recurring file has a logical source BEFORE any report is scaffolded
- [ ] HTML re-rendered
