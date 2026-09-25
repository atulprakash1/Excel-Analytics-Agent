"""
domains.py - choose and record domain packs (knowledge/domains/*.md) for input files.

Each pack starts with a header block:
    ---
    id: money_market
    title: Money market
    parent: treasury_common
    applies_when: ...
    signals:
      keywords: [deposit, placement, repo, ...]
      columns: [deal id, value date, maturity date, principal, ...]
      file_patterns: [*mm*, *deposit*, ...]
    ---

Scoring (deterministic, no AI): for each pack, points for its signal columns found in the file's
column names (3 each), keywords found in file/sheet/column names (1 each) or in the data's
category values (0.5 each), and file-name patterns (2 each). The profiler stores the ranking in
each profile as `suggested_domains`. The Profiler agent confirms with the user and records the
choice with `set`. For a recurring source, the recorded packs are also kept on the source in
knowledge/source_registry.json (via a datasource proposal), so later files reuse them.

Usage:
  python tools/domains.py list
  python tools/domains.py show money_market
  python tools/domains.py suggest <profile_name | source_id>
  python tools/domains.py set <profile_name> treasury_common money_market
  python tools/domains.py validate
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ROOT / "knowledge" / "domains"
PROFILES = ROOT / "profiles"
MIN_SCORE = 3.0


# --------------------------------------------------------------------------- parsing

def _parse_value(v: str):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip("'\"").lower() for x in v[1:-1].split(",") if x.strip()]
    return v


def parse_header(text: str) -> dict:
    """Minimal parser for the pack header (key: value, key: [list], one nested level)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    out, parent = {}, None
    for line in m.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        key, _, val = line.strip().partition(":")
        if indent == 0:
            if val.strip():
                out[key] = _parse_value(val)
                parent = None
            else:
                out[key] = {} if key == "signals" else ""
                parent = key if key == "signals" else None
        elif parent:
            out[parent][key] = _parse_value(val)
    return out


def load_packs() -> dict[str, dict]:
    packs = {}
    for p in sorted(DOMAINS.glob("*.md")):
        if p.name.startswith("_") or p.name == "index.md":
            continue
        h = parse_header(p.read_text(encoding="utf-8"))
        if h.get("id"):
            h["file"] = str(p.relative_to(ROOT)).replace("\\", "/")
            packs[h["id"]] = h
    return packs


# --------------------------------------------------------------------------- scoring

def _norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", str(s).lower())
    return re.sub(r"\s+", " ", re.sub(r"[_]+", " ", s)).strip()


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(s).lower()))


def profile_features(profile: dict) -> dict:
    cols, sheets, values = [], [], []
    for s in profile["sheets"]:
        sheets.append(s["name"])
        for c in s["columns"]:
            cols.append(_norm(c["name"]))
            values += [str(v) for v in (c.get("values") or list(c.get("top_values", {}))[:10])]
    return {"file": profile["source"]["file"].lower(), "columns": cols, "sheets": sheets,
            "name_tokens": _tokens(" ".join([profile["source"]["file"], *sheets, *cols])),
            "value_tokens": _tokens(" ".join(values))}


def score_pack(pack: dict, f: dict) -> tuple[float, dict]:
    sig = pack.get("signals", {}) or {}
    colset = set(f["columns"])
    col_hits = sorted({c for c in sig.get("columns", []) if c in colset or any(
        re.search(rf"(^|\W){re.escape(c)}($|\W)", fc) for fc in f["columns"])})
    kw = set(sig.get("keywords", []))
    kw_names = sorted(kw & f["name_tokens"])
    kw_values = sorted((kw & f["value_tokens"]) - set(kw_names))
    file_hits = [p for p in sig.get("file_patterns", []) if fnmatch.fnmatch(f["file"], p)]
    score = 3 * len(col_hits) + len(kw_names) + 0.5 * len(kw_values) + 2 * len(file_hits)
    return score, {"columns": col_hits, "keywords": kw_names, "value_keywords": kw_values, "file_patterns": file_hits}


def suggest(profile: dict, limit: int = 4) -> list[dict]:
    """Ranked packs for a profile. Parents of suggested packs are added (marked as parent)."""
    packs = load_packs()
    f = profile_features(profile)
    ranked = []
    for pid, p in packs.items():
        sc, why = score_pack(p, f)
        ranked.append({"id": pid, "title": p.get("title", pid), "score": round(sc, 1), "matched": why,
                       "parent": p.get("parent") or None})
    ranked.sort(key=lambda r: -r["score"])
    specific = [r for r in ranked if r["parent"] and r["score"] >= MIN_SCORE][:limit]
    out = list(specific)
    for r in specific:
        par = next((x for x in ranked if x["id"] == r["parent"]), None)
        if par and par["id"] not in {o["id"] for o in out}:
            out.append({**par, "as_parent_of": r["id"]})
    return out


# --------------------------------------------------------------------------- recording

def recorded_domains(profile: dict) -> list[str]:
    """Confirmed packs for a profile: its own annotation, else its logical source's packs."""
    own = profile.get("annotations", {}).get("domains") or []
    if own:
        return own
    try:
        sys.path.insert(0, str(ROOT))
        from tools.knowledge import load_sources
        for sid in profile["source"].get("logical_sources", []):
            src = next((s for s in load_sources()["sources"] if s["id"] == sid), None)
            if src and src.get("domains"):
                return src["domains"]
    except Exception:  # noqa: BLE001
        pass
    return []


def _load_profile(name: str) -> tuple[Path, dict]:
    sys.path.insert(0, str(ROOT))
    from tools.knowledge import load_sources
    if name in {s["id"] for s in load_sources()["sources"]}:
        from tools.load_data import source_profile_name
        name = source_profile_name(name)
    p = PROFILES / f"{Path(name).stem}.profile.json"
    if not p.exists():
        sys.exit(f"No profile {p.name}. Run: python tools/profile_excel.py")
    return p, json.loads(p.read_text(encoding="utf-8"))


def validate() -> list[str]:
    issues = []
    packs = load_packs()
    for p in sorted(DOMAINS.glob("*.md")):
        if p.name.startswith("_") or p.name == "index.md":
            continue
        h = parse_header(p.read_text(encoding="utf-8"))
        if not h.get("id"):
            issues.append(f"{p.name}: missing header or id")
            continue
        for k in ("title", "applies_when"):
            if not h.get(k):
                issues.append(f"{p.name}: missing '{k}'")
        sig = h.get("signals") or {}
        for k in ("keywords", "columns", "file_patterns"):
            if not isinstance(sig.get(k), list) or not sig.get(k):
                issues.append(f"{p.name}: signals.{k} should be a non-empty [list]")
        if h.get("parent") and h["parent"] not in packs:
            issues.append(f"{p.name}: parent '{h['parent']}' does not exist")
    return issues


# --------------------------------------------------------------------------- CLI

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    packs = load_packs()
    if cmd == "list":
        for pid, p in packs.items():
            print(f"{pid:28s} {p.get('title', '')}" + (f"  (parent: {p['parent']})" if p.get("parent") else ""))
            print(f"{'':28s} {p.get('applies_when', '')}")
    elif cmd == "show" and len(args) > 1:
        if args[1] not in packs:
            sys.exit(f"Unknown pack {args[1]}. Known: {list(packs)}")
        print((ROOT / packs[args[1]]["file"]).read_text(encoding="utf-8"))
    elif cmd == "suggest" and len(args) > 1:
        _, prof = _load_profile(args[1])
        rec = recorded_domains(prof)
        print(f"{prof['source']['file']}: recorded packs: {rec or 'none yet'}")
        res = suggest(prof)
        if not res:
            print("No pack scores high enough. Ask the user which area this is, or proceed without a pack.")
        for r in res:
            tag = f"  (parent of {r['as_parent_of']})" if r.get("as_parent_of") else ""
            m = r["matched"]
            print(f"  {r['id']:28s} score {r['score']:>5}{tag}")
            if not r.get("as_parent_of"):
                print(f"      columns: {m['columns']}  keywords: {m['keywords']}"
                      + (f"  values: {m['value_keywords']}" if m["value_keywords"] else "")
                      + (f"  file: {m['file_patterns']}" if m["file_patterns"] else ""))
    elif cmd == "set" and len(args) > 2:
        path, prof = _load_profile(args[1])
        chosen = args[2:]
        unknown = [c for c in chosen if c not in packs]
        if unknown:
            sys.exit(f"Unknown pack(s) {unknown}. Known: {list(packs)}")
        prof["annotations"]["domains"] = chosen
        path.write_text(json.dumps(prof, indent=2, default=str), encoding="utf-8")
        print(f"Recorded domains {chosen} on {path.name}")
        srcs = prof["source"].get("logical_sources") or []
        if srcs:
            print(f"This file belongs to source {srcs[0]}. To reuse these packs for future files, propose:\n"
                  f"  payload {{\"id\": \"{srcs[0]}\", \"domains\": {json.dumps(chosen)}}} -> "
                  "python tools/knowledge.py propose --type datasource --action update ...")
    elif cmd == "validate":
        issues = validate()
        print(f"{len(packs)} pack(s) OK" if not issues else "\n".join(f"- {i}" for i in issues))
        sys.exit(1 if issues else 0)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
