---
description: Start a new report from a business question (profiles the data first if needed)
agent: Profiler
argument-hint: Describe the business question and which files it uses
---
A business user wants a new report.

Question and files: ${input:question:What should the report answer, and from which files?}

0. Run `python tools/reports.py find "<key words>"` and tell me if an existing report already
   answers this; if so, offer to refresh or extend it.
1. Read `knowledge/index.md`. Profile any input that is missing or changed.
2. Confirm the domain packs for each input with me in one line.
3. Tell me how many columns were recognised from the knowledge base, then ask any remaining
   questions in one message.
4. When the data is ready, offer the "Plan an analysis" handoff, restating the question.
