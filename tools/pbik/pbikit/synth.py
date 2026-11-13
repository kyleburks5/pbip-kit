"""Synthetic models: the contract, its approval, the slice, generation and verification (docs/design/synth-to-live.md).

The contract describes a model's structure (tables, typed columns, measures, relationships) and flags what needs a
person's review (Enter-data rows, M code, connection strings, RLS, entity tables). It never copies M code,
connection strings, RLS expressions or row values, except option-table rows a person kept at approval.
"""
import base64, hashlib, json, pathlib, re, tempfile, zlib

from . import dataclass_ as DC, names as N, tmdl

SPECS = pathlib.Path("design") / "specs"
RESOLUTIONS = {"enter-data": ["synthesize", "drop"], "m-code": ["synthesize", "drop"],
               "connection": ["synthesize", "drop"], "rls": ["not reproduced"], "entity": ["synthesize", "drop"]}
ENTITY_RE = re.compile(r"\b(account|member|customer|client|patient|employee|person|people|user|staff|student|"
                       r"contact|vendor|supplier|guest|subscriber)s?\b", re.I)
CONNECTORS = re.compile(r"\b(Sql\.Databases?|Oracle\.Database|Odbc\.\w+|OleDb\.\w+|AnalysisServices\.\w+|"
                        r"Web\.Contents|File\.Contents|Folder\.\w+|SharePoint\.\w+|Snowflake\.\w+|Databricks\.\w+|"
                        r"PowerPlatform\.\w+|Lakehouse\.\w+|Fabric\.\w+|PowerBI\.\w+|AzureStorage\.\w+)\s*\(")
CONN_TEXT = re.compile(r"(Data Source\s*=|Server\s*=|https?://|\\\\[\w.-]+\\)", re.I)
ENTER_DATA = re.compile(r'Binary\.FromText\(\s*"([A-Za-z0-9+/=]+)"')


class ContractError(Exception):
    pass


def specs(root):
    return pathlib.Path(root) / SPECS


def read_json(f, default=None):
    f = pathlib.Path(f)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default


def write_json(f, d):
    f = pathlib.Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
    if not f.exists() or f.read_text(encoding="utf-8") != text:
        f.write_text(text, encoding="utf-8")
        return True
    return False


def content_hash(d, skip=("approval",)):
    body = {k: v for k, v in d.items() if k not in skip}
    return hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- reading a model
def decode_enter_data(source):
    """Rows of an Enter-data partition (Binary.FromText deflated JSON, or a #table literal), else None."""
    m = ENTER_DATA.search(source or "")
    if m:
        try:
            raw = zlib.decompress(base64.b64decode(m.group(1)), -15)
            return json.loads(raw.decode("utf-8"))
        except (ValueError, zlib.error):
            return None
    t = re.match(r"\s*#table\s*\(\s*(?:type table \[[^\]]*\]|\{[^}]*\})\s*,\s*\{(.*)\}\s*\)\s*$", source or "", re.S)
    if t:
        rows = re.findall(r"\{([^{}]*)\}", t.group(1))
        return [[x.strip().strip('"') for x in r.split(",")] for r in rows if r.strip()]
    return None


def _roles_tmdl(texts):
    """[(role, table)] from TMDL role blocks."""
    out, role = [], None
    for text in texts:
        for ln in text.splitlines():
            s = ln.strip()
            if tmdl.level(ln) == 0 and s.startswith("role "):
                role = tmdl.split_decl(s[5:])[0]
            elif s.startswith("tablePermission ") and role:
                out.append((role, tmdl.split_decl(s[len("tablePermission "):])[0]))
    return out


def _from_tmsl(d):
    """A TMSL createOrReplace (JSON) as (tmdl.Model-like, roles, parameters)."""
    db = (d.get("createOrReplace") or d).get("database") or d.get("database") or d
    mod = db.get("model", {})
    model = tmdl.Model(pathlib.Path("."))
    expr = lambda e: "\n".join(e) if isinstance(e, list) else (e or "")          # noqa: E731
    for t in mod.get("tables", []):
        tb = model.tables.setdefault(t["name"], tmdl.Table(t["name"], "tmsl"))
        for c in t.get("columns", []):
            col = tmdl.Column(t["name"], c["name"], expr(c.get("expression")) or None, "tmsl", 0)
            col.data_type, col.sort_by = c.get("dataType"), c.get("sortByColumn")
            tb.columns[c["name"]] = col
        for m in t.get("measures", []):
            ms = tmdl.Measure(t["name"], m["name"], expr(m.get("expression")), "tmsl", 0)
            ms.format_string, ms.data_type = m.get("formatString"), m.get("dataType")
            tb.measures[m["name"]] = ms
        for p in t.get("partitions", []):
            src = p.get("source", {})
            tb.partitions.append([src.get("type", "m"), expr(src.get("expression") or src.get("query")), 0])
    for r in mod.get("relationships", []):
        rel = tmdl.Relationship(r.get("name", ""), "tmsl", 0)
        rel.from_column, rel.to_column = (r["fromTable"], r["fromColumn"]), (r["toTable"], r["toColumn"])
        model.relationships.append(rel)
    roles = [(ro["name"], tp["name"]) for ro in mod.get("roles", []) for tp in ro.get("tablePermissions", [])]
    params = [e["name"] for e in mod.get("expressions", []) if CONN_TEXT.search(expr(e.get("expression")))
              or '"' in expr(e.get("expression"))]
    return model, roles, params, db.get("name")


def read_model(source):
    """(model, roles, parameters, name) from a TMDL folder, a TMDL createOrReplace script or a TMSL script."""
    p = pathlib.Path(source)
    if p.is_dir():
        model = tmdl.load(p)
        folder = model.folder
        roles = _roles_tmdl(f.read_text(encoding="utf-8-sig") for f in sorted(folder.glob("roles/*.tmdl")))
        roles += _roles_tmdl(f.read_text(encoding="utf-8-sig") for f in sorted(folder.glob("*.tmdl")))
        params = []
        for f in folder.glob("expressions.tmdl"):
            for m in re.finditer(r"^expression\s+(.+?)\s*=(.*)$", f.read_text(encoding="utf-8-sig"), re.M):
                if '"' in m.group(2) or CONN_TEXT.search(m.group(2)):
                    params.append(tmdl.split_decl(m.group(1))[0])
        name = p.name[:-len(".SemanticModel")] if p.name.endswith(".SemanticModel") else p.name
        return model, roles, params, name
    text = p.read_text(encoding="utf-8-sig")
    if text.lstrip().startswith("{"):
        return _from_tmsl(json.loads(text))
    lines = text.splitlines()
    body = [ln for ln in lines if ln.strip() != "createOrReplace"]
    ded = [ln[1:] if ln.startswith("\t") else ln[4:] if ln.startswith("    ") else ln for ln in body]
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "script.tmdl"
        f.write_text("\n".join(ded), encoding="utf-8")
        model = tmdl.Model(pathlib.Path(d))
        tmdl._parse(model, f)
    return model, _roles_tmdl(["\n".join(ded)]), [], p.stem


# ---------------------------------------------------------------- the contract
def build_contract(source, root=None):
    model, roles, params, name = read_model(source)
    src = pathlib.Path(source)
    try:
        rel = str(src.resolve().relative_to(pathlib.Path(root or ".").resolve())).replace("\\", "/")
    except ValueError:
        rel = str(src.resolve())
    tables, flags = {}, []

    def flag(kind, table, detail):
        flags.append({"id": f"F{len(flags) + 1}", "kind": kind, "table": table, "detail": detail,
                      "resolution": None})

    for t in model.tables.values():
        part = t.partitions[0] if t.partitions else ["", "", 0]
        kind, srcx = (part[0] or "").lower(), part[1] or ""
        entry = {"columns": {}, "measures": {}}
        rows = decode_enter_data(srcx) if kind == "m" else None
        entry["source"] = "enter-data" if rows is not None else "calculated" if kind == "calculated" else \
            "m" if kind == "m" else kind or "none"
        for c in t.columns.values():
            col = {"type": c.data_type or "string"}
            if c.sort_by:
                col["sortBy"] = c.sort_by
            if c.expression:
                col["expression"] = c.expression
            entry["columns"][c.name] = col
        for m in t.measures.values():
            ms = {"expression": m.expression}
            for k, v in (("formatString", m.format_string), ("dataType", m.data_type),
                         ("dataCategory", m.data_category)):
                if v:
                    ms[k] = v
            entry["measures"][m.name] = ms
        if kind == "calculated":
            entry["expression"] = srcx
        tables[t.name] = entry
        if not entry["columns"]:
            continue                                   # a measures-only table: nothing to synthesize
        if rows is not None:
            flag("enter-data", t.name, f"{len(rows)} row(s) typed into the model (Enter data)")
        elif kind == "m":
            used = sorted(set(m.group(1) for m in CONNECTORS.finditer(srcx)))
            flag("m-code", t.name, "Power Query source" + (f" ({', '.join(used)})" if used else ""))
            if used or CONN_TEXT.search(srcx):
                flag("connection", t.name, "connects to an external source; not copied")
        if ENTITY_RE.search(t.name) or any(ENTITY_RE.search(c) for c in entry["columns"] if "name" in c.lower()):
            entry["entity"] = True
            flag("entity", t.name, "looks like account, member or other entity data")
    for p_ in params:
        flag("connection", None, f"model parameter {p_!r} holds a source value; not copied")
    for role, table in roles:
        flag("rls", table, f"row-level security role {role!r} (filter not copied)")
    rels = []
    for r in model.relationships:
        if r.from_column and r.to_column:
            rels.append({"from": f"{r.from_column[0]}[{r.from_column[1]}]", "to": f"{r.to_column[0]}[{r.to_column[1]}]"})
    return {"version": 1, "model": name, "source": rel, "tables": tables, "relationships": rels, "flags": flags,
            "rules": [], "approval": None}


def apply_rules(contract):
    """Pre-fill unresolved flags from the contract's rules (kind, table or '*'). Returns the flags it filled."""
    filled = []
    for f in contract["flags"]:
        if f.get("resolution"):
            continue
        for r in contract.get("rules", []):
            if r["kind"] == f["kind"] and (r.get("table") == "*" or N.same(r.get("table"), f.get("table"))):
                f["resolution"], f["rule"] = r["resolution"], r["id"]
                filled.append(f)
                break
    return filled


def contract(source, root=".", out=None):
    """Write design/specs/contract.json from a model; rules (and resolutions they cover) carry over."""
    out = pathlib.Path(out) if out else specs(root) / "contract.json"
    c = build_contract(source, root)
    old = read_json(out)
    if old:
        c["rules"] = old.get("rules", [])
    apply_rules(c)
    write_json(out, c)
    return c, out


def resolve(root, target, resolution, why=None, every=False, cfile=None):
    """Resolve a flag (by ID) or every flag of a kind; record the rule behind it."""
    cfile = pathlib.Path(cfile) if cfile else specs(root) / "contract.json"
    c = read_json(cfile)
    if c is None:
        raise ContractError("no contract: run `pbik synth contract` first")
    hits = [f for f in c["flags"] if f["id"] == target or (every and f["kind"] == target)]
    if not hits:
        raise ContractError(f"no flag {target!r}")
    for f in hits:
        allowed = allowed_resolutions(c, f)
        if resolution not in allowed:
            raise ContractError(f"{f['id']} ({f['kind']}) can be resolved as: {', '.join(allowed)}")
    rid = f"R{len(c.get('rules', [])) + 1}"
    table = "*" if every else hits[0].get("table")
    c.setdefault("rules", []).append({"id": rid, "kind": hits[0]["kind"], "table": table, "resolution": resolution,
                                      "why": why or ""})
    for f in hits:
        f["resolution"], f["rule"] = resolution, rid
    c["approval"] = None
    write_json(cfile, c)
    return hits


def allowed_resolutions(c, f):
    return list(RESOLUTIONS.get(f["kind"], []))


def approved(c):
    a = c.get("approval") if c else None
    return bool(a) and a.get("hash") == content_hash(c)


def approve(root, by, ask=None, cfile=None, out=print):
    """Person-only: print what is approved, ask for the model name typed, record by / date / hash."""
    cfile = pathlib.Path(cfile) if cfile else specs(root) / "contract.json"
    c = read_json(cfile)
    if c is None:
        raise ContractError("no contract: run `pbik synth contract` first")
    st = DC.stamp(by)
    open_ = [f["id"] for f in c["flags"] if not f.get("resolution")]
    if open_:
        raise ContractError(f"unresolved flag(s): {', '.join(open_)} (`pbik synth resolve`)")
    out(f"Contract for model {c['model']!r}: {len(c['tables'])} table(s), "
        f"{sum(len(t['columns']) for t in c['tables'].values())} column(s), "
        f"{sum(len(t['measures']) for t in c['tables'].values())} measure(s), {len(c['relationships'])} relationship(s)")
    for f in c["flags"]:
        out(f"  {f['id']} {f['kind']:10} {f.get('table') or '(model)'}: {f['detail']} -> {f['resolution']}")
    extra = approve_hooks(c, root, ask, out)
    DC.confirm(f"Approve this contract as {st['by']}?", c["model"], ask)
    for hook in extra:
        hook()
    c["approval"] = dict(st, hash=content_hash(c))
    write_json(cfile, c)
    return c


def approve_hooks(c, root, ask, out):
    """Extra person checks at approval (option-table rows, batch 3 item 7). Returns callables run after the main
    confirmation."""
    return []


# ---------------------------------------------------------------- the slice
REF_RE = re.compile(r"((?:'(?:[^']|'')+')|[^\[\]\(\),\"'{}:]*?)\[([^\[\]]+)\]")


def layout_refs(layout):
    """[(table or None, name)] named anywhere in layout.json strings (`Table[Column]`, `'T'[C]`, `[Measure]`)."""
    out = []

    def walk(x):
        if isinstance(x, str):
            for m in REF_RE.finditer(x):
                t = m.group(1).strip()
                t = t.split("(")[-1].strip() if t else t
                out.append((tmdl.unquote(t) if t else None, m.group(2)))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(layout.get("visuals", []))
    walk(layout.get("pages", {}))
    return list(dict.fromkeys(out))


class Index:
    """Case-insensitive lookups over a contract (and planned measures)."""

    def __init__(self, c, planned=None):
        self.c, self.planned = c, planned or {}

    def table(self, name):
        return N.find(self.c["tables"], name)

    def column(self, table, name):
        t = self.table(table)
        return (t, N.find(self.c["tables"][t]["columns"], name)) if t else (None, None)

    def measure(self, name, table=None):
        """(home table, measure name, planned?) or None."""
        homes = [(t, N.find(tb["measures"], name)) for t, tb in self.c["tables"].items()]
        homes = sorted((h for h in homes if h[1]), key=lambda h: not (table and N.same(h[0], table)))
        if homes:                                     # the named table first
            return homes[0][0], homes[0][1], False
        p = N.find(self.planned, name)
        if p:
            return self.planned[p].get("table", "_Measures"), p, True
        return None

    def resolve(self, table, name):
        """('column', table, name) / ('measure', table, name) / ('planned', table, name) / None."""
        if table:
            t, col = self.column(table, name)
            if col:
                return "column", t, col
        m = self.measure(name)
        if m:
            return ("planned" if m[2] else "measure"), m[0], m[1]
        return None


def _expr_refs(ix, expr, slice_):
    """Add what a DAX expression uses to the slice; return newly added measures (to follow)."""
    refs, variables, strings = tmdl.references(expr)
    new = []
    code = tmdl.strip_dax(expr or "")[0]
    for t in ix.c["tables"]:
        pat = r"'" + re.escape(t.replace("'", "''")) + r"'" if not re.fullmatch(r"\w+", t) else r"\b" + re.escape(t) + r"\b"
        if re.search(pat, code, re.I):
            slice_.setdefault(t, {"columns": [], "measures": []})
    for table, name in refs:
        if table and N.ci_in(table, variables):
            continue
        hit = ix.resolve(table, name)
        if not hit:
            continue
        kind, t, n = hit
        entry = slice_.setdefault(t, {"columns": [], "measures": []})
        key = "columns" if kind == "column" else "measures"
        if n not in entry[key]:
            entry[key].append(n)
            if kind != "column":
                new.append((t, n, kind == "planned"))
    return new


def slice_contract(c, layout, planned=None):
    """{table: {columns, measures}}: the fields layout.json uses, the measures they need, keys and sort-by columns.
    Also returns names layout.json uses that are in neither the contract nor the planned measures."""
    ix, out, missing, todo = Index(c, planned), {}, [], []
    for table, name in layout_refs(layout):
        hit = ix.resolve(table, name)
        if not hit:
            missing.append(f"{table}[{name}]" if table else f"[{name}]")
            continue
        kind, t, n = hit
        e = out.setdefault(t, {"columns": [], "measures": []})
        key = "columns" if kind == "column" else "measures"
        if n not in e[key]:
            e[key].append(n)
            if kind != "column":
                todo.append((t, n, kind == "planned"))
    while todo:
        t, n, is_planned = todo.pop()
        expr = (planned or {}).get(n, {}).get("expression") if is_planned else c["tables"][t]["measures"][n]["expression"]
        todo += _expr_refs(ix, expr, out)
    for col_owner in list(out):                     # calculated columns' own references, and sort-by columns
        cols = c["tables"][col_owner]["columns"] if col_owner in c["tables"] else {}
        for cn in list(out[col_owner]["columns"]):
            if cols.get(cn, {}).get("expression"):
                _expr_refs(ix, cols[cn]["expression"], out)
            sb = cols.get(cn, {}).get("sortBy")
            if sb and N.find(cols, sb) and N.find(cols, sb) not in out[col_owner]["columns"]:
                out[col_owner]["columns"].append(N.find(cols, sb))
    for r in c["relationships"]:
        (ft, fc), (tt, tc) = split_field(r["from"]), split_field(r["to"])
        if ft in out and tt in out:
            for t, col in ((ft, fc), (tt, tc)):
                if col not in out[t]["columns"]:
                    out[t]["columns"].append(col)
    for t, e in out.items():                         # a table referenced on its own needs one column
        if not e["columns"] and c["tables"].get(t, {}).get("columns"):
            e["columns"].append(next(iter(c["tables"][t]["columns"])))
        order = list(c["tables"][t]["columns"]) + list(c["tables"][t]["measures"]) + list(planned or {})
        for k in ("columns", "measures"):            # contract order, so files don't move between runs
            e[k].sort(key=lambda x: order.index(x) if x in order else len(order))
    return {t: out[t] for t in sorted(out)}, list(dict.fromkeys(missing))


def split_field(text):
    m = re.fullmatch(r"(.+)\[(.+)\]", text)
    return (m.group(1), m.group(2)) if m else (None, text)


def load_contract(root, need_approval=True):
    c = read_json(specs(root) / "contract.json")
    if c is None:
        raise ContractError("no contract: run `pbik synth contract` first")
    if need_approval and not approved(c):
        raise ContractError("the contract isn't approved (or changed since): a person runs `pbik synth approve --by`")
    return c


def slice_(root, layout_path):
    c = load_contract(root)
    gf = specs(root) / "generate.json"
    g = read_json(gf, {"seed": 1, "dateRange": ["2023-01-01", "2025-12-31"], "hints": {}, "plannedMeasures": {},
                       "deviations": []})
    sl, missing = slice_contract(c, read_json(layout_path), g.get("plannedMeasures"))
    for f in c["flags"]:
        if f.get("resolution") == "drop" and f.get("table") in sl:
            sl.pop(f["table"])
    g["slice"], g["contractHash"] = sl, content_hash(c)
    write_json(gf, g)
    return g, missing
