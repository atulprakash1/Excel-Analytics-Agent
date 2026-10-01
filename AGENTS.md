# AGENTS.md - Treasury analytics workspace

Guidance for any AI coding agent working in this repository (GitHub Copilot, Claude Code,
Codex, Cursor and others). Copilot-specific workflow - custom agents, handoffs, skills and
prompts - lives in `.github/copilot-instructions.md`.

## What this repository does
Turns Treasury Excel/CSV files into validated, self-contained HTML reports. Work runs locally:
no remote services, no CI, no external APIs. The pipeline is:

1. **Profile** the inputs (`tools/profile_excel.py`) and confirm their meaning with a person.
2. **Analyse** with pandas in `analysis/<report>/analysis.py`, writing tables to `output/`.
3. **Validate** independently in `analysis/<report>/checks.py` (writes `validation.json`).
4. **Build** the HTML report with `analysis/<report>/build_report.py` into `reports/`.
5. **Learn**: confirmed facts are proposed to `knowledge/` and approved by a person.

## Setup
- Python 3.9+. Only `pandas` and `openpyxl` beyond the standard library:
  `pip install -r requirements.txt`. Do not install or import any other package.
- Run every command from the repository root.

## Repository map
| Path | Contents | Agents may |
|---|---|---|
| `data/raw/` | Source Excel/CSV files | **read only** - never edit, move, rename or re-save |
| `profiles/` | Generated profiles (`*.profile.json`, `*.profile.html`) | edit `annotations` only, after the user confirms |
| `analysis/<report>/` | `report.json`, `plan.md`, `analysis.py`, `checks.py`, `build_report.py`, `output/` | create and edit |
| `reports/` | Generated HTML reports and `index.html` | generate via scripts only |
| `knowledge/` | Confirmed knowledge (catalog, glossary, decisions, lessons, sources, source registry) | **propose only** via `tools/knowledge.py` |
| `knowledge/domains/` | Starter Treasury domain packs (guidance, not confirmed facts) | edit only when the user asks |
| `tools/` | Shared tools used by every report | change only when the user asks |
| `work/` | Scratch files | anything |

## Commands
```
python tools/profile_excel.py                      # profile data/raw (cached when unchanged)
python tools/profile_excel.py <file> --prefill     # + draft annotations and open questions to confirm
python tools/domains.py suggest <profile|source>   # which Treasury domain pack fits
python tools/load_data.py <source|profile> <sheet> # preview data after confirmed cleaning
python tools/reports.py find "<words>"             # look for an existing report first
python tools/scaffold_report.py <report> --source <source_id>:<sheet> --measure "<column>" [--bucket-column "<date>"] [--quick]
python tools/run_pipeline.py <report>              # analysis -> checks -> report, recorded
python tools/reports.py list | uses <file> | check | refresh-all <source>
python tools/fast_path_check.py <source|profile>   # is a one-pass quick report allowed?
python tools/knowledge.py status | pending | lint | sources
python tools/knowledge.py brief [<report>]         # what a run confirmed, in one short text (read this, not the files)
python tools/domains.py validate                   # after editing a domain pack
```
"Tests" for this repo: a report is done only when `run_pipeline.py` finishes with all checks
passed, and `python tools/reports.py check` and `python tools/knowledge.py lint` report no issues.

## Rules
1. **Load data only through `tools/load_data.py`**: `load_source("<source_id>", "<sheet>")` for
   recurring inputs, `load_sheet("<profile>", "<sheet>")` for one-off files. Never call
   `pd.read_excel` in analysis code; never hard-code a dated file name.
2. **Never analyse unconfirmed data.** A profile must have status `confirmed`.
3. **Respect additivity** recorded in the profile:
   stocks (balances, positions, outstanding) are taken at one as-of date, never summed over time;
   flows (payments, interest) are summed; rates and ratios are weighted or recomputed, never
   summed or plain-averaged.
4. **Never add amounts in different currencies** without an explicit conversion with a stated
   rate source and date.
5. **Every number in a report comes from `output/`**, produced by code. Never type numbers.
6. **Validate independently**: `checks.py` recomputes from source and must not import `analysis.py`.
7. **Trust order**: confirmed knowledge in `knowledge/` > domain packs > assumptions. If the data
   contradicts the knowledge base, stop and ask; don't silently follow either.
8. **Humans approve knowledge.** Propose with `tools/knowledge.py`; run `approve`, `reject`,
   `deprecate` or `tools/reset_workspace.py` only when the user explicitly asks.
9. **Build from the tools and the knowledge base**, not by copying other report folders.
10. **Keep data local.** Show at most small samples in chat, mask account numbers, and never write
    raw rows, personal data or account numbers into `knowledge/`.
11. Run code and read its output before stating results.

## Code conventions
- Python, pandas; business-language column names in outputs (`Closing Balance`, not `amt_sum`).
- Outputs: `output/kpis.json` (flat dict, plus `as_of` for stocks) and one CSV per table; ratios as
  0-1 floats, amounts as plain numbers.
- Reports use `tools/report_kit.py` only: no external CSS, fonts, scripts or images.
- Report folder names in `lower_snake_case`.

## Where to learn more
- `.github/copilot-instructions.md` - the multi-agent workflow (Copilot)
- `.github/skills/*/SKILL.md` - detailed procedures (profiling, ingestion, validation, reports, knowledge, registry, fast path, domain packs)
- `knowledge/index.md` and `knowledge/domains/index.md` - how knowledge and domain packs work
- `README.md` - setup, testing and stakeholder sessions
