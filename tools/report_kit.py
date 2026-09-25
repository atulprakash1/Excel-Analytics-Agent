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
    r.table(df, formats={"Closing balance": fmt_money, "Share": fmt_pct})
    r.methodology(["Subtotal rows removed", "Converted at 30 Sep closing rates"], validated=True)
    r.save("reports/cash_position_daily.html")
"""
from __future__ import annotations

import html
import math
from datetime import datetime
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
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 0.5:
        ticks.append(round(t, 10))
        t += step
    return ticks


# --------------------------------------------------------------------------- styles

CSS = """
:root{
  color-scheme: light;
  --canvas:#e9edf1; --paper:#ffffff; --ink:#1c2733; --muted:#5b6b7a; --rule:#d5dbe1;
  --accent:#0e6e6b; --accent-soft:#e2f0ef; --pos:#2f7d4f; --neg:#b43c3c; --warn:#9a6412;
  --s0:#0e6e6b; --s1:#b7791f; --s2:#4a6fa5; --s3:#8a5a83; --s4:#6b7d2a;
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
.s3{stroke:var(--s3);fill:var(--s3)} .s4{stroke:var(--s4);fill:var(--s4)}
svg.chart polyline{fill:none;stroke-width:2.25;stroke-linejoin:round}
.legend{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:.85rem;margin-top:6px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:12px;height:3px;display:inline-block}
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
        """items: {label, value (str), delta (ratio, optional), note, good_when: 'up'|'down'}"""
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
                       f'<div class="v">{_esc(k["value"])}</div>{d}{n}</div>')
        self._blocks.append(f'<div class="kpis">{"".join(out)}</div>')
        return self

    # ---- charts
    def bar_chart(self, labels: Sequence, values: Sequence[float], title: str = "",
                  value_format: Callable = fmt_compact, highlight: Iterable = (),
                  sort: bool = False) -> "Report":
        """Horizontal bar chart. Best for comparing categories (up to ~15)."""
        pairs = list(zip(labels, values))
        if sort:
            pairs.sort(key=lambda p: p[1], reverse=True)
        hl = set(highlight)
        W, lw, vw, rh = 680, 170, 80, 30
        H = rh * len(pairs) + 10
        vmax = max([abs(v) for _, v in pairs] + [1e-9])
        bw = W - lw - vw
        parts = []
        for i, (lab, v) in enumerate(pairs):
            y = i * rh + 5
            w = max(1.5, bw * abs(v) / vmax)
            cls = "bar neg" if v < 0 else ("bar hi" if lab in hl else "bar")
            text_lab = str(lab) if len(str(lab)) <= 24 else str(lab)[:23] + "…"
            parts.append(
                f'<text class="lbl" x="{lw - 10}" y="{y + rh / 2 + 4}" text-anchor="end">{_esc(text_lab)}</text>'
                f'<rect class="{cls}" x="{lw}" y="{y + 5}" width="{w:.1f}" height="{rh - 10}" rx="2"/>'
                f'<text class="val" x="{lw + w + 6:.1f}" y="{y + rh / 2 + 4}">{_esc(value_format(v))}</text>')
        svg = (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title)}">'
               f'{"".join(parts)}</svg>')
        self._figure(svg, title)
        return self

    def line_chart(self, x_labels: Sequence, series: dict, title: str = "",
                   value_format: Callable = fmt_compact, zero_based: bool = True) -> "Report":
        """series: {"Actual": [..], "Target": [..]} - each list aligned with x_labels."""
        W, H, pl, pr, pt, pb = 680, 280, 64, 16, 14, 34
        allv = [v for s in series.values() for v in s if v is not None]
        lo = min(allv + ([0] if zero_based else []))
        hi = max(allv) if allv else 1
        ticks = _nice_ticks(lo, hi)
        lo, hi = ticks[0], ticks[-1]
        n = len(x_labels)
        xs = [pl + (W - pl - pr) * (i / max(1, n - 1)) for i in range(n)]

        def y(v):
            return pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo or 1))

        parts = []
        for t in ticks:
            parts.append(f'<line class="grid" x1="{pl}" x2="{W - pr}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                         f'<text x="{pl - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{_esc(value_format(t))}</text>')
        step = max(1, math.ceil(n / 10))
        for i, lab in enumerate(x_labels):
            if i % step == 0 or i == n - 1:
                parts.append(f'<text x="{xs[i]:.1f}" y="{H - 10}" text-anchor="middle">{_esc(lab)}</text>')
        legend = []
        for si, (name, vals) in enumerate(series.items()):
            c = f"s{si % 5}"
            pts = " ".join(f"{xs[i]:.1f},{y(v):.1f}" for i, v in enumerate(vals) if v is not None)
            parts.append(f'<polyline class="{c}" points="{pts}" style="fill:none"/>')
            for i, v in enumerate(vals):
                if v is not None:
                    parts.append(f'<circle class="{c}" cx="{xs[i]:.1f}" cy="{y(v):.1f}" r="3">'
                                 f'<title>{_esc(name)} {_esc(x_labels[i])}: {_esc(value_format(v))}</title></circle>')
            legend.append(f'<span><i style="background:var(--s{si % 5})"></i>{_esc(name)}</span>')
        svg = (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title)}">'
               f'{"".join(parts)}</svg>')
        leg = f'<div class="legend">{"".join(legend)}</div>' if len(series) > 1 else ""
        self._figure(svg + leg, title)
        return self

    def _figure(self, inner: str, title: str):
        cap = f"<figcaption>{_esc(title)}</figcaption>" if title else ""
        self._blocks.append(f"<figure>{cap}{inner}</figure>")

    # ---- tables
    def table(self, data, title: str = "", formats: dict | None = None, max_rows: int = 50,
              total_row: bool = False, caption: str = "") -> "Report":
        """data: pandas DataFrame or list of dicts. formats: {column: callable}.
        total_row=True styles the last row as a total."""
        formats = formats or {}
        if hasattr(data, "to_dict"):
            cols = [str(c) for c in data.columns]
            rows = data.to_dict("records")
            rows = [{str(k): v for k, v in r.items()} for r in rows]
        else:
            rows = list(data)
            cols = list(rows[0].keys()) if rows else []
        truncated = len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]
        numeric = {c for c in cols if rows and all(
            isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool)
            for r in rows if r.get(c) is not None)}
        head = "".join(f'<th class="{"num" if c in numeric else ""}">{_esc(c)}</th>' for c in cols)
        body = []
        for ri, r in enumerate(rows):
            tds = []
            for c in cols:
                v = r.get(c)
                if isinstance(v, float) and math.isnan(v):
                    v = None
                if c in formats and v is not None:
                    s = formats[c](v)
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
                tds.append(f'<td class="{" ".join(cls)}">{_esc(s)}</td>')
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
