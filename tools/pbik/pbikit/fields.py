"""Layout field notation -> PBIR field expressions, checked against the model's TMDL and the report extensions.

Notation: '[Measure]', 'Table[Column]', "'Table name'[Column]", 'Sum(Table[Column])' (Sum, Avg, Min, Max, First,
Last, Count, DistinctCount). A trailing note in parentheses ('[Sales] (current year)') is ignored.
Filters follow the shapes Desktop saves (semanticQuery Version 2 with a From list of source aliases).
"""
import re

from .objects import AGG_FUNCS, L, column, measure, qref, s

NUMERIC = {"int64": "L", "double": "D", "decimal": "M"}


class FieldError(ValueError):
    pass


class Resolver:
    def __init__(self, report, measure_table=None):
        self.report = report
        self.model = report.model()
        self.ext = report.extensions()
        self.measure_table = measure_table
        self.warnings = []

    def parse(self, text):
        """-> (aggregation or None, table or None, name)."""
        t = text.strip()
        m = re.fullmatch(r"([A-Za-z]+)\(\s*(.+?)\s*\)", t)
        if m and m.group(1).lower() in AGG_FUNCS:
            _, table, name = self.parse(m.group(2))
            return m.group(1).lower(), table, name
        t = re.sub(r"\s+\([^()]*\)\s*$", "", t)
        m = re.fullmatch(r"(?:'((?:[^']|'')+)'|([^'\[\]]*))\[([^\]]+)\]", t)
        if not m:
            raise FieldError(f"not a field: {text!r} (use [Measure] or Table[Column])")
        table = (m.group(1) or "").replace("''", "'") or (m.group(2) or "").strip() or None
        return None, table, m.group(3)

    def measure_ref(self, name, table=None):
        homes = [t for (t, mname) in self.ext if mname == name and (table is None or t == table)]
        if homes:
            return measure(name, homes[0], schema="extension")
        if self.model:
            t = self.model.tables.get(table) if table else None
            if t and name in t.measures:
                return measure(name, table)
            homes = self.model.measure_home(name)
            if table is None and len(homes) == 1:
                return measure(name, homes[0])
            if table is None and len(homes) > 1:
                raise FieldError(f"[{name}] is in several tables {homes}: write Table[{name}]")
            raise FieldError(f"[{name}] is not a measure in the model or reportExtensions.json")
        if table or self.measure_table:
            self.warnings.append(f"no model found: [{name}] assumed in {table or self.measure_table}")
            return measure(name, table or self.measure_table)
        raise FieldError(f"[{name}]: no model found and no measureTable in layout.json")

    def field(self, text):
        agg, table, name = self.parse(text)
        if table is None:
            if agg:
                raise FieldError(f"{text!r}: an aggregation needs Table[Column]")
            return self.measure_ref(name)
        if (table, name) in self.ext:
            return measure(name, table, schema="extension")
        if self.model:
            t = self.model.tables.get(table)
            if t is None:
                raise FieldError(f"{text!r}: no table {table!r} in the model")
            if name in t.measures:
                if agg:
                    raise FieldError(f"{text!r}: can't aggregate a measure")
                return measure(name, table)
            if name not in t.columns:
                raise FieldError(f"{text!r}: no column or measure {name!r} in {table}")
        col = column(table, name)
        if agg:
            return {"Aggregation": {"Expression": col, "Function": AGG_FUNCS[agg]}}
        return col

    def column_type(self, field):
        c = field.get("Column")
        if not c or not self.model:
            return None
        return self.model.column_type(c["Expression"]["SourceRef"]["Entity"], c["Property"])


# ---------------------------------------------------------------- literals
def is_automatic(f):
    """An automatic filter (the filter card Power BI makes for each field a visual uses): `howCreated: Auto` in
    Microsoft's schema, but Desktop 2.159.883.0 saved them with no `howCreated` and no condition, only name, field and
    type (pbik-smoke-013 save, 2026-11-10). A filter with a condition, or made another way, isn't one."""
    if not isinstance(f, dict) or "field" not in f:
        return False
    return f.get("howCreated") == "Auto" or ("howCreated" not in f and "filter" not in f)


def typed_literal(value, data_type):
    """A filter value written the way the column's type needs it (a number as text never matches)."""
    if value is None:
        return {"Literal": {"Value": "null"}}
    if data_type in NUMERIC:
        try:
            num = int(value) if data_type == "int64" else float(value)
        except (TypeError, ValueError):
            raise FieldError(f"{value!r} is not a number, but the column is {data_type}")
        return {"Literal": {"Value": f"{num}{NUMERIC[data_type]}"}}
    if data_type == "boolean":
        return {"Literal": {"Value": "true" if value in (True, "true", "True", 1) else "false"}}
    if data_type == "dateTime":
        v = str(value)
        if "T" not in v:
            v += "T00:00:00"
        return {"Literal": {"Value": f"datetime'{v}'"}}
    if isinstance(value, bool):
        return {"Literal": {"Value": "true" if value else "false"}}
    if isinstance(value, (int, float)) and data_type is None:
        return {"Literal": {"Value": f"{value}{'L' if isinstance(value, int) else 'D'}"}}
    return s(value)["expr"]


def _alias(entity, taken):
    a = (re.sub(r"[^a-z]", "", entity.lower()) or "t")[0]
    while a in taken:
        a += "1"
    taken.add(a)
    return a


def _src(field, alias):
    """The same field, with SourceRef Entity replaced by the From alias."""
    kind = next(iter(field))
    inner = dict(field[kind])
    if kind == "Aggregation":
        return {"Aggregation": {"Expression": _src(inner["Expression"], alias), "Function": inner["Function"]}}
    return {kind: {"Expression": {"SourceRef": {"Source": alias}}, "Property": inner["Property"]}}


def _entity(field):
    kind = next(iter(field))
    inner = field[kind]
    if kind == "Aggregation":
        return _entity(inner["Expression"])
    ref = inner["Expression"]["SourceRef"]
    return ref["Entity"], ref.get("Schema")


def _from(entity, schema, alias):
    f = {"Name": alias, "Entity": entity, "Type": 0}
    if schema:
        f["Schema"] = schema
    return f


def categorical_filter(name, field, data_type, values, invert=False):
    entity, schema = _entity(field)
    a = _alias(entity, set())
    cond = {"In": {"Expressions": [_src(field, a)], "Values": [[typed_literal(v, data_type)] for v in values]}}
    if invert:
        cond = {"Not": {"Expression": cond}}
    return {"name": name, "field": field, "type": "Categorical",
            "filter": {"Version": 2, "From": [_from(entity, schema, a)], "Where": [{"Condition": cond}]},
            "howCreated": "User"}


def topn_filter(name, field, by, n, bottom=False):
    """Top N (or bottom N) members of a column by a measure, in the subquery shape Desktop saves."""
    entity, schema = _entity(field)
    taken = set()
    a = _alias(entity, taken)
    sub_from = [_from(entity, schema, a)]
    by_entity, by_schema = _entity(by)
    if (by_entity, by_schema) == (entity, schema):
        b = a
    else:
        b = _alias(by_entity, taken)
        sub_from.append(_from(by_entity, by_schema, b))
    sub = {"Version": 2, "From": sub_from,
           "Select": [{**_src(field, a), "Name": "field"}],
           "OrderBy": [{"Direction": 1 if bottom else 2, "Expression": _src(by, b)}],
           "Top": int(n)}
    return {"name": name, "field": field, "type": "TopN",
            "filter": {"Version": 2,
                       "From": [{"Name": "subquery", "Expression": {"Subquery": {"Query": sub}}, "Type": 2},
                                _from(entity, schema, a)],
                       "Where": [{"Condition": {"In": {"Expressions": [_src(field, a)],
                                                       "Table": {"SourceRef": {"Source": "subquery"}}}}}]},
            "howCreated": "User"}


def measure_filter(name, field, kind, value):
    """A visual-level filter on a measure (filter pane "Show items when the value is ..."): an Advanced filter with
    one Comparison (ComparisonKind 0 =, 1 >, 2 >=, 3 <, 4 <=). Values are written as decimals (0D)."""
    entity, schema = _entity(field)
    a = _alias(entity, set())
    try:
        lit = {"Literal": {"Value": f"{float(value):g}D"}}
    except (TypeError, ValueError):
        raise FieldError(f"measure filter value {value!r} is not a number")
    cond = {"Comparison": {"ComparisonKind": kind, "Left": _src(field, a), "Right": lit}}
    return {"name": name, "field": field, "type": "Advanced",
            "filter": {"Version": 2, "From": [_from(entity, schema, a)], "Where": [{"Condition": cond}]},
            "howCreated": "User"}


# ---------------------------------------------------------------- roadmap gap 4: filter types from the schema only
# (filterConfiguration 1.3.0 #FilterContainer `type`; semanticQuery 1.4.0 #QueryBetweenExpression,
# #QueryContainsExpression, #QueryStartsWithExpression, #QueryNotExpression, #QueryDateSpanExpression,
# #QueryDateAddExpression, #QueryNowExpression, #TimeUnit). UNVERIFIED in Desktop: no Desktop-saved file in the kit has one.
TIME_UNITS = {"day": 0, "days": 0, "week": 1, "weeks": 1, "month": 2, "months": 2, "year": 3, "years": 3}
TEXT_OPS = ("contains", "doesNotContain", "startsWith", "doesNotStartWith", "is", "isNot", "isBlank", "isNotBlank")


def _where(field, cond_of):
    entity, schema = _entity(field)
    a = _alias(entity, set())
    return {"Version": 2, "From": [_from(entity, schema, a)], "Where": [{"Condition": cond_of(_src(field, a))}]}


def range_filter(name, field, data_type, low, high):
    """Values between low and high, both included: a Range filter with one Between condition."""
    if low is None or high is None:
        raise FieldError("a Range filter needs min and max")
    return {"name": name, "field": field, "type": "Range",
            "filter": _where(field, lambda col: {"Between": {"Expression": col,
                                                             "LowerBound": typed_literal(low, data_type),
                                                             "UpperBound": typed_literal(high, data_type)}}),
            "howCreated": "User"}


def _text_cond(col, op, value, data_type):
    if op not in TEXT_OPS:
        raise FieldError(f"text condition {op!r} ({', '.join(TEXT_OPS)})")
    if op in ("isBlank", "isNotBlank"):
        c = {"Comparison": {"ComparisonKind": 0, "Left": col, "Right": {"Literal": {"Value": "null"}}}}
        return c if op == "isBlank" else {"Not": {"Expression": c}}
    if value is None:
        raise FieldError(f"text condition {op} needs a value")
    if op in ("is", "isNot"):
        c = {"Comparison": {"ComparisonKind": 0, "Left": col, "Right": typed_literal(value, data_type)}}
        return c if op == "is" else {"Not": {"Expression": c}}
    kind = "Contains" if "ontain" in op else "StartsWith"
    c = {kind: {"Left": col, "Right": typed_literal(str(value), None)}}
    return {"Not": {"Expression": c}} if op.startswith("doesNot") else c


def advanced_filter(name, field, data_type, conditions, join="and"):
    """The filter pane's Advanced mode on a column: one or two conditions (Contains, StartsWith, is, blank, and their
    negations) joined by And / Or."""
    if not 1 <= len(conditions) <= 2:
        raise FieldError("an Advanced filter takes one or two conditions")
    if join not in ("and", "or"):
        raise FieldError(f"join {join!r} (and, or)")

    def cond(col):
        cs = [_text_cond(col, c.get("op"), c.get("value"), data_type) for c in conditions]
        return cs[0] if len(cs) == 1 else {join.capitalize(): {"Left": cs[0], "Right": cs[1]}}
    return {"name": name, "field": field, "type": "Advanced", "filter": _where(field, cond), "howCreated": "User"}


def relative_date_filter(name, field, last, unit):
    """In the last <last> <unit>s, today included: Between( DateSpan(DateAdd(DateAdd(Now, 1 day), -last unit), day),
    DateSpan(Now, day) ). Built from the schema's date expressions; Desktop's own form unconfirmed."""
    u = TIME_UNITS.get(str(unit).lower())
    if u is None:
        raise FieldError(f"relative date unit {unit!r} (days, weeks, months, years)")
    if not isinstance(last, int) or isinstance(last, bool) or last < 1:
        raise FieldError(f"relative date `last` must be a whole number of {unit} (1 or more)")
    start = {"DateSpan": {"Expression": {"DateAdd": {"Expression": {"DateAdd": {"Expression": {"Now": {}}, "Amount": 1,
                                                                                  "TimeUnit": 0}},
                                                     "Amount": -last, "TimeUnit": u}}, "TimeUnit": 0}}
    end = {"DateSpan": {"Expression": {"Now": {}}, "TimeUnit": 0}}
    return {"name": name, "field": field, "type": "RelativeDate",
            "filter": _where(field, lambda col: {"Between": {"Expression": col, "LowerBound": start, "UpperBound": end}}),
            "howCreated": "User"}


def selection_filter(field, data_type, values):
    """Slicer default selection (objects.general.filter), as Desktop saves a clicked value."""
    entity, schema = _entity(field)
    a = _alias(entity, set())
    return {"Version": 2, "From": [_from(entity, schema, a)],
            "Where": [{"Condition": {"In": {"Expressions": [_src(field, a)],
                                            "Values": [[typed_literal(v, data_type)] for v in values]}}}]}


__all__ = ["Resolver", "FieldError", "typed_literal", "categorical_filter", "topn_filter", "measure_filter",
           "selection_filter", "qref", "L"]
