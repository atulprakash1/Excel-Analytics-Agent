---
name: fast-path
description: When and how to build a Treasury report in one pass (Quick Report agent) - eligibility gate, scaffold, fill-in blocks, standard checks and fallback to the full flow. Use for routine questions on already-confirmed data.
---
# Fast path

## Allowed only when all hold
0. No existing report answers it: `python tools/reports.py find "<key words>"`.
1. `python tools/fast_path_check.py <source_id or profile> ...` prints **ELIGIBLE** (confirmed
   profiles, unchanged files, every column has a role, every measure has additivity, no ambiguity).
2. Every measure is a `knowledge/glossary.md` term.
3. The analysis is in the profiles' `feasible_analyses`; joins are in `profiles/_relationships.json`.
4. Internal, routine or exploratory use. External, board or regulatory reports use the full flow.

## What makes it fast
| Full flow | Fast path |
|---|---|
| Profiler conversation | Skipped - the gate checks profiles are confirmed |
| Plan approval pause | Plan written, not paused on; assumptions listed in the reply |
| Analyst writes all code | `scaffold_report.py` writes loading, outputs, checks, layout; agent fills small blocks |
| Reviewer writes checks | Standard checks are scaffolded and run automatically |
| 4-5 handoffs | None |

## Scaffold (names illustrative)
```
python tools/scaffold_report.py <report> --source <source_id>:<sheet> [--source ...] \
    --measure "<column>" --title "<title>" --question "<question>" [--currency "EUR "] --quick
```
Treasury-aware defaults from the profile:
- **stock** measure (semi-additive): headline at one as-of date; `kpis["as_of"]` recorded;
  time-series tables are checked by their last date. The as-of column is auto-picked (a
  single-value date = snapshot, then a "reporting/as of/position" name); override with `--as-of-column`
- **bucketing** (maturity ladder, "maturing in next N days", by year): `--bucket-column "<date>"`
  adds cumulative 7/30/90/365-day windows (`kpis["next_<N>d"]`) and a by-year table, each with
  independent checks; the windows table is listed in `CUMULATIVE_TABLES`, so it is not expected
  to sum to the headline. Never pass the as-of column as the bucket column
- **flow** measure (additive): headline = sum over rows in scope
- **rate/ratio** (non-additive): refused as headline - use the amount and a weighted average
- **currency column** present: a check fails until the headline is single-currency, or you
  convert and set `CONVERTED = True` in `checks.py`

## Filling the blocks
- `analysis.py`: filters (status, entity, currency), tables in `tables` (`{"by_x": df}`), first
  column = label or date, measure column named as printed by the scaffold, `Share` where useful.
- `checks.py`: the same filters written differently; checks for joins, applicable lessons and pack checks.
- `build_report.py`: HEADLINE / DETAIL built from `k[...]` and `tables[...]`, KPIs, section titles, NOTES.

## Fallback
Gate fails -> full flow. Checks fail twice, or the failure is about the data -> "Promote to full review".
