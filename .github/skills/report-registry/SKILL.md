---
name: report-registry
description: How reports are registered and connected to their inputs - logical sources, report.json manifests, finding existing reports, dependency lookups, freshness and bulk refresh. Use before building any report, when a new or changed input arrives, and when refreshing.
---
# Report registry

| Registry | File | Answers |
|---|---|---|
| Logical sources | `knowledge/source_registry.json` | Which file is the current one for a recurring input, and its domain packs |
| Report manifests | `analysis/<report>/report.json` | What a report reads and produces, and its run history |

## Logical sources (illustrative)
```json
{"id": "bank_balances", "pattern": "bank_balances_*.xlsx", "select": "last_by_name",
 "description": "Monthly file of daily bank balances", "owner": "Liquidity team",
 "frequency": "monthly", "sheets": ["Balances"], "domains": ["treasury_common", "liquidity_management"]}
```
- `select`: `last_by_name` (date-sortable names like `_2026_09`) or `newest_modified`.
- Reports call `load_source("<source_id>", "<sheet>")`, so the next file is picked up automatically.
- A new file of a source inherits confirmed annotations and domains when the structure matches;
  structure changes or values outside confirmed rules mark it `needs_review`.
- List: `python tools/knowledge.py sources`. Add or change: `datasource` proposal (`knowledge-base` skill).
- One-off files: `load_sheet("<profile>", ...)`.

## Manifests
Written by `scaffold_report.py` (or `python tools/reports.py init <report> --from-code`), updated by
`run_pipeline.py` after each run (status, files and hashes, KPIs, validation, duration; 12 runs kept).

## Commands
```
python tools/reports.py find "<key words>"            # BEFORE building a report
python tools/reports.py list                          # all reports, inputs, freshness
python tools/reports.py show <report>
python tools/reports.py uses <file | source | profile>
python tools/reports.py check [report]
python tools/reports.py refresh-all <file | source>
python tools/reports.py index                         # reports/index.html
```
Freshness: `current` | `new data available` | `never run` | `last run <status>` | `blocked: <reason>`.

## Rules
1. Search before building; offer to refresh or extend a matching report.
2. Recurring inputs get a logical source; never hard-code dated file names.
3. When a profile needs review, run `uses <file>` and name the affected reports.
4. Keep `report.json` in step with the code (`check <report>`).
