# Copilot instructions - Treasury analytics workspace

The repository-wide rules (setup, folder map, commands, data rules, additivity, currencies,
trust order) are in **`AGENTS.md`** at the repository root. Follow them; they are not repeated here.
This file covers how the Copilot custom agents, skills and prompts work together.

## Agents (`.github/agents/`)
| Agent | Does | Hands off to |
|---|---|---|
| Profiler | Profiles inputs, confirms domain packs and meanings with the user | Analyst, Quick Report |
| Analyst | Plans the analysis, writes `analysis.py` | Reviewer (or back to Profiler) |
| Reviewer | Independent checks, `review.md`, pass/fail | Report Builder (or back to Analyst) |
| Report Builder | Builds the HTML report | Curator |
| Curator | Proposes knowledge from the run; suggests domain-pack edits; user approves | Profiler |
| Quick Report | One-pass report on confirmed data, if `fast_path_check.py` says ELIGIBLE | Reviewer, Profiler, Curator |

- **Full flow** for new or changed data, new definitions, and external, board or regulatory reports.
- **Fast path** only when the eligibility gate passes and the question needs confirmed definitions only.
- Each agent stays in its lane and uses the handoff buttons; don't do another agent's job.

## Skills (`.github/skills/`) - load the one that matches the task
`data-profiling`, `domain-packs`, `excel-ingestion`, `validation-checks`, `html-report`,
`knowledge-base`, `report-registry`, `fast-path`.

## Prompts (`.github/prompts/`)
`/new-report`, `/quick-report`, `/refresh-report`, `/capture-learnings`.

## Working style in chat
- Ask the user at most once per step, with all questions in one short numbered list.
- Before building anything, search the registry: `python tools/reports.py find "<words>"`.
- Cite what you rely on: `catalog: <id>`, `glossary: <term>`, `decision: <title>`, `pack: <id>`.
- End each step with a short summary and the relevant handoff.
