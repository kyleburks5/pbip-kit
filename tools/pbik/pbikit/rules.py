"""Flag grouping and plain-language explanations (docs/PLAIN-WORDS.md); the rule library comes in stage (d)."""
from . import synth as S

PLAIN = {"enter-data": "a small table someone typed into the model",
         "m-code": "a table loaded by a query",
         "connection": "a link to a data source; it isn't copied",
         "rls": "a row-level security role; it isn't copied",
         "entity": "a table about accounts, members or other people or organisations"}


def plain(f):
    return f"{f.get('table') or 'the model'}: {PLAIN.get(f['kind'], f['kind'])}"


def groups(c):
    """{"rules": resolved by a rule, "keep": option tables to keep, "you": still need a person} of a contract."""
    out = {"rules": [], "keep": [], "you": []}
    for f in c["flags"]:
        if not f.get("resolution"):
            out["you"].append(f)
        elif f["resolution"] == S.KEEP_ROWS:
            out["keep"].append(f)
        else:
            out["rules"].append(f)
    return out


# ---------------------------------------------------------------- the rule library (stage d)
import json as _json, pathlib as _pathlib, re as _re  # noqa: E402

from . import names as _N  # noqa: E402

LIBRARY = _pathlib.Path(__file__).resolve().parents[1] / "rules" / "library.json"


def load_library(path=None):
    p = _pathlib.Path(path) if path else LIBRARY
    return _json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"rules": []}


def matches(rule, c, f):
    if rule["kind"] != f["kind"]:
        return False
    m = rule.get("match") or {}
    if "maxRows" in m and f.get("rows", 0) > m["maxRows"]:
        return False
    t = _N.find(c["tables"], f.get("table") or "")
    cols = list(c["tables"][t]["columns"]) if t else []
    for pat in m.get("columns", []):
        if not any(_re.search(rf"(^|\b|\s)({pat})", col, _re.I) for col in cols):
            return False
    if m.get("table") and not _re.search(m["table"], f.get("table") or "", _re.I):
        return False
    if rule["resolution"] not in S.allowed_resolutions(c, f):
        return False
    return True


def apply_library(c, lib=None):
    """Resolve flags still open with the library's rules; returns the flags it filled."""
    lib = lib or load_library()
    filled = []
    for f in c["flags"]:
        if f.get("resolution"):
            continue
        for r in lib.get("rules", []):
            if matches(r, c, f):
                f["resolution"], f["rule"], f["source"] = r["resolution"], r["id"], "library"
                filled.append(f)
                break
    c["library"] = lib.get("version")
    return filled


def summary_line(c):
    g = groups(c)
    return (f"{len(g['rules'])} handled by rules, {len(g['keep'])} option table(s) to keep, "
            f"{len(g['you'])} need you")


def propose(c, lib=None):
    """Project rules a person made for every table of a kind (table '*') that the library doesn't have yet."""
    lib = lib or load_library()
    have = {(r["kind"], r["resolution"]) for r in lib.get("rules", []) if not r.get("match")}
    return [r for r in c.get("rules", []) if r.get("table") == "*" and (r["kind"], r["resolution"]) not in have]


def write_proposals(root, props):
    """design/reviews/rule-proposals.md: for review at the next kit update, never added automatically."""
    f = _pathlib.Path(root) / "design" / "reviews" / "rule-proposals.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Rule proposals", "", "Rules a person made for every table of a kind, for the kit's rule library "
             "(tools/pbik/rules/library.json) at the next kit update. Review, never automatic.", ""]
    lines += [f"- {r['kind']}: {r['resolution']} ({r.get('why', '')})" for r in props]
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return props
