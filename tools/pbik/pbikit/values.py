"""pbik values <Report>: the model values written into the report's files (roadmap gap 19), for a privacy review.

Microsoft Learn ("Power BI Desktop project report folder", PBIR folder and files, Important note) warns that filter
and slicer values are saved in the report files, so model data can reach source control. docs/it-security.md decides
what may be there; this lists it: every literal inside filters (report, page and visual filterConfig), slicer
selections (objects.general.filter), per-member selectors (scopeId) and bookmark states, by file and field. Formatting
literals (colours, sizes, text) aren't model values and aren't listed. Read-only.
"""
import json, pathlib

from .objects import load
from .report import Report

SKIP = {"null", "true", "false"}


def _field_of(node, aliases):
    for kind in ("Column", "Measure"):
        c = node.get(kind) if isinstance(node, dict) else None
        if isinstance(c, dict) and "Property" in c:
            ref = c.get("Expression", {}).get("SourceRef", {})
            ent = ref.get("Entity") or aliases.get(ref.get("Source"), ref.get("Source"))
            return f"{ent}[{c['Property']}]"
    return None


def literals(node, aliases=None, field=None):
    """Yield (field or None, literal) for every Literal in a filter-like tree, with the field it is compared to."""
    aliases = dict(aliases or {})
    if isinstance(node, dict):
        for fr in node.get("From") or [] if isinstance(node.get("From"), list) else []:
            if isinstance(fr, dict) and "Entity" in fr:
                aliases[fr.get("Name")] = fr["Entity"]
        for key in ("In", "Comparison", "Between", "Contains", "StartsWith"):
            c = node.get(key)
            if isinstance(c, dict):
                exprs = c.get("Expressions") or [c.get("Left") or c.get("Expression")]
                f = next((x for x in (_field_of(e, aliases) for e in exprs if e) if x), field)
                for v in c.get("Values") or []:
                    for x in v:
                        yield from literals(x, aliases, f)
                for side in ("Right", "LowerBound", "UpperBound"):
                    if side in c:
                        yield from literals(c[side], aliases, f)
                for side in ("Left", "Expression"):
                    if side in c and not _field_of(c[side], aliases):
                        yield from literals(c[side], aliases, f)
                return
        lit = node.get("Literal")
        if isinstance(lit, dict) and "Value" in lit:
            if str(lit["Value"]) not in SKIP:
                yield field, lit["Value"]
            return
        for v in node.values():
            yield from literals(v, aliases, field)
    elif isinstance(node, list):
        for v in node:
            yield from literals(v, aliases, field)


def scan(rep):
    """[(file, where, field, value)]."""
    out = []
    root = rep.path.parent

    def rel(f):
        return str(pathlib.Path(f).relative_to(root)).replace("\\", "/")

    def add(f, where, tree):
        for fld, val in literals(tree):
            out.append((rel(f), where, fld, val))
    rf = rep.defn / "report.json"
    if rf.exists():
        add(rf, "report filters", (load(rf).get("filterConfig") or {}))
    for _, pd, folder in rep.pages():
        add(folder / "page.json", "page filters", pd.get("filterConfig") or {})
        for d, f in rep.visuals(folder):
            add(f, "visual filters", d.get("filterConfig") or {})
            for obj, entries in ((d.get("visual") or {}).get("objects") or {}).items():
                for e in entries:
                    flt = (e.get("properties") or {}).get("filter")
                    if flt:
                        add(f, "slicer selection", flt)
                    sel = e.get("selector") or {}
                    if "scopeId" in json.dumps(sel):
                        add(f, f"selector ({obj})", sel)
    bdir = rep.defn / "bookmarks"
    for f in sorted(bdir.glob("*.bookmark.json")) if bdir.is_dir() else []:
        add(f, "bookmark state", load(f).get("explorationState") or {})
    return out


def values(report_path, out=None):
    rep = Report(report_path)
    rows = scan(rep)
    lines = [f"# Model values in {rep.path.name}", "",
             "Literals written into the report files (filters, slicer selections, per-member selectors, bookmark "
             "states). Check them against docs/it-security.md before committing. Read-only.", ""]
    if not rows:
        lines.append("- none")
    by = {}
    for f, where, fld, val in rows:
        by.setdefault((f, where, fld), []).append(val)
    for (f, where, fld), vals in sorted(by.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2]))):
        shown = sorted(set(map(str, vals)))
        lines.append(f"- {f}: {where}, {fld or '(no field)'}: {', '.join(shown[:12])}"
                     f"{f' ... ({len(shown)} values)' if len(shown) > 12 else ''}")
    text = "\n".join(lines)
    print(text)
    print(f"\n{len(rows)} value(s) in {len({r[0] for r in rows})} file(s)")
    if out:
        p = pathlib.Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {p}")
    return rows
