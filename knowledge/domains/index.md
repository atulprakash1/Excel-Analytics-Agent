# Domain packs (starter knowledge base)

Domain packs give agents area-specific expertise: what the data usually means, which measures
can be summed, known traps, the questions worth asking, and starter definitions.

**Packs are guidance, not confirmed facts.** They shape questions and suggestions. Anything
taken from a pack is confirmed with the data owner before it enters the glossary or the column
catalog. The knowledge base (catalog, glossary, decisions) always wins over a pack.

| Pack | Covers |
|---|---|
| `treasury_common.md` | Conventions for all Treasury data: additivity, dates, currencies, signs, units, day count, intercompany. Always read with an area pack. |
| `liquidity_management.md` | Bank balances, cash positions and pooling, cash forecasts, buffers, LCR / NSFR, liquidity gaps and headroom |
| `money_market.md` | Deposits, placements, borrowings, CDs, CP, repo, MMFs, maturity ladders, weighted average rates |
| `interest_rate_management.md` | Repricing gaps, NII / EVE sensitivity, duration, PV01, swaps and hedges |
| `balance_sheet_management.md` | Balance sheet mix, ALM, NIM, cost of funds, FTP, capital and leverage |
| `fx_management.md` | FX exposures, trades, open positions, hedge ratios, revaluation |
| `funding_management.md` | Facilities, drawdowns, bonds, maturity profiles, covenants, cost of debt |

## How a pack is chosen
1. The profiler script scores every pack against each new file (file name, sheet names,
   column names, values) using the `signals` in the pack header, and stores the ranking in the
   profile as `suggested_domains`.
2. The Profiler agent confirms the choice with the user and records it in the profile
   (`annotations.domains`), e.g. `["treasury_common", "money_market"]`. A file can use several packs.
3. For a recurring source, the chosen packs are stored on the source in
   `knowledge/source_registry.json`, so next month's file uses them without asking.
4. The Analyst, Reviewer and Quick Report agents read the recorded packs.

Commands: `python tools/domains.py list`, `python tools/domains.py suggest <profile or source>`,
`python tools/domains.py set <profile> <pack> [<pack> ...]`, `python tools/domains.py validate`.

## Domains are optional
Everything works without a pack; the Profiler then asks generic questions. Packs matter most for
the first files of a new area. As the column catalog, glossary and decisions fill up with
confirmed knowledge, the packs matter less.

## Improving packs after stakeholder sessions
Edit the Markdown directly (packs don't go through the proposal queue, because they are
never treated as confirmed facts). Good updates:
- add real column names seen in files to `signals.columns` (improves automatic selection)
- turn repeated lessons for an area into "Known traps"
- replace "starter definitions" with a pointer to the confirmed glossary term once agreed
- add a new pack for a new area by copying `_template.md`
Check the header format afterwards: `python tools/domains.py validate`.
