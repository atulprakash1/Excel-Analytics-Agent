---
description: Fast path - one-pass report on data that is already profiled and confirmed
agent: Quick Report
argument-hint: The question, e.g. "EUR cash position by entity as of month-end"
---
Build a quick report for: ${input:question:What should the report answer?}

Search the registry and check eligibility first. If the fast path isn't allowed, tell me why in
one short list and offer the full flow. Otherwise build it in one pass without asking for
approvals, and finish with the headline, the report path, the timings and your assumptions.
