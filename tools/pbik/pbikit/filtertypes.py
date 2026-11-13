"""Filter values typed against the model's column types (batch 3 item 5).

A filter literal must match its column: text ('North') on a text column, a number (2024L, 1.5D, 1.5M) on a number
column. A number written as text never matches, and neither does a number on a text column: the filter silently
selects nothing. Every saved filter counts: report, page and visual filterConfig, bookmarks, slicer state.
"""
import re

from . import names as N

NUMERIC = {"int64", "double", "decimal"}
NUM_LIT = re.compile(r"^-?\d+(\.\d+)?[LDM]$")


def literal_kind(v):
    if not isinstance(v, str):
        return None
    if v.startswith("'") and v.endswith("'"):
        return "text"
    if NUM_LIT.match(v):
        return "number"
    return None


def conditions(node, aliases=None):
    """Yield (entity, column, [literal values]) for every In, Comparison and Between on a column."""
    aliases = dict(aliases or {})
    if isinstance(node, dict):
        if isinstance(node.get("From"), list):
            for fr in node["From"]:
                if isinstance(fr, dict) and "Entity" in fr:
                    aliases[fr.get("Name")] = fr["Entity"]

        def ent_of(col):
            ref = col.get("Expression", {}).get("SourceRef", {})
            return ref.get("Entity") or aliases.get(ref.get("Source"))
        cond = node.get("In")
        if isinstance(cond, dict) and cond.get("Values"):
            for k, e in enumerate(cond.get("Expressions", [])):
                col = e.get("Column") if isinstance(e, dict) else None
                if col:
                    vals = [t[k].get("Literal", {}).get("Value") for t in cond["Values"]
                            if len(t) > k and isinstance(t[k], dict)]
                    yield ent_of(col), col.get("Property"), vals
        cmp_ = node.get("Comparison")
        if isinstance(cmp_, dict) and isinstance(cmp_.get("Left"), dict) and "Column" in cmp_["Left"]:
            col = cmp_["Left"]["Column"]
            lit = cmp_.get("Right", {}).get("Literal", {}).get("Value")
            if lit is not None:
                yield ent_of(col), col.get("Property"), [lit]
        btw = node.get("Between")
        if isinstance(btw, dict) and isinstance(btw.get("Expression"), dict) and "Column" in btw["Expression"]:
            col = btw["Expression"]["Column"]
            vals = [btw.get(b, {}).get("Literal", {}).get("Value") for b in ("LowerBound", "UpperBound")]
            yield ent_of(col), col.get("Property"), [v for v in vals if v is not None]
        for v in node.values():
            yield from conditions(v, aliases)
    elif isinstance(node, list):
        for v in node:
            yield from conditions(v, aliases)


def model_types(model):
    """coltype(entity, column) -> TMDL dataType, case-insensitive, from a tmdl.Model."""
    def coltype(ent, col):
        t = N.find(model.tables, ent) if model and ent else None
        c = N.find(model.tables[t].columns, col) if t else None
        return model.tables[t].columns[c].data_type if c else None
    return coltype


def issues(doc, coltype):
    """Messages for filter values whose type doesn't match the column's."""
    out = []
    for ent, col, vals in conditions(doc):
        dt = coltype(ent, col)
        if not dt:
            continue
        kinds = [(v, literal_kind(v)) for v in vals]
        if dt in NUMERIC:
            texts = [v for v, k in kinds if k == "text"]
            if texts:
                bare = texts[0].strip("'")
                out.append(f"filter on {ent}[{col}] ({dt}) has text values {texts[:3]}: write numbers as "
                           f"{bare}{'L' if dt == 'int64' else 'D'}")
        elif dt == "string":
            nums = [v for v, k in kinds if k == "number"]
            if nums:
                out.append(f"filter on {ent}[{col}] (string) has number values {nums[:3]}: write text as "
                           f"'{nums[0][:-1]}'")
    return list(dict.fromkeys(out))
