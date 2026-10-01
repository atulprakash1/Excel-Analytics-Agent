"""
report_kit.py - build polished, self-contained HTML reports with no extra libraries.

Only the Python standard library is required (pandas is optional: `table()` accepts a
DataFrame or a list of dicts). Charts are rendered as inline SVG, so the output is a
single .html file that opens offline, prints cleanly and always renders in light mode.

Typical use (from a build_report.py script):

    from tools.report_kit import Report, fmt_compact, fmt_money, fmt_pct

    r = Report("Daily cash position", subtitle="Closing balances by entity, bank and currency",
               sources=["bank_balances_2026_09.xlsx (Balances)"], period="30 Sep 2026")
    r.headline("Group cash stood at EUR 412m on 30 Sep, up 6% on the month.",
               "Two banks hold 58% of the balance.")
    r.kpis([
        {"label": "Cash position", "value": fmt_compact(412_000_000, "EUR "), "delta": 0.06, "note": "vs 31 Aug"},
        {"label": "Accounts", "value": "48"},
    ])
    r.section("Cash by bank")
    r.bar_chart(["Bank A", "Bank B"], [140e6, 99e6], value_format=lambda v: fmt_compact(v, "EUR "))
    r.chart(ladder, "stacked_column", x="Bucket", y="Notional", by="Deal Type")   # any chart from a table
    r.table(df, formats={"Closing balance": fmt_money, "Share": fmt_pct})
    r.methodology(["Subtotal rows removed", "Converted at 30 Sep closing rates"], validated=True)
    r.save("reports/cash_position_daily.html")
"""
from __future__ import annotations

import html
import math
import numbers
import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence

# --------------------------------------------------------------------------- formatting


def fmt_num(v, decimals: int = 0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:,.{decimals}f}"


def fmt_money(v, symbol: str = "", decimals: int = 0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    sign = "-" if v < 0 else ""
    return f"{sign}{symbol}{abs(v):,.{decimals}f}"


def fmt_compact(v, symbol: str = "") -> str:
    """1_234_567 -> 1.2M ; useful for chart axes and KPI values."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    a = abs(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if a >= div:
            return f"{'-' if v < 0 else ''}{symbol}{a / div:,.1f}{suf}"
    return f"{'-' if v < 0 else ''}{symbol}{a:,.0f}"


def fmt_pct(v, decimals: int = 1) -> str:
    """Expects a ratio (0.25 -> 25.0%)."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v * 100:,.{decimals}f}%"


def _esc(v) -> str:
    return html.escape("" if v is None else str(v))


def _nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    if hi == lo:
        hi = lo + 1
    span = hi - lo
    step = 10 ** math.floor(math.log10(span / n))
    for m in (1, 2, 2.5, 5, 10):
        if span / (step * m) <= n:
            step *= m
            break
    # the axis must enclose the data: round the ends outwards, never inwards
    start = math.floor(lo / step) * step
    end = math.ceil(hi / step) * step
    ticks, t = [], start
    while t <= end + step * 0.5:
        ticks.append(round(t, 10))
        t += step
    return ticks


# --------------------------------------------------------------------------- chart core
# Every chart is inline SVG on a 680-unit-wide viewBox, built from the helpers below. The kit only
# draws: apart from axis ticks it prints no number it was not given, so totals, shares and running
# balances shown as text must be passed in from output/.

W = 680
MAX_SERIES = 8  # --s0..--s7 in CSS; more series than this must be grouped as "Other" in the analysis
MODES = ("stacked", "grouped", "percent")
R = 3  # corner radius of a bar's data end; the baseline end stays square


def _num(v):
    """A float, or None for a missing value (None, NaN)."""
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) else v


def _lab(v) -> str:
    """Axis label for a category or date."""
    if hasattr(v, "strftime"):
        return v.strftime("%d %b %Y")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return "" if v is None else str(v)


def _clip(label: str, n: int = 24) -> str:
    return label if len(label) <= n else label[:n - 1] + "…"


def _fmt(value_format: Callable, v) -> str:
    return "–" if v is None else str(value_format(v))


def _tip(name: str, label: str, text: str) -> str:
    """Hover text for one mark: "Series Label: value"."""
    return f"<title>{_esc(f'{name} {label}: {text}'.strip())}</title>"


def _as_series(values, n: int) -> dict:
    """A plain list is one unnamed series; a dict is {series name: values}, each aligned with the labels."""
    series = {str(k): list(v) for k, v in values.items()} if isinstance(values, dict) else {"": list(values)}
    if len(series) > MAX_SERIES:
        raise ValueError(f'{len(series)} series, but a chart can tell at most {MAX_SERIES} apart: '
                         'group the smallest into "Other" in analysis.py')
    for name, vals in series.items():
        if len(vals) != n:
            raise ValueError(f"series {name!r} has {len(vals)} values for {n} labels")
    return {name: [_num(v) for v in vals] for name, vals in series.items()}


def _shares(series: dict) -> dict:
    """Each label's values as a share of that label's total: the geometry of a percent chart."""
    if any(v is not None and v < 0 for vals in series.values() for v in vals):
        raise ValueError("a percent chart needs non-negative values")
    n = len(next(iter(series.values())))
    tot = [sum(vals[i] or 0 for vals in series.values()) for i in range(n)]
    return {name: [(v or 0) / tot[i] if tot[i] else 0 for i, v in enumerate(vals)]
            for name, vals in series.items()}


def _stacked(series: dict, i: int) -> list[tuple]:
    """Segments (series index, from, to) for label i: positives stack up from zero, negatives down."""
    up = down = 0.0
    out = []
    for j, vals in enumerate(series.values()):
        v = vals[i]
        if not v:
            continue
        if v > 0:
            out.append((j, up, up + v))
            up += v
        else:
            out.append((j, down, down + v))
            down += v
    return out


def _mark(x: float, y: float, w: float, h: float, cls: str, tip: str = "", end: str = "") -> str:
    """One bar. `end` is the side the data grows towards ("l", "r", "t", "b"): rounded there, square elsewhere."""
    r = min(R, w, h / 2) if end in ("l", "r") else min(R, h, w / 2)
    if not end or r < 1:
        return f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}">{tip}</rect>'
    x1, y1 = x + w, y + h
    if end == "r":
        d = (f"M{x:.1f},{y:.1f}H{x1 - r:.1f}Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f}"
             f"V{y1 - r:.1f}Q{x1:.1f},{y1:.1f} {x1 - r:.1f},{y1:.1f}H{x:.1f}Z")
    elif end == "l":
        d = (f"M{x1:.1f},{y:.1f}H{x + r:.1f}Q{x:.1f},{y:.1f} {x:.1f},{y + r:.1f}"
             f"V{y1 - r:.1f}Q{x:.1f},{y1:.1f} {x + r:.1f},{y1:.1f}H{x1:.1f}Z")
    elif end == "t":
        d = (f"M{x:.1f},{y1:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
             f"H{x1 - r:.1f}Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f}V{y1:.1f}Z")
    else:
        d = (f"M{x:.1f},{y:.1f}V{y1 - r:.1f}Q{x:.1f},{y1:.1f} {x + r:.1f},{y1:.1f}"
             f"H{x1 - r:.1f}Q{x1:.1f},{y1:.1f} {x1:.1f},{y1 - r:.1f}V{y:.1f}Z")
    return f'<path class="{cls}" d="{d}">{tip}</path>'


def _svg(parts: Iterable[str], height: float, title: str) -> str:
    return (f'<svg class="chart" viewBox="0 0 {W} {height:.0f}" role="img" aria-label="{_esc(title)}">'
            f'{"".join(parts)}</svg>')


def _legend(names: Sequence[str], swatch: bool = False, colors: Sequence[str] = ()) -> str:
    """Legend under a chart. A single series gets none: its name belongs in the chart title."""
    if len(names) < 2:
        return ""
    colors = colors or [f"--s{i}" for i in range(len(names))]
    items = "".join(f'<span><i style="background:var({c})"></i>{_esc(n)}</span>' for n, c in zip(names, colors))
    return f'<div class="legend{" sw" if swatch else ""}">{items}</div>'


def _thin(xs: Sequence[float], need: float) -> set:
    """Indices of the x labels to draw when each needs `need` units of width; the last one is always kept."""
    keep: list[int] = []
    for i, x in enumerate(xs):
        if not keep or x - xs[keep[-1]] >= need:
            keep.append(i)
    last = len(xs) - 1
    if keep and keep[-1] != last:
        if len(keep) > 1 and xs[last] - xs[keep[-1]] < need:
            keep.pop()
        keep.append(last)
    return set(keep)


def _wrap(label: str) -> list[str]:
    """A label split in two at the space nearest its middle; one line if it has no space."""
    cuts = [i for i, ch in enumerate(label) if ch == " "]
    if not cuts:
        return [label]
    cut = min(cuts, key=lambda i: abs(i - len(label) / 2))
    return [label[:cut], label[cut + 1:]]


def _cap_class(texts: Sequence[str], slot: float) -> str:
    """CSS class for the value on top of each column: normal, small when tight, "" when it cannot fit
    (the axis, hover text and table then carry the values)."""
    widest = max((len(t) for t in texts), default=0)
    if not widest or widest * 6 + 2 > slot:
        return ""
    return "val" if widest * 6.6 + 4 <= slot else "val sm"


def _guides(reference: dict | None, band: Sequence | None) -> list[float]:
    """The values of reference lines and a band, so the value axis always encloses them."""
    return [float(v) for v in (reference or {}).values()] + [float(v) for v in tuple(band or ())[:2]]


class _Frame:
    """Plot area with a vertical value axis, shared by the column, line and waterfall charts."""

    def __init__(self, lo: float, hi: float, value_format: Callable, top: int = 14,
                 ticks: Sequence[float] | None = None):
        ticks = list(ticks or _nice_ticks(lo, hi))
        texts = [str(value_format(t)) for t in ticks]
        self.lo, self.hi = ticks[0], ticks[-1]
        self.height, self.top, self.bottom = 280, top, 246
        self.left = max(64, round(max(len(t) for t in texts) * 6.6) + 16)
        self.right = W - 16
        self.parts: list[str] = []
        for t, text in zip(ticks, texts):
            y = self.y(t)
            self.parts.append(f'<line class="grid" x1="{self.left}" x2="{self.right}" y1="{y:.1f}" y2="{y:.1f}"/>'
                              f'<text x="{self.left - 8}" y="{y + 4:.1f}" text-anchor="end">{_esc(text)}</text>')
        if self.lo < 0 < self.hi:
            y = self.y(0)
            self.parts.append(f'<line class="axis" x1="{self.left}" x2="{self.right}" y1="{y:.1f}" y2="{y:.1f}"/>')

    def y(self, v: float) -> float:
        return self.top + (self.bottom - self.top) * (1 - (v - self.lo) / ((self.hi - self.lo) or 1))

    def slots(self, n: int) -> tuple:
        """Centres and width of n equal slots across the plot, for columns."""
        w = (self.right - self.left) / max(1, n)
        return [self.left + w * (i + 0.5) for i in range(n)], w

    def x_labels(self, labels: Sequence[str], xs: Sequence[float]):
        """Labels under the plot: on one line if they fit, else on two, else thinned out."""
        room = min([b - a for a, b in zip(xs, xs[1:])] + [self.right - self.left])
        lines, small = [[lab] for lab in labels], ""
        need = max((len(lab) for lab in labels), default=0) * 6.2 + 10  # width of the longest label
        if need > room:
            two = [_wrap(lab) for lab in labels]
            longest = max(len(part) for lab in two for part in lab)
            if longest * 5.6 + 8 <= room:
                lines, need = two, longest * 6.2 + 10
                if need > room:
                    small, need = ' class="sm"', longest * 5.6 + 8
                self.height += 14
        keep = _thin(xs, need)
        for i, lab in enumerate(lines):
            if i in keep:
                text = _esc(lab[0]) if len(lab) == 1 else "".join(
                    f'<tspan x="{xs[i]:.1f}" dy="{14 * j}">{_esc(part)}</tspan>' for j, part in enumerate(lab))
                self.parts.append(f'<text{small} x="{xs[i]:.1f}" y="270" text-anchor="middle">{text}</text>')

    def guides(self, reference: dict | None, band: Sequence | None, value_format: Callable):
        """Dashed reference lines ({"Limit": value}) and a shaded band ((low, high[, label]))."""
        if band:
            y0, y1 = self.y(max(band[0], band[1])), self.y(min(band[0], band[1]))
            self.parts.append(f'<rect class="refband" x="{self.left}" y="{y0:.1f}" '
                              f'width="{self.right - self.left}" height="{y1 - y0:.1f}"/>')
            if len(band) > 2:
                self.parts.append(f'<text x="{self.left + 6}" y="{y0 + 14:.1f}">{_esc(band[2])}</text>')
        for name, v in (reference or {}).items():
            y = self.y(v)
            self.parts.append(f'<line class="ref" x1="{self.left}" x2="{self.right}" y1="{y:.1f}" y2="{y:.1f}"/>'
                              f'<text class="lbl" x="{self.right}" y="{y - 5:.1f}" text-anchor="end">'
                              f'{_esc(f"{name} {value_format(v)}")}</text>')

    def svg(self, title: str) -> str:
        return _svg(self.parts, self.height, title)


def _spark(values: Iterable) -> str:
    """Small trend line for a KPI tile; the latest point is marked."""
    vals = [_num(v) for v in values]
    pts = [(i, v) for i, v in enumerate(vals) if v is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    xy = [(3 + 90 * i / (len(vals) - 1), 20 - 16 * (v - lo) / ((hi - lo) or 1)) for i, v in pts]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    return (f'<svg class="spark" viewBox="0 0 96 24" role="img" aria-label="Trend"><polyline points="{line}"/>'
            f'<circle cx="{xy[-1][0]:.1f}" cy="{xy[-1][1]:.1f}" r="2.5"/></svg>')


def _pivot(rows: Sequence[dict], x: str, ys: Sequence[str], by: str) -> tuple:
    """Labels and values for a chart from table rows. Never aggregates: one row per label (and series)."""
    for col in [x, *ys] + ([by] if by else []):
        if rows and col not in rows[0]:
            raise KeyError(f"no column {col!r} in the table; columns are {list(rows[0])}")
    labels = list(dict.fromkeys(r[x] for r in rows))
    if not by:
        if len(labels) != len(rows):
            raise ValueError(f"{x!r} repeats: one row per label is needed - aggregate in analysis.py or pass by=")
        return labels, ([r[ys[0]] for r in rows] if len(ys) == 1 else {y: [r[y] for r in rows] for y in ys})
    if len(ys) != 1:
        raise ValueError("with by=, y must be a single value column")
    cells = {(r[x], r[by]): r[ys[0]] for r in rows}
    if len(cells) != len(rows):
        raise ValueError(f"({x!r}, {by!r}) repeats: aggregate in analysis.py before charting")
    return labels, {str(s): [cells.get((lab, s)) for lab in labels] for s in dict.fromkeys(r[by] for r in rows)}


ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
SHARE_COL = re.compile(r"(?i)^share|%")
COUNT_COL = re.compile(r"(?i)^(rows|deals|count|number)\b")
CURRENCY_COL = re.compile(r"(?i)\b(currency|ccy|cur)\b")
YEAR_COL = re.compile(r"(?i)\byear\b")


def _as_dates(labels: Sequence) -> Sequence:
    """ISO date text, as read back from a CSV in output/, as dates: a line chart then gets a true time axis."""
    try:
        if labels and all(isinstance(v, str) and ISO_DATE.match(v) for v in labels):
            return [date.fromisoformat(v[:10]) for v in labels]
    except ValueError:
        pass
    return labels


def suggest_chart(data, measure: str = "", ordered: bool = False) -> dict | None:
    """A default chart for a table from output/, as keyword arguments for Report.chart; None means
    show the table only. The first column holds the labels, `measure` names the main value column.
      dates in the first column                 -> line (one line per series for a long table)
      a second label column (long table)        -> stacked by it; grouped for currencies, which must not be added
      value columns that add up to a total      -> stacked, with the totals printed
      years, or ordered=True (buckets, windows) -> column, in the order given
      anything else                             -> bar, first row highlighted
    A single row, or more than 15 labels, gets no chart. Override the choice per table when the
    question needs another kind."""
    rows = data.to_dict("records") if hasattr(data, "to_dict") else list(data)
    if len(rows) < 2:
        return None
    x, *rest = list(rows[0])

    def numeric(col):
        vals = [r.get(col) for r in rows if r.get(col) is not None and r.get(col) == r.get(col)]
        return bool(vals) and all(isinstance(v, numbers.Real) and not isinstance(v, bool) for v in vals)

    nums = [c for c in rest if numeric(c) and not SHARE_COL.search(str(c))]
    values = [c for c in nums if not COUNT_COL.search(str(c))] or nums
    if not values:
        return None
    y = measure if measure in values else values[0]
    labels = [r[x] for r in rows]
    is_date = all(hasattr(v, "strftime") or (isinstance(v, str) and ISO_DATE.match(v)) for v in labels)
    is_year = all(re.fullmatch(r"(19|2[01])\d\d(\.0)?", str(v)) for v in labels)
    stand = "column" if ordered or is_date or is_year else "bar"
    if len(set(labels)) < len(labels):  # long table: one row per label and series
        by = rest[0] if rest and not numeric(rest[0]) else None
        series = {r[by] for r in rows} if by else set()
        if not by or len({(r[x], r[by]) for r in rows}) < len(rows) or len(series) > MAX_SERIES:
            return None
        if is_date:
            return {"kind": "line", "x": x, "y": y, "by": by}
        apart = bool(CURRENCY_COL.search(str(by)))
        if len(set(labels)) > 15 or (apart and len(series) > 4):
            return None
        return {"kind": f"{'grouped' if apart else 'stacked'}_{stand}", "x": x, "y": y, "by": by}
    if is_date and len(rows) > 2:
        return {"kind": "line", "x": x, "y": y if measure in values or len(values) == 1 else values[:MAX_SERIES]}
    if len(rows) > 15:
        return None
    total = next((c for c in values if c == measure or str(c).lower() == "total"), None)
    parts = [c for c in values if c != total]
    if total and 2 <= len(parts) <= MAX_SERIES and all(
            abs(sum(r[c] or 0 for c in parts) - (r[total] or 0)) <= 1e-6 * max(1.0, abs(r[total] or 0)) for r in rows):
        return {"kind": f"stacked_{stand}", "x": x, "y": parts, "totals": [r[total] for r in rows]}
    if stand == "column":
        return {"kind": "column", "x": x, "y": y}
    return {"kind": "bar", "x": x, "y": y, "highlight": [_lab(labels[0])]}


# --------------------------------------------------------------------------- styles

CSS = """
:root{
  color-scheme: light;
  --canvas:#e9edf1; --paper:#ffffff; --ink:#1c2733; --muted:#5b6b7a; --rule:#d5dbe1;
  --accent:#0e6e6b; --accent-soft:#e2f0ef; --pos:#2f7d4f; --neg:#b43c3c; --warn:#9a6412;
  --s0:#0e6e6b; --s1:#b7791f; --s2:#466ea8; --s3:#964d09; --s4:#24a0cc; --s5:#634d99; --s6:#6b7e1f; --s7:#8c5184;
  --tot:#7d8b99; --bar-soft:#cde5e3;
  --zebra:#f5f7f9; --font: "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--canvas);color:var(--ink);font-family:var(--font);
  font-size:15px;line-height:1.55;font-variant-numeric:tabular-nums}
.page{max-width:980px;margin:32px auto;background:var(--paper);padding:48px 56px 40px;
  border-top:6px solid var(--accent)}
header.rh h1{font-size:2rem;line-height:1.15;margin:0 0 6px;font-weight:650;letter-spacing:-0.01em}
header.rh .sub{color:var(--muted);font-size:1.05rem;margin:0 0 18px;max-width:70ch}
header.rh dl{display:flex;flex-wrap:wrap;gap:6px 28px;margin:0;font-size:.85rem;color:var(--muted)}
header.rh dt{font-weight:600;color:var(--ink)} header.rh dl div{display:flex;gap:6px}
header.rh dd{margin:0}
.badge{display:inline-block;padding:1px 8px;border-radius:3px;font-size:.78rem;font-weight:600}
.badge.ok{background:var(--accent-soft);color:var(--pos)} .badge.no{background:#fbeaea;color:var(--neg)}
.badge.quick{background:var(--zebra);color:var(--s2);border:1px solid var(--rule)}
.headline{margin:32px 0 8px;padding:4px 0 4px 20px;border-left:4px solid var(--accent)}
.headline p{margin:0;font-size:1.45rem;line-height:1.3;font-weight:600;max-width:52ch}
.headline .detail{font-size:1rem;font-weight:400;color:var(--muted);margin-top:8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:0;margin:28px 0 8px;
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.kpi{padding:16px 18px 14px;border-left:1px solid var(--rule)} .kpi:first-child{border-left:none;padding-left:0}
.kpi .l{font-size:.85rem;color:var(--muted)} .kpi .v{font-size:1.7rem;font-weight:650;line-height:1.2;margin-top:2px}
.kpi .d{font-size:.85rem;font-weight:600} .kpi .d.up{color:var(--pos)} .kpi .d.down{color:var(--neg)}
.kpi .n{font-size:.8rem;color:var(--muted)}
section.rs{margin-top:40px}
section.rs>h2{font-size:1.25rem;margin:0 0 4px;font-weight:650}
section.rs>.intro{color:var(--muted);margin:0 0 14px;max-width:72ch}
p.body{max-width:72ch;margin:0 0 12px}
figure{margin:18px 0 8px} figcaption{font-size:.85rem;color:var(--muted);margin-bottom:6px;font-weight:600}
svg.chart{width:100%;height:auto;display:block;overflow:visible}
svg.chart text{fill:var(--muted);font-family:var(--font);font-size:12px}
svg.chart .lbl{fill:var(--ink)} svg.chart .val{fill:var(--ink);font-weight:600}
svg.chart .grid{stroke:var(--rule);stroke-width:1} svg.chart .axis{stroke:var(--muted);stroke-width:1}
svg.chart .bar{fill:var(--s0)} svg.chart .bar.hi{fill:var(--s1)} svg.chart .bar.neg{fill:var(--neg)}
.s0{stroke:var(--s0);fill:var(--s0)} .s1{stroke:var(--s1);fill:var(--s1)} .s2{stroke:var(--s2);fill:var(--s2)}
.s3{stroke:var(--s3);fill:var(--s3)} .s4{stroke:var(--s4);fill:var(--s4)} .s5{stroke:var(--s5);fill:var(--s5)}
.s6{stroke:var(--s6);fill:var(--s6)} .s7{stroke:var(--s7);fill:var(--s7)}
svg.chart polyline{fill:none;stroke-width:2.25;stroke-linejoin:round}
svg.chart .lbl,svg.chart .val{paint-order:stroke;stroke:var(--paper);stroke-width:3px;stroke-linejoin:round}
svg.chart .sm{font-size:11px}
svg.chart .m{stroke:none} svg.chart .area{stroke:none;fill-opacity:.1} svg.chart .area.band{fill-opacity:.24}
svg.chart .hit{fill:transparent;stroke:none}
svg.chart .bar.up{fill:var(--s0)} svg.chart .bar.down{fill:var(--neg)} svg.chart .bar.tot{fill:var(--tot)}
svg.chart .bar.warn{fill:var(--warn)} svg.chart .track{fill-opacity:.16}
svg.chart .conn{stroke:var(--muted);stroke-width:1} svg.chart .lim{stroke:var(--ink);stroke-width:2}
svg.chart .ref{stroke:var(--ink);stroke-width:1.25;stroke-dasharray:5 4}
svg.chart .refband{fill:var(--ink);opacity:.06}
svg.chart .ring{fill:none;stroke-width:24} svg.chart .big{fill:var(--ink);font-size:17px;font-weight:650}
.legend{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:.85rem;margin-top:6px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:12px;height:3px;display:inline-block}
.legend.sw i{width:10px;height:10px;border-radius:2px}
svg.spark{width:96px;height:24px;display:block;margin-top:6px;overflow:visible}
svg.spark polyline{fill:none;stroke:var(--muted);stroke-width:1.5;stroke-linejoin:round}
svg.spark circle{fill:var(--accent)}
td.dbar{position:relative} td.dbar span{position:relative}
td.dbar i{position:absolute;left:8px;width:calc((100% - 16px)*var(--w));top:5px;bottom:5px;
  background:var(--bar-soft);border-radius:0 2px 2px 0;
  -webkit-print-color-adjust:exact;print-color-adjust:exact} td.dbar i.neg{background:#f3d3d3}
.tw{overflow-x:auto;margin:14px 0 6px;border:1px solid var(--rule)}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{padding:7px 12px;text-align:left;white-space:nowrap}
th{position:sticky;top:0;background:var(--paper);border-bottom:2px solid var(--ink);font-weight:650}
tbody tr:nth-child(even){background:var(--zebra)}
td.num,th.num{text-align:right} td.negv{color:var(--neg)}
tr.total td{font-weight:650;border-top:1px solid var(--ink)}
.tcap{font-size:.8rem;color:var(--muted)}
.callout{margin:16px 0;padding:12px 16px;border-left:4px solid var(--s2);background:var(--zebra);max-width:78ch}
.callout.warning{border-color:var(--warn)} .callout.success{border-color:var(--pos)}
.callout strong{display:block;margin-bottom:2px}
ul.findings{padding-left:1.1rem;max-width:74ch} ul.findings li{margin:6px 0}
ul.links{list-style:none;padding:0;max-width:74ch} ul.links li{margin:10px 0}
ul.links a{color:var(--accent);font-weight:600;text-decoration:none} ul.links a:hover{text-decoration:underline}
ul.links span{display:block;color:var(--muted);font-size:.9rem}
td a{color:var(--accent);font-weight:600;text-decoration:none} td a:hover{text-decoration:underline}
footer.rf{margin-top:48px;padding-top:16px;border-top:1px solid var(--rule);font-size:.85rem;color:var(--muted)}
footer.rf h2{font-size:.95rem;color:var(--ink);margin:0 0 6px} footer.rf ul{margin:0 0 10px;padding-left:1.1rem}
@media (max-width:700px){.page{margin:0;padding:28px 20px}.kpi{padding-left:12px}
  header.rh h1{font-size:1.55rem}.headline p{font-size:1.2rem}}
@media print{body{background:#fff}.page{margin:0;max-width:none;padding:0;border-top:none}
  section.rs,figure,.tw{break-inside:avoid}.tw{overflow:visible}}
"""

# --------------------------------------------------------------------------- report


class Report:
    def __init__(self, title: str, subtitle: str = "", sources: Sequence[str] = (),
                 author: str = "", period: str = ""):
        self.title, self.subtitle = title, subtitle
        self.sources, self.author, self.period = list(sources), author, period
        self._blocks: list[str] = []
        self._footer = ""
        self._validated: bool | None = None
        self._review = "full"

    # ---- text blocks
    def headline(self, message: str, detail: str = "") -> "Report":
        d = f'<p class="detail">{_esc(detail)}</p>' if detail else ""
        self._blocks.append(f'<div class="headline"><p>{_esc(message)}</p>{d}</div>')
        return self

    def section(self, title: str, intro: str = "") -> "Report":
        i = f'<p class="intro">{_esc(intro)}</p>' if intro else ""
        self._blocks.append(f'</section><section class="rs"><h2>{_esc(title)}</h2>{i}')
        return self

    def text(self, *paragraphs: str) -> "Report":
        for p in paragraphs:
            self._blocks.append(f'<p class="body">{_esc(p)}</p>')
        return self

    def findings(self, items: Iterable[str]) -> "Report":
        lis = "".join(f"<li>{_esc(i)}</li>" for i in items)
        self._blocks.append(f'<ul class="findings">{lis}</ul>')
        return self

    def links(self, items: Iterable[tuple]) -> "Report":
        """items: (label, href, note) - e.g. links between reports in a catalogue page."""
        lis = "".join(f'<li><a href="{_esc(h)}">{_esc(l)}</a>' + (f'<span>{_esc(n)}</span>' if n else "") + "</li>"
                      for l, h, n in items)
        self._blocks.append(f'<ul class="links">{lis}</ul>')
        return self

    def callout(self, text: str, title: str = "", kind: str = "note") -> "Report":
        t = f"<strong>{_esc(title)}</strong>" if title else ""
        self._blocks.append(f'<div class="callout {kind}">{t}{_esc(text)}</div>')
        return self

    # ---- KPIs
    def kpis(self, items: Sequence[dict]) -> "Report":
        """items: {label, value (str), delta (ratio, optional), note, good_when: 'up'|'down',
        trend (optional list of past values, oldest first, drawn as a small line)}"""
        out = []
        for k in items:
            d = ""
            if k.get("delta") is not None:
                delta = k["delta"]
                good_up = k.get("good_when", "up") == "up"
                cls = "up" if (delta >= 0) == good_up else "down"
                arrow = "▲" if delta >= 0 else "▼"
                d = f'<div class="d {cls}">{arrow} {fmt_pct(abs(delta))}</div>'
            n = f'<div class="n">{_esc(k["note"])}</div>' if k.get("note") else ""
            out.append(f'<div class="kpi"><div class="l">{_esc(k["label"])}</div>'
                       f'<div class="v">{_esc(k["value"])}</div>{d}{n}{_spark(k.get("trend") or ())}</div>')
        self._blocks.append(f'<div class="kpis">{"".join(out)}</div>')
        return self

    # ---- charts
    def chart(self, data, kind: str, x: str, y, by: str = "", title: str = "", **options) -> "Report":
        """Any chart from a table in output/. data: DataFrame or list of dicts; x: label column;
        y: value column, or a list of value columns (one series each); by: column whose values become
        the series of a long table. The kit never aggregates: one row per x (and by).
        kind: bar | column (or stacked_ / grouped_ / percent_ bar and column), line | area | step |
        stacked_area, waterfall, donut, bullet (with limit="<column>"). Other options go to that chart."""
        rows = data.to_dict("records") if hasattr(data, "to_dict") else list(data)
        ys = [y] if isinstance(y, str) else list(y)
        labels, values = _pivot(rows, x, ys, by)
        kind = kind.lower().replace("-", "_").replace(" ", "_")
        mode, _, base = kind.rpartition("_")
        if base in ("bar", "column") and mode in ("",) + MODES:
            draw = self.bar_chart if base == "bar" else self.column_chart
            return draw(labels, values, title=title, mode=mode or "stacked", **options)
        if (mode, base) in (("", "line"), ("", "area"), ("", "step"), ("stacked", "area")):
            series = values if isinstance(values, dict) else {ys[0]: values}
            return self.line_chart(_as_dates(labels), series, title=title, area=base == "area", step=base == "step",
                                   stacked=mode == "stacked", **options)
        if kind not in ("waterfall", "donut", "bullet"):
            raise ValueError(f"unknown chart kind {kind!r}")
        if isinstance(values, dict):
            raise ValueError(f"a {kind} chart takes one value column")
        if kind == "bullet":
            limit = options.pop("limit", None)
            if limit not in (rows[0] if rows else {}):
                raise KeyError(f'a bullet chart needs limit="<column>"; columns are {list(rows[0]) if rows else []}')
            return self.bullet_chart(labels, values, [r[limit] for r in rows], title=title, **options)
        draw = self.waterfall if kind == "waterfall" else self.donut_chart
        return draw(labels, values, title=title, **options)

    def bar_chart(self, labels: Sequence, values, title: str = "",
                  value_format: Callable = fmt_compact, highlight: Iterable = (),
                  sort: bool = False, mode: str = "stacked", totals: Sequence | None = None) -> "Report":
        """Horizontal bars. Best for comparing categories (up to ~15); negative values run left of zero.
        values: a list, or {series: list} drawn as mode="stacked" | "grouped" | "percent".
        totals: the value to print at the end of each stack, from output/."""
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        labels = [_lab(lab) for lab in labels]
        shown = _as_series(values, len(labels))
        names, n = list(shown), len(labels)
        multi = len(names) > 1
        stack, pct = multi and mode != "grouped", multi and mode == "percent"
        geom = _shares(shown) if pct else shown
        order = list(range(n))
        if sort:
            order.sort(key=lambda i: sum(vals[i] or 0 for vals in shown.values()), reverse=True)
        hl = {str(h) for h in highlight}
        lw, vw = 170, 80
        rh = 16 * len(names) + 14 if multi and not stack else 30
        body = rh * n + 10
        ends = ([b for i in range(n) for _, _, b in _stacked(geom, i)] if stack
                else [v for vals in geom.values() for v in vals if v is not None])
        lo, hi = min(ends + [0]), max(ends + [0])
        ticks = ([0, 0.25, 0.5, 0.75, 1] if pct else _nice_ticks(lo, hi)) if stack else []
        if ticks:
            lo, hi = ticks[0], ticks[-1]
        left = lw + (vw if lo < 0 and not stack else 0)
        span = (W - vw - left) / ((hi - lo) or 1)

        def x(v):
            return left + (v - lo) * span

        parts = []
        for t in ticks:  # stacks carry no value on every segment, so they get a value axis
            parts.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="5" y2="{body - 5}"/>'
                         f'<text x="{x(t):.1f}" y="{body + 12}" text-anchor="middle">'
                         f'{_esc(fmt_pct(t, 0) if pct else value_format(t))}</text>')
        for row, i in enumerate(order):
            y = row * rh + 5
            full = f"<title>{_esc(labels[i])}</title>" if len(labels[i]) > 24 else ""
            parts.append(f'<text class="lbl" x="{lw - 10}" y="{y + rh / 2 + 4}" text-anchor="end">'
                         f'{_esc(_clip(labels[i]))}{full}</text>')
            if stack:
                segs = _stacked(geom, i)
                tips = {max([b for _, _, b in segs] + [0]), min([b for _, _, b in segs] + [0])}
                for j, a, b in segs:
                    xa, xb = x(a), x(b)
                    if a and abs(xb - xa) > 3:  # surface gap between touching segments
                        xa += 2 if b > a else -2
                    parts.append(_mark(min(xa, xb), y + 5, abs(xb - xa), rh - 10, f"s{j} m",
                                       _tip(names[j], labels[i], _fmt(value_format, shown[names[j]][i])),
                                       ("r" if b > a else "l") if b in tips else ""))
                if totals is not None:
                    parts.append(f'<text class="val" x="{x(max(tips)) + 6:.1f}" y="{y + rh / 2 + 4}">'
                                 f'{_esc(_fmt(value_format, _num(totals[i])))}</text>')
                continue
            for j, name in enumerate(names):
                v = geom[name][i]
                top, th = (y + 7 + 16 * j, 14) if multi else (y + 5, rh - 10)
                text = _esc(_fmt(value_format, v))
                if v is None:
                    parts.append(f'<text class="val" x="{x(0) + 6:.1f}" y="{top + th / 2 + 4}">{text}</text>')
                    continue
                w = max(1.5, abs(x(v) - x(0)))
                cls = f"s{j} m" if multi else ("bar neg" if v < 0 else ("bar hi" if labels[i] in hl else "bar"))
                tip = _tip(name, labels[i], _fmt(value_format, v))
                if v < 0:
                    parts.append(_mark(x(0) - w, top, w, th, cls, tip, "l")
                                 + f'<text class="val" x="{x(0) - w - 6:.1f}" y="{top + th / 2 + 4}" '
                                   f'text-anchor="end">{text}</text>')
                else:
                    parts.append(_mark(x(0), top, w, th, cls, tip, "r")
                                 + f'<text class="val" x="{x(0) + w + 6:.1f}" y="{top + th / 2 + 4}">{text}</text>')
        if lo < 0:
            parts.append(f'<line class="axis" x1="{x(0):.1f}" x2="{x(0):.1f}" y1="5" y2="{body - 5}"/>')
        self._figure(_svg(parts, body + (20 if ticks else 0), title) + _legend(names, swatch=True), title)
        return self

    def column_chart(self, labels: Sequence, values, title: str = "",
                     value_format: Callable = fmt_compact, highlight: Iterable = (), mode: str = "stacked",
                     totals: Sequence | None = None, reference: dict | None = None,
                     band: Sequence | None = None) -> "Report":
        """Vertical columns in the order given: time buckets, maturity ladders, tenor bands.
        values: a list, or {series: list} drawn as mode="stacked" | "grouped" | "percent".
        totals: the value to print on top of each stack, from output/.
        reference: {"Limit": value} dashed lines; band: (low, high[, label]) shaded range."""
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        labels = [_lab(lab) for lab in labels]
        shown = _as_series(values, len(labels))
        names, n = list(shown), len(labels)
        multi = len(names) > 1
        stack, pct = multi and mode != "grouped", multi and mode == "percent"
        geom = _shares(shown) if pct else shown
        ends = ([b for i in range(n) for _, _, b in _stacked(geom, i)] if stack
                else [v for vals in geom.values() for v in vals if v is not None])
        ends += [0] + _guides(reference, band)
        f = _Frame(min(ends), max(ends), (lambda v: fmt_pct(v, 0)) if pct else value_format, top=22,
                   ticks=[0, 0.25, 0.5, 0.75, 1] if pct else None)
        xs, slot = f.slots(n)
        hl = {str(h) for h in highlight}
        k = 1 if stack else len(names)
        cw = min(32.0, slot * 0.62) if k == 1 else min(24.0, slot * 0.8 / k - 2)
        caps = [_fmt(value_format, v) for v in shown[names[0]]] if not multi else (
            [_fmt(value_format, _num(t)) for t in totals] if stack and totals is not None else [])
        cap = _cap_class(caps, slot)
        y0, on_top = f.y(0), []  # value labels go on last, over any reference line
        for i, cx in enumerate(xs):
            cap_y = y0
            if stack:
                segs = _stacked(geom, i)
                tips = {max([b for _, _, b in segs] + [0]), min([b for _, _, b in segs] + [0])}
                for j, a, b in segs:
                    ya, yb = f.y(a), f.y(b)
                    if a and abs(yb - ya) > 3:  # surface gap between touching segments
                        ya += -2 if b > a else 2
                    f.parts.append(_mark(cx - cw / 2, min(ya, yb), cw, abs(yb - ya), f"s{j} m",
                                         _tip(names[j], labels[i], _fmt(value_format, shown[names[j]][i])),
                                         ("t" if b > a else "b") if b in tips else ""))
                cap_y = f.y(max(tips))
            for j, name in enumerate([] if stack else names):
                v = geom[name][i]
                if v is None:
                    continue
                h = max(1.5, abs(f.y(v) - y0))
                cls = f"s{j} m" if multi else ("bar neg" if v < 0 else ("bar hi" if labels[i] in hl else "bar"))
                f.parts.append(_mark(cx - k * (cw + 2) / 2 + 1 + j * (cw + 2), y0 - h if v >= 0 else y0, cw, h, cls,
                                     _tip(name, labels[i], _fmt(value_format, v)), "t" if v >= 0 else "b"))
                cap_y = min(cap_y, y0 - h if v >= 0 else y0)
            if cap:
                on_top.append(f'<text class="{cap}" x="{cx:.1f}" y="{cap_y - 5:.1f}" text-anchor="middle">'
                              f'{_esc(caps[i])}</text>')
        f.x_labels(labels, xs)
        f.guides(reference, band, value_format)
        f.parts += on_top
        self._figure(f.svg(title) + _legend(names, swatch=True), title)
        return self

    def line_chart(self, x_labels: Sequence, series: dict, title: str = "",
                   value_format: Callable = fmt_compact, zero_based: bool = True, area: bool = False,
                   stacked: bool = False, step: bool = False, reference: dict | None = None,
                   band: Sequence | None = None) -> "Report":
        """series: {"Actual": [..], "Target": [..]} - each list aligned with x_labels; None leaves a gap.
        Dates (not text) as x_labels are placed on a true time axis.
        area: shade under the line; stacked: stack the series as areas; step: hold each value until
        the next (rates, limits). reference: {"Limit": value} dashed lines; band: (low, high[, label])."""
        n = len(x_labels)
        vals = _as_series(dict(series), n)
        names = list(vals)
        tops = vals
        if stacked:
            if any(v is None for s in vals.values() for v in s):
                raise ValueError("a stacked area chart needs a value for every point")
            run = [0.0] * n
            tops = {}
            for name, s in vals.items():
                run = [a + b for a, b in zip(run, s)]
                tops[name] = run
        allv = [v for s in tops.values() for v in s if v is not None] + _guides(reference, band)
        f = _Frame(min(allv + ([0] if zero_based or stacked else [])), max(allv) if allv else 1, value_format)
        days = [lab.toordinal() for lab in x_labels] if n > 1 and all(
            hasattr(lab, "toordinal") for lab in x_labels) else list(range(n))
        d0, d1 = (days[0], days[-1]) if n else (0, 0)
        xs = [f.left + (f.right - f.left) * ((d - d0) / ((d1 - d0) or 1)) for d in days]
        labels = [_lab(lab) for lab in x_labels]
        floor = f.y(min(max(0, f.lo), f.hi))

        def path(idx, ys):
            """Points for a run of x positions; a step line holds each value until the next x."""
            pts = []
            for a, i in enumerate(idx):
                if step and a:
                    pts.append((xs[i], pts[-1][1]))
                pts.append((xs[i], ys[i]))
            return pts

        def join(pts):
            return " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)

        base = [floor] * n
        for si, name in enumerate(names):
            c = f"s{si}"
            ys = [None if v is None else f.y(v) for v in tops[name]]
            runs, cur = [], []
            for i, yv in enumerate(ys):  # a missing value breaks the line instead of being bridged
                if yv is None:
                    runs, cur = runs + ([cur] if cur else []), []
                else:
                    cur.append(i)
            for idx in runs + ([cur] if cur else []):
                if area or stacked:
                    f.parts.append(f'<polygon class="{c} area{" band" if stacked else ""}" '
                                   f'points="{join(path(idx, ys) + path(idx, base)[::-1])}"/>')
                f.parts.append(f'<polyline class="{c}" points="{join(path(idx, ys))}" style="fill:none"/>')
            dots = n <= 40  # beyond that, markers crowd the line: keep only the hover targets
            for i, v in enumerate(vals[name]):
                if v is not None:
                    f.parts.append(f'<circle class="{c if dots else "hit"}" cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" '
                                   f'r="{3 if dots else 6}">{_tip(name, labels[i], _fmt(value_format, v))}</circle>')
            if stacked:
                base = ys
        f.x_labels(labels, xs)
        f.guides(reference, band, value_format)
        self._figure(f.svg(title) + _legend(names), title)
        return self

    def waterfall(self, labels: Sequence, values: Sequence[float], title: str = "",
                  value_format: Callable = fmt_compact, totals: Iterable = ()) -> "Report":
        """Bridge between positions: what moved the balance from opening to closing.
        values are changes, except for the labels named in `totals` (e.g. "Opening", "Closing"),
        whose values are levels drawn from zero. A total must equal the steps before it."""
        labels = [_lab(lab) for lab in labels]
        vals = [_num(v) for v in values]
        if len(vals) != len(labels) or any(v is None for v in vals):
            raise ValueError("a waterfall needs one value for every label")
        levels = {str(t) for t in totals}
        spans, level = [], 0.0
        for i, (lab, v) in enumerate(zip(labels, vals)):
            if lab in levels:
                if i and abs(v - level) > 0.001 * max(abs(v), abs(level)):
                    raise ValueError(f"waterfall total {lab!r} is {v:,.2f} but the steps before it reach "
                                     f"{level:,.2f}: add the missing movement in analysis.py")
                spans.append((0.0, v))
                level = v
            else:
                spans.append((level, level + v))
                level += v
        f = _Frame(min([b for _, b in spans] + [0]), max([b for _, b in spans] + [0]), value_format, top=22)
        xs, slot = f.slots(len(labels))
        cw = min(40.0, slot * 0.6)
        caps = [_fmt(value_format, v) if lab in levels else ("+" if v > 0 else "") + _fmt(value_format, v)
                for lab, v in zip(labels, vals)]
        cap = _cap_class(caps, slot)
        for i, ((a, b), cx) in enumerate(zip(spans, xs)):
            ya, yb = f.y(a), f.y(b)
            h, up = max(1.5, abs(yb - ya)), b >= a
            cls = "bar tot" if labels[i] in levels else ("bar up" if up else "bar down")
            f.parts.append(_mark(cx - cw / 2, ya - h if up else ya, cw, h, cls, _tip("", labels[i], caps[i]),
                                 "t" if up else "b"))
            if i + 1 < len(xs):
                f.parts.append(f'<line class="conn" x1="{cx + cw / 2:.1f}" x2="{xs[i + 1] - cw / 2:.1f}" '
                               f'y1="{yb:.1f}" y2="{yb:.1f}"/>')
            if cap:
                f.parts.append(f'<text class="{cap}" x="{cx:.1f}" y="{min(ya, yb) - 5:.1f}" text-anchor="middle">'
                               f'{_esc(caps[i])}</text>')
        f.x_labels(labels, xs)
        key = _legend(["Position", "Increase", "Decrease"], swatch=True, colors=["--tot", "--s0", "--neg"])
        self._figure(f.svg(title) + key, title)
        return self

    def bullet_chart(self, labels: Sequence, values: Sequence[float], limits: Sequence[float], title: str = "",
                     value_format: Callable = fmt_compact, good_when: str = "below",
                     buffer: float = 0.1) -> "Report":
        """Usage against a limit, one row each; the limit marks line up so rows compare at a glance.
        good_when="below": over the limit is a breach (exposure limits); "above": under it is a breach
        (minimum ratios, targets). Rows within `buffer` (10%) of the limit are flagged as close."""
        labels = [_lab(lab) for lab in labels]
        words = (("within limit", "close to limit", "over limit") if good_when == "below"
                 else ("above minimum", "close to minimum", "below minimum"))
        lw, rh, tw = 170, 40, 300
        mark = lw + tw * 0.8  # every row's limit sits here; the track ends at 125% of the limit
        parts = []
        for i, (lab, v, lim) in enumerate(zip(labels, values, limits)):
            v, lim = _num(v), _num(lim)
            if v is None or not lim or lim < 0:
                raise ValueError(f"bullet row {lab!r} needs a value and a positive limit")
            ratio = v / lim
            if good_when == "below":
                state = 2 if ratio > 1 else (1 if ratio >= 1 - buffer else 0)
            else:
                state = 2 if ratio < 1 else (1 if ratio <= 1 + buffer else 0)
            cls = ("bar", "bar warn", "bar neg")[state]
            y = i * rh + 5
            of = f"of {_fmt(value_format, lim)}"
            full = f"<title>{_esc(lab)}</title>" if len(lab) > 24 else ""
            parts.append(
                f'<text class="lbl" x="{lw - 10}" y="{y + 21}" text-anchor="end">{_esc(_clip(lab))}{full}</text>'
                f'<rect class="{cls} track" x="{lw}" y="{y + 12}" width="{tw}" height="10" rx="2"/>'
                + _mark(lw, y + 12, max(1.5, tw * 0.8 * min(max(ratio, 0), 1.25)), 10, cls,
                        _tip("", lab, f"{_fmt(value_format, v)} {of}, {words[state]}"), "r")
                + f'<line class="lim" x1="{mark:.1f}" x2="{mark:.1f}" y1="{y + 7}" y2="{y + 27}"/>'
                f'<text class="val" x="{lw + tw + 14}" y="{y + 15}">{_esc(_fmt(value_format, v))}</text>'
                f'<text x="{lw + tw + 14}" y="{y + 30}">{_esc(of + " · " + words[state])}</text>')
        self._figure(_svg(parts, rh * len(labels) + 10, title), title)
        return self

    def donut_chart(self, labels: Sequence, values: Sequence[float], title: str = "",
                    value_format: Callable = fmt_compact, center: str = "", center_note: str = "") -> "Report":
        """Share of a whole for 2-6 parts; for more parts or close values use a sorted bar_chart.
        center / center_note: text for the middle, e.g. the formatted total from kpis.json."""
        labels = [_lab(lab) for lab in labels]
        vals = [_num(v) or 0 for v in values]
        if not 2 <= len(vals) <= 6 or len(vals) != len(labels) or min(vals) < 0 or not sum(vals):
            raise ValueError('a donut needs 2 to 6 non-negative parts: group the rest as "Other" in analysis.py, '
                             "or use a bar_chart")
        cx, cy, r = 110, 95, 70
        circ, total, at = 2 * math.pi * r, sum(vals), 0.0
        top = cy - 12 * len(vals) + 16
        parts = []
        for i, (lab, v) in enumerate(zip(labels, vals)):
            arc = circ * v / total
            text = _fmt(value_format, v)
            if v:
                parts.append(f'<circle class="s{i} ring" cx="{cx}" cy="{cy}" r="{r}" '
                             f'stroke-dasharray="{max(arc - 2, 0.5):.2f} {circ:.2f}" stroke-dashoffset="{-at:.2f}" '
                             f'transform="rotate(-90 {cx} {cy})">{_tip("", lab, text)}</circle>')
            at += arc
            y = top + 24 * i
            parts.append(f'<rect class="s{i} m" x="230" y="{y - 10}" width="10" height="10" rx="2"/>'
                         f'<text class="lbl" x="248" y="{y}">{_esc(_clip(lab, 36))}</text>'
                         f'<text class="val" x="{W - 120}" y="{y}" text-anchor="end">{_esc(text)}</text>')
        if center:
            parts.append(f'<text class="big" x="{cx}" y="{cy + (2 if center_note else 6)}" '
                         f'text-anchor="middle">{_esc(center)}</text>')
        if center_note:
            parts.append(f'<text x="{cx}" y="{cy + 20}" text-anchor="middle">{_esc(center_note)}</text>')
        self._figure(_svg(parts, 190, title), title)
        return self

    def _figure(self, inner: str, title: str):
        cap = f"<figcaption>{_esc(title)}</figcaption>" if title else ""
        self._blocks.append(f"<figure>{cap}{inner}</figure>")

    # ---- tables
    def table(self, data, title: str = "", formats: dict | None = None, max_rows: int = 50,
              total_row: bool = False, caption: str = "", links: dict | None = None,
              bars: Iterable[str] = ()) -> "Report":
        """data: pandas DataFrame or list of dicts. formats: {column: callable}.
        total_row=True styles the last row as a total.
        links: {column: href_key} renders that column as a link to row[href_key]; href_key is not shown.
        bars: numeric columns that get a bar behind each value, scaled to the column's largest."""
        formats = formats or {}
        links = links or {}
        if hasattr(data, "to_dict"):
            cols = [str(c) for c in data.columns]
            rows = data.to_dict("records")
            rows = [{str(k): v for k, v in r.items()} for r in rows]
        else:
            rows = list(data)
            cols = list(rows[0].keys()) if rows else []
        cols = [c for c in cols if c not in set(links.values())]
        truncated = len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]
        numeric = {c for c in cols if rows and all(
            isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool)
            for r in rows if r.get(c) is not None)}
        # a year is a label, not a quantity: no thousands separator, aligned like text
        years = {c for c in numeric if YEAR_COL.search(c) and all(
            float(r[c]).is_integer() and 1000 <= r[c] <= 9999 for r in rows if r.get(c) is not None and r[c] == r[c])}
        numeric -= years
        head = "".join(f'<th class="{"num" if c in numeric else ""}">{_esc(c)}</th>' for c in cols)
        plain = rows[:-1] if total_row else rows  # a total row would dwarf every other bar
        peak = {c: max([abs(r[c]) for r in plain if isinstance(r.get(c), (int, float)) and r[c] == r[c]] + [0])
                for c in bars if c in numeric}
        body = []
        for ri, r in enumerate(rows):
            tds = []
            for c in cols:
                v = r.get(c)
                if isinstance(v, float) and math.isnan(v):
                    v = None
                if c in formats and v is not None:
                    s = formats[c](v)
                elif c in years and v is not None:
                    s = str(int(v))
                elif isinstance(v, float):
                    s = fmt_num(v, 2)
                elif isinstance(v, int) and not isinstance(v, bool):
                    s = fmt_num(v)
                elif hasattr(v, "strftime"):
                    s = v.strftime("%d %b %Y")
                else:
                    s = "–" if v is None else str(v)
                cls = []
                if c in numeric:
                    cls.append("num")
                    if isinstance(v, (int, float)) and v < 0:
                        cls.append("negv")
                cell = _esc(s)
                if c in links and r.get(links[c]):
                    cell = f'<a href="{_esc(r[links[c]])}">{cell}</a>'
                if peak.get(c) and isinstance(v, (int, float)) and not (total_row and ri == len(rows) - 1):
                    cls.append("dbar")
                    cell = (f'<i class="{"neg" if v < 0 else ""}" style="--w:{abs(v) / peak[c]:.3f}"></i>'
                            f'<span>{cell}</span>')
                tds.append(f'<td class="{" ".join(cls)}">{cell}</td>')
            tr_cls = ' class="total"' if total_row and ri == len(rows) - 1 else ""
            body.append(f"<tr{tr_cls}>{''.join(tds)}</tr>")
        cap = f"<figcaption>{_esc(title)}</figcaption>" if title else ""
        note = caption or (f"Showing first {max_rows} rows." if truncated else "")
        note_html = f'<div class="tcap">{_esc(note)}</div>' if note else ""
        self._blocks.append(f'<figure>{cap}<div class="tw"><table><thead><tr>{head}</tr></thead>'
                            f'<tbody>{"".join(body)}</tbody></table></div>{note_html}</figure>')
        return self

    # ---- footer
    def methodology(self, steps: Iterable[str] = (), validated: bool | None = None,
                    notes: Iterable[str] = (), review: str = "full") -> "Report":
        """review: "full" (separate Reviewer agent) or "quick" (fast path, automated checks only)."""
        self._validated = validated
        self._review = review
        s = "".join(f"<li>{_esc(x)}</li>" for x in steps)
        n = "".join(f"<li>{_esc(x)}</li>" for x in notes)
        src = "".join(f"<li>{_esc(x)}</li>" for x in self.sources)
        self._footer = (
            '<footer class="rf">'
            + (f"<h2>Data sources</h2><ul>{src}</ul>" if src else "")
            + (f"<h2>How this report was prepared</h2><ul>{s}</ul>" if s else "")
            + (f"<h2>Caveats</h2><ul>{n}</ul>" if n else "")
            + "</footer>")
        return self

    # ---- output
    def render(self) -> str:
        meta = [("Generated", datetime.now().strftime("%d %b %Y, %H:%M"))]
        if self.period:
            meta.insert(0, ("Period", self.period))
        if self.author:
            meta.append(("Prepared by", self.author))
        meta_html = "".join(f"<div><dt>{_esc(k)}</dt><dd>{_esc(v)}</dd></div>" for k, v in meta)
        if self._validated is not None:
            if not self._validated:
                b = '<span class="badge no">Not yet validated</span>'
            elif self._review == "quick":
                b = '<span class="badge quick">Quick report: automated checks passed</span>'
            else:
                b = '<span class="badge ok">Reviewed and validated</span>'

            meta_html += f"<div><dt>Status</dt><dd>{b}</dd></div>"
        sub = f'<p class="sub">{_esc(self.subtitle)}</p>' if self.subtitle else ""
        body = "".join(self._blocks)
        return (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="color-scheme" content="light">'
            f"<title>{_esc(self.title)}</title><style>{CSS}</style></head><body>"
            f'<main class="page"><header class="rh"><h1>{_esc(self.title)}</h1>{sub}<dl>{meta_html}</dl></header>'
            f'<section class="rs">{body}</section>{self._footer}</main></body></html>')

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.render(), encoding="utf-8")
        return p
