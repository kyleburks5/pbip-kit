"""Example values for the fast HTML preview (the plan picture and quick changes): made up, never read from data.

    gen_wireframe_hf.py --data example

Two renderers (v1.7 walkthrough): this preview, drawn from layout.json, tokens, the theme and the templates' look with
believable example numbers, is what the person approves; after the build, a real Power BI Desktop screenshot is
compared against it (design/scripts/fidelity_check.py, `pbik plan compare`). Nothing here touches a model: the values
come from a seed per visual, so the same layout always draws the same picture. Formats follow the measure's name
(share, rate, % and "vs" as percentages, averages with two decimals, everything else whole numbers with thousands
separators); categories follow the field's name (months in calendar order, years, then "<Name> 1..n").
"""
import json, pathlib, random, re

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PCT = re.compile(r"%|share|rate|ratio|pct|percent|\bvs\b|growth|change", re.I)
AVG = re.compile(r"\bavg\b|average|mean|per\b", re.I)
COUNT = re.compile(r"qty|quantity|count|units|orders?$|number|visits|tickets", re.I)
MEASURE_TABLE = re.compile(r"^_|measure", re.I)
DAYS = re.compile(r"days|hours|duration|\btime\b", re.I)
SPLY = re.compile(r"^\s*CALCULATE\s*\(\s*\[([^\]]+)\]\s*,\s*(SAMEPERIODLASTYEAR|DATEADD|PARALLELPERIOD|PREVIOUSYEAR)", re.I)
MODEL = {}           # measure name -> {formatString, expression}: the model contract and planned measures (v1.12)
COLS = {}            # column name -> {type, expression, table}: the contract's columns and the planned columns
YEARS = []           # the years the made-up model covers (generate.json dateRange)
FACT_ROWS = {"per_year": None}
HINT_WEIGHTS = {}    # member -> weight (generate.json hints weights): the made-up mix (shots by area)
HINT_RATES = {}      # outcome column -> {member: rate} (generate.json hints rates)  # a fact table's rows per year in the made-up model (generate.json rowsPerYear, default 6,000)
LABEL_KEY = {}       # label column -> {label: key} (a SWITCH over a key column): the label's numbers are the key's
LABELS = {}          # column name -> the labels an option table writes in its own DAX (kept as they are, v1.12)
_CACHE = {}          # (measure, context) -> value: one value per measure and filter context, so every visual agrees


def load_model(root):
    """What the model says about its measures (format, expression), so the example values follow the model rather
    than the measure's name: a 0.0% format is a rate, CALCULATE ( [X], SAMEPERIODLASTYEAR ... ) is X last year,
    DIVIDE ( [A], [B] ) is A over B (v1.12: compliance and breaches add up to the whole)."""
    MODEL.clear()
    LABEL_KEY.clear()
    YEARS.clear()
    COLS.clear()
    LABELS.clear()
    _CACHE.clear()
    for p in [pathlib.Path(root), *pathlib.Path(root).parents][:4]:
        spec = p / "design" / "specs"
        if (spec / "contract.json").exists():
            try:
                c = json.loads((spec / "contract.json").read_text(encoding="utf-8"))
                for tn, t in (c.get("tables") or {}).items():
                    MODEL.update({k: v for k, v in (t.get("measures") or {}).items() if isinstance(v, dict)})
                    for k, v in (t.get("columns") or {}).items():
                        COLS.setdefault(k, {**(v if isinstance(v, dict) else {}), "table": tn})
                g = json.loads((spec / "generate.json").read_text(encoding="utf-8")) if (spec / "generate.json").exists() else {}
                MODEL.update({k: v for k, v in (g.get("plannedMeasures") or {}).items() if isinstance(v, dict)})
                for tn, cols in (g.get("plannedColumns") or {}).items():
                    for k, v in (cols or {}).items():
                        COLS[k] = {"type": v.get("dataType", "string"), "expression": v.get("expression", ""), "table": tn}
                _option_labels(c, p)
                for cn, info in list(COLS.items()):    # SWITCH ( key, "k", "Label" ... ): labels with their keys
                    m = re.match(r"\s*SWITCH\s*\(\s*('?[^'\[]*'?\[[^\]]+\])\s*,(.*)\)\s*(//.*)?$", info.get("expression") or "", re.S | re.I)
                    if not m:
                        continue
                    args, depth, cur = [], 0, ""
                    for ch in m.group(2):
                        depth += ch in "(" and 1 or (ch == ")" and -1 or 0)
                        if ch == "," and depth == 0:
                            args.append(cur.strip())
                            cur = ""
                        else:
                            cur += ch
                    args.append(cur.strip())
                    un = lambda x: x.strip().strip('"')
                    pairs = [(un(args[i]), un(args[i + 1])) for i in range(0, len(args) - 1, 2)]
                    if len(args) % 2:                  # the default (OT): a label after the pairs
                        pairs.append((f"(else:{un(args[-1])})", un(args[-1])))
                    if pairs:
                        base = _bare(m.group(1))
                        order = LABELS.get(base) or [k for k, _ in pairs]
                        pairs.sort(key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order))
                        LABELS[cn] = [lab for _, lab in pairs]
                        LABEL_KEY[cn] = {lab: k for k, lab in pairs}
                HINT_WEIGHTS.clear()
                HINT_RATES.clear()
                for tn, h in (g.get("hints") or {}).items():
                    for cn, wd in ((h or {}).get("weights") or {}).items():
                        HINT_WEIGHTS.update({str(k): float(x) for k, x in wd.items()})
                    for cn, dd in ((h or {}).get("derive") or {}).items():
                        labs = list(dict.fromkeys([str(x) for x in (dd.get("map") or {}).values()] +
                                                  ([str(dd["default"])] if dd.get("default") is not None else [])))
                        if labs:
                            LABELS[cn] = sorted(labs)
                    for cn, rd in ((h or {}).get("rates") or {}).items():
                        HINT_RATES[cn] = {str(k): float(x) for k, x in (rd.get("values") or {}).items()}
                    for cn, vals in ((h or {}).get("values") or {}).items():
                        if isinstance(vals, list) and vals:
                            LABELS[cn] = [str(x) for x in vals]
                FACT_ROWS["per_year"] = int(g.get("rowsPerYear") or 6000) if g else None
                rng = g.get("dateRange") or []
                if len(rng) == 2:                  # years from the made-up model's date range
                    YEARS[:] = list(range(int(str(rng[0])[:4]), int(str(rng[1])[:4]) + 1))
            except (OSError, ValueError):
                pass
            return


def _option_labels(c, root):
    """The labels option tables write in their DAX (pbik's synthgen.literal_rows, the same rows the made-up model
    keeps), ordered by their order column: a picker in the picture shows them, not "Metric 1"."""
    import sys
    kit = pathlib.Path(root) / "tools" / "pbik"
    here = pathlib.Path(__file__).resolve().parents[2] / "tools" / "pbik"
    for k in (kit, here):
        if (k / "pbikit").is_dir() and str(k) not in sys.path:
            sys.path.insert(0, str(k))
    try:
        from pbikit import synthgen as SG
    except ImportError:
        return
    for t, tb in (c.get("tables") or {}).items():
        if tb.get("source") != "calculated":
            continue
        try:
            lit = SG.literal_rows(c, t)
        except Exception:                          # a model the parser doesn't follow: no labels, never a failure
            lit = None
        if not lit:
            continue
        types, rows = lit
        cols = rows["columns"]
        order = next((i for i, x in enumerate(cols) if re.search(r"order|sort", x, re.I) and types.get(x) == "int64"), None)
        body = sorted(rows["rows"], key=lambda r: r[order]) if order is not None else rows["rows"]
        for i, x in enumerate(cols):
            if types.get(x) == "string" and not re.search(r"fields", x, re.I) and i != order:
                LABELS.setdefault(x, [str(r[i]) for r in body])


# ---------------------------------------------------------------- a small DAX evaluator for example values
# Only what measures are made of in practice: [Measure], numbers, + - * /, comparisons, && || NOT, VAR / RETURN,
# IF, DIVIDE, ISBLANK, BLANK, ABS, and the column aggregations (their example value per column). Anything else
# (FILTER, SUMX over a table, text) gives up, and the measure keeps its name-based example value.
class _GiveUp(Exception):
    pass


_TOK = re.compile(r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<msr>\[[^\]]+\])|(?P<col>(?:'[^']+'\s*|[A-Za-z_]\w*)\[[^\]]+\])|"
                  r"(?P<str>\"(?:[^\"]|\"\")*\")|(?P<tbl>'[^']+')|(?P<op>&&|\|\||<=|>=|<>|==|[-+*/(),<>=&])|(?P<id>[A-Za-z_][\w.]*))")
AGG = {"AVERAGE", "SELECTEDVALUE", "MIN", "MAX", "MEDIAN", "SUM", "COUNTROWS", "DISTINCTCOUNT", "COUNT", "RELATED"}


def _tokens(expr):
    expr = re.sub(r"(//|--)[^\n]*", "", expr or "")
    out, i = [], 0
    while i < len(expr):
        m = _TOK.match(expr, i)
        if not m or m.end() == i:
            if expr[i:].strip():
                raise _GiveUp(expr[i:i + 20])
            break
        kind = m.lastgroup
        out.append((kind, m.group(kind).strip()))
        i = m.end()
    return out


class _Eval:
    def __init__(self, toks, ctx, env=None):
        self.t, self.i, self.ctx, self.env = toks, 0, ctx, dict(env or {})

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def take(self, val=None):
        tok = self.peek()
        if val is not None and (tok[1] or "").upper() != val:
            raise _GiveUp(f"expected {val}")
        self.i += 1
        return tok

    def program(self):
        while (self.peek()[1] or "").upper() == "VAR":
            self.take()
            name = self.take()[1]
            self.take("=")
            self.env[name] = self.expr()
        if (self.peek()[1] or "").upper() == "RETURN":
            self.take()
        return self.expr()

    def expr(self):
        return self.logic()

    def logic(self):
        a = self.cmp()
        while self.peek()[1] in ("&&", "||"):
            op = self.take()[1]
            b = self.cmp()
            a = (bool(a) and bool(b)) if op == "&&" else (bool(a) or bool(b))
        return a

    def cmp(self):
        a = self.add()
        while self.peek()[1] in ("<", ">", "<=", ">=", "=", "==", "<>"):
            op = self.take()[1]
            b = self.add()
            x, y = (a or 0), (b or 0)
            a = {"<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y, "=": x == y, "==": x == y, "<>": x != y}[op]
        return a

    def add(self):
        a = self.mul()
        while self.peek()[1] in ("+", "-", "&"):
            op = self.take()[1]
            if op == "&":
                raise _GiveUp("text")
            b = self.mul()
            a = None if a is None and b is None else ((a or 0) + (b or 0) if op == "+" else (a or 0) - (b or 0))
        return a

    def mul(self):
        a = self.unary()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            b = self.unary()
            if a is None or b is None:
                a = None
            elif op == "*":
                a = a * b
            else:
                a = a / b if b else None
        return a

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            x = self.unary()
            return None if x is None else -x
        if (self.peek()[1] or "").upper() == "NOT":
            self.take()
            return not self.unary()
        return self.atom()

    def args(self):
        self.take("(")
        out = []
        if self.peek()[1] == ")":
            self.take()
            return out
        while True:
            start = self.i
            out.append((start, None))
            self.skip_arg()
            out[-1] = (start, self.i)
            if self.take()[1] == ")":
                return out
            # a comma: next argument

    def skip_arg(self):
        depth = 0
        while self.i < len(self.t):
            v = self.peek()[1]
            if v == "(":
                depth += 1
            elif v == ")":
                if depth == 0:
                    return
                depth -= 1
            elif v == "," and depth == 0:
                return
            self.i += 1
        raise _GiveUp("unbalanced")

    def sub(self, span):
        e = _Eval(self.t[span[0]:span[1]], self.ctx, self.env)
        e.expect, e.columns = getattr(self, "expect", None), getattr(self, "columns", False)   # SUMX / AVERAGEX rows
        v = e.program()
        if e.i != len(e.t):
            raise _GiveUp("trailing")
        return v

    def atom(self):
        kind, val = self.take()
        if kind == "num":
            return float(val)
        if kind == "msr":
            return value_for(val[1:-1], self.ctx)
        if kind == "col":
            raise _GiveUp("a bare column")
        if kind == "op" and val == "(":
            x = self.expr()
            self.take(")")
            return x
        if kind == "id":
            up = val.upper()
            if up in ("TRUE", "FALSE") and self.peek()[1] == "(":
                self.args()
                return up == "TRUE"
            if self.peek()[1] != "(":
                if val in self.env:
                    return self.env[val]
                raise _GiveUp(f"unknown name {val}")
            spans = self.args()
            if up == "BLANK":
                return None
            if up == "ISBLANK":
                return self.sub(spans[0]) is None
            if up == "ABS":
                x = self.sub(spans[0])
                return None if x is None else abs(x)
            if up == "DIVIDE":
                a, b = self.sub(spans[0]), self.sub(spans[1])
                return (a / b) if (a is not None and b) else (self.sub(spans[2]) if len(spans) > 2 else None)
            if up == "IF":
                c = self.sub(spans[0])
                if getattr(self, "expect", None) and isinstance(c, float) and 0 < c < 1:   # a share: the expected value
                    a_, b_ = self.sub(spans[1]), (self.sub(spans[2]) if len(spans) > 2 else 0)
                    return None if a_ is None or b_ is None else c * a_ + (1 - c) * b_
                if c:
                    return self.sub(spans[1])
                return self.sub(spans[2]) if len(spans) > 2 else None
            if up in AGG and len(spans) == 1 and spans[0][1] - spans[0][0] == 1 and self.t[spans[0][0]][0] == "col":
                return column_value(self.t[spans[0][0]][1], up, self.ctx)
            if up == "CALCULATE" and len(spans) >= 2 and spans[0][1] - spans[0][0] == 1 and self.t[spans[0][0]][0] == "msr":
                drop = set()
                for sp in spans[1:]:
                    toks = self.t[sp[0]:sp[1]]
                    if len(toks) >= 4 and toks[0][1].upper() in ("REMOVEFILTERS", "ALL") and toks[2][0] in ("tbl", "id", "col"):
                        ref = toks[2][1]
                        tbl = ref.strip("'") if toks[2][0] != "col" else None
                        cols = [c for c, i in COLS.items() if i.get("table") == tbl] if tbl else [_bare(ref)]
                        drop |= {tuple(members_of(c, 6)) for c in cols}
                    else:
                        raise _GiveUp("a CALCULATE filter")
                ctx2 = tuple(e for e in self.ctx if e[1] not in drop)
                return value_for(self.t[spans[0][0]][1][1:-1], ctx2)
            if up == "SUMX" and len(spans) == 2 and self.t[spans[0][0]][0] in ("tbl", "id"):
                tbl = self.t[spans[0][0]][1].strip("'")
                rows = _rows_measure(tbl)
                n = value_for(rows, self.ctx) if rows else None
                if not isinstance(n, (int, float)):
                    raise _GiveUp("SUMX rows")
                e = _Eval(self.t[spans[1][0]:spans[1][1]], self.ctx, self.env)
                e.expect = tbl
                per = e.program()
                return None if per is None else n * per
            if up == "AVERAGEX" and len(spans) == 2:          # AVERAGEX ( T, a - b ): the columns' typical values
                e = _Eval(self.t[spans[1][0]:spans[1][1]], self.ctx, self.env)
                e.columns = True
                return e.program()
            raise _GiveUp(f"function {val}")
        raise _GiveUp(f"token {val}")


def _col_atom(self, _orig=_Eval.atom):
    """Inside AVERAGEX, a column stands for its typical value; RELATED ( col ) too. Inside SUMX (`expect`), a 0/1
    outcome column stands for its rate and `col = "label"` for that label's share."""
    if getattr(self, "expect", None):
        kind, val = self.peek()
        if kind == "col":
            m = COLREF.match(val)
            col = m.group(2) if m else val
            nxt = self.t[self.i + 1] if self.i + 1 < len(self.t) else (None, None)
            if nxt[1] in ("=", "==") and self.i + 2 < len(self.t) and self.t[self.i + 2][0] == "str":
                self.i += 3                               # col = "label": the label's share of the rows
                lab = self.t[self.i - 1][1].strip('"')
                mems = members_of(col, 6)
                return share(lab, tuple(mems)) if lab in mems else 1 / max(len(mems), 1)
            self.take()
            if OUTCOME.search(col):
                rows = _rows_measure(self.expect)
                whole = value_for(rows, self.ctx) if rows else None
                made = column_value(val, "SUM", self.ctx)
                return made / whole if whole and isinstance(made, (int, float)) else 0.45
            return column_value(val, "AVERAGE", self.ctx)
    if getattr(self, "columns", False):
        kind, val = self.peek()
        if kind == "col":
            self.take()
            return column_value(val, "AVERAGE", self.ctx)
    return _orig(self)


_Eval.atom = _col_atom
COLREF = re.compile(r"^\s*'?([^'\[]*?)'?\s*\[([^\]]+)\]\s*$")


def column_value(ref, agg, ctx=()):
    """The example value of an aggregation of one column (AVERAGE, SELECTEDVALUE, MEDIAN, SUM, COUNTROWS ...):
    durations a few days, thresholds (SLA, target, limit) above them, a median below the average (skewed)."""
    m = COLREF.match(ref)
    col = m.group(2) if m else ref
    ck = ctx_key(ctx)
    if agg == "SUM" and OUTCOME.search(col) and (COLS.get(col) or {}).get("type") in ("int64", "integer", "boolean", None):
        tbl = (m.group(1).strip("'") if m else None) or (COLS.get(col) or {}).get("table")
        rows = _rows_measure(tbl) if tbl else None
        whole = value_for(rows, ctx) if rows else None
        if isinstance(whole, (int, float)):            # a 0/1 outcome: the rows where it is 1
            rates = HINT_RATES.get(col) or {}
            if rates:                                   # per-member rates from the hint (an area's own rate)
                byr = [(i, mm) for i, (mm, _) in enumerate(ctx) if str(mm) in rates]
                if byr:
                    part = rates[str(byr[0][1])]
                else:                                   # the mix's rate: the members' rates by their weights
                    ws = {k: HINT_WEIGHTS.get(k, 1.0) for k in rates}
                    part = sum(rates[k] * ws[k] for k in rates) / (sum(ws.values()) or 1)
                for i, (mm, sib) in enumerate(ctx):     # a team or player: small moves, some areas up, some down
                    if str(mm) in rates:
                        others = "|".join(str(x) for x, _ in ctx[:i]) or "-"
                        if others != "-":
                            part += random.Random(f"rate/{col}/{others}/{mm}").uniform(-0.06, 0.06)
                    else:
                        part += random.Random(f"rate/{col}/{mm}").uniform(-0.02, 0.02)
                return float(round(whole * min(max(part, 0.02), 0.98)))
            base = random.Random(f"outcome/{col.lower()}").uniform(0.38, 0.52)
            return float(round(whole * min(max(base + sum(_jit(col, mm, sib, "|".join(str(x) for x, _ in ctx[:i]))
                                                             for i, (mm, sib) in enumerate(ctx)), 0.02), 0.98)))
    rnd = random.Random(f"col/{col.lower()}/{agg if agg in ('SUM', 'COUNTROWS', 'DISTINCTCOUNT', 'COUNT') else 'avg'}")
    jit = random.Random(f"col/{col.lower()}/{ck}").uniform(0.82, 1.18) if ctx else 1
    whole = (COLS.get(col) or {}).get("type") in ("int64", "integer") or THRESH.search(col)
    if THRESH.search(col):                         # an SLA, target or limit: whole days, above the typical duration
        v = round(rnd.uniform(6, 10))
        return float(v if not ctx else max(1, round(v * random.Random(f"col/{col}/{ck}").uniform(0.8, 1.2))))
    if DAYS.search(col):
        v = rnd.uniform(3.2, 5.6) * jit
        if agg == "MEDIAN":                        # durations are right-skewed: the median sits below the average
            v *= random.Random(f"median/{col.lower()}").uniform(0.55, 0.75)
        return round(v) if whole and agg not in ("AVERAGE", "MEDIAN") else round(v, 2)
    if agg in ("COUNTROWS", "COUNT", "DISTINCTCOUNT"):
        raise _GiveUp("a count")                   # counts follow the measure (the table's rows), not a column
    v = rnd.uniform(20, 90) * jit
    return round(v) if whole else round(v, 2)


OUTCOME = re.compile(r"^(made|won|win|hit|converted|success|scored|is |has |completed?)\b|\b(made|won|hit|flag)$", re.I)
THRESH = re.compile(r"\b(sla|target|threshold|goal|limit|budget|quota)\b", re.I)
WITHIN = re.compile(r"within|on time|in sla|resolved|\bmet\b|success|complete|kept|retained|passed|\bok\b", re.I)
FLAG = re.compile(r"^(within|on[ -]time|in sla|met|is|has|was)\b", re.I)    # a yes / no column ("Within SLA")
ROWS = re.compile(r"COUNTROWS\s*\(\s*'?([^')]+?)'?\s*\)", re.I)


def ctx_key(ctx):
    return "|".join(str(m) for m, _ in ctx)


def _rows_measure(table):
    """The measure that is just COUNTROWS ( 'table' ), if the model has one (the whole the subsets are parts of)."""
    best = None
    for k, v in MODEL.items():
        e = re.sub(r"\s+", "", re.sub(r"(//|--)[^\n]*", "", v.get("expression", "")))
        if re.fullmatch(rf"COUNTROWS\('?{re.escape(table)}'?\)", e, re.I):
            if best is None or (re.match(r"^[\d_]", best) and not re.match(r"^[\d_]", k)):
                best = k
    return best


def _jit(name, member, siblings, others=""):
    """A member's own move away from the whole's share; centred (weighted by the members' shares) over its siblings,
    so a category's within-SLA count is the sum of its channels' (the matrix adds up to the list)."""
    k = 0.35 if isinstance(siblings, tuple) and set(siblings) <= set(MONTHS) else 1   # months move less than categories
    # a member's own move (the same under any parent: an area's pattern for a team and for the league) plus a small
    # move of its own within its parent (a team's area differs a little from the league's)
    raw = lambda m: k * (random.Random(f"part/{_key(name)}/{m}").uniform(-0.16, 0.13)
                         + (0.25 * random.Random(f"part/{_key(name)}/{others}/{m}").uniform(-0.16, 0.13) if others else 0))
    if not isinstance(siblings, tuple):
        return raw(member)
    return raw(member) - sum(share(m, siblings, None, others) * raw(m) for m in siblings)


def model_value(name, ctx):
    """The measure's value from its DAX (None when the evaluator gives up)."""
    expr = (MODEL.get(name) or {}).get("expression")
    if not expr:
        return None
    flat = re.sub(r"\s+", "", re.sub(r"(//|--)[^\n]*", "", expr))
    rows = ROWS.search(expr)
    if rows and not re.fullmatch(r"COUNTROWS\('?[^')]+'?\)", flat, re.I):
        parent = _rows_measure(rows.group(1))       # a filtered count: a share of the table's rows (within SLA ...)
        if parent and parent != name:
            whole = value_for(parent, ctx)
            if isinstance(whole, (int, float)):
                base = random.Random(f"part/{_key(name)}").uniform(0.78, 0.9) if WITHIN.search(name) else \
                    random.Random(f"part/{_key(name)}").uniform(0.25, 0.6)
                part = base + sum(_jit(name, m, sib, "|".join(str(x) for x, _ in ctx[:i])) for i, (m, sib) in enumerate(ctx))
                return float(round(whole * min(max(part, 0.03), 0.98)))
    if re.fullmatch(r"COUNTROWS\('?[^')]+'?\)", flat, re.I):
        if FACT_ROWS["per_year"] and YEARS:               # the made-up model's volume: rows per year x years, split
            v = float(FACT_ROWS["per_year"] * len(YEARS))
            for i, (mem, sib) in enumerate(ctx):
                v *= share(mem, sib, name, "|".join(str(x) for x, _ in ctx[:i]))   # as _plain splits a count
            return float(round(v))
        return None                                  # the table's rows: the name-based count, shared by its twins
    try:
        e = _Eval(_tokens(expr), ctx)
        v = e.program()
        if e.i != len(e.t):
            return None
        return None if isinstance(v, bool) else v
    except (_GiveUp, ZeroDivisionError, RecursionError, IndexError, TypeError):
        return None


def is_pct(name):
    f = (MODEL.get(name) or {}).get("formatString")
    return "%" in f if f else bool(PCT.search(name or ""))


def ly_base(name):
    """The measure a last-year measure shifts, from its DAX when the model has it, else from its name."""
    m = SPLY.match((MODEL.get(name) or {}).get("expression", ""))
    if m:
        return m.group(1)
    if (MODEL.get(name) or {}).get("expression") or CMP_WORDS.search(name or ""):
        return None                                  # the model says what it is; "vs PY" is a change, not last year
    if LY.search(name or ""):
        base = LY.sub("", name).strip(" _-")
        return base if base else None
    return None


def contract_measures(root):
    """Measure names from design/specs/contract.json (the approved model contract), if the project has one."""
    for p in [pathlib.Path(root), *pathlib.Path(root).parents][:4]:
        f = p / "design" / "specs" / "contract.json"
        if f.exists():
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                return set()
            tabs = c.get("tables") or {}
            items = tabs.items() if isinstance(tabs, dict) else ((t.get("name"), t) for t in tabs)
            return {m for _, t in items for m in (t.get("measures") or {})}
    return set()


def is_measure(field, role=None, measures=None):
    """A bound field is a measure when the model contract says so, it is written [Name], or its table is a measure
    table (_Measures); a Data or Y binding without a table is one too. Columns keep their table: T[C]."""
    f = str(field or "")
    m = re.match(r"^'?([^'\[]*)'?\[(.+)\]$", f)
    if not m:
        return "(" in f
    table, name = m.group(1), m.group(2)
    if measures and name in measures:
        return True
    if not table:
        return True
    return bool(MEASURE_TABLE.search(table))


def fmt_for(name):
    f = (MODEL.get(name) or {}).get("formatString")
    if f and f not in ("0", "General"):
        return f
    if is_pct(name):
        return "+0.0%;-0.0%;0.0%" if re.search(r"\bvs\b|growth|change", name, re.I) else "0.0%"
    if AVG.search(name or ""):
        return "#,0.00"
    return "#,0"


CMP_WORDS = re.compile(r"\bvs\b|change|growth|variance|\bdiff|delta|\byoy\b", re.I)
LY = re.compile(r"\b(LY|PY|last year|prior|previous)\b", re.I)
SMALL = re.compile(r"return|refund|cost|discount|claim|breach|late|overdue|fail|error|backlog", re.I)


def _key(name):
    """The measure a name stands for: last-year versions share their base measure's numbers."""
    key = LY.sub("", name or "").strip(" _-[]").lower()
    return re.sub(r"^(fact|total|sum of)\s+", "", key)


def value_for(name, ctx=()):
    """A measure's value in a filter context (ctx: ((member, siblings), ...), () for the total), the same for the same
    measure and context in every visual. The model's DAX decides when it can (v1.12): a ratio is its parts divided,
    a breach count is the rows less those within SLA; otherwise the name does. A last-year version is its base
    measure's value moved by a seeded amount (never equal to this year, so the change shown agrees)."""
    if not isinstance(ctx, tuple):
        ctx = ()
    key = (name, ctx)
    if key in _CACHE:
        return _CACHE[key]
    _CACHE[key] = None                               # a measure that (indirectly) refers to itself: blank
    _CACHE[key] = _value(name, ctx)
    return _CACHE[key]


def _value(name, ctx):
    src = ly_base(name)
    if src and src != name:
        base = value_for(src, ctx) if src in MODEL else _plain(name, ctx)
        if not isinstance(base, (int, float)):
            return base
        r = random.Random("ly/" + _key(name) + ("/" + ctx_key(ctx) if ctx else ""))
        if is_pct(src if src in MODEL else name):
            return round(min(base - (r.uniform(-0.03, 0.05) if ctx else r.uniform(-0.012, 0.025)), 0.999), 4)
        v = base * r.uniform(0.86, 1.04)
        return round(v, 2) if (AVG.search(name or "") or DAYS.search(name or "")) else float(round(v))
    v = model_value(name, ctx)
    if isinstance(v, (int, float)):
        return round(v, 6)
    return _plain(name, ctx)


def _plain(name, ctx):
    """The name-based value: the total, split over the context (a part for counts and sums, a nearby value for rates,
    averages and durations)."""
    total = _base_value(name)
    if not ctx or not isinstance(total, (int, float)):
        return total
    v = total
    for i, (mem, n) in enumerate(ctx):
        if is_pct(name) or AVG.search(name) or DAYS.search(name):
            v *= random.Random(f"{_key(name)}/{mem}").uniform(0.8, 1.2)
        else:
            others = "|".join(str(m) for m, _ in ctx[:i])     # varies with the members outside it: parts still add up
            v *= share(mem, n, name, others)
    if float(total).is_integer() and not (is_pct(name) or AVG.search(name) or DAYS.search(name)):
        return float(round(v))                       # a count's part is a whole number
    return round(v, 4 if is_pct(name) else 2)


def change_text(cur, ly, pct_points=False):
    """(text, sign) for the change from last year to this year, computed from the two shown values."""
    if cur is None or ly is None:
        return "", 0
    x = (cur - ly) if pct_points else ((cur - ly) / ly if ly else 0)
    if abs(x) < 0.0005:
        return "no change", 0
    txt = f"{abs(x) * 100:.1f} pts" if pct_points else format_value(abs(x), "0.0%")
    return ("▲ " if x > 0 else "▼ ") + txt, (1 if x > 0 else -1)


def _base_value(name):
    rnd = random.Random("total/" + _key(name))
    if is_pct(name):
        return round(rnd.uniform(-0.08, 0.12) if re.search(r"\bvs\b|growth|change", name, re.I)
                     else rnd.uniform(0.08, 0.35), 4)
    if DAYS.search(name or ""):                  # days to resolve, SLA days: a few, not thousands
        return round(rnd.uniform(2, 12), 2 if AVG.search(name or "") else 0)
    if AVG.search(name or ""):
        return round(rnd.uniform(20, 90), 2)
    scale = 0.12 if SMALL.search(name or "") else 1
    if COUNT.search(name or ""):
        return float(round(rnd.randint(8_000, 40_000) * scale))
    return float(round(rnd.randint(900_000, 2_400_000) * scale))


def _w(category):
    return random.Random("w/" + str(category)).uniform(0.6, 1.4)


def _bin_weight(category, siblings):
    """Whole-day bins: right-skewed, most rows in the first few days (a log-normal shape)."""
    import math
    x = float(category) + 0.5
    return math.exp(-((math.log(x) - 1.2) ** 2) / (2 * 0.55 ** 2)) / x


def share(category, n_cats, name=None, others=""):
    """The part of a total that one category holds: weights seeded by the category, summing to 1 over its siblings
    when they are known (n_cats a tuple of the members: the cells of a matrix add up to its row, v1.12)."""
    if isinstance(n_cats, tuple) and n_cats and all(str(c) in HINT_WEIGHTS for c in n_cats):
        hw = lambda c: HINT_WEIGHTS[str(c)] * (random.Random(f"hw/{c}/{others}").uniform(0.85, 1.15) if others else 1)
        return hw(category) / (sum(hw(c) for c in n_cats) or 1)
    if isinstance(n_cats, tuple) and n_cats and all(re.fullmatch(r"\d+", str(c)) for c in n_cats):
        return _bin_weight(category, n_cats) / (sum(_bin_weight(c, n_cats) for c in n_cats) or 1)
    if isinstance(n_cats, tuple):
        w = (lambda c: _w(c) * random.Random(f"w/{c}/{others}").uniform(0.75, 1.25)) if others else _w
        return w(category) / (sum(w(c) for c in n_cats) or 1)
    return _w(category) / n_cats


def categories(label, n=6):
    low = (label or "").lower()
    if "month" in low or low in ("date", "period"):
        return MONTHS[:max(n, 12)][:12]
    if "year" in low:
        ys = YEARS or list(range(2021, 2026))
        return [str(y) for y in ys[-min(n, 5):]] if len(ys) >= min(n, 5) else [str(y) for y in ys]
    if "quarter" in low:
        return ["Q1", "Q2", "Q3", "Q4"]
    base = re.sub(r"\s*(name|key|label)$", "", label or "Item", flags=re.I).strip() or "Item"
    return [f"{base} {i + 1}" for i in range(n)]


def _bare(f):
    return re.sub(r"^.*\[|\]\)?$", "", str(f or ""))


def members_of(col, n=6):
    if DAYS.search(col or "") and n == 13:          # a histogram over a days column: whole-day bins
        return [str(i) for i in range(1, 14)]
    """The members a column shows: a planned "top N + Other" column its base column's top N and Other (v1.12),
    otherwise categories() by the column's name (the same names in every visual: slicer, chart, matrix)."""
    if col in LABELS:                              # an option table's own labels, in its order
        return list(LABELS[col])
    info = COLS.get(col) or {}
    expr = info.get("expression") or ""
    if '"Other"' in expr:
        top = re.search(r"TOPN\s*\(\s*(\d+)", expr, re.I) or re.search(r"_rank\s*<=\s*(\d+)", expr, re.I)
        base = next((c for c in re.findall(r"\[([^\]]+)\]", expr) if c != col and c in COLS
                     and (COLS[c].get("type") or "string") == "string"), None)
        k = int(top.group(1)) if top else 4
        if base in LABELS:                         # the option table's own labels: Other only when there are more
            return LABELS[base][:k] + (["Other"] if len(LABELS[base]) > k else [])
        return categories(base or col, k) + ["Other"]
    return categories(col, n)


def column_example(col, i, row, seed=""):
    """One cell of a detail table (a column, not a measure), as Desktop shows it by default: typed like the column
    (whole numbers, days with a decimal, dates as M/d/yyyy, a dateTime with its time), and agreeing with the rest of
    its row (resolved after received, "within" Yes only when the days are inside the threshold)."""
    info = COLS.get(col) or {}
    typ = (info.get("type") or "string").lower()
    r = random.Random(f"cell/{col}/{seed}/{i}")
    low = col.lower()
    if re.search(r"\bid\b|number|\bno\b|key|code|\bref\b", low) and typ in ("int64", "integer", "double", "string"):
        return str(100000 + i * 37 + r.randint(0, 30))
    if FLAG.search(col):
        days = next((float(x) for k, x in row.items() if DAYS.search(k) and not THRESH.search(k)
                     and re.fullmatch(r"[\d.]+", str(x))), None)
        lim = next((float(x) for k, x in row.items() if THRESH.search(k) and re.fullmatch(r"[\d.]+", str(x))), None)
        ok = days <= lim if days is not None and lim is not None else r.random() < 0.8
        return "Yes" if ok else "No"
    if THRESH.search(col):
        return str(int(column_value(col, "SELECTEDVALUE", ((f"row{i}", 9),))))   # (a threshold, after "within")
    if DAYS.search(col) and typ not in ("datetime", "date"):
        return f"{max(0.2, r.lognormvariate(1.3, 0.75)):.1f}" if typ in ("double", "decimal") else str(r.randint(1, 14))
    if typ in ("datetime", "date") or re.search(r"\bdate\b|received|resolved|opened|closed", low):
        import datetime as _dt
        start = _dt.date(2025, 1, 1) + _dt.timedelta(days=random.Random(f"day/{seed}/{i}").randint(0, 330))
        if re.search(r"resolv|close|end|finish|complet|shipped|due", low):
            days = next((float(x) for k, x in row.items() if DAYS.search(k) and not THRESH.search(k)
                         and re.fullmatch(r"[\d.]+", str(x))), r.uniform(1, 8))
            start += _dt.timedelta(days=round(days + 0.49))
        fs = info.get("formatString") or ""
        if re.search(r"h|n:|ss", fs, re.I) and "general" in fs.lower():
            return f"{start.month}/{start.day}/{start.year} 12:00:00 AM"
        return f"{start.month}/{start.day}/{start.year}"     # the made-up model's short date (v1.12)
    if typ in ("int64", "integer", "double", "decimal"):
        return str(r.randint(1, 99))
    mems = members_of(col, 6)
    return mems[r.randrange(len(mems))]


def _passes(val, op, lim):
    if val is None:
        return False
    return {">": val > lim, ">=": val >= lim, "<": val < lim, "<=": val <= lim, "=": val == lim,
            "==": val == lim, "<>": val != lim, "!=": val != lim}.get(op, True)


def _gradient(lo_c, hi_c, f):
    a = [int(lo_c[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hi_c[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * f):02X}" for x, y in zip(a, b))


def _row_order(col):
    """Fill a detail row's cells so the ones that depend on others come last (resolved after received and days,
    "within" after the days and the threshold)."""
    return (bool(re.search(r"resolv|close|end|finish|complet|within|^(is|has|was)\s", col, re.I)),)


def for_visual(v, measures=None, colors=None, fixed=()):
    """The wireframe data entry (as wireframe_data.py writes it) for one visual, with example values. `fixed`: the
    filter context the whole page has (a drill-through page: the member drilled into), so its numbers are that
    member's, not the whole report's (v1.12)."""
    groups, values, names, group_roles, gcols = [], [], [], [], []
    for role, b in (v.get("bindings") or {}).items():
        if role in ("Tooltips", "Details") and v.get("type") != "scatterChart":             # tooltip fields aren't drawn; details are the points, not a series
            continue
        for it in b if isinstance(b, list) else [b]:
            it = it if isinstance(it, dict) else {"field": it}
            fld = it.get("field") or it.get("fieldParameter") or ""
            label = it.get("displayName") or _bare(fld)
            if is_measure(fld, role, measures):
                values.append(label)
                names.append(_bare(fld) or label)
            else:
                groups.append(label)
                group_roles.append(role)
                gcols.append(_bare(fld) or label)
    if not values and not groups:
        return None
    t = v.get("type", "")
    one = t in ("cardVisual", "card", "kpi", "gauge") or not groups
    base = tuple(fixed or ())
    for f in v.get("filters") or []:              # a visual filtered to one member (a panel): that member's numbers
        vals = f.get("values")
        if isinstance(vals, list) and len(vals) == 1 and not str(f.get("field", "")).startswith("[") and f.get("type") != "TopN":
            col = _bare(f.get("field"))
            base = base + ((str(vals[0]), tuple(members_of(col, 6))),)
    rows, ctxs = [], []
    detail = t == "tableEx" and len(groups) > 1 and not any(r in ("Series", "Legend", "Columns") for r in group_roles)
    leg = None
    if one:
        rows.append([value_for(x, base) for x in names])
        ctxs.append(base)
    elif detail:                                  # a detail table: one example row per item, every column filled
        n = 14
        for i in range(n):
            cells = {}
            for col in sorted(gcols, key=_row_order):
                cells[col] = column_example(col, i, cells, seed=v.get("id", ""))
            row = [cells[c] for c in gcols]
            ctx = base + ((f"row {i}", tuple(f"row {j}" for j in range(n))),)
            row += [None if value_for(x, ctx) is None else round(value_for(x, ctx), 4 if is_pct(x) else 2) for x in names]
            rows.append(row)
            ctxs.append(ctx)
    else:
        n0 = v.get("items") if isinstance(v.get("items"), int) else (12 if "month" in gcols[0].lower() else 6)
        if (v.get("props") or {}).get("categoryAxis.axisType") == "Scalar" and DAYS.search(gcols[0]):
            n0 = 13                                # a continuous days axis: bins 0 to 12
        if isinstance(v.get("items"), list) and gcols[0] not in LABELS:
            n0 = len(v["items"])
        cats = members_of(gcols[0], n0)
        pin = next((f["values"] for f in v.get("filters") or [] if _bare(f.get("field")) == gcols[0]
                    and isinstance(f.get("values"), list) and f.get("type") != "TopN"), None)
        if pin:                                    # filtered to its own members (a panel's bar): only those rows
            cats = [c for c in cats if c in [str(x) for x in pin]] or [str(x) for x in pin]
        # a legend / matrix column field splits each category into members (stacked columns, a matrix's columns)
        leg = next((i for i, r in enumerate(group_roles) if r in ("Series", "Legend", "Columns") and i > 0), None)
        mems = members_of(gcols[leg], 4) if leg is not None else [None]
        keyed = LABEL_KEY.get(gcols[0]) or {}
        kcats = tuple(keyed.get(x, x) for x in cats)
        for c, mem in ((c, m) for c in cats for m in mems):
            row = [c] + [None] * (len(groups) - 1)
            ctx = base + ((keyed.get(c, c), kcats),) + (((mem, tuple(mems)),) if mem else ())
            if leg is not None:
                row[leg] = mem
            for x in names:
                val = value_for(x, ctx)
                row.append(None if val is None else round(val, 4 if is_pct(x) else 2))
            rows.append(row)
            ctxs.append(ctx)
    nG = 0 if one else len(groups)
    if not one:
        # the visual's own measure filters (an exception list's rule) keep only the rows that pass, as Desktop does
        keep = []
        for row, ctx in zip(rows, ctxs):
            ok = True
            for f in v.get("filters") or []:
                fn = _bare(f.get("field"))
                if not (str(f.get("field", "")).startswith("[") or fn in MODEL) or not isinstance(f.get("value"), (int, float)):
                    continue
                val = row[nG + names.index(fn)] if fn in names else value_for(fn, ctx)
                ok = ok and _passes(val, f.get("op", ">"), f["value"])
            keep.append(ok)
        rows = [r for r, k in zip(rows, keep) if k]
        ctxs = [c for c, k in zip(ctxs, keep) if k]
        topn = next((f for f in v.get("filters") or [] if f.get("type") == "TopN"), None)
        if topn and names:                           # Top N by a measure: the N biggest, biggest first
            by = _bare(topn.get("by"))
            k = nG + names.index(by) if by in names else nG
            pairs = sorted(zip(rows, ctxs), key=lambda p: -(p[0][k] or 0))[:int(topn.get("n", 5))]
            rows, ctxs = [p[0] for p in pairs], [p[1] for p in pairs]
        srt = v.get("sort") if isinstance(v.get("sort"), dict) else None
        sk = _bare(srt.get("field")) if srt else None
        num = lambda x: float(x) if isinstance(x, (int, float)) or re.fullmatch(r"-?[\d.]+", str(x or "")) else None
        if sk and (sk in names or sk in gcols) and leg is None:
            k = nG + names.index(sk) if sk in names else gcols.index(sk)
            desc = str(srt.get("direction", "Descending")).lower().startswith("desc")
            if k >= nG or num(rows[0][k] if rows else None) is not None:     # months and names keep their order
                pairs = sorted(zip(rows, ctxs), key=lambda p: (num(p[0][k]) is None,
                                                               -(num(p[0][k]) or 0) if desc else (num(p[0][k]) or 0)))
                rows, ctxs = [p[0] for p in pairs], [p[1] for p in pairs]
        elif t in ("barChart", "clusteredBarChart", "columnChart", "clusteredColumnChart", "tableEx") and values \
                and "month" not in gcols[0].lower() and leg is None and not detail:
            pairs = sorted(zip(rows, ctxs), key=lambda p: -(p[0][nG] or 0))      # ranked, as the plan usually asks
            rows, ctxs = [p[0] for p in pairs], [p[1] for p in pairs]
    if not one and gcols and gcols[0] in LABELS and "slicer" in t.lower():
        out_items = [r[0] for r in rows]           # a picker on an option table: the model's labels win (kept)
    else:
        out_items = None
    if t == "custom" and v.get("pattern") == "spatial-canvas":
        b = v.get("bindings") or {}
        zcol = _bare(b.get("Zone"))
        rate = _bare(v.get("zoneRate") or "")
        bench = _bare(b.get("Benchmark") or "")
        if zcol and rate:
            zs = members_of(zcol, 10)
            zones = {}
            for z in zs:
                ctx = base + ((z, tuple(zs)),)
                r_, b_ = value_for(rate, ctx), (value_for(bench, ctx) if bench else None)
                zones[z] = {"rate": r_, "bench": b_}
            return {"groups": [], "values": [], "formats": [], "rows": [], "counts": [], "hidden": 0, "total": 0,
                    "example": True, "zones": zones,
                    "span": float((v.get("props") or {}).get("space.benchmarkSpan@none") or 0.1)}
    out = {"groups": [] if one else groups, "values": values, "formats": [fmt_for(x) for x in names],
           "cat": 0, "leg": None if one else leg, "rows": rows, "counts": [99] * len(rows), "hidden": 0, "total": len(rows),
           "example": True}
    if out_items:
        out["items"] = out_items
    colors = colors or {}
    for c in v.get("cf", []) or []:              # a coloured column, as its colour measure does
        if c.get("type") != "measure" or c.get("property") != "fontColor" or one:
            continue
        tgt = _bare(c.get("target"))
        if tgt not in names:
            continue
        k = nG + names.index(tgt)
        lower = bool(c.get("lowerIsBetter"))
        good, bad = colors.get("good", "#197982"), colors.get("bad", "#B94642")
        cm = _bare(c.get("measure"))
        rule = re.search(r"\[" + re.escape(tgt) + r"\]\s*(>=|<=|>|<)\s*(-?[\d.]+)\s*,\s*\"(#[0-9A-Fa-f]{6})\"\s*,\s*\"(#[0-9A-Fa-f]{6})\"",
                         (MODEL.get(cm) or {}).get("expression", ""))
        if rule:                                  # IF ( [X] > 0.2, "#bad", "#text" ): the measure's own threshold
            op, lim, hit, miss = rule.group(1), float(rule.group(2)), rule.group(3), rule.group(4)
            out["fonts"] = [None if r[k] is None else (hit if _passes(r[k], op, lim) else miss) for r in rows]
        else:                                     # a "vs" column coloured by direction
            out["fonts"] = [None if r[k] is None else (good if (r[k] >= 0) != lower else bad) for r in rows]
        out.setdefault("fontsBy", {})[values[names.index(tgt)]] = out["fonts"]
        out["fontTarget"] = values[names.index(tgt)]
    for c in v.get("cf", []) or []:              # a threshold histogram: bins within in colour, beyond in grey
        sp = c.get("split") if isinstance(c.get("split"), dict) else None
        if not sp or one or not rows:
            continue
        at = value_for(_bare(sp.get("at")), base)
        tok = lambda x: x if str(x or "").startswith("#") else colors.get(x)
        num = lambda x: float(x) if re.fullmatch(r"-?[\d.]+", str(x)) else None
        out["colours"] = [tok(sp.get("within")) if (num(r[0]) is not None and at is not None and num(r[0]) <= at)
                          else tok(sp.get("beyond", "outSla")) or "#C5CCD8" for r in rows]
    for c in v.get("cf", []) or []:              # a heat gradient: each cell between the two colours (v1.12)
        if c.get("type") != "gradient" or one:
            continue
        tgt = _bare(c.get("target") or c.get("field"))
        if tgt not in names:
            continue
        k = nG + names.index(tgt)
        nums = [r[k] for r in rows if isinstance(r[k], (int, float))]
        if not nums:
            continue
        lo, hi = min(nums), max(nums)
        tok = lambda x, d: x if str(x or "").startswith("#") else colors.get(x or d)
        lo_c, hi_c = tok(c.get("min"), "card"), tok(c.get("max"), "bad")
        if not (isinstance(lo_c, str) and isinstance(hi_c, str) and lo_c.startswith("#") and hi_c.startswith("#")):
            continue
        mid_c = tok(c.get("mid"), None)
        mv = c.get("midValue")

        def shade(x):
            if isinstance(mid_c, str) and mid_c.startswith("#") and mv is not None:   # diverging around midValue
                if x < mv:
                    return _gradient(mid_c[:7], lo_c[:7], min(1, (mv - x) / ((mv - lo) or 1)))
                return _gradient(mid_c[:7], hi_c[:7], min(1, (x - mv) / ((hi - mv) or 1)))
            return _gradient(lo_c[:7], hi_c[:7], (x - lo) / (hi - lo) if hi > lo else 1)
        cols = [None if not isinstance(r[k], (int, float)) else shade(r[k]) for r in rows]
        if c.get("property") == "fontColor":
            out.setdefault("fontsBy", {})[values[names.index(tgt)]] = cols
            out["fontTarget"] = values[names.index(tgt)]
        else:
            out["backs"] = cols
            out["backTarget"] = values[names.index(tgt)]
    rl = v.get("referenceLabels")
    if isinstance(rl, dict) and rl.get("labels"):
        out["refs"], out["refDetails"] = [], []
        for lab in rl["labels"]:
            name = _bare(lab.get("value", ""))
            if lab.get("chip"):                   # a change chip: its text on its tint, green / red by the polarity
                text = preview_text(lab.get("preview") or "", ctx=base)
                cur, ly = value_for(names[0], base) if names else None, value_for(name, base)
                sign = 0 if not isinstance(cur, (int, float)) or not isinstance(ly, (int, float)) else (cur > ly) - (cur < ly)
                good = None if sign == 0 else (sign > 0) != bool(lab.get("lowerIsBetter"))
                out["refs"].append("")
                out["refDetails"].append({"text": text, "good": good, "chip": True})
                continue
            if lab.get("preview"):                # a text measure (a plain line such as "5.0 days under the SLA")
                out["refs"].append(preview_text(lab["preview"], ctx=base))
            else:
                out["refs"].append(format_value(value_for(name, base), fmt_for(name)))
            det = _bare(lab.get("detail", "") or "")
            if det:                               # the change beside it, computed from the two values shown
                cur = value_for(names[0], base) if names else None
                ly = value_for(name, base)
                if ly_base(name) and isinstance(cur, (int, float)) and isinstance(ly, (int, float)):
                    text, sign = change_text(cur, ly, pct_points=is_pct(names[0]))   # a rate moves in points
                elif CMP_WORDS.search(det) and isinstance(cur, (int, float)) and isinstance(ly, (int, float)):
                    # against a target or threshold (the SLA, a budget): the difference in the card's own units
                    x = cur - ly
                    sign = 1 if x > 0 else -1 if x < 0 else 0
                    shown = f"{abs(x) * 100:.1f} pts" if is_pct(names[0]) else format_value(abs(x), fmt_for(names[0]).lstrip("+"))
                    text = "no change" if sign == 0 else ("▲ " if sign > 0 else "▼ ") + shown
                else:
                    x = value_for(det, base) or 0
                    text = ("▲ " if x >= 0 else "▼ ") + format_value(abs(x), "0.0%") if PCT.search(det) or \
                        CMP_WORDS.search(det) else format_value(x, fmt_for(det))
                    sign = 1 if x > 0 else -1 if x < 0 else 0
                good = None if sign == 0 else (sign > 0) != bool(lab.get("lowerIsBetter"))   # a fall is good for costs
                out["refDetails"].append({"text": text, "good": good if lab.get("detailColor") else None})
            else:
                out["refDetails"].append(None)
    # one accent (dark glass rule): a cf colour measure with `emphasis: "top"` paints the top item in the accent, the
    # rest muted; the rows are ranked, so the top item is the first
    for c in v.get("cf", []) or []:
        if c.get("emphasis") in ("top", "last") and rows and not one:
            k_ = nG if names else None
            vals_ = [r[k_] if k_ is not None and isinstance(r[k_], (int, float)) else None for r in rows]
            okv = [x for x in vals_ if x is not None]
            if okv:                                   # the best (or worst) value, wherever its row sits
                pick = vals_.index(max(okv) if c["emphasis"] == "top" else min(okv))
            else:
                pick = 0 if c["emphasis"] == "top" else len(rows) - 1
            out["colours"] = [colors.get(c.get("accent", "brand"), "#F2A541") if i == pick else colors.get(c.get("muted", "second"), "#8C9BB2")
                              for i in range(len(rows))]
    rls = [r for r in v.get("referenceLines") or [] if isinstance(r.get("value"), (int, float, str))]
    if rls:                                       # a measure line ("[SLA Days]") at that measure's example value
        val = lambda x: x if isinstance(x, (int, float)) else value_for(_bare(x), base)
        dec = next((x for k, x in (v.get("props") or {}).items() if "ReferenceLine.dataLabelDecimalPoints" in k), None)
        out["refLines"] = [{"axis": r.get("axis", "value"), "label": r.get("label", ""), "value": val(r["value"]),
                            **({"decimals": dec} if dec is not None else {})} for r in rls]
    page_members = FIXED_NAMES.get(base) or {}
    if v.get("preview"):                          # a sentence for the plan picture, its numbers from these values
        out["preview"] = preview_text(v["preview"], ctx=base, rows=len(rows), members=page_members)
    c = v.get("container") if isinstance(v.get("container"), dict) else {}
    ttl = c.get("title")
    for key in ("title", "subtitle"):              # a title measure's sentence, from these rows
        tv = c.get(key)
        if isinstance(tv, dict) and "{" in str(tv.get("preview", "")):
            out.setdefault("titles", {})[key] = preview_text(tv["preview"], ctx=base, rows=len(rows), members=page_members)
    return out


FIXED_NAMES = {}       # a drill-through page's context -> {column: member}, for {top:Column} on that page


def preview_text(tpl, ctx=(), rows=None, members=None):
    """`{value:[M]}` the example value of M (`{value:[M]|0.0}` in that format); `{abs:[M]}` without its sign;
    `{word:[M]|below|above}` the first word when M is below zero, else the second; `{change:[M]|[M PY]}` the change
    between two; `{top:Field|[M]}` the member with the most of M (the first bar), `{top:Field}` the first member (the
    drilled member on a drill-through page); `{rows}` the rows the visual shows, `{rows:item|items}` with the word
    (v1.12: a list's title counts the rows its filter keeps)."""
    members = members or {}

    def sub(m):
        kind, arg = m.group(1), (m.group(2) or "")
        if kind == "rows":
            n = rows or 0
            if arg:
                one_w, _, many = arg.partition("|")
                return f"{n} {one_w if n == 1 else (many or one_w + 's')}"
            return str(n)
        if kind in ("value", "abs"):
            n, _, fmt = arg.partition("|")
            n = n.strip().strip("[]")
            x = value_for(n, ctx)
            if x is None:
                return "–"
            if kind == "abs":
                return format_value(abs(x), fmt or fmt_for(n).split(";")[0].lstrip("+"))
            return format_value(x, fmt or fmt_for(n))
        if kind == "delta":                     # {delta:[M]|[M PY]|2024}: "▲ +252 · +2.8% vs 2024"
            parts = [x.strip() for x in arg.split("|")]
            a, b = parts[0].strip("[]"), parts[1].strip("[]")
            vs = f"vs {parts[2]}" if len(parts) > 2 and parts[2] else "vs last year"
            ca, cb = value_for(a, ctx), value_for(b, ctx)
            if not isinstance(ca, (int, float)) or not isinstance(cb, (int, float)):
                return "No last year"
            d = ca - cb
            sign = "+" if d > 0 else "−" if d < 0 else ""
            arrow = "▲ " if d > 0 else "▼ " if d < 0 else "■ "
            return f"{arrow}{sign}{abs(d):,.0f} · {sign}{abs(d) / cb * 100 if cb else 0:.1f}% {vs}"
        if kind == "word":
            n, below, above = (arg.split("|") + ["", "", ""])[:3]
            x = value_for(n.strip().strip("[]"), ctx) or 0
            return below if x < 0 else above
        if kind == "change":
            a, b = (x.strip().strip("[]") for x in arg.split("|"))
            ca, cb = value_for(a, ctx), value_for(b, ctx)
            t, sign = change_text(ca, cb, pct_points=is_pct(a))
            return t.replace("▲ ", "up ").replace("▼ ", "down ") if t else ""
        if kind == "top":                      # {top:Field|[Measure]}: the member the ranked bars show first
            fld, _, msr = arg.partition("|")
            col = _bare(fld)
            if col in members:
                return members[col]
            cats = members_of(col, 6)
            if not msr:
                return cats[0]
            msr = msr.strip().strip("[]")
            keyed = LABEL_KEY.get(col) or {}
            kc = tuple(keyed.get(x, x) for x in cats)          # a label column: its keys carry the numbers
            return max(cats, key=lambda c: value_for(msr, tuple(ctx) + ((keyed.get(c, c), kc),)) or 0)
        return m.group(0)
    return re.sub(r"\{(value|abs|word|change|top|rows|delta)(?::([^}]+))?\}", sub, tpl)


def format_value(x, fmt):
    """A number in a Power BI format string: the first section (sign, decimals, %, thousands), the second section's
    sign for a negative."""
    if x is None:
        return ""
    secs = (fmt or "#,0").split(";")
    sec = secs[0] if x >= 0 or len(secs) < 2 else secs[1]
    pct = "%" in sec
    v = abs(x) * (100 if pct else 1)
    dm = re.search(r"\.([0#]+)", sec)
    dec = len(dm.group(1)) if dm else 0
    body = f"{v:,.{dec}f}" if "," in sec else f"{v:.{dec}f}"
    sign = ""
    if x < 0:
        sign = "-" if (len(secs) < 2 or "-" in sec) else ""
    elif x > 0 and sec.lstrip().startswith("+"):
        sign = "+"
    return sign + body + ("%" if pct else "")


def data_for(layout, root=None):
    """The whole wireframe data document: {"visuals": {id: entry}, "privacy": [...], "example": true}."""
    measures = contract_measures(root or layout.get("_root") or ".")
    load_model(root or layout.get("_root") or ".")
    colors = {}
    try:
        import json as _json, pathlib as _p
        colors = _json.loads((_p.Path(root or layout.get("_root") or ".") / "design" / "tokens.json")
                             .read_text(encoding="utf-8")).get("colors", {})
    except (OSError, ValueError):
        pass
    vis = {}
    FIXED_NAMES.clear()
    pages = layout.get("pages") or {}
    drill = {k: p["drillthrough"] for k, p in pages.items() if isinstance(p, dict) and isinstance(p.get("drillthrough"), dict)}
    picked = {}
    for v in layout.get("visuals", []):           # a picker's saved selection: the page opens filtered to it
        sel = v.get("selection") if isinstance(v.get("selection"), dict) else None
        vals = (sel or {}).get("values")
        if sel and isinstance(vals, list) and len(vals) == 1 and "slicer" in str(v.get("type", "")).lower():
            col = _bare(sel.get("field"))
            picked.setdefault(v.get("page"), []).append((str(vals[0]), tuple(members_of(col, 6))))
    for v in sorted(layout.get("visuals", []), key=lambda v: v.get("page") in drill):   # drill sources first
        fixed = tuple(picked.get(v.get("page")) or ()) if "slicer" not in str(v.get("type", "")).lower() else ()
        if v.get("page") in drill:            # a drill-through page shows one member: the source list's first row
            col = _bare((drill[v["page"]].get("fields") or [""])[0])
            src = next((x for x in layout.get("visuals", []) if (x.get("action") or {}).get("type") == "Drillthrough"
                        and (x.get("action") or {}).get("page") == v["page"] and x["id"] in vis), None)
            first = None
            if src and vis[src["id"]].get("rows") and vis[src["id"]].get("groups"):
                gl = [_bare(f.get("field") if isinstance(f, dict) else f) for xs in (src.get("bindings") or {}).values()
                      for f in (xs if isinstance(xs, list) else [xs])]
                if col in gl:
                    first = vis[src["id"]]["rows"][0][0]
            mems = members_of(col, 6)
            fixed = fixed + ((first or mems[0], tuple(mems)),)
            FIXED_NAMES[fixed] = {col: first or mems[0]}
        e = for_visual(v, measures, colors, fixed=fixed)
        if e:
            vis[v["id"]] = e
    vis = {v["id"]: vis[v["id"]] for v in layout.get("visuals", []) if v["id"] in vis}
    return {"visuals": vis, "example": True,
            "privacy": ["example values (made up from a seed per visual, no data read): passed"]}
