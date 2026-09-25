---
name: html-report
description: How to build a polished, self-contained HTML Treasury report with tools/report_kit.py - structure, chart choice, writing rules and API. Use when writing build_report.py or changing report design.
---
# Building the HTML report

[report_kit.py](../../../tools/report_kit.py): standard library only, inline SVG charts, one offline
`.html` file that prints cleanly and supports dark mode.

## Structure (in this order)
1. **Title, subtitle, period** - for positions the as-of date, for flows the period.
2. **Headline** - the most important answer as a full sentence with a number, built from data.
3. **KPIs** - 3-5 numbers the reader cares about; `delta` only for a real comparison.
4. **Sections** - one per question in `plan.md`; chart first, then the supporting table.
5. **Caveats** - from `review.md` and validation warnings (`callout(kind="warning")`).
6. **Methodology footer** - sources (`describe_logs`), cleaning steps, validation status.

## Writing rules
- Findings, not topics: "EUR cash fell 8% to 24.1M as of 30 Sep", not "EUR cash overview".
- Every amount shows its currency; converted figures say so ("in EUR at 30 Sep closing rates").
- Rates state their format (%, bp) and basis (weighted by principal).
- Use glossary term names so every report says the same thing the same way.
- `fmt_compact` for headlines and charts, full values in tables. Sentence case; no jargon in the body.

## Chart choice
| Question | Use |
|---|---|
| Compare entities, banks, counterparties | `bar_chart`, sorted, highlight the one in the headline |
| Position or rate over time | `line_chart` (add limit/target as a second series) |
| Maturity ladder / tenor buckets | `bar_chart` in bucket order (not sorted by size) |
| Exact values | `table` with `formats` |
Up to ~15 bars; group the rest as "Other" in the analysis.

## API
```python
from tools.report_kit import Report, fmt_money, fmt_compact, fmt_pct, fmt_num
money = lambda v: fmt_compact(v, "EUR ")
r = Report(title, subtitle="", sources=describe_logs(log), period="30 Sep 2026")
r.headline(message, detail="")
r.kpis([{"label", "value", "delta", "note", "good_when": "up"|"down"}])
r.section(title, intro="");  r.text("..."); r.findings([...]); r.links([(label, href, note)])
r.bar_chart(labels, values, title="", value_format=money, highlight=[...], sort=False)
r.line_chart(x_labels, {"Series": [...]}, title="", value_format=money)
r.table(df, title="", formats={"Col": fmt_money}, max_rows=50, total_row=False)
r.callout(text, title="", kind="note"|"warning"|"success")
r.methodology(steps=[...], validated=True|False, notes=[...], review="full"|"quick")
r.save("reports/<report>.html")
```
Branding: CSS variables at the top of `CSS` in `report_kit.py` (`--accent`, `--s0`..`--s4`, `--font`).
