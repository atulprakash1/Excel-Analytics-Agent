"""
load_data.py - load a sheet exactly as its profile describes, then apply cleaning rules.

Analysis scripts must load data ONLY through this module, so every report uses the same
header row, the same cleaning and the same audit trail.

Prefer LOGICAL SOURCES for recurring files, so a report always reads the current file:

    from tools.load_data import load_source
    df, log = load_source("<source_id>", "<sheet>")      # e.g. the newest bank_balances_*.xlsx

Use a fixed profile only for one-off files:

    from tools.load_data import load_sheet
    df, log = load_sheet("<profile_name>", "<sheet>")    # profile name = file name without extension
    # log is a list of human-readable steps, e.g. "drop_rows_matching Entity: -5 rows"

Rules come from profile["annotations"]["sheets"][sheet]["cleaning_rules"] (confirmed by
the Profiler agent + a human). If that list is empty, the loader falls back to the
profile's "suggested_cleaning_rules" but SKIPS any rule marked needs_confirmation and
records a warning in the log.

Supported rule ops:
  drop_blank_rows
  drop_rows_matching   {column, pattern}
  drop_columns         {columns}
  strip_whitespace     {columns}
  map_values           {column, map}
  canonical_values     {column, values}  match case/space variants to the listed spellings
                        ("eur ", "Eur" -> "EUR"); values not in the list are kept and warned
  to_numeric           {columns}
  to_datetime          {columns, dayfirst}
  drop_duplicates      {subset (optional)}
  rename               {map}
  unpivot              {id_columns, value_columns (list, or "periods" = every period or tenor-bucket column),
                        var_name, value_name}
  filter               {column, op: eq|ne|in|not_in|gt|lt, value}

CLI preview:
  python tools/load_data.py bank_balances Balances      # source id or profile name
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "profiles"


def load_profile(name: str) -> dict:
    p = PROFILE_DIR / (name if name.endswith(".profile.json") else f"{Path(name).stem}.profile.json")
    if not p.exists():
        raise FileNotFoundError(f"No profile at {p}. Run: python tools/profile_excel.py")
    return json.loads(p.read_text(encoding="utf-8"))


def _num(v):
    if isinstance(v, str):
        t = v.strip().replace(",", "").replace("£", "").replace("$", "").replace("€", "")
        if t.startswith("(") and t.endswith(")"):
            t = "-" + t[1:-1]
        return t
    return v


def apply_rule(df: pd.DataFrame, rule: dict, log: list[str]) -> pd.DataFrame:
    op, before = rule["op"], len(df)
    if op == "drop_blank_rows":
        df = df.dropna(how="all")
    elif op == "drop_rows_matching":
        pat = re.compile(rule["pattern"])
        mask = df[rule["column"]].map(lambda v: isinstance(v, str) and bool(pat.search(v)))
        df = df[~mask]
    elif op == "drop_columns":
        df = df.drop(columns=[c for c in rule["columns"] if c in df.columns])
    elif op == "strip_whitespace":
        for c in rule["columns"]:
            df[c] = df[c].map(lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v)
    elif op == "canonical_values":
        key = lambda v: re.sub(r"\s+", " ", v).strip().casefold()  # noqa: E731
        canon = {key(v): v for v in rule["values"]}
        col = rule["column"]
        df[col] = df[col].map(lambda v: canon.get(key(v), v.strip()) if isinstance(v, str) else v)
        unknown = sorted({v for v in df[col].dropna().unique() if isinstance(v, str) and key(v) not in canon})
        if unknown:
            log.append(f"  WARNING canonical_values {col}: values not in the confirmed list: {unknown}")
    elif op == "map_values":
        df[rule["column"]] = df[rule["column"]].replace(rule["map"])
    elif op == "to_numeric":
        for c in rule["columns"]:
            converted = pd.to_numeric(df[c].map(_num), errors="coerce")
            failed = int((converted.isna() & df[c].notna()).sum())
            if failed:
                log.append(f"  WARNING to_numeric {c}: {failed} value(s) could not be converted -> NaN")
            df[c] = converted
    elif op == "to_datetime":
        for c in rule["columns"]:
            converted = pd.to_datetime(df[c], errors="coerce", dayfirst=rule.get("dayfirst", True))
            failed = int((converted.isna() & df[c].notna()).sum())
            if failed:
                log.append(f"  WARNING to_datetime {c}: {failed} value(s) could not be parsed -> NaT")
            df[c] = converted
    elif op == "drop_duplicates":
        df = df.drop_duplicates(subset=rule.get("subset"))
    elif op == "rename":
        df = df.rename(columns=rule["map"])
    elif op == "unpivot":
        vc = rule["value_columns"]
        if vc == "periods":
            from tools.profile_excel import is_period_column  # local import: avoids loading it for every script
            vc = [c for c in df.columns if c not in rule["id_columns"] and is_period_column(c)]
        df = df.melt(id_vars=rule["id_columns"], value_vars=vc,
                     var_name=rule.get("var_name", "Period"), value_name=rule.get("value_name", "Value"))
    elif op == "filter":
        s, v = df[rule["column"]], rule["value"]
        masks = {"eq": lambda: s == v, "ne": lambda: s != v, "gt": lambda: s > v, "lt": lambda: s < v,
                 "in": lambda: s.isin(v), "not_in": lambda: ~s.isin(v)}
        df = df[masks[rule.get("op", "eq")]()]
    else:
        raise ValueError(f"Unknown cleaning op: {op}")
    delta = len(df) - before
    target = rule.get("column") or ",".join(rule.get("columns", [])) or ""
    log.append(f"{op} {target}".strip() + (f": {delta:+d} rows" if delta else ""))
    return df


def describe_logs(logs) -> list[str]:
    """Human labels of the files actually read, from loader logs: ['bank_balances_2026_09.xlsx (Balances)']."""
    items = logs.values() if isinstance(logs, dict) else logs
    out = []
    for log in items:
        for line in log:
            if line.startswith("Loaded "):
                f, sheet = line[len("Loaded "):].split(" (header")[0].split(" / ", 1)
                out.append(f"{f} ({sheet})")
    return list(dict.fromkeys(out))


def source_profile_name(source_id: str) -> str:
    """Profile name (file stem) of the file that currently represents a logical source."""
    from tools.knowledge import resolve_source
    return resolve_source(source_id).stem


def load_source_profile(source_id: str) -> dict:
    return load_profile(source_profile_name(source_id))


def load_source(source_id: str, sheet: str, apply_rules: bool = True) -> tuple[pd.DataFrame, list[str]]:
    """Load a sheet from the CURRENT file of a logical source (see knowledge/source_registry.json)."""
    name = source_profile_name(source_id)
    if not (PROFILE_DIR / f"{name}.profile.json").exists():
        raise FileNotFoundError(f"Source '{source_id}' resolves to {name}, which has no profile yet. "
                                "Run: python tools/profile_excel.py")
    df, log = load_sheet(name, sheet, apply_rules)
    log.insert(0, f"source {source_id} -> {name}")
    return df, log


def load_sheet(profile_name: str, sheet: str, apply_rules: bool = True) -> tuple[pd.DataFrame, list[str]]:
    prof = load_profile(profile_name)
    sp = next((s for s in prof["sheets"] if s["name"] == sheet), None)
    if sp is None:
        raise KeyError(f"Sheet '{sheet}' not in profile. Available: {[s['name'] for s in prof['sheets']]}")
    src = ROOT / prof["source"]["path"]
    log = [f"Loaded {prof['source']['file']} / {sheet} (header row {sp['header_row']}, "
           f"profile status: {prof['annotations']['status']})"]
    if prof["annotations"]["status"] == "needs_review":
        log.append("  WARNING profile structure changed since annotations were confirmed")

    if src.suffix.lower() == ".csv":
        df = pd.read_csv(src, header=sp["header_row"] - 1, dtype=object)
    else:
        df = pd.read_excel(src, sheet_name=sheet, header=sp["header_row"] - 1, dtype=object, engine="openpyxl")
    df = df.dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    log.append(f"raw rows: {len(df)}")

    if apply_rules:
        rules = prof["annotations"]["sheets"].get(sheet, {}).get("cleaning_rules") or []
        if not rules:
            rules = [r for r in sp.get("suggested_cleaning_rules", []) if not r.get("needs_confirmation")]
            log.append("  WARNING using unconfirmed suggested rules (rules needing confirmation skipped)")
        for rule in rules:
            df = apply_rule(df, rule, log)
    df = df.infer_objects().reset_index(drop=True)
    log.append(f"final rows: {len(df)}")
    return df, log


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python tools/load_data.py <profile_name | source_id> <sheet>")
        sys.exit(1)
    sys.path.insert(0, str(ROOT))
    from tools.knowledge import load_sources
    is_source = any(s["id"] == sys.argv[1] for s in load_sources()["sources"])
    frame, steps = (load_source if is_source else load_sheet)(sys.argv[1], sys.argv[2])
    print("\n".join(steps))
    print(frame.head(10).to_string())
    print(frame.dtypes.to_string())
