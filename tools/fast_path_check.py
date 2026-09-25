"""
fast_path_check.py - decide whether a request may use the fast path (Quick Report agent).

The fast path skips the separate Profiler and Reviewer conversations, so it is only allowed
when the data is already fully understood and confirmed. This script checks that
deterministically; the agent must not override a NOT ELIGIBLE result.

Checks per profile:
  - profile exists and the source file is unchanged since profiling (hash match)
  - annotations status is "confirmed" (not draft / needs_review)
  - every included sheet has a grain and confirmed cleaning rules
  - every column in included sheets has a confirmed role (from the catalog or the profile)
  - no ambiguous catalog matches, no catalog type warnings
  - every measure has an additivity
It also prints the glossary terms and feasible analyses so the agent can check the question
only needs known definitions.

Usage:
  python tools/fast_path_check.py bank_balances mm_deals           # logical sources (preferred)
  python tools/fast_path_check.py bank_balances_2026_09             # or profile names
Exit code 0 = ELIGIBLE, 1 = NOT ELIGIBLE.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.profile_excel import sha256  # noqa: E402
from tools.knowledge import load_sources  # noqa: E402
from tools.load_data import source_profile_name  # noqa: E402

PROFILE_DIR = ROOT / "profiles"
GLOSSARY = ROOT / "knowledge" / "glossary.md"


def check_profile(name: str) -> tuple[list[str], dict]:
    problems: list[str] = []
    if name in {s["id"] for s in load_sources()["sources"]}:
        try:
            resolved = source_profile_name(name)
        except FileNotFoundError as e:
            return [f"{name}: {e}"], {}
        print(f"source {name} -> {resolved}")
        name = resolved
    path = PROFILE_DIR / f"{Path(name).stem}.profile.json"
    if not path.exists():
        return [f"{name}: no profile - run the Profiler"], {}
    prof = json.loads(path.read_text(encoding="utf-8"))
    src = ROOT / prof["source"]["path"]
    ann = prof["annotations"]
    if not src.exists():
        problems.append(f"{name}: source file {prof['source']['path']} is missing")
    elif sha256(src) != prof["source"]["sha256"]:
        problems.append(f"{name}: source file changed since profiling - run python tools/profile_excel.py")
    if ann.get("status") != "confirmed":
        problems.append(f"{name}: profile status is '{ann.get('status')}', needs 'confirmed'")
    for s in prof["sheets"]:
        sa = ann["sheets"].get(s["name"], {})
        if sa.get("include") is False:
            continue
        tag = f"{name}/{s['name']}"
        if not sa.get("grain"):
            problems.append(f"{tag}: no grain recorded")
        if not sa.get("cleaning_rules") and s.get("suggested_cleaning_rules"):
            problems.append(f"{tag}: cleaning rules not confirmed")
        roles = sa.get("column_roles", {})
        periods = set(s.get("wide_format", {}).get("period_columns", []))
        missing = [c["name"] for c in s["columns"] if c["name"] not in periods and c["name"] not in roles]
        if missing:
            problems.append(f"{tag}: columns without a confirmed role: {missing}")
        amb = [c["name"] for c in s["columns"] if c.get("catalog", {}).get("match") == "ambiguous"]
        if amb:
            problems.append(f"{tag}: ambiguous catalog matches: {amb}")
        warn = [f"{c['name']} ({c['catalog']['warning']})" for c in s["columns"] if c.get("catalog", {}).get("warning")]
        if warn:
            problems.append(f"{tag}: data contradicts catalog: {warn}")
        measures = [c for c, r in roles.items() if r == "measure"]
        no_add = [m for m in measures if m not in sa.get("column_additivity", {})]
        if no_add:
            problems.append(f"{tag}: measures without additivity: {no_add}")
    return problems, prof


def main():
    names = sys.argv[1:]
    if not names:
        print(__doc__)
        sys.exit(1)
    all_problems, feasible, not_feasible = [], [], []
    for n in names:
        probs, prof = check_profile(n)
        all_problems += probs
        if prof:
            feasible += prof["annotations"].get("feasible_analyses", [])
            not_feasible += prof["annotations"].get("not_feasible", [])
    terms = re.findall(r"^### (.+)$", GLOSSARY.read_text(encoding="utf-8"), re.M) if GLOSSARY.exists() else []

    if all_problems:
        print("NOT ELIGIBLE for the fast path. Use the full flow (Profiler first):")
        for p in all_problems:
            print(f"  - {p}")
    else:
        print("ELIGIBLE for the fast path.")
    print("\nGlossary terms available:", ", ".join(terms) or "none")
    print("Feasible analyses:", "; ".join(feasible) or "none recorded")
    print("Not feasible:", "; ".join(not_feasible) or "none recorded")
    print("\nThe question must only need the glossary terms above and a feasible analysis. "
          "If it needs a new definition, a new join or a new file, use the full flow.")
    sys.exit(1 if all_problems else 0)


if __name__ == "__main__":
    main()
