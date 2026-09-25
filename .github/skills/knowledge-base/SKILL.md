---
name: knowledge-base
description: How to read, cite and grow the confirmed knowledge in knowledge/ (column catalog, glossary, decisions, lessons, source notes, source registry) with the propose-then-approve workflow. Use at the start of any task and at the end of a run.
---
# Using and growing the knowledge base

Start with [knowledge/index.md](../../../knowledge/index.md). All writes go through
[knowledge.py](../../../tools/knowledge.py). Domain packs are separate: see the `domain-packs` skill.

## Reading
1. `lessons.md` and the relevant `decisions.md` entries before any work.
2. The profiler has matched every column to the catalog: `catalog.match` = `confirmed` |
   `ambiguous` | `none` | `period_column`; confirmed matches pre-fill roles, meanings and additivity.
3. Measure definitions come from `glossary.md` - cite them ("Weighted average rate - glossary").
   Missing: use a domain-pack starter definition marked **NEW - to confirm**.
4. One column: `python tools/knowledge.py lookup "<column name>" --file <file>`.

## Trust rules
- `confirmed`: use and cite, but check it fits the data (`catalog.warning` flags type conflicts).
- `ambiguous`: ask which entry applies, then propose `scope_files`.
- `none`: unknown - never borrow a meaning from a similar name without asking.
- Same meaning, new name -> alias. Same name, different meaning or format -> new entry scoped to its file.

## Writing: propose, never edit
| To record | Command |
|---|---|
| Columns from a confirmed profile | `python tools/knowledge.py propose-from-profile <profile>` |
| Alias for an existing column | `python tools/knowledge.py propose-alias <entry_id> "<name>" --seen-in "<file>:<sheet>" --why "..."` |
| Glossary, decision, lesson, source note | payload in `work/proposal.json`, then `python tools/knowledge.py propose --type glossary|decision|lesson|source --payload-file work/proposal.json --why "..."` |
| Logical source for a recurring file | `--type datasource` with `{id, pattern, select, description, owner, frequency, sheets, domains}` |
| Several at once (preferred) | a JSON **list** `[{"type": "decision", "payload": {...}, "why": "..."}, ...]`, then `python tools/knowledge.py propose --payload-file work/proposals.json` - one call; the whole list is checked before anything is added (`--type` / `--why` fill items that omit them) |
| Change to an existing entry | payload with `id` + changed fields, `--action update` |

Payloads:
- **column:** `id` (business snake_case, e.g. `closing_balance`), `label`, `aliases`, `meaning`,
  `role`, `type`, `unit` (e.g. currency or "%"), `additivity`, `semi_additive_over`, `scope_files`, `seen_in`, `source`, `notes`
- **glossary:** `term`, `definition`, `formula`, `related_columns`
- **decision:** `title`, `decision`, `applies_to`
- **lesson:** `title`, `what_happened`, `rule`, `applies_to`
- **source:** `file`, `description`, `owner`, `frequency`, `quirks`, `used_by`

Pending items in `knowledge/_proposals.json` may be improved before approval. Nothing else in
`knowledge/` is edited directly, except domain packs with the user's OK.

## Approval (a person decides)
1. `python tools/knowledge.py pending` -> present in plain English, grouped by type.
2. Apply exactly what the user says: `approve <ids> --by "<name>"`, `reject <ids> --by ... --reason ...`.
3. `python tools/profile_excel.py` so profiles pick up the new knowledge.

## Maintenance
`python tools/knowledge.py lint` (alias clashes, missing additivity, stale entries, source
patterns, pending proposals); retire entries with `deprecate`; `status` for an overview.
