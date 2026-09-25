---
name: domain-packs
description: How to choose, read, apply and improve the Treasury domain packs in knowledge/domains/ (treasury_common, liquidity_management, money_market, interest_rate_management, balance_sheet_management, fx_management, funding_management). Use when profiling a new file, planning or reviewing an analysis, and after stakeholder sessions.
---
# Domain packs

Packs are **starter Treasury expertise**, not confirmed facts. They tell you what data usually
means, which measures can be summed, the traps, the questions to ask, and starter definitions.
Confirmed knowledge (catalog, glossary, decisions, profile annotations) always wins.
Overview: [knowledge/domains/index.md](../../../knowledge/domains/index.md).

## Choosing packs (Profiler)
1. `python tools/profile_excel.py` stores `suggested_domains` in each profile: packs ranked by
   signals (column names 3 pts, keywords in names 1 pt, keywords in values 0.5 pt, file-name
   patterns 2 pts). Details: `python tools/domains.py suggest <profile or source>`.
2. Confirm with the user in one line, then record:
   `python tools/domains.py set <profile> treasury_common <area pack>`.
   Always include `treasury_common` with an area pack. Several area packs are allowed
   (e.g. a balance sheet file with a repricing sheet).
3. No pack scores >= 3: ask which area it is, or continue without a pack (packs are optional).
4. Recurring files: add `domains` to the source's `datasource` proposal so future files reuse
   them. A new file of a known source inherits `annotations.domains` automatically.

## Using packs
| Section | Who uses it | How |
|---|---|---|
| Typical data | Profiler | Suggest meanings, roles and additivity for unknown columns - then ask |
| Starter definitions | Analyst | Use when the glossary has no term; mark **NEW - to confirm** in the plan |
| Known traps | Analyst, Reviewer, Quick Report | Check each one that could apply |
| Questions to ask | Profiler | Include the relevant ones in the single batch of questions |
| Typical analyses | Profiler | Fill `feasible_analyses` |
| Extra validation checks | Reviewer | Add to `checks.py` where they apply |

Cite the pack when you use it, e.g. "additivity: money_market pack, principal is semi-additive".

## Improving packs (after stakeholder sessions)
Packs are edited directly (with the user's OK), not through proposals:
- add real column names and keywords seen in files to `signals` (better automatic selection)
- move area-wide lessons from `knowledge/lessons.md` into "Known traps"
- when a starter definition is confirmed into the glossary, replace it with "see glossary: <term>"
- new area: copy `_template.md`, fill the header, list it in `index.md`
Then run `python tools/domains.py validate`.
