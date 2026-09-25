"""
reports.py - the report registry: which report reads which inputs and produces which outputs.

Every report folder has a manifest, analysis/<report>/report.json, written by
scaffold_report.py (or `init` for older folders) and updated by run_pipeline.py after each run:

  {
    "report": "cash_position_daily", "title": "...", "question": "...",
    "review_level": "quick" | "full", "owner": "...", "schedule": "monthly" | "ad hoc",
    "inputs":  [{"source": "bank_balances", "sheet": "Balances"},         # logical source (preferred)
                {"profile": "some_one_off_file", "sheet": "Data"}],         # fixed file
    "outputs": {"html": "reports/cash_position_daily.html", "folder": "analysis/cash_position_daily/output"},
    "tags": [...], "created": "2026-09-24",
    "last_run": {"at", "status", "inputs": [{..., "file", "sha256"}], "kpis", "validation", "seconds"},
    "history": [ ...last 12 runs, newest first... ]
  }

There is no separate index file to go stale: every command reads the manifests directly.

Usage:
  python tools/reports.py list                       # all reports, inputs, last run, freshness
  python tools/reports.py show cash_position_daily
  python tools/reports.py uses bank_balances_2026_10.xlsx     # or a source id, or a profile name
  python tools/reports.py find "revenue by product"  # search before building a new report
  python tools/reports.py check [report]             # manifest vs code, profiles, outputs, freshness
  python tools/reports.py init <report> --input bank_balances:Balances ... --title "..."
  python tools/reports.py init <report> --from-code  # build a manifest from analysis.py
  python tools/reports.py refresh-all bank_balances           # re-run every dependent report
  python tools/reports.py index                      # rebuild reports/index.html
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.knowledge import load_sources, match_source, resolve_source  # noqa: E402

ANALYSIS = ROOT / "analysis"
PROFILES = ROOT / "profiles"
HISTORY_KEEP = 12
LOAD_CALL = re.compile(r"load_(source|sheet)\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"']([^\"']+)[\"']")


# --------------------------------------------------------------------------- manifests

def manifest_path(report: str) -> Path:
    return ANALYSIS / report / "report.json"


def load_manifest(report: str) -> dict | None:
    p = manifest_path(report)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_manifest(m: dict):
    manifest_path(m["report"]).write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")


def all_reports() -> list[str]:
    return sorted(p.name for p in ANALYSIS.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


def all_manifests() -> list[dict]:
    return [m for r in all_reports() if (m := load_manifest(r))]


def new_manifest(report: str, inputs: list[dict], title: str = "", question: str = "",
                 review_level: str = "full", owner: str = "", schedule: str = "ad hoc",
                 tags: list[str] | None = None, domains: list[str] | None = None) -> dict:
    return {"schema_version": "1.0", "report": report,
            "title": title or report.replace("_", " ").capitalize(), "question": question,
            "review_level": review_level, "owner": owner, "schedule": schedule,
            "inputs": inputs,
            "outputs": {"html": f"reports/{report}.html", "folder": f"analysis/{report}/output"},
            "tags": tags or [], "domains": domains or [],
            "created": date.today().isoformat(), "last_run": None, "history": []}


def parse_input(spec: str) -> dict:
    """'bank_balances:Balances' -> source input if it is a registered source, else profile input."""
    name, sheet = spec.split(":", 1)
    kind = "source" if any(s["id"] == name for s in load_sources()["sources"]) else "profile"
    return {kind: name, "sheet": sheet}


def code_inputs(report: str) -> dict[str, list[dict]]:
    """Inputs referenced in each script of a report folder (by static scan of load_* calls)."""
    out = {}
    for script in ("analysis.py", "checks.py"):
        p = ANALYSIS / report / script
        if p.exists():
            out[script] = [{("source" if k == "source" else "profile"): n, "sheet": s}
                           for k, n, s in LOAD_CALL.findall(p.read_text(encoding="utf-8"))]
    return out


def _key(i: dict) -> tuple:
    return ("source", i["source"], i["sheet"]) if "source" in i else ("profile", i["profile"], i["sheet"])


# --------------------------------------------------------------------------- resolution

def resolve_input(i: dict) -> dict:
    """Which file and profile an input points at right now, and whether it is usable."""
    r = dict(i)
    try:
        if "source" in i:
            f = resolve_source(i["source"])
            r["file"], r["profile_name"] = f.name, f.stem
        else:
            r["profile_name"] = i["profile"]
            pj = PROFILES / f"{i['profile']}.profile.json"
            r["file"] = json.loads(pj.read_text(encoding="utf-8"))["source"]["file"] if pj.exists() else None
    except (FileNotFoundError, KeyError) as e:
        r["error"] = str(e)
        return r
    pj = PROFILES / f"{r['profile_name']}.profile.json"
    if not pj.exists():
        r["error"] = f"no profile for {r['file']} - run python tools/profile_excel.py"
        return r
    prof = json.loads(pj.read_text(encoding="utf-8"))
    r["sha256"] = prof["source"]["sha256"]
    r["profile_status"] = prof["annotations"]["status"]
    if r["profile_status"] != "confirmed":
        r["error"] = f"profile {r['profile_name']} is '{r['profile_status']}' - Profiler must confirm it"
    elif i["sheet"] not in {s["name"] for s in prof["sheets"]}:
        r["error"] = f"sheet '{i['sheet']}' not found in {r['file']}"
    return r


def freshness(m: dict) -> str:
    """'never run' | 'current' | 'new data available' | 'last run failed' | 'blocked: ...'"""
    res = [resolve_input(i) for i in m["inputs"]]
    errs = list(dict.fromkeys(r["error"] for r in res if r.get("error")))
    if errs:
        return "blocked: " + "; ".join(errs)
    lr = m.get("last_run")
    if not lr:
        return "never run"
    if lr["status"] != "success":
        return f"last run {lr['status']}"
    used = {_key(u): (u.get("file"), u.get("sha256")) for u in lr.get("inputs", [])}
    for r in res:
        if used.get(_key(r)) != (r["file"], r["sha256"]):
            return "new data available"
    return "current"


def record_run(report: str, status: str, resolved: list[dict], seconds: float, note: str = ""):
    """Called by run_pipeline.py after every run."""
    m = load_manifest(report)
    if m is None:
        return
    out = ANALYSIS / report / "output"
    kp = out / "kpis.json"
    val = ANALYSIS / report / "validation.json"
    v = json.loads(val.read_text(encoding="utf-8")) if val.exists() else None
    run = {"at": datetime.now().isoformat(timespec="seconds"), "status": status,
           "inputs": [{k: r[k] for k in ("source", "profile", "sheet", "file", "sha256") if k in r}
                      for r in resolved],
           "kpis": json.loads(kp.read_text(encoding="utf-8")) if kp.exists() and status == "success" else None,
           "validation": (f"{v['n_checks'] - v['n_failed']}/{v['n_checks']} passed ({v.get('review_level', 'full')})"
                          if v else None),
           "seconds": round(seconds, 1), "note": note}
    m["last_run"] = run
    m["history"] = [run] + m.get("history", [])[:HISTORY_KEEP - 1]
    save_manifest(m)


# --------------------------------------------------------------------------- queries

def uses(target: str) -> list[dict]:
    """Reports that depend on a file name, a profile name or a logical source id."""
    tgt = Path(target).name
    sources = {tgt} | set(match_source(tgt))           # a source id matches itself
    stems = {Path(tgt).stem}
    for sid in list(sources):                           # a source id also covers its current file
        try:
            stems.add(resolve_source(sid).stem)
        except (KeyError, FileNotFoundError):
            pass
    hits = []
    for m in all_manifests():
        for i in m["inputs"]:
            if i.get("source") in sources or i.get("profile") in stems:
                hits.append({"report": m["report"], "input": i, "via": "source" if "source" in i else "file"})
                break
    return hits


def find(query: str, limit: int = 8) -> list[tuple[int, dict]]:
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
    scored = []
    for m in all_manifests():
        plan = ANALYSIS / m["report"] / "plan.md"
        hay = " ".join([m["report"], m["title"], m.get("question", ""), " ".join(m.get("tags", [])),
                        " ".join(str(v) for i in m["inputs"] for v in i.values()),
                        plan.read_text(encoding="utf-8") if plan.exists() else ""]).lower()
        head = f"{m['report']} {m['title']} {m.get('question', '')}".lower()
        score = sum(hay.count(w) for w in words) + 5 * sum(w in head for w in words)
        if score:
            scored.append((score, m))
    return sorted(scored, key=lambda x: -x[0])[:limit]


def check(report: str) -> list[str]:
    issues = []
    m = load_manifest(report)
    if not m:
        return [f"{report}: no report.json - run python tools/reports.py init {report} --from-code"]
    declared = {_key(i) for i in m["inputs"]}
    for script, ins in code_inputs(report).items():
        used = {_key(i) for i in ins}
        if used - declared:
            issues.append(f"{report}: {script} reads inputs not in report.json: {sorted(used - declared)}")
        if script == "analysis.py" and declared - used:
            issues.append(f"{report}: report.json lists inputs analysis.py does not read: {sorted(declared - used)}")
        fixed = [i for i in ins if "profile" in i]
        for i in fixed:
            ms = match_source(f"{i['profile']}.xlsx") or match_source(f"{i['profile']}.csv")
            if ms:
                issues.append(f"{report}: {script} reads fixed file '{i['profile']}' but it belongs to source "
                              f"{ms[0]} - use load_source(\"{ms[0]}\", ...) so new files are picked up")
    for f in ("analysis.py", "checks.py", "build_report.py", "plan.md"):
        if not (ANALYSIS / report / f).exists():
            issues.append(f"{report}: missing {f}")
    fr = freshness(m)
    if fr != "current":
        issues.append(f"{report}: {fr}")
    if not (ROOT / m["outputs"]["html"]).exists():
        issues.append(f"{report}: report HTML not built yet")
    return issues


# --------------------------------------------------------------------------- index page

def build_index() -> Path:
    from tools.report_kit import Report
    ms = all_manifests()
    r = Report("Report catalogue", subtitle="Every report in this workspace, what it reads, and whether "
               "it is up to date.")
    fr = {m["report"]: freshness(m) for m in ms}
    stale = [m for m in ms if fr[m["report"]] != "current"]
    r.headline(f"{len(ms) - len(stale)} of {len(ms)} reports are up to date.",
               "Needs attention: " + ", ".join(m["title"] for m in stale) if stale else "Nothing needs attention.")
    for m in ms:
        lr = m.get("last_run") or {}
        inputs = ", ".join(f"{i.get('source') or i.get('profile')}/{i['sheet']}" for i in m["inputs"])
        r.section(m["title"], f"{m.get('question', '')} Inputs: {inputs}. Review: {m['review_level']}. "
                              f"Schedule: {m['schedule']}.")
        status = fr[m["report"]].split(":")[0]
        snap = re.compile(rf"^{re.escape(m['report'])}_(\d{{4}}-\d{{2}}-\d{{2}})\.html$")
        snaps = sorted(((mt.group(1), p) for p in (ROOT / "reports").glob(f"{m['report']}_*.html")
                        if (mt := snap.match(p.name))), reverse=True)
        rows = [{"Report": f"{m['title']} – {as_of}", "href": p.name, "As of": as_of,
                 "Status": status if i == 0 else "snapshot",
                 "Last run": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}
                for i, (as_of, p) in enumerate(snaps)]
        if not rows and (ROOT / m["outputs"]["html"]).exists():
            # reports built before dated snapshots existed only have the undated file
            rows.append({"Report": m["title"], "href": Path(m["outputs"]["html"]).name,
                         "As of": (lr.get("kpis") or {}).get("as_of", "–"), "Status": status,
                         "Last run": (lr.get("at") or "never")[:16].replace("T", " ")})
        if rows:
            r.table(rows, links={"Report": "href"})
        else:
            r.text("Not built yet.")
    details = [f"{m['title']}: {fr[m['report']]}" for m in stale if ":" in fr[m["report"]]]
    if details:
        r.section("Why reports are blocked", "Resolve these with the Profiler agent, then refresh.")
        r.findings(details)
    return r.save(ROOT / "reports" / "index.html")


# --------------------------------------------------------------------------- CLI

def _fmt_inputs(m: dict) -> str:
    return ", ".join(f"{i.get('source') or i.get('profile')}:{i['sheet']}" for i in m["inputs"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sh = sub.add_parser("show"); sh.add_argument("report")  # noqa: E702
    us = sub.add_parser("uses"); us.add_argument("target")  # noqa: E702
    fd = sub.add_parser("find"); fd.add_argument("query")  # noqa: E702
    ck = sub.add_parser("check"); ck.add_argument("report", nargs="?")  # noqa: E702
    it = sub.add_parser("init"); it.add_argument("report")  # noqa: E702
    it.add_argument("--input", action="append", default=[], help="source_or_profile:sheet")
    it.add_argument("--from-code", action="store_true")
    it.add_argument("--title", default=""); it.add_argument("--question", default="")  # noqa: E702
    it.add_argument("--level", default="full", choices=["full", "quick"])
    it.add_argument("--owner", default=""); it.add_argument("--schedule", default="ad hoc")  # noqa: E702
    it.add_argument("--tag", action="append", default=[])
    it.add_argument("--force", action="store_true")
    ra = sub.add_parser("refresh-all"); ra.add_argument("target")  # noqa: E702
    sub.add_parser("index")
    a = ap.parse_args()

    if a.cmd == "list":
        ms = all_manifests()
        missing = [r for r in all_reports() if not load_manifest(r)]
        for m in ms:
            lr = m.get("last_run") or {}
            print(f"{m['report']}  [{m['review_level']}, {m['schedule']}]  {m['title']}")
            print(f"    inputs: {_fmt_inputs(m)}")
            print(f"    last run: {(lr.get('at') or 'never')[:16]}  status: {freshness(m)}")
        for r in missing:
            print(f"{r}  (no report.json - run: python tools/reports.py init {r} --from-code)")
    elif a.cmd == "show":
        m = load_manifest(a.report)
        if not m:
            sys.exit(f"No manifest for {a.report}")
        print(json.dumps({k: v for k, v in m.items() if k != "history"}, indent=2, ensure_ascii=False))
        print(f"\nCurrent inputs: {json.dumps([resolve_input(i) for i in m['inputs']], indent=2)}")
        print(f"Freshness: {freshness(m)}  |  runs recorded: {len(m.get('history', []))}")
    elif a.cmd == "uses":
        hits = uses(a.target)
        srcs = match_source(Path(a.target).name)
        if srcs:
            print(f"{a.target} belongs to logical source(s): {srcs}")
        if not hits:
            print(f"No report depends on {a.target}.")
        for h in hits:
            m = load_manifest(h["report"])
            print(f"{h['report']}  ({m['title']}) via {h['via']} {h['input']}  - {freshness(m)}")
    elif a.cmd == "find":
        res = find(a.query)
        if not res:
            print("No similar report found.")
        for score, m in res:
            print(f"{m['report']}  score {score}  [{m['review_level']}]  {m['title']}")
            print(f"    question: {m.get('question') or '-'}")
            print(f"    inputs: {_fmt_inputs(m)}")
    elif a.cmd == "check":
        targets = [a.report] if a.report else all_reports()
        issues = [i for r in targets for i in check(r)]
        print("All reports OK" if not issues else "\n".join(f"- {i}" for i in issues))
        sys.exit(1 if issues else 0)
    elif a.cmd == "init":
        if load_manifest(a.report) and not a.force:
            sys.exit(f"{a.report} already has report.json (use --force to replace)")
        if not (ANALYSIS / a.report).exists():
            sys.exit(f"No folder analysis/{a.report}")
        inputs = [parse_input(s) for s in a.input]
        if a.from_code:
            inputs = code_inputs(a.report).get("analysis.py", [])
        if not inputs:
            sys.exit("No inputs: pass --input source:sheet or --from-code")
        doms = []
        for i in inputs:
            r = resolve_input(i)
            pj = PROFILES / f"{r.get('profile_name')}.profile.json"
            if pj.exists():
                from tools.domains import recorded_domains
                doms += [d for d in recorded_domains(json.loads(pj.read_text(encoding="utf-8"))) if d not in doms]
        m = new_manifest(a.report, inputs, a.title, a.question, a.level, a.owner, a.schedule, a.tag, domains=doms)
        save_manifest(m)
        print(f"Wrote {manifest_path(a.report).relative_to(ROOT)} with inputs {_fmt_inputs(m)}")
        for i in check(a.report):
            print(f"  note: {i}")
    elif a.cmd == "refresh-all":
        hits = uses(a.target)
        if not hits:
            print(f"No report depends on {a.target}.")
        results = []
        for h in hits:
            print(f"\n==== {h['report']} ====")
            rc = subprocess.call([sys.executable, "tools/run_pipeline.py", h["report"]], cwd=ROOT)
            results.append((h["report"], "ok" if rc == 0 else "STOPPED"))
        print("\nSummary: " + ", ".join(f"{r} {s}" for r, s in results))
        sys.exit(0 if all(s == "ok" for _, s in results) else 1)
    elif a.cmd == "index":
        print(f"Wrote {build_index().relative_to(ROOT)}")


if __name__ == "__main__":
    main()
