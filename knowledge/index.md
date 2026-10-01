# Knowledge base - read this first

Two kinds of knowledge live here:

1. **Confirmed knowledge** - facts about *this organisation's* data, confirmed by a person.
   Starts empty and grows with every run. Agents rely on it and cite it.
2. **Domain packs** (`domains/`) - starter Treasury expertise shipped with the workspace
   (liquidity, money market, interest rate, balance sheet, FX, funding, common conventions).
   Guidance for asking the right questions; never treated as confirmed. See `domains/index.md`.

| File | Holds | Used by |
|---|---|---|
| `column_catalog.json` | Confirmed columns: aliases, meaning, role, unit, additivity, where seen | Profiler script (auto-match), all agents |
| `glossary.md` | Confirmed business terms and formulas | Analyst, Reviewer, Report Builder |
| `decisions.md` | Answers to past questions | Profiler (don't re-ask), Analyst, Reviewer |
| `lessons.md` | Rules learned from mistakes caught in review | Everyone |
| `sources.md` | Notes on recurring files for people (owner, quirks) | Profiler |
| `source_registry.json` | Logical sources: file pattern -> current file, and domain packs | `load_source`, profiler, `reports.py` |
| `domains/*.md` | Starter Treasury domain packs | Profiler, Analyst, Reviewer, Quick Report |
| `_proposals.json`, `_proposals_archive.json`, `changelog.md` | Pending changes and their history | Curator, approvers, audit |

## Rules
1. **Agents propose, humans approve.** Confirmed files change only through
   `python tools/knowledge.py approve` after a person says yes.
2. **Only confirmed entries count.** Proposed or deprecated catalog entries are ignored.
3. **Cite what you use**: `catalog: <id>`, `glossary: <term>`, `decision: <title>`, `pack: <id>`.
4. **Confirmed knowledge beats domain packs; the data beats both** - raise contradictions.
5. **Domain packs are improved directly** (with the user's OK) after stakeholder sessions.

## Commands
```
python tools/knowledge.py status | pending | lint | sources
python tools/knowledge.py brief [<report>]         # what a run confirmed, in one short text
python tools/knowledge.py lookup "<column name>"
python tools/domains.py list | suggest <profile> | set <profile> <packs...> | validate
python tools/reports.py uses <file or source>
```
Start a fresh test: `python tools/reset_workspace.py --yes` (archives, then clears learned knowledge;
keeps the domain packs).
