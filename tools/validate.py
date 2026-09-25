"""
validate.py - independent checks the Reviewer agent runs before a report is built.

The Reviewer writes analysis/<report>/checks.py, which recomputes key numbers
*independently* from the source (via tools.load_data) and compares them with the
Analyst's outputs in analysis/<report>/output/. Results are saved to
analysis/<report>/validation.json, which the Report Builder reads to set the
"validated" status on the report.

    from tools.validate import Validator
    v = Validator("cash_position_daily")
    v.reconcile("Total revenue", source_total, report_total)          # tolerance 0.5% default
    v.row_count("Orders in scope", expected=240, actual=len(df))
    v.no_nulls(df, ["Entity", "Currency", "Closing Balance"])
    v.unique(df, ["Order No"], label="Grain: one row per order line")
    v.shares_sum_to_one(summary["Share"])
    v.check("No negative revenue", (df["Amount"] >= 0).all())
    v.save()        # prints summary, writes validation.json, exits 1 if any check failed

CLI (summarise an existing validation):
    python tools/validate.py cash_position_daily
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"


class Validator:
    def __init__(self, report: str, review_level: str = "full"):
        """review_level: "full" (Reviewer agent) or "quick" (fast path, automated checks only)."""
        self.report = report
        self.review_level = review_level
        self.results: list[dict] = []

    def _add(self, name: str, passed: bool, detail: str = "", severity: str = "error"):
        self.results.append({"check": name, "passed": bool(passed), "detail": detail, "severity": severity})
        return passed

    def check(self, name: str, passed, detail: str = "", severity: str = "error"):
        return self._add(name, bool(passed), detail, severity)

    def reconcile(self, name: str, source_value: float, report_value: float, tolerance: float = 0.005):
        diff = report_value - source_value
        rel = abs(diff) / abs(source_value) if source_value else (0 if diff == 0 else math.inf)
        return self._add(f"Reconcile: {name}", rel <= tolerance,
                         f"source={source_value:,.2f} report={report_value:,.2f} diff={diff:,.2f} ({rel:.2%})")

    def row_count(self, name: str, expected: int, actual: int):
        return self._add(f"Row count: {name}", expected == actual, f"expected={expected} actual={actual}")

    def no_nulls(self, df, columns, severity: str = "error"):
        for c in columns:
            n = int(df[c].isna().sum())
            self._add(f"No nulls: {c}", n == 0, f"{n} null(s)", severity)

    def unique(self, df, columns, label: str = ""):
        d = int(df.duplicated(subset=columns).sum())
        return self._add(label or f"Unique: {columns}", d == 0, f"{d} duplicate key(s)")

    def shares_sum_to_one(self, series, tolerance: float = 0.001):
        s = float(series.sum())
        return self._add("Shares sum to 100%", abs(s - 1) <= tolerance, f"sum={s:.4f}")

    def warn(self, name: str, detail: str):
        return self._add(name, True, detail, severity="warning")

    def save(self, exit_on_fail: bool = True) -> dict:
        failed = [r for r in self.results if not r["passed"] and r["severity"] == "error"]
        out = {"report": self.report, "review_level": self.review_level,
               "validated_at": datetime.now().isoformat(timespec="seconds"),
               "passed": not failed, "n_checks": len(self.results), "n_failed": len(failed),
               "results": self.results}
        p = ANALYSIS_DIR / self.report / "validation.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=2), encoding="utf-8")
        _print(out)
        if failed and exit_on_fail:
            sys.exit(1)
        return out


def _print(out: dict):
    print(f"Validation for '{out['report']}': {'PASSED' if out['passed'] else 'FAILED'} "
          f"({out['n_checks'] - out['n_failed']}/{out['n_checks']})")
    for r in out["results"]:
        mark = "OK  " if r["passed"] else ("WARN" if r["severity"] == "warning" else "FAIL")
        print(f"  [{mark}] {r['check']}  {r['detail']}")


def load_validation(report: str) -> dict | None:
    p = ANALYSIS_DIR / report / "validation.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python tools/validate.py <report_name>")
        sys.exit(1)
    v = load_validation(sys.argv[1])
    if not v:
        print(f"No validation.json for '{sys.argv[1]}'. The Reviewer must run analysis/{sys.argv[1]}/checks.py")
        sys.exit(1)
    _print(v)
