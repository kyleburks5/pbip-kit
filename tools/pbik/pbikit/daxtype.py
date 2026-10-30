"""Is a DAX measure's result text? Inferred from the expression, so text measures need no `formatString: @`.

text when the result expression (after VAR ... RETURN) is:
- a string literal, or a concatenation with & at the top level;
- a text function: FORMAT, CONCATENATE, CONCATENATEX, COMBINEVALUES, LEFT, RIGHT, MID, UPPER, LOWER, TRIM,
  SUBSTITUTE, REPLACE, REPT, UNICHAR, FIXED, VALUE is not (it returns a number);
- IF / SWITCH / COALESCE / IFERROR / DIVIDE-free branching whose result branches include text (BLANK() is neutral);
- CALCULATE / CALCULATETABLE-free wrappers whose first argument is text (CALCULATE, KEEPFILTERS-free);
- a VAR or a measure that is text (declared dataType string / ImageUrl, or inferred, recursively), also written
  table-qualified ('_Measures'[Name]);
- SELECTEDVALUE / MIN / MAX / FIRSTNONBLANK / LASTNONBLANK of a text column (SELECTEDVALUE also with a text
  alternate result).
Anything else counts as a number. A wrong "number" only means the format-string rule asks for one, as before.
"""
import re

TEXT_FNS = {"FORMAT", "CONCATENATE", "CONCATENATEX", "COMBINEVALUES", "LEFT", "RIGHT", "MID", "UPPER", "LOWER",
            "TRIM", "SUBSTITUTE", "REPLACE", "REPT", "UNICHAR", "FIXED", "NAMEOF", "PATH", "PATHITEM"}
FIRST_ARG = {"CALCULATE", "SELECTEDMEASURE"}
COLUMN_VALUE = {"SELECTEDVALUE", "MIN", "MAX", "FIRSTNONBLANK", "LASTNONBLANK", "VALUES", "DISTINCT"}
TOKEN = re.compile(r'''\s*(?:(?P<str>"(?:[^"]|"")*")|(?P<col>(?:'(?:[^']|'')+'|[A-Za-z_][\w.]*)?\[[^\]]+\])'''
                   r'''|(?P<num>\d+(?:\.\d+)?)|(?P<id>[A-Za-z_][\w.]*)|(?P<op>&&|\|\||<=|>=|<>|==|[-+*/^&=<>(),!]))''')


def strip_comments(expr):
    out, i, n = [], 0, len(expr)
    while i < n:
        c = expr[i]
        if c == '"':
            j = i + 1
            while j < n and not (expr[j] == '"' and (j + 1 >= n or expr[j + 1] != '"')):
                j += 2 if expr[j] == '"' else 1
            out.append(expr[i:j + 1])
            i = j + 1
        elif expr.startswith("//", i) or expr.startswith("--", i):
            while i < n and expr[i] != "\n":
                i += 1
        elif expr.startswith("/*", i):
            k = expr.find("*/", i + 2)
            i = n if k < 0 else k + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def tokens(expr):
    expr = strip_comments(expr or "").strip().strip("`").strip()
    out, pos = [], 0
    while pos < len(expr):
        m = TOKEN.match(expr, pos)
        if not m or m.end() == pos:
            pos += 1
            continue
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
        pos = m.end()
    return out


def split_top(toks, sep=","):
    parts, depth, cur = [], 0, []
    for t in toks:
        if t == ("op", "("):
            depth += 1
        elif t == ("op", ")"):
            depth -= 1
        if depth == 0 and t == ("op", sep):
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    parts.append(cur)
    return parts


def _vars(toks):
    """VAR a = ... VAR b = ... RETURN expr -> ({name: tokens}, result tokens)."""
    defs, i = {}, 0
    if not toks or not (toks[0][0] == "id" and toks[0][1].upper() == "VAR"):
        return defs, toks
    depth, start, name = 0, None, None
    for k, t in enumerate(toks):
        if t == ("op", "("):
            depth += 1
        elif t == ("op", ")"):
            depth -= 1
        if depth == 0 and t[0] == "id" and t[1].upper() in ("VAR", "RETURN"):
            if name is not None:
                defs[name] = toks[start:k]
            if t[1].upper() == "RETURN":
                return defs, toks[k + 1:]
            if k + 2 < len(toks) and toks[k + 2] == ("op", "="):
                name, start = toks[k + 1][1], k + 3
    return defs, toks


def infer(toks, measure_text, vars_=None, depth=0, column_text=lambda ref: False):
    """'text' or 'number' for a token list."""
    if depth > 40 or not toks:
        return "number"
    defs, toks = _vars(toks)
    scope = dict(vars_ or {})
    scope.update(defs)
    if not toks:
        return "number"
    level = 0
    for t in toks:                               # & at the top level
        if t == ("op", "("):
            level += 1
        elif t == ("op", ")"):
            level -= 1
        elif level == 0 and t == ("op", "&"):
            return "text"
    if len(toks) == 1:
        kind, val = toks[0]
        if kind == "str":
            return "text"
        if kind == "col":
            return "text" if measure_text(val[val.index("[") + 1:-1]) else "number"
        if kind == "id" and val in scope:
            return infer(scope[val], measure_text, scope, depth + 1, column_text)
        return "number"
    if toks[0] == ("op", "(") and toks[-1] == ("op", ")") and _closes_at_end(toks):
        return infer(toks[1:-1], measure_text, scope, depth + 1, column_text)
    if toks[0][0] == "id" and len(toks) > 2 and toks[1] == ("op", "(") and _closes_at_end(toks[1:]):
        fn, args = toks[0][1].upper(), split_top(toks[2:-1])
        if fn in TEXT_FNS:
            return "text"
        if fn in COLUMN_VALUE:
            first = args[0] if args else []
            if len(first) == 1 and first[0][0] == "col" and "[" in first[0][1] and not first[0][1].startswith("[")                     and column_text(first[0][1]):
                return "text"
            if fn == "SELECTEDVALUE" and len(args) > 1:
                return infer(args[1], measure_text, scope, depth + 1, column_text)
            return "number"
        if fn == "IF":
            branches = args[1:3]
        elif fn == "SWITCH":
            branches = [a for k, a in enumerate(args[2:]) if k % 2 == 0] + ([args[-1]] if len(args) % 2 == 0 else [])
        elif fn in ("COALESCE", "IFERROR"):
            branches = args
        elif fn in FIRST_ARG:
            branches = args[:1]
        else:
            return "number"
        return "text" if any(infer(a, measure_text, scope, depth + 1, column_text) == "text" for a in branches) else "number"
    return "number"


def _closes_at_end(toks):
    depth = 0
    for k, t in enumerate(toks):
        if t == ("op", "("):
            depth += 1
        elif t == ("op", ")"):
            depth -= 1
            if depth == 0 and k != len(toks) - 1:
                return False
    return depth == 0


def text_measures(model):
    """{(table, name)} of measures whose result is text: declared (dataType string, ImageUrl) or inferred."""
    by_name = {}
    for mm in model.all_measures():
        by_name.setdefault(mm.name, mm)
    memo, busy = {}, set()

    def column_text(ref):
        tbl, col = ref[:ref.index("[")].strip().strip("'").replace("''", "'"), ref[ref.index("[") + 1:-1]
        return (model.column_type(tbl, col) or "").lower() == "string"

    def is_text(name):
        mm = by_name.get(name)
        if mm is None:
            return False
        if name in memo:
            return memo[name]
        if name in busy:
            return False
        busy.add(name)
        r = mm.is_text() or infer(tokens(mm.expression), is_text, column_text=column_text) == "text"
        busy.discard(name)
        memo[name] = r
        return r
    return {(mm.table, mm.name) for mm in model.all_measures() if is_text(mm.name)}


def is_text_expression(expr, measure_text=lambda name: False):
    return infer(tokens(expr), measure_text) == "text"
