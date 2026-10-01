# Treasury analytics workspace - multi-agent reporting in VS Code

Treasury Excel files go in; validated, well-designed HTML reports come out. Everything runs
locally in VS Code with GitHub Copilot Chat: no remote repo, no CI, no external API.

The workspace ships **clean**: no sample reports and no learned knowledge, only the agents, the
tools and a **starter Treasury knowledge pack** (domain packs). Knowledge about your own files is
built up with your stakeholders, one confirmed fact at a time.

```
data/raw/*.xlsx
    │
Profiler ──► profiles/<file>.profile.json + .html   (data contract + domain packs, confirmed by a person)
    │
Analyst ───► analysis/<report>/plan.md, analysis.py → output/
    │
Reviewer ──► checks.py → validation.json, review.md
    │
Report Builder ► build_report.py → reports/<report>.html
    │
Curator ───► proposals → (you approve) → knowledge/   (and suggested improvements to domain packs)
```
**Fast path:** once data is confirmed, the Quick Report agent does the whole thing in one pass.

## What's in the box
| Path | Purpose |
|---|---|
| `AGENTS.md` | Repository-wide rules for any AI agent: setup, folder map, commands, data rules (read by Copilot and other tools) |
| `.github/copilot-instructions.md` | Copilot-specific workflow: the six agents, handoffs, skills and prompts |
| `.github/agents/` | Profiler, Analyst, Reviewer, Report Builder, Curator, Quick Report |
| `.github/skills/` | data-profiling, domain-packs, excel-ingestion, validation-checks, html-report, knowledge-base, report-registry, fast-path |
| `.github/prompts/` | `/new-report`, `/quick-report`, `/refresh-report`, `/capture-learnings` |
| `knowledge/domains/` | **Starter Treasury knowledge pack** (see below) |
| `knowledge/` (other files) | Confirmed knowledge - starts empty |
| `tools/profile_excel.py` | Profiler: structure, types, quality, drift, joins, catalog matches, domain suggestions |
| `tools/domains.py` | Rank, record and validate domain packs |
| `tools/load_data.py` | The only data loader (`load_source` / `load_sheet`) with confirmed cleaning rules |
| `tools/knowledge.py` | Catalog matching, logical sources, curation brief, proposals, approval, lint |
| `tools/scaffold_report.py` | Writes a report's four files, Treasury-aware (stocks, rates, currencies) |
| `tools/validate.py` | Validation helper |
| `tools/report_kit.py` | Dependency-free HTML reports with inline SVG charts |
| `tools/run_pipeline.py` | Runs a report end to end and records the run |
| `tools/reports.py` | Report registry: list, find, uses, check, refresh-all, catalogue page |
| `tools/fast_path_check.py` | Eligibility gate for the fast path |
| `tools/reset_workspace.py` | Archive and return to a clean slate |
| `samples/make_treasury_samples.py` | Optional messy Treasury sample files for a smoke test |
| `.vscode/settings.json` | Auto-approves the workspace's own scripts; always asks for approvals and resets |

## Libraries
Only `pandas` and `openpyxl` (plus the standard library): `pip install -r requirements.txt`.
No jinja2, matplotlib, plotly or scipy. Legacy `.xls` files: re-save as `.xlsx`.

## Setup
1. Python 3.9+, `pip install -r requirements.txt`.
2. Open the folder in VS Code, sign in to GitHub Copilot.
3. Check your Copilot policies allow custom agents, agent skills and terminal commands in agent mode.
4. Open Chat; the agents dropdown should list the six agents.
5. If an agent can't run commands or edit files, reselect its tools with **Configure Tools**
   (tool names differ slightly between VS Code versions).

## Starter knowledge pack (domain packs)
`knowledge/domains/` holds Treasury expertise the agents use before anything is confirmed:

| Pack | Covers |
|---|---|
| `treasury_common` | Additivity of stocks/flows/rates, dates, currencies, signs, units, day count, intercompany |
| `liquidity_management` | Bank balances, cash positions and pooling, forecasts, buffers, LCR/NSFR, liquidity gaps |
| `money_market` | Deposits, placements, borrowings, CDs, CP, repo, MMFs, maturity ladders, weighted rates |
| `interest_rate_management` | Repricing gaps, NII/EVE sensitivity, duration, PV01, swaps and hedges |
| `balance_sheet_management` | Balance sheet mix, ALM, NIM, cost of funds, FTP, capital and leverage |
| `fx_management` | Exposures, trades, open positions, hedge ratios, revaluation |
| `funding_management` | Facilities, drawdowns, bonds, maturity profiles, covenants |

Each pack has: typical columns with their additivity, starter definitions, known traps,
questions to ask, typical analyses and extra validation checks.

**How a pack is chosen:** the profiler scores every pack against each file (column names, file
and sheet names, values) and stores a ranking. The Profiler agent confirms the choice with you and
records it (`python tools/domains.py set <profile> treasury_common money_market`). For recurring
files the choice is stored on the source, so next month's file reuses it.

**Domains are optional.** Without a pack the Profiler asks generic questions; everything else works.
Packs matter most for the first files of a new area.

**Packs are guidance, never confirmed facts.** A starter definition is used only after a
stakeholder confirms it, and then it moves to the glossary. After stakeholder sessions, edit the
packs directly (real column names into `signals`, lessons into "Known traps"); the Curator
suggests such edits. Add a new area by copying `_template.md`. Check with `python tools/domains.py validate`.

## Starting (and restarting) from a clean slate
```
python tools/reset_workspace.py --dry-run      # what would be archived and cleared
python tools/reset_workspace.py --yes          # archive to _archive/, then reset
```
Clears data, profiles, reports and all learned knowledge; keeps agents, skills, tools and the
domain packs. Restore a previous test by unzipping its archive over the workspace.

**Testing several Treasury areas:** use one copy of the clean workspace per area to compare
results fairly, then one combined workspace. Compare: questions asked by the Profiler, columns
recognised from memory on the second and third file of a source, and checks that failed.

## Smoke test (optional, 5 minutes)
```
python samples/make_treasury_samples.py   # bank balances, money market deals, repricing gap
python tools/profile_excel.py             # note the suggested domain packs per file
```
Then in Chat: `/new-report What is the EUR cash position by entity at month-end?` and follow the
handoffs. Things the samples are designed to trigger: title rows above headers, daily "Total" rows
that mix currencies, account numbers with leading zeros, currency case variants, amounts and rates
stored as text, cancelled deals, a wide tenor-bucket gap report with subtotal rows and a Total column.
`python samples/make_treasury_samples.py --next-month` adds next month's balances file to test refresh.

## Confirmed knowledge (grows with use)
- The profiler matches column names to `knowledge/column_catalog.json`; recognised columns are
  pre-filled, so the Profiler only asks about new ones.
- The Analyst takes definitions from `knowledge/glossary.md` (or a pack's starter definition marked NEW).
- The Reviewer checks against the glossary, decisions, lessons and the packs' checks.
- The Curator works from `python tools/knowledge.py brief <report>` - one short text of what the run
  confirmed - instead of re-reading the profiles, plan, review and knowledge files.
- The Curator proposes what was confirmed; nothing enters memory without your approval
  (`python tools/knowledge.py pending | approve <ids> --by "<name>"`). Every change is logged.

## Report registry and recurring files
- Recurring inputs are **logical sources** (`knowledge/source_registry.json`): a file pattern such
  as `bank_balances_*.xlsx`, a rule for the current file, and the domain packs. Reports load
  `load_source("bank_balances", "Balances")`, never a dated file name.
- A new month's file inherits the confirmed annotations if its structure matches; structure changes
  or unexpected values (a new currency or entity) block only the reports that use it.
- Each report has `analysis/<report>/report.json`: inputs, outputs, owner, schedule, run history.
```
python tools/reports.py list | find "<words>" | uses <file> | refresh-all <source> | check
```
`reports/index.html` is the catalogue page for the business.

## Fast path
`/quick-report <question>` for routine questions on confirmed data. A gate script decides
eligibility; the scaffold handles Treasury traps automatically (stocks at one as-of date, rates
never summed, multi-currency totals blocked until converted). Reports carry a "Quick report" badge
and can be promoted to a full review. External, board and regulatory reports use the full flow.

## Suggested stakeholder session per Treasury area (60-90 minutes)
1. Bring 2-3 real files for the area (anonymised if needed) and one existing manual report.
2. Profile them; walk through the profile HTML and answer the Profiler's questions together.
3. Build the existing manual report with the agents and reconcile the numbers.
4. Run `/capture-learnings`: approve glossary terms, decisions and columns; accept pack edits.
5. Afterwards: re-profile the next month's file and count how many questions remain.

## Success criteria (suggested)
- Numbers match the existing manual report exactly.
- Time from question to validated report vs today.
- Questions per new file fall as confirmed knowledge grows; columns recognised from memory rise.
- A monthly refresh runs in one command and stops safely when inputs change.
- Quick reports on confirmed data in a few minutes, with no manual steps.

## Data handling
Source files stay in `data/raw/` and are never modified. Copilot sees file content that agents read
into chat, so use approved or anonymised data and follow your organisation's Copilot data policy.
Account numbers are masked in reports; raw rows are never stored in the knowledge base.
