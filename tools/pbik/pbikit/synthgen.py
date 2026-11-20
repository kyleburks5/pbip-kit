"""Generate and verify a synthetic model from the approved contract and generate.json (docs/design/synth-to-live.md).

Every table is a calculated table (inline DATATABLE). Values are deterministic: each column draws from
random.Random(sha1(seed/table/column)). Dimension keys are unique, fact keys draw from them, a date key covers
generate.json `dateRange`; hints (`rows`, `rowsPerYear`, `fact`, `trend`, `seasonality`, `monthEnd`, `values`: a column's labels) shape the
rest; a fact table gets generate.json `rowsPerYear` (default 6,000) rows for each year of the date range.
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


def month_end(d):
    nxt = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)


def month_weights(g, hint):
    """[(year, month, weight)] over the date range: trend = growth per year (0.1 = +10%), seasonality = 12 monthly
    weights (Jan..Dec, any scale)."""
    a, b = date_range(g)
    trend = float(hint.get("trend") or 0)
    season = hint.get("seasonality") or [1] * 12
    if len(season) != 12:
        raise ContractError("generate.json hints: seasonality needs 12 monthly weights (Jan..Dec)")
    out, y, m = [], a.year, a.month
    while (y, m) <= (b.year, b.month):
        out.append((y, m, (1 + trend) ** (y - a.year) * float(season[m - 1])))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def wants_month_end(hint, col):
    me = hint.get("monthEnd")
    return me is True or (isinstance(me, list) and N.ci_in(col, me))


def shaped(hint):
    return bool(hint.get("trend") or hint.get("seasonality"))


def fact_dates(r, g, hint, n, col=None):
    """n dates in the date range, shaped by the hints: more rows in later years (trend) and busier months
    (seasonality); month-end dates when asked."""
    a, b = date_range(g)
    if not shaped(hint) and not wants_month_end(hint, col):
        span = (b - a).days
        return [a + dt.timedelta(days=r.randrange(span + 1)) for _ in range(n)]
    months = month_weights(g, hint)
    picks = r.choices(months, weights=[w for _, _, w in months], k=n)
    out = []
    for y, m, _ in picks:
        first, last = dt.date(y, m, 1), month_end(dt.date(y, m, 1))
        lo, hi = max(first, a), min(last, b)
        out.append(hi if wants_month_end(hint, col) else lo + dt.timedelta(days=r.randrange((hi - lo).days + 1)))
    return out


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


FACT_ROWS_PER_YEAR = 6000                         # thousands a year, like a real desk: histograms and quarters take shape
LIT_TYPE = {"INTEGER": "int64", "STRING": "string", "DOUBLE": "double", "CURRENCY": "decimal", "DATETIME": "dateTime",
            "BOOLEAN": "boolean"}
DAYS_RE = re.compile(r"days|hours|duration|\btime\b", re.I)
THRESH_RE = re.compile(r"\b(sla|target|threshold|goal|limit|quota)\b", re.I)
FLAG_RE = re.compile(r"^(within|on[ -]time|in sla|met|is|has|was)\b", re.I)


def _split_top(text, sep=","):
    out, depth, cur, quote = [], 0, "", False
    for ch in text:
        if ch == '"':
            quote = not quote
        if not quote:
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth -= 1
            elif ch == sep and depth == 0:
                out.append(cur.strip())
                cur = ""
                continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _literal(x):
    x = x.strip()
    if x.startswith('"') and x.endswith('"'):
        return x[1:-1].replace('""', '"')
    m = re.fullmatch(r"NAMEOF\s*\(\s*(.+?)\s*\)", x, re.I)
    if m:
        return m.group(1)
    if re.fullmatch(r"-?\d+", x):
        return int(x)
    if re.fullmatch(r"-?\d*\.\d+", x):
        return float(x)
    if re.fullmatch(r"TRUE\s*(\(\s*\))?", x, re.I):
        return True
    if re.fullmatch(r"FALSE\s*(\(\s*\))?", x, re.I):
        return False
    return None


def literal_rows(c, t):
    """The rows a calculated table writes in its own DAX (DATATABLE ( ... ) or a { ( ... ) } table constructor, as an
    option list or a field parameter has): (column types, {columns, rows}), else None. These are labels in the model's
    code, not data, so the made-up model keeps them as they are (v1.12): a picker shows Revenue / Profit, not
    Metric 1 / Metric 2, and a fact table's keys match its option table."""
    tb = c["tables"].get(t) or {}
    expr = re.sub(r"(//|--)[^\n]*", "", tb.get("expression") or "").strip()
    cols = [x for x, v in (tb.get("columns") or {}).items() if not v.get("expression")]
    m = re.fullmatch(r"DATATABLE\s*\((.*)\)", expr, re.S | re.I)
    if m:
        parts = _split_top(m.group(1))
        body = parts[-1] if parts and parts[-1].startswith("{") else None
        decl = parts[:-1] if body else parts
        if not body or len(decl) % 2:
            return None
        names = [_literal(decl[i]) for i in range(0, len(decl), 2)]
        if not all(isinstance(n, str) for n in names):
            return None
        types = {n: LIT_TYPE.get(decl[i + 1].strip().upper(), "string") for n, i in zip(names, range(0, len(decl), 2))}
        rows = [[_literal(v) for v in _split_top(r.strip()[1:-1])] for r in _split_top(body.strip()[1:-1])]
        if not rows or any(len(r) != len(names) for r in rows):
            return None
        return types, {"columns": names, "rows": rows}
    if expr.startswith("{") and expr.endswith("}"):
        rows = [[_literal(v) for v in _split_top(r.strip()[1:-1])] for r in _split_top(expr[1:-1])
                if r.strip().startswith("(")]
        if not rows or len({len(r) for r in rows}) != 1 or any(v is None for r in rows for v in r):
            return None
        k = len(rows[0])
        # a field parameter: (label, NAMEOF ( field ), order); the columns by their role, not their listed order
        label = next((x for x in cols if not re.search(r"fields|order|sort", x, re.I)), None)
        fields = next((x for x in cols if re.search(r"fields", x, re.I)), None)
        order = next((x for x in cols if re.search(r"order|sort", x, re.I)), None)
        if k == 3 and label and fields and order:
            return ({label: "string", fields: "string", order: "int64"},
                    {"columns": [label, fields, order], "rows": rows})
        if k == len(cols):
            types = {x: ("int64" if isinstance(rows[0][i], int) and not isinstance(rows[0][i], bool) else
                         "double" if isinstance(rows[0][i], float) else
                         "boolean" if isinstance(rows[0][i], bool) else "string") for i, x in enumerate(cols)}
            return types, {"columns": cols, "rows": rows}
    return None


def calculated_tables(c, g):
    """In memory, for the made-up model only (the approved contract is unchanged): option tables keep the rows their
    DAX writes (literal_rows), and a calculated date table (CALENDAR, a date template) on the one side of a
    relationship from a date column gets date types (its key a date, Year / Month Number numbers), so it fills from
    the date range like any date table. Returns plain lines."""
    notes = []
    sl = g.get("slice", {})
    for t in sl:
        tb = c["tables"].get(t) or {}
        if tb.get("source") != "calculated" or tb.get("rows"):
            continue
        lit = literal_rows(c, t)
        if lit:
            types, rows = lit
            for x, ty in types.items():
                if x in tb["columns"]:
                    tb["columns"][x]["type"] = ty
            tb["rows"] = rows
            notes.append(f"{t}: its {len(rows['rows'])} label(s) kept as the model writes them")
    for r in c["relationships"]:
        (ft, fc), (tt, tc) = split_field(r["from"]), split_field(r["to"])
        tb = c["tables"].get(tt) or {}
        if tt not in sl or tb.get("source") != "calculated" or tb.get("rows"):
            continue
        if (c["tables"].get(ft, {}).get("columns", {}).get(fc) or {}).get("type") != "dateTime":
            continue
        for x, col in tb["columns"].items():
            if col.get("expression") or col.get("type") not in (None, "string"):
                continue
            if N.key(x) == N.key(tc):
                col["type"] = "dateTime"
            elif isinstance(date_part(x, dt.date(2024, 1, 1)), int) and not re.search(r"name|label", x, re.I):
                col["type"] = "int64"
        notes.append(f"{tt}: a date table, filled from the date range")
    return notes


ID_RE = re.compile(r"(\bid|\bkey|\bnumber|\bno\.?)$", re.I)
END_RE = re.compile(r"resolv|clos|end|finish|complet|ship|deliver", re.I)
START_RE = re.compile(r"receiv|open|start|creat|order|log|raise|submit", re.I)


def consistent_rows(vals, types, keys, fkeys, n, r):
    """v1.12: a made-up row that reads like a real one: an ID column counts up (unique), an end date (resolved,
    closed) falls after its start date (received, opened) by the row's duration, and a "within" yes / no column says
    whether the row's duration is inside its threshold (SLA days)."""
    for x, ty in types.items():
        if ID_RE.search(x) and x not in keys and x not in fkeys and ty in ("int64", "string") and x in vals                 and date_part(x, dt.date(2024, 1, 1)) is None:     # Month Number is a date part, not an ID
            vals[x] = [100000 + k for k in range(n)] if ty == "int64" else [f"{x} {100000 + k}" for k in range(n)]
    dur = next((x for x, ty in types.items() if ty in ("double", "decimal", "int64") and DAYS_RE.search(x)
                and not THRESH_RE.search(x) and x in vals), None)
    lim = next((x for x, ty in types.items() if ty in ("double", "decimal", "int64") and THRESH_RE.search(x) and x in vals), None)
    start = next((x for x, ty in types.items() if ty == "dateTime" and START_RE.search(x) and x in vals), None)
    end = next((x for x, ty in types.items() if ty == "dateTime" and END_RE.search(x) and x != start and x in vals
                and x not in fkeys), None)
    if start and end:
        for k in range(n):
            a = vals[start][k]
            if hasattr(a, "toordinal"):
                days = vals[dur][k] if dur else r.uniform(0.5, 10)
                vals[end][k] = a + dt.timedelta(days=int(round(days + 0.49)))
    if dur and lim:
        for x, ty in types.items():
            if FLAG_RE.search(x) and x in vals and x not in fkeys:
                vals[x] = [("Yes" if vals[dur][k] <= vals[lim][k] else "No") if ty == "string"
                           else vals[dur][k] <= vals[lim][k] for k in range(n)]


def shaped_rows(vals, types, hint, n, r):
    """generate.json hints that make made-up rows read like the subject (v1.12), each from a column already made:
    `derive` {col: {from, map, default}} (a shot's type from its area); `rates` {col: {by, values, default}} (a 0/1
    outcome at the rate of the row's member: rim 0.62, threes 0.35); `points` {x, y, zone, space} (coordinates inside
    the row's area of a kit space, by the space's own rule, so the court and the data agree)."""
    for col, d in (hint.get("derive") or {}).items():
        src = vals.get(d.get("from"))
        if src is not None and col in vals:
            vals[col] = [d.get("map", {}).get(str(v), d.get("default", v)) for v in src]
    for col, d in (hint.get("rates") or {}).items():
        by = vals.get(d.get("by"))
        if by is not None and col in vals:
            rate = lambda v: float(d.get("values", {}).get(str(v), d.get("default", 0.45)))
            yes, no = (True, False) if types.get(col) == "boolean" else (1, 0)
            vals[col] = [yes if r.random() < rate(v) else no for v in by]
    pt = hint.get("points") or {}
    if pt.get("space") == "court" and pt.get("zone") in vals and pt.get("x") in vals and pt.get("y") in vals:
        import sys
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "design" / "scripts"))
        import space_svg as SP
        xs, ys = [], []
        boxes = {k: (min(x for x, _ in p_), max(x for x, _ in p_), min(y for _, y in p_), max(y for _, y in p_))
                 for k, p_ in SP.court_zone_shapes().items()}
        hx, hy = SP.COURT["W"] / 2, SP.COURT["hoop_y"]
        for z in vals[pt["zone"]]:
            x0, x1, y0, y1 = boxes.get(z, (0, 50, 0, 47))
            y1 = min(y1, hy + 30) if z in ("three-top", "wing3-left", "wing3-right") else y1   # threes from near the arc
            for _ in range(2000):                      # a point inside the area (its box first), by the space's own rule
                dx, dy = round(r.uniform(x0, x1) - hx, 2), round(r.uniform(y0, y1) - hy, 2)
                if SP.court_zone(dx, dy) == z:       # the rounded point, as the model stores it
                    break
            xs.append(round(dx, 2))
            ys.append(round(dy, 2))
        vals[pt["x"]], vals[pt["y"]] = xs, ys


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
            if wants_month_end(hint, date_key):
                days = [d for d in days if d == month_end(d)]
            vals[date_key], n = days, len(days)
        else:
            if hint.get("rows"):
                n = int(hint["rows"])
            elif hint.get("fact") or t in facts:      # a fact table: rows per year of the date range (v1.12)
                a_, b_ = date_range(g)
                years = max(1, round(((b_ - a_).days + 1) / 365.25))
                n = int(hint.get("rowsPerYear") or g.get("rowsPerYear") or FACT_ROWS_PER_YEAR) * years
            else:
                n = 8
        for x in cols:
            if x in vals:
                continue
            r, typ = rng(seed, t, x), types[x]
            if (hint.get("values") or {}).get(x) and not ((t, x) in keys_from):   # the column's own values first
                pool = list(hint["values"][x])
                vals[x] = [r.choice(pool) for _ in range(n)]
            elif days and date_part(x, days[0]) is not None:
                vals[x] = [date_part(x, d) for d in days]
            elif (t, x) in keys_from and keys_from[(t, x)][0] in out:
                pool = out[keys_from[(t, x)][0]].get(keys_from[(t, x)][1]) or [None]
                if typ == "dateTime":
                    vals[x] = fact_keys(r, g, hint, pool, n, x)
                elif (hint.get("weights") or {}).get(x):  # the mix the hint gives (shots by area)
                    wd = hint["weights"][x]
                    w = [float(wd.get(str(k), 0.0)) for k in pool]
                    vals[x] = r.choices(pool, weights=w if sum(w) else None, k=n)
                    w = None
                else:                                  # uneven, like real data: the first keys busier (seeded order)
                    order = sorted(range(len(pool)), key=lambda i: rng(seed, t, x, "w", str(pool[i])).random())
                    w = [0.0] * len(pool)
                    for rank, i in enumerate(order):
                        w[i] = 1 / (rank + 1) ** 0.8
                    if w is not None:
                        vals[x] = r.choices(pool, weights=w, k=n)
            elif x in keys_to.get(t, ()):
                vals[x] = list(range(1, n + 1)) if typ in ("int64", "double", "decimal") else \
                    [f"{x} {k}" for k in range(1, n + 1)]
            elif typ == "dateTime":
                vals[x] = fact_dates(r, g, hint, n, x)
            elif typ == "int64" and THRESH_RE.search(x):
                vals[x] = [r.choice((3, 5, 5, 7, 8, 10)) for _ in range(n)]       # an SLA or target: a few set values
            elif typ == "int64":
                vals[x] = [r.randint(1, 20) for _ in range(n)]
            elif typ in ("double", "decimal") and DAYS_RE.search(x):
                vals[x] = [float(round(min(r.lognormvariate(1.25, 0.7), 60))) for _ in range(n)]   # durations: whole days, right-skewed
            elif typ in ("double", "decimal"):
                vals[x] = [round(r.uniform(10, 1000), 2) for _ in range(n)]
            elif typ == "boolean":
                vals[x] = [r.random() < 0.5 for _ in range(n)]
            elif FLAG_RE.search(x):
                vals[x] = ["Yes" if r.random() < 0.8 else "No" for _ in range(n)]      # a yes / no column
            else:
                pool = [f"{x} {k}" for k in range(1, min(n, 6) + 1)]
                vals[x] = [pool[k] if k < len(pool) else r.choice(pool) for k in range(n)]
        consistent_rows(vals, types, keys_to.get(t, ()), {x for (ft, x) in keys_from if ft == t}, n, rng(seed, t, "rows"))
        shaped_rows(vals, types, hint, n, rng(seed, t, "shaped"))
        for x in cols:                                       # sort-by columns follow their column's order
            sb = N.find(cols, tcols[x].get("sortBy") or "")
            if sb and not (days and date_part(sb, days[0]) is not None):
                order = sorted(set(vals[x]), key=lambda v: (MONTHS.index(v) if v in MONTHS else 99, str(v)))
                vals[sb] = [order.index(v) + 1 for v in vals[x]]
        out[t] = vals
    return out


def fact_keys(r, g, hint, pool, n, col=None):
    """Fact dates drawn from a date dimension's keys, shaped like fact_dates."""
    if not shaped(hint) and not wants_month_end(hint, col):
        return [r.choice(pool) for _ in range(n)]
    by_month = {}
    for d in pool:
        if d is not None and (not wants_month_end(hint, col) or d == month_end(d)):
            by_month.setdefault((d.year, d.month), []).append(d)
    months = [(y, m, w) for y, m, w in month_weights(g, hint) if (y, m) in by_month]
    if not months:
        return [r.choice(pool) for _ in range(n)]
    picks = r.choices(months, weights=[w for _, _, w in months], k=n)
    return [r.choice(by_month[(y, m)]) for y, m, _ in picks]


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


def tmdl_value(v):
    """A TMDL property value: one holding a double quote (an arrow format "▲ "0.0%) goes in double quotes with its
    quotes doubled, or Desktop refuses the model (InvalidValueFormat, test 3 of the batch studies, v1.12)."""
    v = str(v)
    return '"' + v.replace('"', '""') + '"' if '"' in v else v


def measure_lines(m, src, planned):
    body = (src or {}).get("expression", "BLANK ()").strip().splitlines()
    L = [f"\tmeasure {q(m)} = " + (body[0] if len(body) == 1 else "")]
    if len(body) > 1:
        L += ["\t\t\t" + ln.strip() for ln in body]
    fmt = (src or {}).get("formatString")
    if not fmt and not (src or {}).get("dataType") and not re.search(r"%|share|rate|ratio|vs\b|colou?r$", m, re.I):
        fmt = "#,0.00" if re.search(r"\bavg\b|average|mean", m, re.I) else "#,0"   # thousands separators (fix 8)
    if fmt:
        L.append(f"\t\tformatString: {tmdl_value(thousands(fmt))}")
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
        if typ == "dateTime" and not col.get("formatString"):
            L.append("\t\tformatString: m/d/yyyy")           # v1.12: dates as 4/21/2025, not with 12:00:00 AM
        elif col.get("formatString"):
            L.append(f"\t\tformatString: {tmdl_value(col['formatString'])}")
        if not col.get("expression"):
            L.append(f"\t\tsourceColumn: [{x}]")
        if col.get("sortBy"):
            L.append(f"\t\tsortByColumn: {q(col['sortBy'])}")
        L.append("")
    prepared = {N.key(x) for x in g.get("prepared", [])}     # planned measures bind prepare moved to the report
    for m in sl["measures"]:
        if N.key(m) in prepared and m not in tb["measures"]:
            continue
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
    """Kept rows need the flag's resolution "keep rows: option labels", a person's KEEP at approval (the approval
    hash covers them) and a table that isn't entity data."""
    from .synth import KEEP_ROWS, is_entity
    for t, e in c["tables"].items():
        if not e.get("rows"):
            continue
        marked = any(f.get("resolution") == KEEP_ROWS and N.same(f.get("table"), t) for f in c["flags"])
        if not marked or is_entity(c, t):
            raise ContractError(f"{t}: kept rows without a 'keep rows: option labels' resolution, or entity data")


NUMBER_WORDS = {"no", "number", "num", "nr", "index", "idx", "sort", "order"}


def _is_month_number(col):
    k = N.key(col)
    return "month" in k and bool(set(re.split(r"\W+", k)) & NUMBER_WORDS)


def month_sorts(c, g):
    """Month names sort by the month number (walkthrough fix 8): a text column named like Month with no sort-by column
    gets the table's month-number column (Month No, MonthNumber, ...) as its sort-by column in the made-up model, the
    number column joining the slice if it isn't in it. Returns plain lines: what was set, or exactly why not."""
    notes = []
    for t, sl in g["slice"].items():
        tcols = c["tables"].get(t, {}).get("columns", {})
        for x in list(sl.get("columns", [])):
            col = tcols.get(x) or {}
            if "month" not in N.key(x) or _is_month_number(x) or col.get("sortBy") or col.get("type") not in (None, "string"):
                continue
            sib = next((y for y in tcols if y != x and _is_month_number(y)
                        and tcols[y].get("type") in ("int64", "double", "decimal")), None)
            if not sib:
                notes.append(f"{t}[{x}] will sort A to Z: the model has no month-number column beside it to sort by")
                continue
            if sib not in sl["columns"]:
                sl["columns"].append(sib)
            col["sortBy"] = sib
            notes.append(f"{t}[{x}] sorts by {t}[{sib}] (month order, not A to Z)")
    return notes


def thousands(fmt):
    """A whole-number or decimal format string with thousands separators ("0" -> "#,0", "0.00" -> "#,0.00");
    percentages, dates, currency with its own grouping and text stay as they are."""
    if not fmt or "%" in fmt or "," in fmt or re.search(r"[yMdhHsE\"@]", fmt):
        return fmt
    return re.sub(r"(^|;)([^;0#]*)([0#]+)", lambda m: m.group(1) + m.group(2) + "#,0", fmt)


def generate(root, name, out_folder=None, notes=None):
    """Write <name>.SemanticModel from the approved contract and generate.json. Returns the folder. `notes` collects
    plain lines about what the kit set (month order)."""
    c = load_contract(root)
    g = read_json(specs(root) / "generate.json")
    if not g or "slice" not in g:
        raise ContractError("no slice: run `pbik synth slice <layout.json>` first")
    if g.get("contractHash") != content_hash(c):
        raise ContractError("the slice was made from another contract: run `pbik synth slice` again")
    check_kept_rows(c, g)
    folder = pathlib.Path(out_folder) if out_folder else pathlib.Path(root) / f"{name}.SemanticModel"
    chash = content_hash(c)                       # before month_sorts sets sort-by columns in memory
    from .synth import with_planned_columns
    with_planned_columns(c, g)                    # the plan's calculated columns (top N + Other, bands)
    said = calculated_tables(c, g) + month_sorts(c, g)
    if notes is not None:
        notes.extend(said)
    d = folder / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    vals = generate_values(c, g)
    write_text(folder / "definition.pbism", json.dumps({"version": "4.2", "settings": {}}, indent=2) + "\n")
    write_text(d / "database.tmdl", "database\n\tcompatibilityLevel: 1606\n")
    tables = sorted(g["slice"])
    write_text(d / "model.tmdl", "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\n"
               f"annotation {DC.SYNTH_MARK} = {chash}\n\nannotation {PLAN_MARK} = {plan_stamp(g)}\n\n"
               + "".join(f"ref table {q(t)}\n" for t in tables))
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
    from . import udf as U                       # UDFs installed for the synthetic model (pbik udf install)
    wanted = [n for n, v in U.state(root).get("installed", {}).items() if v.get("model") == "synthetic"]
    if wanted:
        names = U.write_functions(folder, U.load(root), wanted, U.load_tokens(root), U.state(root).get("dateTable"))
        if notes is not None:
            notes.append(f"{len(names)} DAX function(s) added for the UDF cards (compatibility level {U.MIN_LEVEL})")
    return folder


PLAN_MARK = "PBIK_SynthPlan"
GEN_VERSION = 12                                  # raise when the made-up rows change


def plan_stamp(g):
    """What the made-up model was made from (the slice, planned measures and columns, seed, hints, dates)."""
    keys = ("slice", "plannedMeasures", "plannedColumns", "seed", "hints", "dateRange", "contractHash", "prepared")
    body = {k: g.get(k) for k in keys} | {"generator": GEN_VERSION}     # a kit change to the made-up rows remakes it
    return hashlib.sha1(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]


def ensure(root, name, layout_path, notes=None):
    """Before a build on the made-up model (v1.12): slice from the layout and write <name>.SemanticModel when it is
    missing or was made from another plan (new fields, planned measures or columns), then verify it. Returns "made",
    "updated", "current", or None when the project has no approved contract or the folder is the person's own model
    (never touched). Raises ContractError when the plan names a field the model doesn't have."""
    from . import synth as S
    root = pathlib.Path(root)
    try:
        S.load_contract(root)
    except ContractError as e:
        if (specs(root) / "contract.json").exists() and (root / f"{name}.SemanticModel").exists():
            if notes is not None:            # a contract changed since its approval: the model stays as it was, said
                notes.append(f"the made-up model was not remade: {e}")
            return "stale"
        return None
    folder = root / f"{name}.SemanticModel"
    if folder.exists() and not DC.is_synthetic(folder):
        return None
    g, missing = S.slice_(root, layout_path)
    if missing:
        raise ContractError("the plan uses field(s) the model doesn't have: " + ", ".join(missing))
    f = folder / "definition" / "model.tmdl"
    stamp = plan_stamp(read_json(specs(root) / "generate.json", {}))
    if f.exists() and f"{PLAN_MARK} = {stamp}" in f.read_text(encoding="utf-8"):
        return "current"
    was = folder.exists()
    generate(root, name, notes=notes)
    errs, _ = verify(root, folder)
    if errs:
        raise ContractError("the made-up model doesn't match the contract: " + "; ".join(errs[:3]))
    return "updated" if was else "made"


def norm_dax(x):
    return re.sub(r"\s+", " ", (x or "").strip())


def verify(root, model_folder):
    """(errors, notes): the synthetic model against the contract slice."""
    c = load_contract(root, need_approval=False)
    g = read_json(specs(root) / "generate.json", {})
    from .synth import with_planned_columns
    with_planned_columns(c, g)
    calculated_tables(c, g)                       # the same in-memory types generate used
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
            if N.ci_in(x, g.get("prepared", [])) and x not in c["tables"][t]["measures"]:
                continue
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
