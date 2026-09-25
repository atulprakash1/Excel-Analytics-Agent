"""
run_pipeline.py - re-run a report end to end (monthly refresh, or after the agent writes it).

Steps:
  1. profile inputs (cached files take well under a second; new files of a known source
     inherit confirmed annotations when the structure matches)
  2. resolve the report's inputs from analysis/<report>/report.json - logical sources pick up
     the newest file automatically - and stop if any input is not usable (profile missing,
     draft or needs_review, sheet missing). Other reports' inputs do not block this one.
  3. back up output/kpis.json, then analysis.py -> checks.py -> build_report.py
  4. record the run (status, input files + hashes, KPIs, validation, timings) in report.json
     and rebuild the catalogue page reports/index.html

Usage:
  python tools/run_pipeline.py cash_position_daily
To refresh every report that depends on a file or source: python tools/reports.py refresh-all <target>
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import reports  # noqa: E402

TIMINGS: list = []


def run(cmd: list) -> int:
    print(f"\n$ {' '.join(cmd)}")
    t0 = time.perf_counter()
    rc = subprocess.call([sys.executable, *cmd], cwd=ROOT)
    TIMINGS.append((cmd[0], time.perf_counter() - t0))
    return rc


def finish(report: str, status: str, resolved: list, t_start: float, note: str = "", code: int = 0):
    reports.record_run(report, status, resolved, time.perf_counter() - t_start, note.strip())
    try:
        reports.build_index()
    except Exception as e:  # noqa: BLE001 - the index is a convenience, never block on it
        print(f"(index not rebuilt: {e})")
    if TIMINGS:
        print("Timings: " + ", ".join(f"{Path(n).name} {s:.1f}s" for n, s in TIMINGS)
              + f" | total {sum(s for _, s in TIMINGS):.1f}s")
    if note:
        print(note)
    sys.exit(code)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    report = sys.argv[1]
    folder = ROOT / "analysis" / report
    if not folder.exists():
        sys.exit(f"No report folder {folder}")
    t_start = time.perf_counter()

    if run(["tools/profile_excel.py"]) != 0:
        sys.exit("Profiling failed")

    m = reports.load_manifest(report)
    if m is None:
        print(f"WARNING: no report.json for {report}; using inputs found in analysis.py. "
              f"Create one with: python tools/reports.py init {report} --from-code")
        inputs = reports.code_inputs(report).get("analysis.py", [])
    else:
        inputs = m["inputs"]
    resolved = [reports.resolve_input(i) for i in inputs]
    print("\nInputs for this run:")
    for r in resolved:
        label = f"{r.get('source') or r.get('profile')}:{r['sheet']}"
        print(f"  {label:40s} -> {r.get('file') or '?'}" + (f"   BLOCKED: {r['error']}" if r.get("error") else ""))
    blocked = [r for r in resolved if r.get("error")]
    if blocked:
        finish(report, "blocked", resolved, t_start, code=1,
               note="\nSTOPPED: an input is not ready (see above). Ask the Profiler agent to review it. "
                    f"See what else is affected: python tools/reports.py uses {blocked[0].get('file') or ''}")
    for msg in reports.check(report):
        if "reads fixed file" in msg or "not in report.json" in msg:
            print(f"  WARNING: {msg}")

    kpis = folder / "output" / "kpis.json"
    if kpis.exists():
        (folder / "output" / "kpis.previous.json").write_text(kpis.read_text(encoding="utf-8"), encoding="utf-8")
    if run([f"analysis/{report}/analysis.py"]) != 0:
        finish(report, "failed_analysis", resolved, t_start, code=1,
               note="\nSTOPPED at analysis.py. Ask the Analyst (or Quick Report) agent to investigate.")
    if run([f"analysis/{report}/checks.py"]) != 0:
        finish(report, "failed_checks", resolved, t_start, code=1,
               note="\nSTOPPED at checks.py. Ask the Reviewer agent to investigate validation.json.")
    if run([f"analysis/{report}/build_report.py"]) != 0:
        finish(report, "failed_build", resolved, t_start, code=1, note="\nReport build failed.")
    run(["tools/knowledge.py", "lint"])  # informational only
    finish(report, "success", resolved, t_start, note=f"\nDone: reports/{report}.html")


if __name__ == "__main__":
    main()
