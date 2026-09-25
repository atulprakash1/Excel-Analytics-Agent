---
description: Re-run reports on the latest data (monthly refresh) with drift checks
agent: Reviewer
argument-hint: Report name, or a source id / file name to refresh everything that uses it
---
Refresh `${input:target:Report name, or a source id / file name}` on the latest data.

1. `python tools/reports.py list` to see freshness. For a report run
   `python tools/run_pipeline.py <report>`; for a source or file run
   `python tools/reports.py refresh-all <target>`.
2. If an input is blocked (needs review), explain the reason in plain words and tell me to run
   the Profiler. Change nothing.
3. If checks fail, explain each failed check from `validation.json` and what likely changed in
   the data; offer "Return to Analyst".
4. If it completes, compare `output/kpis.json` with `output/kpis.previous.json`, summarise the
   movement in 3 bullets, and give the report path.
