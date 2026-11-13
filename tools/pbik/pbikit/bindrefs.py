"""Every place a PBIR report references a model field, found and rewritten through a name map (docs/design/synth-to-live.md).

Sites: Column / Measure objects (SourceRef by Entity or by a From alias, so visual queries, filters at report, page
and visual level, sorts, conditional formatting, bookmarks, tooltip and drillthrough bindings and slicer state all
count), any SourceRef Entity (hierarchies, variations), From entries, the strings `queryRef` and selector `metadata`
("Table.Field", "Sum(Table.Field)"), reportExtensions.json entity names, and DAX in report-level measures.
"""
import re

from . import names as N, tmdl


class Mapper:
    """Synthetic -> live names, case-insensitive as in DAX. tables {syn: live}; fields [(syn table or None, syn name,
    live table or None, live name)]; measures: (table key, name key) of the synthetic measures (for [X] in DAX).
    Identity when empty."""

    def __init__(self, tables=None, fields=(), measures=()):
        self._t = {N.key(s): (s, l) for s, l in (tables or {}).items()}
        self._f = {(N.key(st) if st else None, N.key(sn)): (st, sn, lt, ln) for st, sn, lt, ln in fields}
        self.measures = set(measures)

    @classmethod
    def from_map(cls, m, measures=()):
        fields = []
        for k, v in (m.get("fields") or {}).items():
            st, sn = split(k)
            lt, ln = split(v)
            fields.append((st, sn, lt, ln))
        return cls(m.get("tables", {}), fields, {(N.key(t), N.key(n)) for t, n in measures})

    def empty(self):
        return not self._t and not self._f

    def table(self, t):
        hit = self._t.get(N.key(t)) if t else None
        return hit[1] if hit else t

    def entry(self, t, name):
        k = (N.key(t) if t else None, N.key(name))
        hit = self._f.get(k)
        if hit is None and t is not None and k in self.measures:
            hit = self._f.get((None, k[1]))
        if hit is None and t is None:
            homes = [e for kk, e in self._f.items() if kk[1] == k[1] and (kk[0] is None or kk in self.measures)]
            hit = homes[0] if homes else None
        return hit

    def field(self, t, name):
        """(live table, live name) for synthetic t[name]; t None means a [Measure] (any home)."""
        hit = self.entry(t, name)
        if hit is None:
            return self.table(t), name
        return (hit[2] or self.table(t)), hit[3]

    def reverse(self):
        fields, measures = [], set()
        for k, (st, sn, lt, ln) in self._f.items():
            live_t = lt or (self.table(st) if st else None)
            fields.append((live_t, ln, st, sn))
            if st is None or k in self.measures:
                measures.add((N.key(live_t) if live_t else None, N.key(ln)))
        return Mapper({l: s for s, l in self._t.values()}, fields, measures)


def split(text):
    """'Table[Name]' / "'T'[Name]" / '[Name]' / 'Name' -> (table or None, name)."""
    m = re.fullmatch(r"\s*(.*?)\s*\[(.+)\]\s*", text or "")
    if not m:
        return None, (text or "").strip()
    return (tmdl.unquote(m.group(1)) or None), m.group(2)


# ---------------------------------------------------------------- PBIR JSON
STRING_KEYS = ("queryRef", "metadata")
FUNC_RE = re.compile(r"^([A-Za-z]+\()?(.+)\.([^.]+?)(\))?$")


def split_dotted(text, tables):
    """'Sum(Table.Field)' -> (prefix, table, field, suffix) using the known table names (dots in names allowed)."""
    m = re.match(r"^([A-Za-z]+\()?(.*?)(\))?$", text or "")
    pre, body, suf = m.group(1) or "", m.group(2), m.group(3) or ""
    for t in sorted(tables, key=len, reverse=True):
        if N.key(body).startswith(N.key(t) + "."):
            return pre, body[:len(t)], body[len(t) + 1:], suf
    m2 = FUNC_RE.match(text or "")
    if m2 and not pre:
        return m2.group(1) or "", m2.group(2), m2.group(3), m2.group(4) or ""
    if "." in body:
        t, _, f = body.partition(".")
        return pre, t, f, suf
    return None


def sites(node, tables=(), path="", aliases=None):
    """Yield (kind, entity, property, schema, path) for every field reference; kind Column, Measure, ref (a string
    site: queryRef / metadata) or Entity (a From entry or SourceRef naming a table)."""
    aliases = dict(aliases or {})
    if isinstance(node, dict):
        if isinstance(node.get("From"), list):
            for k, fr in enumerate(node["From"]):
                if isinstance(fr, dict) and "Entity" in fr:
                    aliases[fr.get("Name")] = (fr["Entity"], fr.get("Schema"))
                    yield "Entity", fr["Entity"], None, fr.get("Schema"), f"{path}/From/{k}"
        for kind in ("Column", "Measure"):
            x = node.get(kind)
            if isinstance(x, dict) and "Property" in x:
                sr = x.get("Expression", {}).get("SourceRef", {})
                if "Entity" in sr:
                    yield kind, sr["Entity"], x["Property"], sr.get("Schema"), f"{path}/{kind}"
                elif sr.get("Source") in aliases:
                    ent, sch = aliases[sr["Source"]]
                    yield kind, ent, x["Property"], sch, f"{path}/{kind}"
        for k in STRING_KEYS:
            if isinstance(node.get(k), str):
                hit = split_dotted(node[k], tables)
                if hit:
                    yield "ref", hit[1], hit[2], None, f"{path}/{k}"
        for k, v in node.items():
            yield from sites(v, tables, f"{path}/{k}", aliases)
    elif isinstance(node, list):
        for k, v in enumerate(node):
            yield from sites(v, tables, f"{path}/{k}", aliases)


def rewrite(doc, mapper, tables=(), keep_labels=True, labels=None):
    """Rewrite every field reference in a PBIR JSON tree in place. Returns the number of edits.
    keep_labels: a projection whose field is renamed gets `displayName` = the old name (unless it has one), so headers
    keep the synthetic label; `labels` collects the paths given one."""
    edits = {}                                  # (id(holder), key) -> (priority, holder, key, value)

    def put(holder, key, value, prio=0):
        cur = edits.get((id(holder), key))
        if holder.get(key) != value and (cur is None or prio >= cur[0]):
            edits[(id(holder), key)] = (prio, holder, key, value)

    def walk(node, aliases, path):
        if isinstance(node, dict):
            aliases = dict(aliases)
            if isinstance(node.get("From"), list):
                for fr in node["From"]:
                    if isinstance(fr, dict) and "Entity" in fr:
                        aliases[fr.get("Name")] = (fr["Entity"], fr.get("Schema"))
                        put(fr, "Entity", mapper.table(fr["Entity"]))
            sr = node.get("SourceRef")
            if isinstance(sr, dict) and "Entity" in sr:
                put(sr, "Entity", mapper.table(sr["Entity"]))
            renamed = None
            for kind in ("Column", "Measure"):
                x = node.get(kind)
                if isinstance(x, dict) and "Property" in x:
                    ref = x.get("Expression", {}).get("SourceRef", {})
                    ent = ref.get("Entity") or (aliases.get(ref.get("Source")) or (None,))[0]
                    if ent is None:
                        continue
                    lt, ln = mapper.field(ent, x["Property"])
                    if ln != x["Property"]:
                        renamed = x["Property"]
                    put(x, "Property", ln, 1)
                    if "Entity" in ref:
                        put(ref, "Entity", lt, 1)
                    elif N.key(lt) != N.key(mapper.table(ent)):
                        raise ValueError(f"{path}: {ent}[{x['Property']}] moves to table {lt} inside a query with "
                                         "aliases; map it to a field in the same table")
            for k in STRING_KEYS:
                if isinstance(node.get(k), str):
                    hit = split_dotted(node[k], tables)
                    if hit:
                        pre, t, f, suf = hit
                        lt, ln = mapper.field(t, f)
                        put(node, k, f"{pre}{lt}.{ln}{suf}")
            if keep_labels and "field" in node and "queryRef" in node and "displayName" not in node:
                f = node["field"]
                for kind in ("Column", "Measure", "Aggregation"):
                    x = f.get(kind) if isinstance(f, dict) else None
                    if kind == "Aggregation" and isinstance(x, dict):
                        x = x.get("Expression", {}).get("Column")
                    if isinstance(x, dict) and "Property" in x:
                        ref = x.get("Expression", {}).get("SourceRef", {})
                        ent = ref.get("Entity") or (aliases.get(ref.get("Source")) or (None,))[0]
                        if ent and mapper.field(ent, x["Property"])[1] != x["Property"]:
                            put(node, "displayName", node.get("nativeQueryRef") or x["Property"], 2)
                            if labels is not None:
                                labels.append(path)
            for k, v in node.items():
                walk(v, aliases, f"{path}/{k}")
        elif isinstance(node, list):
            for k, v in enumerate(node):
                walk(v, aliases, f"{path}/{k}")

    walk(doc, {}, "")
    for _, holder, key, value in edits.values():
        holder[key] = value
    return len(edits)


def drop_labels(doc, paths):
    """Undo `rewrite`'s keep-labels: remove displayName at the given projection paths."""
    n = 0
    for p in paths:
        cur = doc
        try:
            for part in [x for x in p.split("/") if x]:
                cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        except (KeyError, IndexError, ValueError, TypeError):
            continue
        if isinstance(cur, dict) and "displayName" in cur and cur["displayName"] == cur.get("nativeQueryRef"):
            del cur["displayName"]
            n += 1
    return n


# ---------------------------------------------------------------- DAX
DAX_TOKEN = re.compile(r"'((?:[^']|'')+)'\s*\[([^\]]+)\]|(?<![\w\]\.])([A-Za-z_][\w\.]*)\s*\[([^\]]+)\]|\[([^\]]+)\]"
                       r"|'((?:[^']|'')+)'|(?<![\w\.\[@])([A-Za-z_][\w\.]*)\b(?!\s*[\(\[])")


def sub_code(expr, pattern, fn):
    """re.sub over the code of a DAX expression only: string literals and comments stay as they are."""
    out, k, n, seg = [], 0, len(expr or ""), 0
    expr = expr or ""
    while k < n:
        if expr.startswith(("//", "--", "/*"), k) or expr[k] == '"':
            out.append(pattern.sub(fn, expr[seg:k]))
            if expr[k] == '"':
                j = k + 1
                while j < n and not (expr[j] == '"' and not expr.startswith('""', j)):
                    j += 2 if expr.startswith('""', j) else 1
                j += 1
            elif expr.startswith("/*", k):
                j = expr.find("*/", k + 2)
                j = n if j < 0 else j + 2
            else:
                j = expr.find("\n", k)
                j = n if j < 0 else j
            out.append(expr[k:j])
            k = seg = j
        else:
            k += 1
    out.append(pattern.sub(fn, expr[seg:n]))
    return "".join(out)


def rewrite_dax(expr, mapper, tables=(), variables=None):
    """DAX with every model reference renamed per the mapper (strings and comments untouched)."""
    if mapper.empty():
        return expr
    variables = {N.key(v) for v in (variables or tmdl.references(expr)[1])}
    tkeys = {N.key(t) for t in tables}
    return sub_code(expr, DAX_TOKEN, lambda m: _dax_sub(m, mapper, tkeys, variables))


def qt(t):
    return t if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t) else "'" + t.replace("'", "''") + "'"


def _dax_sub(m, mapper, tkeys, variables):
    if m.group(1) or m.group(3):                       # Table[Field]
        t = m.group(1).replace("''", "'") if m.group(1) else m.group(3)
        if m.group(3) and (N.key(t) in variables or t.upper() in tmdl.DAX_WORDS):
            return m.group(0)
        lt, ln = mapper.field(t, m.group(2) or m.group(4))
        return f"{qt(lt)}[{ln}]"
    if m.group(5):                                     # [Measure] (or a column in row context)
        name = m.group(5)
        if name.startswith("@"):
            return m.group(0)
        return f"[{mapper.field(None, name)[1]}]"
    t = m.group(6).replace("''", "'") if m.group(6) else m.group(7)
    if N.key(t) in tkeys and N.key(t) not in variables:  # a table on its own: COUNTROWS ( Orders )
        lt = mapper.table(t)
        return qt(lt) if m.group(6) or lt != t else m.group(0)
    return m.group(0)
