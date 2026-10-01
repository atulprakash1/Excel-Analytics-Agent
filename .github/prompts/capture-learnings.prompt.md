---
description: Capture what was confirmed in the latest run into the knowledge base and domain packs (with your approval)
agent: Curator
argument-hint: Report folder name under analysis/ (optional)
---
Capture learnings from `${input:report:Report folder under analysis/ (leave blank for the latest)}`.

Start from `python tools/knowledge.py brief <report>` and work from that text alone: do not re-read
the profiles, plan.md, review.md, validation.json, the knowledge files or the domain packs. The
brief does not need the earlier chat, so this can run in a new chat.

Propose catalog entries, aliases, glossary terms (including confirmed domain-pack starter
definitions), decisions, lessons and source updates from the brief, plus anything I confirm here.
Also suggest improvements to the domain packs used.
List everything in plain English and wait for my decision before approving or editing anything.
