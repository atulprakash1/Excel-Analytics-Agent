"""
Render one of every chart in tools/report_kit.py, to check the kit by eye after changing it.

All figures here are made up for the demo. The page goes to work/ (scratch), not reports/,
because it is not a report: real reports take every number from output/.

Usage:  python samples/chart_gallery.py
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.report_kit import Report, fmt_compact, fmt_money, fmt_pct  # noqa: E402

money = lambda v: fmt_compact(v, "EUR ")  # noqa: E731

BUCKETS = ["0-7d", "8-30d", "1-3m", "3-6m", "6-12m", "1-2y", "2-5y", ">5y"]
LADDER = [  # long table: one row per bucket and deal type
    {"Bucket": b, "Deal Type": t, "Notional": n}
    for b, loan, dep in zip(BUCKETS, [40e6, 95e6, 180e6, 240e6, 310e6, 150e6, 90e6, 35e6],
                            [120e6, 210e6, 260e6, 190e6, 140e6, 60e6, 25e6, 5e6])
    for t, n in (("Loan", loan), ("Deposit", dep))
]
LADDER_TOTALS = [160e6, 305e6, 440e6, 430e6, 450e6, 210e6, 115e6, 40e6]
BY_CCY = [  # wide table: one row per bucket, one column per currency (EUR equivalent)
    {"Bucket": b, "EUR": e, "USD": u, "GBP": g, "CHF": c}
    for b, e, u, g, c in zip(BUCKETS, [90e6, 160e6, 230e6, 220e6, 240e6, 120e6, 70e6, 30e6],
                             [40e6, 90e6, 130e6, 120e6, 130e6, 60e6, 30e6, 8e6],
                             [20e6, 35e6, 50e6, 60e6, 55e6, 20e6, 10e6, 2e6],
                             [10e6, 20e6, 30e6, 30e6, 25e6, 10e6, 5e6, 0])
]
GAP = [{"Bucket": b, "Net gap": v} for b, v in zip(BUCKETS, [-80e6, -115e6, -80e6, 50e6, 170e6, 90e6, 65e6, 30e6])]
MONTH_ENDS = [date(2026, m, d) for m, d in ((1, 31), (2, 28), (3, 31), (4, 30), (6, 30), (7, 31), (8, 31), (9, 30))]
CASH = [388e6, 402e6, 371e6, 395e6, 441e6, 428e6, 389e6, 412e6]
BRIDGE = [{"Step": s, "Amount": v} for s, v in (
    ("Opening 31 Aug", 389e6), ("Customer receipts", 96e6), ("Supplier payments", -58e6),
    ("Payroll", -21e6), ("Debt service", -14e6), ("New deposits", 32e6), ("FX revaluation", -12e6),
    ("Closing 30 Sep", 412e6))]
LIMITS = [{"Counterparty": c, "Exposure": e, "Limit": lim} for c, e, lim in (
    ("Bank A", 138e6, 200e6), ("Bank B", 96e6, 100e6), ("Bank C", 131e6, 120e6),
    ("Bank D", 22e6, 80e6), ("Money market fund E", 58e6, 60e6))]
BANKS = [{"Bank": b, "Closing Balance": v, "Share": s} for b, v, s in (
    ("Bank A", 140e6, 0.34), ("Bank B", 99e6, 0.24), ("Bank C", 81e6, 0.197),
    ("Bank D", 54e6, 0.131), ("Other", 38e6, 0.092), ("Total", 412e6, 1.0))]

r = Report("Chart gallery", subtitle="Every chart in report_kit.py, drawn from made-up figures",
           period="30 Sep 2026", sources=["Dummy data in samples/chart_gallery.py"])
r.headline("Every chart the kit can draw, all inline SVG with no libraries.",
           "Hover any mark for its value. Pick the chart by the question, as listed in the html-report skill.")
r.kpis([
    {"label": "Cash position", "value": money(412e6), "delta": 0.059, "note": "vs 31 Aug", "trend": CASH},
    {"label": "Weighted average rate", "value": "3.42%", "trend": [3.1, 3.2, 3.35, 3.3, 3.4, 3.38, 3.45, 3.42]},
    {"label": "Counterparties over limit", "value": "1", "delta": 1.0, "good_when": "down", "note": "vs 31 Aug"},
    {"label": "Deals", "value": "1,019"},
])

r.section("Compare categories", "bar_chart: horizontal bars, sorted, with the headline item highlighted.")
r.bar_chart([b["Bank"] for b in BANKS[:-1]], [b["Closing Balance"] for b in BANKS[:-1]],
            title="Closing balance by bank", value_format=money, highlight=["Bank A"], sort=True)
r.chart(GAP, "bar", x="Bucket", y="Net gap", title="Net liquidity gap by bucket (negatives run left of zero)",
        value_format=money)
r.chart(BY_CCY[:5], "grouped_bar", x="Bucket", y=["EUR", "USD"], title="EUR and USD side by side (grouped_bar)",
        value_format=money)
r.chart(BY_CCY, "stacked_bar", x="Bucket", y=["EUR", "USD", "GBP", "CHF"],
        title="Notional by bucket and currency, EUR equivalent (stacked_bar with totals)",
        value_format=money, totals=LADDER_TOTALS)

r.section("Ordered buckets and time", "column_chart: vertical columns keep the order of the buckets.")
r.column_chart(BUCKETS, LADDER_TOTALS, title="Maturity ladder (column)", value_format=money,
               reference={"Refinancing limit": 400e6})
r.chart(LADDER, "stacked_column", x="Bucket", y="Notional", by="Deal Type",
        title="Maturity ladder by deal type (stacked_column with totals)", value_format=money, totals=LADDER_TOTALS)
r.chart(LADDER, "grouped_column", x="Bucket", y="Notional", by="Deal Type",
        title="Loans against deposits (grouped_column)", value_format=money)
r.chart(BY_CCY, "percent_column", x="Bucket", y=["EUR", "USD", "GBP", "CHF"],
        title="Currency mix by bucket (percent_column)", value_format=money)
r.chart(GAP, "column", x="Bucket", y="Net gap", title="Net liquidity gap (column, negatives below zero)",
        value_format=money)

r.section("Over time", "line_chart: dates are placed on a true time axis; a missing value leaves a gap.")
r.line_chart(MONTH_ENDS, {"Cash position": CASH},
             title="Month-end cash, no May figure: dates keep their true spacing (area)",
             value_format=money, area=True, zero_based=False, reference={"Minimum liquidity": 380e6})
r.line_chart(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"],
             {"Portfolio yield": [0.031, 0.032, 0.0335, 0.033, None, 0.034, 0.0338, 0.0345, 0.0342],
              "Policy rate": [0.03, 0.03, 0.0325, 0.0325, 0.0325, 0.0325, 0.035, 0.035, 0.035]},
             title="Yield against the policy rate (step, with a target band and a gap in May)",
             value_format=lambda v: fmt_pct(v, 2), zero_based=False, step=True,
             band=(0.032, 0.034, "Target range"))
r.chart(BY_CCY, "stacked_area", x="Bucket", y=["EUR", "USD", "GBP", "CHF"],
        title="Notional by currency across the ladder (stacked_area)", value_format=money)

r.section("What changed", "waterfall: totals are levels, everything between is a change.")
r.chart(BRIDGE, "waterfall", x="Step", y="Amount", title="Cash bridge, August to September",
        value_format=money, totals=["Opening 31 Aug", "Closing 30 Sep"])

r.section("Against a limit", "bullet_chart: every limit sits on the same mark, so utilisation compares by eye.")
r.chart(LIMITS, "bullet", x="Counterparty", y="Exposure", limit="Limit",
        title="Counterparty exposure against limit", value_format=money)
r.bullet_chart(["LCR", "NSFR"], [1.32, 1.04], [1.0, 1.0], title="Regulatory ratios against the minimum",
               value_format=lambda v: fmt_pct(v, 0), good_when="above")

r.section("Share of a whole", "donut_chart: only for a few parts; the table carries the exact shares.")
r.donut_chart([b["Bank"] for b in BANKS[:-1]], [b["Closing Balance"] for b in BANKS[:-1]],
              title="Cash by bank", value_format=money, center=money(412e6), center_note="total cash")
r.table(BANKS, title="Table with data bars", formats={"Closing Balance": fmt_money, "Share": fmt_pct},
        total_row=True, bars=["Closing Balance", "Share"])

r.methodology(steps=["Dummy figures typed into the sample script"], notes=["Not a report: for checking the kit only"])
print(f"Gallery written to {r.save(ROOT / 'work' / 'chart_gallery.html')}")
