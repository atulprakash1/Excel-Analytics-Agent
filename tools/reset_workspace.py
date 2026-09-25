"""
reset_workspace.py - return the workspace to a clean slate (archive first).

Keeps:   .github/ (agents, skills, instructions), tools/, .vscode/, samples/, README,
         knowledge/domains/ (the starter domain packs) and knowledge/index.md
Clears:  data/raw/ (unless --keep-data), profiles/, analysis/, reports/, work/,
         and the learned knowledge: column catalog, source registry, glossary, decisions,
         lessons, source notes, proposals, proposal archive and changelog.

Before clearing, everything that will be removed is zipped to _archive/workspace_<timestamp>.zip,
so a previous test can always be restored (unzip it over the workspace).

Usage:
  python tools/reset_workspace.py --dry-run          # show what would be archived and cleared
  python tools/reset_workspace.py --yes              # archive, then reset
  python tools/reset_workspace.py --yes --keep-data  # keep the files in data/raw
Agents must never run this; it is for people starting a new test.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "knowledge"

MD_HEADERS = {
    "glossary.md": "# Glossary\n\nBusiness terms and how they are calculated, confirmed with the business.\n"
                   "The Analyst uses these definitions in `plan.md` and cites them by term. Domain packs\n"
                   "hold starter definitions; once a stakeholder confirms one, it is proposed here.\n"
                   "Entries are added only by `python tools/knowledge.py approve`.\n\n",
    "decisions.md": "# Decisions\n\nAnswers to questions raised during profiling or review, so they are not asked again.\n"
                    "Newest at the bottom. If a decision is reversed, add a new decision that says so.\n\n",
    "lessons.md": "# Lessons learned\n\nMistakes or near-misses caught in review, turned into rules every agent follows.\n"
                  "Lessons that apply to a whole Treasury area can later move into its domain pack.\n\n",
    "sources.md": "# Source notes\n\nFor people: what each recurring input is, who owns it, how often it arrives and its quirks.\n"
                  "The machine-readable list of sources is `source_registry.json`.\n\n",
}
EMPTY_JSON = {
    "column_catalog.json": {"schema_version": "1.0", "entries": []},
    "source_registry.json": {"schema_version": "1.0", "sources": []},
}
REMOVE_KB = ["_proposals.json", "_proposals_archive.json", "changelog.md"]


def targets(keep_data: bool) -> list[Path]:
    t = []
    dirs = ["profiles", "analysis", "reports", "work"] + ([] if keep_data else ["data/raw"])
    for d in dirs:
        p = ROOT / d
        if p.exists():
            t += [c for c in p.iterdir() if not (d == "work" and c.name == "README.txt")]
    t += [KB / f for f in list(MD_HEADERS) + list(EMPTY_JSON) + REMOVE_KB if (KB / f).exists()]
    return t


def archive(paths: list[Path]) -> Path:
    arc_dir = ROOT / "_archive"
    arc_dir.mkdir(exist_ok=True)
    arc = arc_dir / f"workspace_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(arc, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
            for f in files:
                if "__pycache__" not in f.parts:
                    z.write(f, f.relative_to(ROOT))
    return arc


def reset(keep_data: bool):
    for d in ["profiles", "analysis", "reports", "work"] + ([] if keep_data else ["data/raw"]):
        p = ROOT / d
        p.mkdir(parents=True, exist_ok=True)
        for c in p.iterdir():
            if d == "work" and c.name == "README.txt":
                continue
            shutil.rmtree(c) if c.is_dir() else c.unlink()
    for f, text in MD_HEADERS.items():
        (KB / f).write_text(text, encoding="utf-8")
    for f, data in EMPTY_JSON.items():
        (KB / f).write_text(json.dumps(data, indent=2), encoding="utf-8")
    for f in REMOVE_KB:
        (KB / f).unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="confirm the reset")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-data", action="store_true", help="keep files in data/raw")
    ap.add_argument("--no-archive", action="store_true", help="skip the safety archive")
    a = ap.parse_args()
    t = targets(a.keep_data)
    print(f"{len(t)} item(s) will be archived and cleared:")
    for p in t:
        print(f"  {p.relative_to(ROOT)}{'/' if p.is_dir() else ''}")
    print("Kept: .github/, tools/, .vscode/, samples/, knowledge/domains/, knowledge/index.md")
    if a.dry_run:
        return
    if not a.yes:
        sys.exit("\nNothing changed. Re-run with --yes to reset (or --dry-run to preview).")
    if t and not a.no_archive:
        print(f"\nArchived to {archive(t).relative_to(ROOT)}")
    reset(a.keep_data)
    print("Workspace reset. Next: put files in data/raw and run python tools/profile_excel.py")


if __name__ == "__main__":
    main()
