"""
knowledge.py - the workspace's long-term memory.

Memory lives in knowledge/ as plain files that people can read and edit:
  column_catalog.json   canonical columns, their aliases, meaning, role, unit, additivity
  source_registry.json  logical data sources: file pattern -> which file is "current"
  glossary.md           business terms and formulas
  decisions.md          answers to past open questions
  lessons.md            mistakes caught in review, turned into rules
  sources.md            what each recurring input file is
  domains/*.md          domain packs (typical columns, traps, questions to ask)
  _proposals.json       queue of changes proposed by agents, waiting for a human
  changelog.md          every approval/rejection, with who and when

The golden rule: AGENTS PROPOSE, HUMANS APPROVE.
Agents add items to _proposals.json (directly, or with `propose-from-profile`).
Only `approve` (run after a person says yes) writes to the memory files.
Agents rely only on catalog entries with status "confirmed".

CLI:
  python tools/knowledge.py status
  python tools/knowledge.py lookup "Closing Bal"
  python tools/knowledge.py propose-from-profile bank_balances_2026_09
  python tools/knowledge.py propose-alias closing_balance "Closing Bal" --seen-in "bank_balances_2026_10.xlsx:Balances" --why "..."
  python tools/knowledge.py propose --type glossary --payload-file work/p.json --why "..."
  python tools/knowledge.py propose --payload-file work/batch.json   # a JSON list, one call for many:
      [{"type": "decision", "payload": {...}, "why": "..."}, {"type": "lesson", "payload": {...}, "why": "..."}]
      (--type / --why act as defaults for items that omit them; items are validated before any is added)
  python tools/knowledge.py pending
  python tools/knowledge.py approve p-0003 p-0004 --by "Jane Smith"
  python tools/knowledge.py approve all --by "Jane Smith"
  python tools/knowledge.py reject p-0005 --by "Jane Smith" --reason "Amount is gross here"
  python tools/knowledge.py deprecate closing_balance --by "Jane Smith" --reason "..."
  python tools/knowledge.py lint [--stale-days 180]
  python tools/knowledge.py sources                  # logical sources and the file each resolves to
  python tools/knowledge.py propose --type datasource --payload-file work/p.json --why "..."
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "knowledge"
CATALOG = KB / "column_catalog.json"
SOURCES = KB / "source_registry.json"
RAW_DIR = ROOT / "data" / "raw"
SELECT_RULES = {"last_by_name", "newest_modified"}
PROPOSALS = KB / "_proposals.json"
CHANGELOG = KB / "changelog.md"
MD_TARGETS = {"glossary": "glossary.md", "decision": "decisions.md", "lesson": "lessons.md", "source": "sources.md"}
PROPOSAL_TYPES = ["column", "datasource", *MD_TARGETS]
ROLES = {"dimension", "measure", "date", "identifier", "attribute", "unused"}
ADDITIVITY = {"additive", "semi_additive", "non_additive", None}
REQUIRED_COLUMN_FIELDS = ("id", "label", "aliases", "meaning", "role")


# --------------------------------------------------------------------------- io

def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_catalog() -> dict:
    return _read(CATALOG, {"schema_version": "1.0", "entries": []})


def load_proposals() -> dict:
    return _read(PROPOSALS, {"proposals": []})


def norm(name: str) -> str:
    """'Closing Bal (EUR)' -> 'closingbal' ; used for alias matching."""
    s = re.sub(r"\(.*?\)", "", str(name)).casefold()
    return re.sub(r"[^a-z0-9]", "", s)


def _log(action: str, by: str, detail: str):
    CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
    if not CHANGELOG.exists():
        CHANGELOG.write_text("# Knowledge changelog\n\n| When | Action | By | Detail |\n|---|---|---|---|\n",
                             encoding="utf-8")
    with open(CHANGELOG, "a", encoding="utf-8") as f:
        f.write(f"| {datetime.now():%Y-%m-%d %H:%M} | {action} | {by} | {detail.replace('|', '/')} |\n")


# --------------------------------------------------------------------------- logical sources

def load_sources() -> dict:
    return _read(SOURCES, {"schema_version": "1.0", "sources": []})


def _pattern_regex(pattern: str) -> re.Pattern:
    """Glob-style file pattern ('bank_balances_*.xlsx') -> case-insensitive regex."""
    return re.compile("^" + re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".") + "$", re.I)


def match_source(filename: str) -> list[str]:
    """Ids of confirmed logical sources whose file pattern matches this file name."""
    return [s["id"] for s in load_sources()["sources"]
            if s.get("status", "confirmed") == "confirmed" and _pattern_regex(s["pattern"]).match(filename)]


def source_files(source_id: str) -> list[Path]:
    """All files in data/raw for a source, ordered oldest -> newest by its select rule."""
    src = next((s for s in load_sources()["sources"] if s["id"] == source_id), None)
    if src is None:
        raise KeyError(f"Unknown source '{source_id}'. Known: {[s['id'] for s in load_sources()['sources']]}")
    rx = _pattern_regex(src["pattern"])
    files = [p for p in RAW_DIR.iterdir() if p.is_file() and rx.match(p.name) and not p.name.startswith("~$")]
    if src.get("select", "last_by_name") == "newest_modified":
        return sorted(files, key=lambda p: p.stat().st_mtime)
    return sorted(files, key=lambda p: p.name.lower())


def resolve_source(source_id: str) -> Path:
    """The file that currently represents a logical source (newest by its select rule)."""
    files = source_files(source_id)
    if not files:
        src = next(s for s in load_sources()["sources"] if s["id"] == source_id)
        raise FileNotFoundError(f"No file in data/raw matches source '{source_id}' ({src['pattern']})")
    return files[-1]


# --------------------------------------------------------------------------- matching

def match_column(name: str, source_file: str | None = None, include_proposed: bool = False) -> dict:
    """Return {"match": "confirmed"|"ambiguous"|"proposed"|"none", "entries": [...]}.
    An alias scoped to specific files (scope_files) only matches those files."""
    n = norm(name)
    hits = []
    for e in load_catalog()["entries"]:
        if e.get("status") == "deprecated":
            continue
        scope = e.get("scope_files") or []
        if scope and source_file and source_file not in scope:
            continue
        if n in {norm(a) for a in e.get("aliases", [])} | {norm(e["id"]), norm(e.get("label", ""))}:
            hits.append(e)
    confirmed = [e for e in hits if e.get("status") == "confirmed"]
    # prefer file-scoped entries over global ones
    scoped = [e for e in confirmed if e.get("scope_files")]
    if scoped:
        confirmed = scoped
    if len(confirmed) == 1:
        return {"match": "confirmed", "entries": confirmed}
    if len(confirmed) > 1:
        return {"match": "ambiguous", "entries": confirmed}
    if include_proposed and hits:
        return {"match": "proposed", "entries": hits}
    return {"match": "none", "entries": []}


def apply_catalog(profile: dict) -> dict:
    """Tag every profiled column with its catalog match and pre-fill empty annotations
    from CONFIRMED entries. Returns a small summary. Called by profile_excel.py."""
    src = profile["source"]["file"]
    summary = {"recognised": 0, "ambiguous": 0, "unknown": 0}
    for s in profile["sheets"]:
        ann = profile["annotations"]["sheets"].setdefault(s["name"], {})
        roles = ann.setdefault("column_roles", {})
        meanings = ann.setdefault("column_meanings", {})
        additivity = ann.setdefault("column_additivity", {})
        prefilled = ann.setdefault("prefilled_from_catalog", {})
        unknown = []
        if ann.get("include") is False:
            s["unknown_columns"] = []
            continue
        periods = set(s.get("wide_format", {}).get("period_columns", []))
        for c in s["columns"]:
            if c["name"] in periods:
                c["catalog"] = {"match": "period_column"}
                continue
            m = match_column(c["name"], src)
            if m["match"] == "confirmed":
                e = m["entries"][0]
                c["catalog"] = {"match": "confirmed", "id": e["id"], "label": e.get("label")}
                if c["name"] not in roles:
                    roles[c["name"]] = e["role"]
                if c["name"] not in meanings:
                    unit = f" [{e['unit']}]" if e.get("unit") else ""
                    meanings[c["name"]] = f"{e['meaning']}{unit}"
                if e.get("role") == "measure" and c["name"] not in additivity and e.get("additivity"):
                    additivity[c["name"]] = e["additivity"] + (
                        f" over {e['semi_additive_over']}" if e.get("semi_additive_over") else "")
                prefilled[c["name"]] = e["id"]
                if e.get("type") and e["type"] != c["inferred_type"] and c["inferred_type"] != "empty":
                    c["catalog"]["warning"] = (f"catalog says {e['type']}, profiler found "
                                               f"{c['inferred_type']}")
                summary["recognised"] += 1
            elif m["match"] == "ambiguous":
                c["catalog"] = {"match": "ambiguous", "candidates": [e["id"] for e in m["entries"]]}
                unknown.append(c["name"])
                summary["ambiguous"] += 1
            else:
                c["catalog"] = {"match": "none"}
                unknown.append(c["name"])
                summary["unknown"] += 1
        s["unknown_columns"] = unknown
    profile["knowledge"] = {**summary, "catalog_entries": len(load_catalog()["entries"]),
                            "applied_at": datetime.now().isoformat(timespec="seconds")}
    return summary


# --------------------------------------------------------------------------- proposals

def _next_id(data: dict) -> str:
    nums = [int(p["id"].split("-")[1]) for p in data["proposals"] if re.match(r"p-\d+$", p.get("id", ""))]
    return f"p-{max(nums + [data.get('last_id', 0)]) + 1:04d}"


def add_proposal(ptype: str, payload: dict, rationale: str, evidence: str = "",
                 action: str = "add", proposed_by: str = "agent") -> str:
    data = load_proposals()
    pid = _next_id(data)
    data["proposals"].append({"id": pid, "type": ptype, "action": action, "payload": payload,
                              "rationale": rationale, "evidence": evidence,
                              "proposed_by": proposed_by, "proposed_on": date.today().isoformat(),
                              "state": "pending"})
    _write(PROPOSALS, data)
    return pid


def _pending_twin(name: str) -> dict | None:
    for p in load_proposals()["proposals"]:
        if p["state"] == "pending" and p["type"] == "column" and p["action"] == "add" and \
                norm(name) in {norm(a) for a in p["payload"].get("aliases", [])}:
            return p
    return None


def _save_twin(twin: dict):
    data = load_proposals()
    data["proposals"] = [twin if p["id"] == twin["id"] else p for p in data["proposals"]]
    _write(PROPOSALS, data)


def propose_from_profile(profile_name: str) -> list[str]:
    """Turn a CONFIRMED profile's annotations into catalog proposals:
    new entries for unknown columns, alias/seen_in updates for recognised ones."""
    from tools.load_data import load_profile  # local import keeps this module light
    prof = load_profile(profile_name)
    if prof["annotations"]["status"] != "confirmed":
        raise SystemExit(f"Profile {profile_name} is '{prof['annotations']['status']}'. Confirm it first.")
    src = prof["source"]["file"]
    by = prof["annotations"].get("confirmed_by") or "unknown"
    catalog = {e["id"]: e for e in load_catalog()["entries"]}
    pending = {json.dumps(p["payload"], sort_keys=True) for p in load_proposals()["proposals"]
               if p["state"] == "pending"}
    created = []
    for s in prof["sheets"]:
        ann = prof["annotations"]["sheets"].get(s["name"], {})
        if not ann.get("include", True):
            continue
        raw = {c["name"]: c for c in s["columns"]}
        derived = [n for n in ann.get("column_roles", {}) if n not in raw]  # created by cleaning, e.g. unpivot
        for name in list(raw) + derived:
            c = raw.get(name, {"name": name, "inferred_type": None, "sample_values": []})
            where = f"{src}:{s['name']}" + ("" if name in raw else " (after cleaning)")
            role = ann.get("column_roles", {}).get(name)
            meaning = ann.get("column_meanings", {}).get(name)
            m = match_column(name, src)
            if m["match"] == "confirmed":
                e = m["entries"][0]
                if where not in e.get("seen_in", []):
                    payload = {"id": e["id"], "seen_in": [where]}
                    if norm(name) not in {norm(a) for a in e["aliases"]}:
                        payload["aliases"] = [name]
                    if json.dumps(payload, sort_keys=True) not in pending:
                        created.append(add_proposal("column", payload, f"'{name}' seen again in {where}",
                                                    action="update", proposed_by="propose-from-profile"))
                continue
            if not role or not meaning or role == "unused":
                continue
            twin = _pending_twin(name)
            if twin:  # same column already proposed in this batch: add where it was seen
                if where not in twin["payload"]["seen_in"]:
                    twin["payload"]["seen_in"].append(where)
                    if meaning != twin["payload"]["meaning"]:
                        twin["evidence"] += f" | other description in {where}: {meaning}"
                    _save_twin(twin)
                continue
            cid = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
            if cid in catalog:
                cid = f"{cid}_{re.sub(r'[^a-z0-9]+', '_', Path(src).stem.casefold())}"
            payload = {"id": cid, "label": name, "aliases": [name], "meaning": meaning, "role": role,
                       "type": c["inferred_type"], "unit": None,
                       "additivity": ("additive" if role == "measure" else None),
                       "scope_files": [], "seen_in": [where], "source": by, "notes": ""}
            add = ann.get("column_additivity", {}).get(name)
            if add:
                payload["additivity"] = add.split(" ")[0]
                if " over " in add:
                    payload["semi_additive_over"] = add.split(" over ")[1]
            if json.dumps(payload, sort_keys=True) not in pending:
                created.append(add_proposal("column", payload, f"Confirmed in profile of {where}",
                                            evidence=f"examples: {c.get('sample_values', [])[:3]}",
                                            proposed_by="propose-from-profile"))
    return created


# --------------------------------------------------------------------------- approval

def _apply_column(p: dict, by: str):
    cat = load_catalog()
    entries = {e["id"]: e for e in cat["entries"]}
    pl = p["payload"]
    today = date.today().isoformat()
    if p["action"] == "add" and pl["id"] not in entries:
        missing = [f for f in REQUIRED_COLUMN_FIELDS if not pl.get(f)]
        if missing:
            raise ValueError(f"{p['id']}: missing fields {missing}")
        if pl["role"] not in ROLES or pl.get("additivity") not in ADDITIVITY:
            raise ValueError(f"{p['id']}: invalid role or additivity")
        entry = {**pl, "status": "confirmed", "confirmed_by": by, "confirmed_on": today}
        cat["entries"].append(entry)
    else:
        e = entries.get(pl["id"])
        if not e:
            raise ValueError(f"{p['id']}: catalog entry '{pl['id']}' not found")
        for k, v in pl.items():
            if k == "id":
                continue
            if isinstance(v, list) and isinstance(e.get(k), list):
                e[k] = e[k] + [x for x in v if x not in e[k]]
            else:
                e[k] = v
        e["confirmed_by"], e["confirmed_on"], e["status"] = by, today, "confirmed"
    cat["updated"] = today
    cat["entries"].sort(key=lambda e: e["id"])
    _write(CATALOG, cat)


def _md_block(ptype: str, pl: dict, by: str) -> str:
    today = date.today().isoformat()
    if ptype == "glossary":
        lines = [f"### {pl['term']}", f"- **Definition:** {pl['definition']}"]
        if pl.get("formula"):
            lines.append(f"- **Formula:** `{pl['formula']}`")
        if pl.get("related_columns"):
            lines.append(f"- **Columns:** {', '.join(pl['related_columns'])}")
    elif ptype == "decision":
        lines = [f"### {today} - {pl['title']}", f"- **Decision:** {pl['decision']}",
                 f"- **Applies to:** {pl.get('applies_to', 'all')}"]
    elif ptype == "lesson":
        lines = [f"### {pl['title']}", f"- **What happened:** {pl['what_happened']}",
                 f"- **Rule:** {pl['rule']}", f"- **Applies to:** {pl.get('applies_to', 'all')}"]
    elif ptype == "source":
        lines = [f"### {pl['file']}", f"- **What it is:** {pl['description']}",
                 f"- **Owner:** {pl.get('owner', 'unknown')}", f"- **Frequency:** {pl.get('frequency', 'unknown')}",
                 f"- **Known quirks:** {pl.get('quirks', 'none recorded')}",
                 f"- **Used by reports:** {', '.join(pl.get('used_by', [])) or 'none yet'}"]
    else:
        raise ValueError(f"Unknown proposal type {ptype}")
    lines.append(f"- **Confirmed:** {by}, {today}")
    return "\n".join(lines) + "\n\n"


def _apply_datasource(p: dict, by: str):
    reg = load_sources()
    pl = p["payload"]
    existing = next((s for s in reg["sources"] if s["id"] == pl["id"]), None)
    if p["action"] == "add" and existing is None:
        missing = [f for f in ("id", "pattern", "description") if not pl.get(f)]
        if missing:
            raise ValueError(f"{p['id']}: missing fields {missing}")
        if pl.get("select", "last_by_name") not in SELECT_RULES:
            raise ValueError(f"{p['id']}: select must be one of {sorted(SELECT_RULES)}")
        reg["sources"].append({"select": "last_by_name", **pl, "status": "confirmed",
                               "confirmed_by": by, "confirmed_on": date.today().isoformat()})
    else:
        if existing is None:
            raise ValueError(f"{p['id']}: source '{pl['id']}' not found")
        existing.update({k: v for k, v in pl.items() if k != "id"})
        existing.update(confirmed_by=by, confirmed_on=date.today().isoformat(), status="confirmed")
    reg["sources"].sort(key=lambda s: s["id"])
    _write(SOURCES, reg)


def approve(ids: list[str], by: str) -> list[str]:
    data = load_proposals()
    todo = [p for p in data["proposals"] if p["state"] == "pending" and ("all" in ids or p["id"] in ids)]
    done = []
    for p in todo:
        if p["type"] == "column":
            _apply_column(p, by)
        elif p["type"] == "datasource":
            _apply_datasource(p, by)
        else:
            target = KB / MD_TARGETS[p["type"]]
            with open(target, "a", encoding="utf-8") as f:
                f.write(_md_block(p["type"], p["payload"], by))
        p["state"], p["decided_by"], p["decided_on"] = "approved", by, date.today().isoformat()
        _log("approve", by, f"{p['id']} {p['type']} {p['action']}: "
             f"{p['payload'].get('id') or p['payload'].get('term') or p['payload'].get('title') or p['payload'].get('file')}")
        done.append(p["id"])
    _archive(data)
    return done


def reject(ids: list[str], by: str, reason: str) -> list[str]:
    data = load_proposals()
    done = []
    for p in data["proposals"]:
        if p["state"] == "pending" and p["id"] in ids:
            p["state"], p["decided_by"], p["reason"] = "rejected", by, reason
            p["decided_on"] = date.today().isoformat()
            _log("reject", by, f"{p['id']} {p['type']}: {reason}")
            done.append(p["id"])
    _archive(data)
    return done


def _archive(data: dict):
    """Keep only pending proposals in the queue; decided ones go to _proposals_archive.json."""
    arch_path = KB / "_proposals_archive.json"
    arch = _read(arch_path, {"proposals": []})
    arch["proposals"] += [p for p in data["proposals"] if p["state"] != "pending"]
    _write(arch_path, arch)
    # keep id sequence monotonic by remembering the highest id
    last = max([int(p["id"].split("-")[1]) for p in arch["proposals"] + data["proposals"]] + [0])
    _write(PROPOSALS, {"last_id": last, "proposals": [p for p in data["proposals"] if p["state"] == "pending"]})


def deprecate(entry_id: str, by: str, reason: str):
    cat = load_catalog()
    for e in cat["entries"]:
        if e["id"] == entry_id:
            e["status"], e["notes"] = "deprecated", f"{e.get('notes', '')} Deprecated: {reason}".strip()
            _write(CATALOG, cat)
            _log("deprecate", by, f"{entry_id}: {reason}")
            return
    raise SystemExit(f"No catalog entry '{entry_id}'")


# --------------------------------------------------------------------------- lint

def lint(stale_days: int = 180) -> list[str]:
    issues = []
    entries = load_catalog()["entries"]
    alias_owner: dict[tuple, str] = {}
    for e in entries:
        if e.get("status") != "confirmed":
            continue
        for f in REQUIRED_COLUMN_FIELDS:
            if not e.get(f):
                issues.append(f"{e.get('id')}: missing '{f}'")
        if e.get("role") == "measure" and not e.get("additivity"):
            issues.append(f"{e['id']}: measure without additivity")
        if e.get("additivity") == "semi_additive" and not e.get("semi_additive_over"):
            issues.append(f"{e['id']}: semi_additive but 'semi_additive_over' not set")
        for a in e.get("aliases", []):
            for scope in (e.get("scope_files") or ["*"]):
                key = (norm(a), scope)
                if key in alias_owner and alias_owner[key] != e["id"]:
                    issues.append(f"alias '{a}' ({scope}) maps to both {alias_owner[key]} and {e['id']} - "
                                  "scope one of them with scope_files")
                alias_owner[key] = e["id"]
        try:
            age = (date.today() - date.fromisoformat(e.get("confirmed_on", "1900-01-01"))).days
            if age > stale_days:
                issues.append(f"{e['id']}: last confirmed {age} days ago - review")
        except ValueError:
            issues.append(f"{e['id']}: bad confirmed_on date")
    owners: dict[str, list[str]] = {}
    for s in load_sources()["sources"]:
        if s.get("status", "confirmed") != "confirmed":
            continue
        try:
            files = source_files(s["id"])
        except KeyError:
            files = []
        if not files:
            issues.append(f"source {s['id']}: no file in data/raw matches '{s['pattern']}'")
        for f in files:
            owners.setdefault(f.name, []).append(s["id"])
    for fname, ids in owners.items():
        if len(ids) > 1:
            issues.append(f"file {fname} matches several sources {ids} - make the patterns more specific")
    pend = load_proposals()["proposals"]
    if pend:
        issues.append(f"{len(pend)} proposal(s) waiting for approval")
    return issues


# --------------------------------------------------------------------------- CLI

def _print_pending():
    props = load_proposals()["proposals"]
    if not props:
        print("No pending proposals.")
        return
    for p in props:
        pl = p["payload"]
        head = pl.get("id") or pl.get("term") or pl.get("title") or pl.get("file")
        print(f"\n{p['id']}  [{p['type']} {p['action']}]  {head}")
        print(f"   why: {p['rationale']}")
        for k, v in pl.items():
            if k not in ("id",) and v not in (None, "", [], {}):
                print(f"   {k}: {v}")
        if p.get("evidence"):
            print(f"   evidence: {p['evidence']}")


def main():
    sys.path.insert(0, str(ROOT))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    lk = sub.add_parser("lookup"); lk.add_argument("name"); lk.add_argument("--file")  # noqa: E702
    pf = sub.add_parser("propose-from-profile"); pf.add_argument("profile")  # noqa: E702
    sub.add_parser("pending")
    pa = sub.add_parser("propose-alias"); pa.add_argument("entry"); pa.add_argument("alias")  # noqa: E702
    pa.add_argument("--seen-in", default=""); pa.add_argument("--why", required=True)  # noqa: E702
    sub.add_parser("sources")
    pr = sub.add_parser("propose"); pr.add_argument("--type", choices=PROPOSAL_TYPES)  # noqa: E702
    pr.add_argument("--payload-file", required=True); pr.add_argument("--why")  # noqa: E702
    pr.add_argument("--action", default="add", choices=["add", "update"])
    apv = sub.add_parser("approve"); apv.add_argument("ids", nargs="+"); apv.add_argument("--by", required=True)  # noqa: E702,E501
    rj = sub.add_parser("reject"); rj.add_argument("ids", nargs="+")  # noqa: E702
    rj.add_argument("--by", required=True); rj.add_argument("--reason", required=True)  # noqa: E702
    dp = sub.add_parser("deprecate"); dp.add_argument("entry")  # noqa: E702
    dp.add_argument("--by", required=True); dp.add_argument("--reason", required=True)  # noqa: E702
    ln = sub.add_parser("lint"); ln.add_argument("--stale-days", type=int, default=180)  # noqa: E702
    a = ap.parse_args()

    if a.cmd == "status":
        entries = load_catalog()["entries"]
        by_status = {}
        for e in entries:
            by_status[e.get("status")] = by_status.get(e.get("status"), 0) + 1
        print(f"Catalog: {len(entries)} entries {by_status}")
        for t, fname in MD_TARGETS.items():
            p = KB / fname
            n = p.read_text(encoding="utf-8").count("\n### ") if p.exists() else 0
            print(f"{fname}: {n} entries")
        print(f"Logical sources: {len(load_sources()['sources'])}")
        print(f"Pending proposals: {len(load_proposals()['proposals'])}")
    elif a.cmd == "lookup":
        m = match_column(a.name, a.file, include_proposed=True)
        print(f"{a.name!r}: {m['match']}")
        for e in m["entries"]:
            print(json.dumps(e, indent=2, ensure_ascii=False))
    elif a.cmd == "propose-from-profile":
        ids = propose_from_profile(a.profile)
        print(f"Created {len(ids)} proposal(s): {', '.join(ids) or '-'}")
        _print_pending()
    elif a.cmd == "pending":
        _print_pending()
    elif a.cmd == "propose-alias":
        if not any(e["id"] == a.entry for e in load_catalog()["entries"]):
            raise SystemExit(f"No catalog entry '{a.entry}'. Use 'propose --type column' for a new column.")
        payload = {"id": a.entry, "aliases": [a.alias]}
        if a.seen_in:
            payload["seen_in"] = [a.seen_in]
        print(add_proposal("column", payload, a.why, action="update", proposed_by="agent"))
    elif a.cmd == "propose":
        payload = json.loads(Path(a.payload_file).read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else [{"payload": payload}]
        jobs = []
        for n, item in enumerate(items, 1):
            t, why = item.get("type", a.type), item.get("why", a.why)
            if t not in PROPOSAL_TYPES:
                raise SystemExit(f"Item {n}: type must be one of {PROPOSAL_TYPES} (got {t!r})")
            if not why:
                raise SystemExit(f"Item {n}: 'why' is required (in the item or via --why)")
            if "payload" not in item:
                raise SystemExit(f"Item {n}: missing 'payload'")
            jobs.append((t, item["payload"], why, item.get("action", a.action)))
        for t, p, why, action in jobs:
            print(add_proposal(t, p, why, action=action, proposed_by="agent"))
    elif a.cmd == "approve":
        print(f"Approved: {approve(a.ids, a.by) or 'nothing'}")
    elif a.cmd == "reject":
        print(f"Rejected: {reject(a.ids, a.by, a.reason) or 'nothing'}")
    elif a.cmd == "deprecate":
        deprecate(a.entry, a.by, a.reason)
        print(f"Deprecated {a.entry}")
    elif a.cmd == "sources":
        for s in load_sources()["sources"]:
            try:
                files = source_files(s["id"])
                cur = files[-1].name if files else "NO MATCHING FILE"
            except KeyError:
                files, cur = [], "?"
            print(f"{s['id']}: pattern '{s['pattern']}' ({s.get('select', 'last_by_name')}) -> current: {cur}"
                  f"{f'  [{len(files)} files]' if len(files) > 1 else ''}")
    elif a.cmd == "lint":
        issues = lint(a.stale_days)
        print("Knowledge base OK" if not issues else "\n".join(f"- {i}" for i in issues))


if __name__ == "__main__":
    main()
