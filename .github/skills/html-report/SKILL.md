---
name: html-report
description: How to build a polished, self-contained HTML Treasury report with tools/report_kit.py - structure, chart choice, writing rules and API. Use when writing build_report.py or changing report design.
---
# Building the HTML report

[report_kit.py](../../../tools/report_kit.py): standard library only, inline SVG charts, one offline
`.html` file that prints cleanly and always renders in light mode (no dark theme).

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
Pick the chart from the question, then draw it from a table in `output/` with
`r.chart(table, "<kind>", x=..., y=..., by=...)`.

| Question | Kind | Notes |
|---|---|---|
| Compare entities, banks, counterparties | `bar` | `sort=True`, `highlight` the one in the headline |
| Net position, gap, variance (signed values) | `bar` or `column` | negatives run left of / below zero |
| Maturity ladder, tenor or time buckets | `column` | keeps bucket order; never sort by size |
| Ladder or comparison split by a second dimension | `stacked_column`, `stacked_bar` | `by=` the dimension; pass `totals=` from `output/` |
| Two or three measures side by side | `grouped_column`, `grouped_bar` | e.g. loans against deposits, this date against the last |
| Mix (share) per bucket | `percent_column`, `percent_bar` | non-negative values only |
| Position or rate over time | `line` | `reference={"Limit": v}` or `band=(low, high, "Target")` |
| One balance over time, emphasis on level | `area` | single series |
| Composition over time | `stacked_area` | every point needs a value |
| Rates, limits that hold until changed | `step` | |
| What moved a balance between two dates | `waterfall` | `totals=["Opening", "Closing"]`; the steps must add up |
| Usage against a limit, ratio against a minimum | `bullet` | `limit="<column>"`, `good_when="below"` or `"above"` |
| Share of a whole, 2-6 parts | `donut` | `center=` formatted total from `kpis.json`; else a sorted `bar` |
| Trend behind a headline number | `kpis` with `trend` | list of past values, oldest first |
| Exact values | `table` with `formats` | `bars=["Share"]` adds in-cell bars |

A scaffolded `build_report.py` already draws one chart per table, chosen from the table's shape by
`suggest_chart` (dates -> `line`; years and tables listed in `ORDERED` -> `column`; value columns
that add up to a total column -> stacked with totals; a long table -> stacked by its second label
column, grouped when that column is a currency; otherwise `bar`; a single row or more than 15
labels -> table only). Check each choice against the question and override it per table:
`CHARTS = {"by_bucket": {"kind": "stacked_column", "x": "Bucket", "y": "Notional", "by": "Deal Type"},
"by_entity": None}`.

Rules the kit enforces (it raises a clear error, fix it in `analysis.py`):
- **The kit only draws.** It never aggregates and prints no number it was not given: one row per
  label (and series), and bins, shares, running balances and totals come from `output/`.
- Up to 8 series and ~15 bars; group the rest as "Other" in the analysis.
- A stack adds its segments by eye: only stack amounts that may be added (same currency or
  converted, same as-of date).
- Never two value axes on one chart: use two charts, or index both series to a common base.

## API
```python
from tools.report_kit import Report, fmt_money, fmt_compact, fmt_pct, fmt_num
money = lambda v: fmt_compact(v, "EUR ")
r = Report(title, subtitle="", sources=describe_logs(log), period="30 Sep 2026")
r.headline(message, detail="")
r.kpis([{"label", "value", "delta", "note", "good_when": "up"|"down", "trend": [...]}])
r.section(title, intro="");  r.text("..."); r.findings([...]); r.links([(label, href, note)])
r.chart(table, kind, x="Label column", y="Value column" | [columns], by="Series column",
        title="", value_format=money, ...)   # table: DataFrame or list of dicts; extra options below
r.bar_chart(labels, values | {"Series": [...]}, title="", value_format=money, highlight=[...],
            sort=False, mode="stacked"|"grouped"|"percent", totals=[...])
r.column_chart(labels, values | {"Series": [...]}, title="", value_format=money, highlight=[...],
               mode="stacked"|"grouped"|"percent", totals=[...], reference={"Limit": v}, band=(lo, hi, "Label"))
r.line_chart(x_labels, {"Series": [...]}, title="", value_format=money, zero_based=True,
             area=False, stacked=False, step=False, reference={"Limit": v}, band=(lo, hi, "Label"))
r.waterfall(labels, values, title="", value_format=money, totals=["Opening", "Closing"])
r.bullet_chart(labels, values, limits, title="", value_format=money, good_when="below"|"above", buffer=0.1)
r.donut_chart(labels, values, title="", value_format=money, center="", center_note="")
r.table(df, title="", formats={"Col": fmt_money}, max_rows=50, total_row=False, bars=["Col"])
r.callout(text, title="", kind="note"|"warning"|"success")
r.methodology(steps=[...], validated=True|False, notes=[...], review="full"|"quick")
r.save("reports/<report>.html")
```
`suggest_chart(table, measure="", ordered=False)` returns the keyword arguments for `r.chart`, or `None`.
Line charts put dates on a true time axis (`r.chart` reads ISO dates from a CSV as dates;
`line_chart` needs date objects, not text) and leave a gap at `None`.
See every chart: `python samples/chart_gallery.py` (writes `work/chart_gallery.html`).
Branding: CSS variables at the top of `CSS` in `report_kit.py` (`--accent`, `--s0`..`--s7`, `--font`).
