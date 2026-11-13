"""Generate and verify a synthetic model from the approved contract and generate.json (docs/design/synth-to-live.md).

Every table is a calculated table (inline DATATABLE). Values are deterministic: each column draws from
random.Random(sha1(seed/table/column)). Dimension keys are unique, fact keys draw from them, a date key covers
generate.json `dateRange`; hints (`rows`, `fact`, `trend`, `seasonality`, `monthEnd`) shape the rest.
"""
import datetime as dt, hashlib, json, pathlib, random, re, uuid

from . import dataclass_ as DC, names as N, tmdl
from .synth import ContractError, content_hash, load_contract, read_json, specs, split_field

DAX_TYPE = {"int64": "INTEGER", "double": "DOUBLE", "decimal": "CURRENCY", "string": "STRING", "boolean": "BOOLEAN",
            "dateTime": "DATETIME"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def q(name):
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


def tag(*parts):
    return str(uuid.UUID(hashlib.sha1("/".join(parts).encode("utf-8")).hexdigest()[:32]))


def rng(seed, *parts):
    return random.Random(int(hashlib.sha1("/".join(map(str, (seed,) + parts)).encode("utf-8")).hexdigest()[:12], 16))


def date_range(g):
    a, b = (dt.date.fromisoformat(x) for x in g.get("dateRange", ["2023-01-01", "2025-12-31"]))
    return a, b


def table_order(sl, rels):
    """Dimensions (relationship 'to' sides) before the tables that point at them."""
    deps = {t: set() for t in sl}
    for r in rels:
        (ft, _), (tt, _) = split_field(r["from"]), split_field(r["to"])
        if ft in deps and tt in deps and ft != tt:
            deps[ft].add(tt)
    out = []
    while deps:
        ready = sorted(t for t, d in deps.items() if not (d - set(out))) or sorted(deps)
        for t in ready:
            out.append(t)
            deps.pop(t)
    return out


def fact_dates(r, g, hint, n):
    """n dates in the date range (uniform; batch 3 item 8 adds trend, seasonality and month-end)."""
    a, b = date_range(g)
    span = (b - a).days
    return [a + dt.timedelta(days=r.randrange(span + 1)) for _ in range(n)]


def date_part(col, d):
    k = N.key(col)
    words = set(re.split(r"\W+", k))
    if "year" in k:
        return d.year
    if "quarter" in k:
        return f"Q{(d.month - 1) // 3 + 1}"
    if "month" in k and words & {"no", "number", "num", "nr"}:
        return d.month
    if "month" in k:
        return MONTHS[d.month - 1]
    if "day" in k:
        return d.day
    return None


def relations(c, sl):
    keys_to, keys_from = {}, {}
    for r in c["relationships"]:
        (ft, fc), (tt, tc) = split_field(r["from"]), split_field(r["to"])
        if ft in sl and tt in sl:
            keys_to.setdefault(tt, set()).add(tc)
            keys_from[(ft, fc)] = (tt, tc)
    return keys_to, keys_from


def generate_values(c, g):
    """{table: {column: [values]}} for the slice, deterministic for the seed."""
    sl, seed, hints = g["slice"], g.get("seed", 1), g.get("hints", {})
    keys_to, keys_from = relations(c, sl)
    facts = {ft for (ft, _) in keys_from}
    out = {}
    for t in table_order(sl, c["relationships"]):
        tcols = c["tables"][t]["columns"]
        cols = [x for x in sl[t]["columns"] if not tcols[x].get("expression")]
        if not cols:
            continue
        hint, types = hints.get(t, {}), {x: tcols[x]["type"] for x in cols}
        kept = c["tables"][t].get("rows")
        if kept:                                           # option-table rows a person kept (item 7)
            out[t] = {x: [row[i] for row in kept["rows"]] for i, x in enumerate(kept["columns"]) if x in cols}
            continue
        date_key = next((x for x in cols if x in keys_to.get(t, ()) and types[x] == "dateTime"), None)
        vals, days = {}, None
        if date_key:
            a, b = date_range(g)
            days = [a + dt.timedelta(days=k) for k in range((b - a).days + 1)]
            if hint.get("monthEnd"):
                days = [d for d in days if (d + dt.timedelta(days=1)).day == 1]
            vals[date_key], n = days, len(days)
        else:
            n = int(hint.get("rows") or (500 if (hint.get("fact") or t in facts) else 8))
        for x in cols:
            if x in vals:
                continue
            r, typ = rng(seed, t, x), types[x]
            if days and date_part(x, days[0]) is not None:
                vals[x] = [date_part(x, d) for d in days]
            elif (t, x) in keys_from and keys_from[(t, x)][0] in out:
                pool = out[keys_from[(t, x)][0]].get(keys_from[(t, x)][1]) or [None]
                vals[x] = fact_keys(r, g, hint, pool, n) if typ == "dateTime" else [r.choice(pool) for _ in range(n)]
            elif x in keys_to.get(t, ()):
                vals[x] = list(range(1, n + 1)) if typ in ("int64", "double", "decimal") else \
                    [f"{x} {k}" for k in range(1, n + 1)]
            elif typ == "dateTime":
                vals[x] = fact_dates(r, g, hint, n)
            elif typ == "int64":
                vals[x] = [r.randint(1, 20) for _ in range(n)]
            elif typ in ("double", "decimal"):
                vals[x] = [round(r.uniform(10, 1000), 2) for _ in range(n)]
            elif typ == "boolean":
                vals[x] = [r.random() < 0.5 for _ in range(n)]
            else:
                pool = [f"{x} {k}" for k in range(1, min(n, 6) + 1)]
                vals[x] = [pool[k] if k < len(pool) else r.choice(pool) for k in range(n)]
        for x in cols:                                       # sort-by columns follow their column's order
            sb = N.find(cols, tcols[x].get("sortBy") or "")
            if sb and not (days and date_part(sb, days[0]) is not None):
                order = sorted(set(vals[x]), key=lambda v: (MONTHS.index(v) if v in MONTHS else 99, str(v)))
                vals[sb] = [order.index(v) + 1 for v in vals[x]]
        out[t] = vals
    return out


def fact_keys(r, g, hint, pool, n):
    """Fact dates drawn from a date dimension's keys (item 8 shapes them)."""
    return [r.choice(pool) for _ in range(n)]


def dax_value(v, typ):
    if v is None:
        return "BLANK ()"
    if typ == "dateTime":
        return f'"{v.isoformat() if hasattr(v, "isoformat") else v}"'
    if typ == "boolean":
        return "TRUE" if v in (True, "true", "True", "1", 1) else "FALSE"
    if typ in ("int64", "double", "decimal"):
        return str(v)
    return '"' + str(v).replace('"', '""') + '"'


def measure_lines(m, src, planned):
    body = (src or {}).get("expression", "BLANK ()").strip().splitlines()
    L = [f"\tmeasure {q(m)} = " + (body[0] if len(body) == 1 else "")]
    if len(body) > 1:
        L += ["\t\t\t" + ln.strip() for ln in body]
    if (src or {}).get("formatString"):
        L.append(f"\t\tformatString: {src['formatString']}")
    L.append(f"\t\tlineageTag: {tag('measure', m)}")
    if planned:
        L += ["", "\t\tannotation PBIK_Planned = 1"]
    return L + [""]


def table_tmdl(c, g, t, vals):
    tb, sl = c["tables"][t], g["slice"][t]
    planned = g.get("plannedMeasures", {})
    keys = {split_field(r[k])[1] for r in c["relationships"] for k in ("from", "to") if split_field(r[k])[0] == t}
    L = [f"table {q(t)}", f"\tlineageTag: {tag(t)}", ""]
    data_cols = [x for x in sl["columns"] if not tb["columns"][x].get("expression")]
    for x in sl["columns"]:
        col, typ = tb["columns"][x], tb["columns"][x]["type"]
        L += [f"\tcolumn {q(x)}" + (f" = {col['expression']}" if col.get("expression") else ""),
              f"\t\tdataType: {typ if typ in DAX_TYPE else 'string'}", f"\t\tlineageTag: {tag(t, x)}",
              f"\t\tsummarizeBy: {'sum' if typ in ('int64', 'double', 'decimal') and x not in keys else 'none'}"]
        if not col.get("expression"):
            L.append(f"\t\tsourceColumn: [{x}]")
        if col.get("sortBy"):
            L.append(f"\t\tsortByColumn: {q(col['sortBy'])}")
        L.append("")
    for m in sl["measures"]:
        L += measure_lines(m, tb["measures"].get(m, planned.get(m)), m not in tb["measures"])
    if not data_cols:                                   # a measures-only table: one hidden column
        L += ["\tcolumn _", "\t\tdataType: string", "\t\tisHidden", f"\t\tlineageTag: {tag(t, '_')}",
              "\t\tsummarizeBy: none", "\t\tsourceColumn: [_]", "",
              f"\tpartition {q(t)} = calculated", "\t\tmode: import",
              '\t\tsource = DATATABLE ( "_", STRING, { { BLANK () } } )', ""]
        return "\n".join(L)
    types = [tb["columns"][x]["type"] for x in data_cols]
    n = len(vals[data_cols[0]])
    L += [f"\tpartition {q(t)} = calculated", "\t\tmode: import", "\t\tsource =", "\t\t\t\tDATATABLE ("]
    L += [f'\t\t\t\t\t"{x}", {DAX_TYPE.get(ty, "STRING")},' for x, ty in zip(data_cols, types)]
    L.append("\t\t\t\t\t{")
    for k in range(n):
        row = ", ".join(dax_value(vals[x][k], ty) for x, ty in zip(data_cols, types))
        L.append(f"\t\t\t\t\t\t{{ {row} }}" + ("," if k < n - 1 else ""))
    return "\n".join(L + ["\t\t\t\t\t}", "\t\t\t\t)", ""])


def write_text(f, text):
    f = pathlib.Path(f)
    if not f.exists() or f.read_text(encoding="utf-8") != text:
        f.write_text(text, encoding="utf-8")
        return True
    return False


def check_kept_rows(c, g):
    """Item 7 allows kept option-table rows; until then a contract with kept rows can't generate."""
    for t, e in c["tables"].items():
        if e.get("rows") and t in g["slice"]:
            raise ContractError(f"{t}: kept rows are not supported")


def generate(root, name, out_folder=None):
    """Write <name>.SemanticModel from the approved contract and generate.json. Returns the folder."""
    c = load_contract(root)
    g = read_json(specs(root) / "generate.json")
    if not g or "slice" not in g:
        raise ContractError("no slice: run `pbik synth slice <layout.json>` first")
    if g.get("contractHash") != content_hash(c):
        raise ContractError("the slice was made from another contract: run `pbik synth slice` again")
    check_kept_rows(c, g)
    folder = pathlib.Path(out_folder) if out_folder else pathlib.Path(root) / f"{name}.SemanticModel"
    d = folder / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    vals = generate_values(c, g)
    write_text(folder / "definition.pbism", json.dumps({"version": "4.2", "settings": {}}, indent=2) + "\n")
    write_text(d / "database.tmdl", "database\n\tcompatibilityLevel: 1606\n")
    tables = sorted(g["slice"])
    write_text(d / "model.tmdl", "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\n"
               f"annotation {DC.SYNTH_MARK} = {content_hash(c)}\n\n" + "".join(f"ref table {q(t)}\n" for t in tables))
    written = set()
    for t in tables:
        f = d / "tables" / f"{t}.tmdl"
        write_text(f, table_tmdl(c, g, t, vals.get(t, {})))
        written.add(f.name)
    for f in (d / "tables").glob("*.tmdl"):
        if f.name not in written:
            f.unlink()                                  # a table that left the slice (pbik's own synthetic folder)
    rels = []
    for r in c["relationships"]:
        (ft, fc), (tt, tc) = split_field(r["from"]), split_field(r["to"])
        if ft in g["slice"] and tt in g["slice"]:
            rels += [f"relationship {tag('rel', r['from'], r['to'])}", f"\tfromColumn: {q(ft)}.{q(fc)}",
                     f"\ttoColumn: {q(tt)}.{q(tc)}", ""]
    write_text(d / "relationships.tmdl", "\n".join(rels))
    return folder


def norm_dax(x):
    return re.sub(r"\s+", " ", (x or "").strip())


def verify(root, model_folder):
    """(errors, notes): the synthetic model against the contract slice."""
    c = load_contract(root, need_approval=False)
    g = read_json(specs(root) / "generate.json", {})
    m = tmdl.load(model_folder)
    errs, notes = [], []
    if not DC.is_synthetic(model_folder):
        errs.append(f"{model_folder}: no {DC.SYNTH_MARK} annotation (not a pbik synthetic model)")
    dev = {(N.key(x.get("table")), N.key(x.get("column"))): x for x in g.get("deviations", [])}
    planned = g.get("plannedMeasures", {})
    sl = g.get("slice", {})
    for t, e in sl.items():
        mt = N.find(m.tables, t)
        if not mt:
            errs.append(f"table {t}: missing")
            continue
        for x in e["columns"]:
            col = N.find(m.tables[mt].columns, x)
            want = c["tables"][t]["columns"][x]["type"]
            got = m.tables[mt].columns[col].data_type if col else None
            if not col:
                errs.append(f"{t}[{x}]: missing")
            elif got != want:
                d = dev.get((N.key(t), N.key(x)))
                if d:
                    notes.append(f"{t}[{x}]: {got} instead of {want} (deviation: {d.get('why', '')})")
                else:
                    errs.append(f"{t}[{x}]: type {got}, contract {want}")
        for x in e["measures"]:
            ms = N.find(m.tables[mt].measures, x)
            want = c["tables"][t]["measures"].get(x, planned.get(x, {})).get("expression")
            if not ms:
                errs.append(f"{t}[{x}]: measure missing")
            elif norm_dax(m.tables[mt].measures[ms].expression) != norm_dax(want):
                errs.append(f"{t}[{x}]: DAX differs from the contract")
    have = {tuple(N.key(v) for v in r.from_column + r.to_column) for r in m.relationships
            if r.from_column and r.to_column}
    for r in c["relationships"]:
        (ft, fc), (tt, tc) = split_field(r["from"]), split_field(r["to"])
        if ft in sl and tt in sl and tuple(N.key(v) for v in (ft, fc, tt, tc)) not in have:
            errs.append(f"relationship {r['from']} -> {r['to']}: missing")
    return errs, notes
