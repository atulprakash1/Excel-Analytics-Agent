"""Build reports/deal_inventory_overview.html from output/ + validation.json."""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from tools.report_kit import Report, fmt_compact, fmt_money, fmt_num, fmt_pct  # noqa: E402,F401
from tools.validate import load_validation  # noqa: E402
from tools.load_data import describe_logs  # noqa: E402

REPORT = "deal_inventory_overview"
out = HERE / "output"
k = json.loads((out / "kpis.json").read_text())
log = json.loads((out / "data_log.json").read_text())
val = load_validation(REPORT)
tables = {p.stem: pd.read_csv(p) for p in sorted(out.glob("*.csv"))}
money = lambda v: fmt_compact(v, "EUR ")  # noqa: E731

TITLE = "IAM Deal Inventory Overview"
SUBTITLE = "Outstanding Loan and Deposit notional, maturity profile and portfolio composition"
PERIOD = k["as_of"]
HEADLINE = (
    f"IAM held {money(k['notional_in_ccy'])} of outstanding notional as of {k['as_of']}, "
    f"split {fmt_pct(k['total_deposit'] / k['notional_in_ccy'])} Deposits and "
    f"{fmt_pct(k['total_loan'] / k['notional_in_ccy'])} Loans, entirely in EUR."
)
DETAIL = (
    f"{money(k['maturing_next_365d'])} ({fmt_pct(k['maturing_next_365d'] / k['notional_in_ccy'])}) matures within "
    f"the next 365 days; nothing is due within 7, 30 or 90 days. The book runs across 8 portfolios."
)
KPIS = [
    {"label": "Total notional", "value": money(k["notional_in_ccy"]), "note": f"as of {k['as_of']}"},
    {"label": "Deposits", "value": money(k["total_deposit"]),
     "note": fmt_pct(k["total_deposit"] / k["notional_in_ccy"]) + " of total"},
    {"label": "Loans", "value": money(k["total_loan"]),
     "note": fmt_pct(k["total_loan"] / k["notional_in_ccy"]) + " of total"},
    {"label": "Maturing in 365 days", "value": money(k["maturing_next_365d"]),
     "note": fmt_pct(k["maturing_next_365d"] / k["notional_in_ccy"]) + " of total"},
]
FORMATS = {
    "Notional": fmt_money, "Loan": fmt_money, "Deposit": fmt_money, "Total": fmt_money,
    "Share of Total": fmt_pct,
}
NOTES = [
    "Notional is an outstanding stock: totals are the position on the single reporting date, "
    "never summed across dates.",
    "All deals are denominated in EUR; the currency table has a single row by design.",
]

r = Report(TITLE, subtitle=SUBTITLE, period=PERIOD, sources=describe_logs(log))
r.headline(HEADLINE, DETAIL)
r.kpis(KPIS)

# 1. Loan vs Deposit split
r.section("1. Notional by deal type", "Total outstanding notional split between Loan and Deposit.")
t = tables["by_deal_type"]
r.bar_chart(list(t["Deal Type"]), list(t["Notional"]), value_format=money,
            highlight=[str(t["Deal Type"].iloc[0])])
r.table(t, formats=FORMATS)

# 2. Maturing in next 7/30/90/365 days
r.section("2. Amount maturing soon", "Outstanding notional falling due within each horizon from the reporting date.")
t = tables["maturity_windows"]
r.bar_chart(list(t["Window"]), list(t["Notional"]), value_format=money)
r.table(t, formats=FORMATS)

# 3. Maturity profile by year
r.section("3. Maturity profile by year", "Outstanding notional grouped by the calendar year of maturity.")
t = tables["maturity_by_year"]
r.line_chart([str(y) for y in t["Maturity Year"]], {"Notional": list(t["Notional"])}, value_format=money)
r.table(t, formats=FORMATS)

# 4. Notional exposure by currency
r.section("4. Notional exposure by currency", "Outstanding notional by settlement currency.")
t = tables["by_currency"]
r.bar_chart(list(t["Currency"]), list(t["Notional"]), value_format=money)
r.table(t, formats=FORMATS)

# 5. Loan / Deposit split by portfolio
r.section("5. Loan and Deposit split by portfolio", "Outstanding notional by Murex portfolio, broken down by deal type.")
t = tables["portfolio_split"]
r.bar_chart(list(t["Murex Portfolio"]), list(t["Total"]), value_format=money,
            highlight=[str(t["Murex Portfolio"].iloc[0])])
r.table(t, formats=FORMATS)

warnings = [x["detail"] for x in (val or {}).get("results", []) if x["severity"] == "warning"]
if warnings:
    r.callout(" ".join(warnings), title="Needs a decision", kind="warning")
steps = [s for lg in log.values() for s in lg
         if not s.startswith(("  ", "Loaded", "raw rows", "final rows", "source "))]
r.methodology(
    steps=["Data cleaned with confirmed rules: " + ("; ".join(steps) or "none needed"),
           (f"{val['n_checks'] - val['n_failed']} of {val['n_checks']} automated checks passed" if val
            else "Not yet checked")],
    validated=bool(val and val["passed"]), notes=NOTES,
    review=(val or {}).get("review_level", "full"))
print(f"Report written to {r.save(ROOT / 'reports' / (REPORT + '.html'))}")
