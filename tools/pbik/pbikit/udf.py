"""Kit UDF libraries: an optional toolbelt of DAX user-defined functions (UDF KPI card study, 2026-11-15).

design/udf/library/<library>/ holds one .tmdl per function and index.json (description, parameters, Use when / Avoid
when, the model tables a function reads, a fingerprint per file, enabled or disabled). Nothing uses a library unless
the plan or the person picks a function. Commands (`pbik udf ...`):

list     the functions in plain words, by role (disabled ones are not offered)
show     one function: what it draws, its arguments, what it pulls in, the tables it needs
check    fingerprints, enabled, the model tables it reads (against the contract or a TMDL folder)
render   the install text with the report's design tokens (`--format query` for a query-scoped test)
install  add functions and what they call to the synthetic model (always), or to a person's own TMDL model folder
         (only on request: --own-model); the model's compatibility level goes to 1702
inline   a call expanded into plain DAX (no UDF needed), for a report-level measure on a live model
desktop  the Desktop version check before UDFs are used

The bind check (pbik bind check) errors when the report calls a library function the live model doesn't have and
the call wasn't inlined; `udfCard` in layout.json (pbik build) writes a whole UDF KPI card in one step.
"""
import datetime, hashlib, json, pathlib, re

LIBRARY = pathlib.Path("design") / "udf" / "library"
UDF_STATE = pathlib.Path("design") / "specs" / "udf.json"
MIN_LEVEL = 1702
ANNOTATION = "PBIK_UDF"
ROLES = ["card", "chart", "microchart", "icon", "number", "format", "helper"]
ROLE_WORDS = {"card": "KPI cards", "chart": "charts", "microchart": "small charts inside a card",
              "icon": "icons", "number": "numbers", "format": "number formats", "helper": "helpers"}
RAW_TYPES = {"ANYREF", "TABLE", "ANYVAL"}        # an EXPR argument of these types goes in without brackets
# the first Desktop release with UDFs (preview, September 2025: from the study, not confirmed in the kit's sources)
FIRST_UDF_DESKTOP = "2.147"
# Desktop releases whose UDF switch is still to be checked by a person (Desktop check 4)
PREVIEW_UNKNOWN = {"2.155": "verify in Desktop", "2.159": "verify in Desktop"}


class UdfError(Exception):
    pass


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def kit_root():
    return pathlib.Path(__file__).resolve().parents[3]


def library_root(root="."):
    """The project's library folder (a project is a copy of the kit), else the kit's own."""
    p = pathlib.Path(root) / LIBRARY
    return p if p.is_dir() else kit_root() / LIBRARY


def load(root="."):
    """{name: entry} over every library; each entry gets `library` and `dir`."""
    out = {}
    base = library_root(root)
    for ix in sorted(base.glob("*/index.json")):
        d = json.loads(ix.read_text(encoding="utf-8"))
        for f in d.get("functions", []):
            out[f["name"]] = {**f, "library": ix.parent.name, "dir": str(ix.parent)}
    return out


def find(by, name):
    for n in by:
        if n.lower() == (name or "").lower():
            return n
    return None


def closure(by, names):
    """The names plus everything they call, in library order."""
    seen, todo = set(), list(names)
    while todo:
        n = todo.pop()
        k = find(by, n)
        if not k:
            raise UdfError(f"there is no function called {n} in the kit's UDF libraries")
        if k not in seen:
            seen.add(k)
            todo += by[k]["calls"]
    return [n for n in by if n in seen]


def disabled_reason(entry):
    st = str(entry.get("status", "enabled"))
    return None if st == "enabled" else st


def text_of(entry):
    return (pathlib.Path(entry["dir"]) / entry["file"]).read_text(encoding="utf-8")


# ---------------------------------------------------------------- list / show
def lines_list(by, role=None, all_=False):
    out = []
    for r in ROLES:
        if role and r != role:
            continue
        fs = [f for f in by.values() if f["role"] == r and (all_ or not disabled_reason(f))]
        if not fs:
            continue
        w = ROLE_WORDS[r]
        out.append(f"{w[0].upper()}{w[1:]}:")
        for f in fs:
            size = f" ({f['size'][0]} x {f['size'][1]})" if f.get("size") else ""
            off = "  [turned off]" if disabled_reason(f) else ""
            out.append(f"  {f['name']}{size}: {f['description']}{off}")
            if f.get("useWhen"):
                out.append(f"      use when: {f['useWhen']}")
            if f.get("avoidWhen"):
                out.append(f"      avoid when: {f['avoidWhen']}")
    return out


def lines_show(by, name):
    k = find(by, name)
    if not k:
        raise UdfError(f"there is no function called {name} in the kit's UDF libraries")
    f = by[k]
    pulls = [n for n in closure(by, [k]) if n != k]
    out = [f"{k} ({f['role']}, library {f['library']}): {f['description']}"]
    if disabled_reason(f):
        out.append(f"turned off: {disabled_reason(f)}")
    out.append("arguments: " + ", ".join(f"{p['name']} ({p['type'].lower()}, {p['mode'].lower()})"
                                         for p in f["params"]))
    if f.get("styleParams"):
        out.append("style (leave blank for the report's design tokens): "
                   + ", ".join(f"{p} = {t}" for p, t in f["styleParams"].items()))
    if f.get("styles"):
        out.append("chart styles: " + ", ".join(f["styles"]))
    if f.get("size"):
        out.append(f"draws {f['size'][0]} x {f['size'][1]}: keep that shape when sizing the box")
    out.append("brings along: " + (", ".join(pulls) if pulls else "nothing (it works on its own)"))
    req = tables_needed(by, [k])
    out.append("needs in the model: " + ("; ".join(f"a table '{r['table']}' ({r['why']})" for r in req)
                                         if req else "no table of its own"))
    if f.get("useWhen"):
        out.append(f"use when: {f['useWhen']}")
    if f.get("avoidWhen"):
        out.append(f"avoid when: {f['avoidWhen']}")
    if f.get("example"):
        out.append(f"example: {f['example']}")
    return out


def tables_needed(by, names):
    out = {}
    for n in closure(by, names):
        for r in by[n].get("requires", []):
            e = out.setdefault(r["table"], {"table": r["table"], "columns": [], "why": r["why"]})
            e["columns"] = sorted(set(e["columns"]) | set(r.get("columns", [])))
    return list(out.values())


# ---------------------------------------------------------------- check
def model_tables(root=".", model=None):
    """{table lower: {column lower}} from a TMDL folder, else the project's contract; None when neither exists."""
    if model:
        from . import tmdl
        m = tmdl.load(model)
        return {t.lower(): {c.lower() for c in m.tables[t].columns} for t in m.tables}
    f = pathlib.Path(root) / "design" / "specs" / "contract.json"
    if not f.exists():
        return None
    c = json.loads(f.read_text(encoding="utf-8"))
    return {t.lower(): {x.lower() for x in v.get("columns", {})} for t, v in c.get("tables", {}).items()}


def check(by, names=None, tables=None):
    """Problems (plain lines) for the named functions and everything they call (default: every function)."""
    names = closure(by, names) if names else list(by)
    errors = []
    for n in names:
        f = by[n]
        if sha(text_of(f)) != f["sha256"]:
            errors.append(f"{n}: its file changed since the kit fingerprinted it; rebuild the index after a reviewed "
                          "change")
        if disabled_reason(f):
            errors.append(f"{n}: {disabled_reason(f)}")
        if tables is None:
            continue
        for r in f.get("requires", []):
            cols = tables.get(r["table"].lower())
            if cols is None:
                errors.append(f"{n}: needs a table '{r['table']}' in the model ({r['why']})")
                continue
            for c in r.get("columns", []):
                if c.lower() not in cols:
                    errors.append(f"{n}: needs '{r['table']}'[{c}] in the model ({r['why']})")
    return errors


# ---------------------------------------------------------------- render
PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_.]+)\}\}")


def token(tokens, path):
    v = tokens
    for k in path.split("."):
        if not isinstance(v, dict) or k not in v:
            raise KeyError(path)
        v = v[k]
    if isinstance(v, (dict, list)):
        raise KeyError(path)
    return str(v)


def fill(text, tokens):
    missing = set()

    def one(m):
        try:
            return token(tokens, m.group(1))
        except KeyError:
            missing.add(m.group(1))
            return m.group(0)
    out = PLACEHOLDER.sub(one, text)
    if missing:
        raise UdfError("the design tokens lack " + ", ".join(sorted(missing)) + " (design/tokens.json)")
    return out


def load_tokens(root="."):
    f = pathlib.Path(root) / "design" / "tokens.json"
    if not f.exists():
        f = kit_root() / "design" / "tokens.json"
    return json.loads(f.read_text(encoding="utf-8"))


def split_tmdl(text):
    """A function's .tmdl text -> (name, header text, body text); the header is the parameter list."""
    lines = [ln for ln in text.splitlines()]
    m = re.match(r"function '([^']+)' =\s*(?:```)?\s*$", lines[0])
    if not m:
        raise UdfError(f"unexpected function header: {lines[0]!r}")
    rest = "\n".join(ln[2:] if ln.startswith("\t\t") else ln for ln in lines[1:])
    rest = re.sub(r"\n\s*```\s*$", "", rest.rstrip())
    head, arrow, body = rest.partition("=>")
    if not arrow:
        raise UdfError(f"{m.group(1)}: no => in the function")
    return m.group(1), head, body


def to_query(text):
    name, head, body = split_tmdl(text)
    return f"FUNCTION {name} =\n{head}=>{body}\n"


def render(by, names, tokens, fmt="tmdl", rename=None, allow_disabled=False, annotate=False):
    names = closure(by, names) if names else list(by)
    off = [n for n in names if disabled_reason(by[n])]
    if off and not allow_disabled:
        raise UdfError("turned off: " + "; ".join(f"{n}: {disabled_reason(by[n])}" for n in off))
    blocks = []
    for n in names:
        text = fill(text_of(by[n]), tokens)
        if rename:
            old, new = rename.split("=", 1)
            text = text.replace(old, new)
        if fmt == "query":
            blocks.append(to_query(text))
        else:
            if annotate:
                text = text.rstrip() + f"\n\n\tannotation {ANNOTATION} = {by[n]['library']}:{by[n]['sha256']}\n"
            blocks.append(text.rstrip() + "\n")
    return ("DEFINE\n" + "\n".join(blocks)) if fmt == "query" else "\n".join(blocks)


# ---------------------------------------------------------------- functions in a model
FUNC_HEAD = re.compile(r"^function\s+('(?:[^']|'')+'|[\w.]+)\s*=", re.M)


def model_functions(folder):
    """{name: {"kit": "<library>:<sha256>" or None}} from a TMDL folder's function blocks."""
    folder = pathlib.Path(folder)
    if (folder / "definition").is_dir():
        folder = folder / "definition"
    out = {}
    for f in sorted(folder.glob("*.tmdl")):
        text = f.read_text(encoding="utf-8-sig")
        heads = list(FUNC_HEAD.finditer(text))
        for k, m in enumerate(heads):
            end = heads[k + 1].start() if k + 1 < len(heads) else len(text)
            nxt = re.search(r"^(?:table|relationship|ref|model|database|role|expression|cultureInfo)\b",
                            text[m.end():end], re.M)
            block = text[m.start():m.end() + nxt.start() if nxt else end]
            name = m.group(1).strip("'").replace("''", "'")
            a = re.search(rf"^\s*annotation\s+{ANNOTATION}\s*=\s*(\S+)", block, re.M)
            out[name] = {"kit": a.group(1) if a else None}
    return out


def compatibility_level(folder):
    folder = pathlib.Path(folder)
    if (folder / "definition").is_dir():
        folder = folder / "definition"
    f = folder / "database.tmdl"
    m = re.search(r"compatibilityLevel:\s*(\d+)", f.read_text(encoding="utf-8-sig")) if f.exists() else None
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- install
def state(root="."):
    f = pathlib.Path(root) / UDF_STATE
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"installed": {}}


def save_state(root, st):
    f = pathlib.Path(root) / UDF_STATE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def synthetic_folder(root="."):
    """The synthetic model folder pbik made (its model.tmdl carries the synthetic mark), if there is one."""
    from . import dataclass_ as DC
    for p in sorted(pathlib.Path(root).glob("*.SemanticModel")):
        m = p / "definition" / "model.tmdl"
        if m.exists() and DC.SYNTH_MARK in m.read_text(encoding="utf-8-sig"):
            return p
    return None


def write_functions(folder, by, names, tokens):
    """Write the functions into <folder>/definition/functions.tmdl (pbik's own block, replaced as a whole) and raise
    the compatibility level to 1702. Returns the names written."""
    folder = pathlib.Path(folder)
    d = folder / "definition" if (folder / "definition").is_dir() else folder
    names = closure(by, names)
    text = render(by, names, tokens, annotate=True)
    f = d / "functions.tmdl"
    keep = ""
    if f.exists():
        old = f.read_text(encoding="utf-8-sig")
        theirs = {n for n, v in model_functions(d).items() if not v["kit"]}
        clash = sorted(theirs & set(names))
        if clash:
            raise UdfError("the model already has its own " + ", ".join(clash) + ": I won't overwrite them")
        keep = _without_kit_blocks(old)
    new = (keep.rstrip() + "\n\n" if keep.strip() else "") + text
    if not f.exists() or f.read_text(encoding="utf-8-sig") != new:
        f.write_text(new, encoding="utf-8")
    db = d / "database.tmdl"
    if db.exists():
        t = db.read_text(encoding="utf-8-sig")
        lv = compatibility_level(d) or 0
        if lv < MIN_LEVEL:
            t = re.sub(r"compatibilityLevel:\s*\d+", f"compatibilityLevel: {MIN_LEVEL}", t) \
                if "compatibilityLevel" in t else t.rstrip() + f"\n\tcompatibilityLevel: {MIN_LEVEL}\n"
            db.write_text(t, encoding="utf-8")
    return names


def _without_kit_blocks(text):
    """functions.tmdl text without the blocks pbik wrote (they carry the PBIK_UDF annotation)."""
    heads = list(FUNC_HEAD.finditer(text))
    if not heads:
        return text
    out, prev = [text[:heads[0].start()]], heads[0].start()
    for k, m in enumerate(heads):
        end = heads[k + 1].start() if k + 1 < len(heads) else len(text)
        block = text[m.start():end]
        if not re.search(rf"^\s*annotation\s+{ANNOTATION}\s*=", block, re.M):
            out.append(block)
    return "".join(out)


def install(root, names, model="synthetic", own_model=False, tokens=None):
    """Install into the synthetic model (always allowed) or a person's own TMDL folder (own_model=True: the person
    asked for it). Records the install in design/specs/udf.json. Returns (folder, names)."""
    by = load(root)
    names = closure(by, names)
    probs = check(by, names, None)
    if probs:
        raise UdfError("; ".join(probs))
    if model == "synthetic":
        folder = synthetic_folder(root)
        kind = "synthetic"
    else:
        folder = pathlib.Path(model)
        kind = "own"
        if synthetic_folder(root) and folder.resolve() == synthetic_folder(root).resolve():
            kind = "synthetic"
        elif not own_model:
            raise UdfError("that is your own model: I add functions to it only when you ask (say so, and I'll run "
                           "it again with your OK)")
    tables = model_tables(root, folder) if folder else model_tables(root)
    if tables is not None:
        need = [p for p in check(by, names, tables) if "needs" in p]
        if need:
            raise UdfError("; ".join(need) + ". Pick a card that takes the month columns as arguments (Card1, "
                                             "Card2, SVGKPICard) instead")
    tokens = tokens if tokens is not None else load_tokens(root)
    st = state(root)
    if folder is not None:
        write_functions(folder, by, names, tokens)
    when = datetime.date.today().isoformat()
    for n in names:
        st.setdefault("installed", {})[n] = {"library": by[n]["library"], "sha256": by[n]["sha256"],
                                             "model": kind, "date": when}
    save_state(root, st)
    return folder, names


def drift(root="."):
    """Installed functions whose library file changed since (a later library update)."""
    by = load(root)
    out = []
    for n, v in state(root).get("installed", {}).items():
        if n in by and by[n]["sha256"] != v.get("sha256"):
            out.append(f"{n}: the kit's library changed since it was installed ({v.get('date')}); install it again")
    return out


# ---------------------------------------------------------------- DAX scanning
def segments(expr):
    """[(kind, text)] with kind code, string, comment, quoted ('Table name') or bracket ([Name])."""
    out, k, n, seg = [], 0, len(expr), 0

    def push(kind, a, b):
        if b > a:
            out.append((kind, expr[a:b]))
    while k < n:
        c = expr[k]
        if expr.startswith(("//", "--"), k):
            j = expr.find("\n", k)
            j = n if j < 0 else j
            kind = "comment"
        elif expr.startswith("/*", k):
            j = expr.find("*/", k + 2)
            j = n if j < 0 else j + 2
            kind = "comment"
        elif c == '"':
            j = k + 1
            while j < n and not (expr[j] == '"' and not expr.startswith('""', j)):
                j += 2 if expr.startswith('""', j) else 1
            j += 1
            kind = "string"
        elif c == "'":
            j = k + 1
            while j < n and not (expr[j] == "'" and not expr.startswith("''", j)):
                j += 2 if expr.startswith("''", j) else 1
            j += 1
            kind = "quoted"
        elif c == "[":
            j = expr.find("]", k)
            j = n if j < 0 else j + 1
            kind = "bracket"
        else:
            k += 1
            continue
        push("code", seg, k)
        push(kind, k, min(j, n))
        k = seg = min(j, n)
    push("code", seg, n)
    return out


def sub_code(expr, pattern, fn):
    return "".join(pattern.sub(fn, t) if kind == "code" else t for kind, t in segments(expr))


CALL = re.compile(r"(?<![\w.'\]])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\(")


def code_only(expr):
    return "".join(t if kind == "code" else " " * len(t) for kind, t in segments(expr or ""))


def calls_in(expr, by=None):
    """Dotted function calls in a DAX expression (library functions only when `by` is given)."""
    found = []
    for m in CALL.finditer(code_only(expr)):
        name = m.group(1)
        if by is not None:
            name = find(by, name)
            if not name:
                continue
        if name not in found:
            found.append(name)
    return found


def call_args(expr, open_at):
    """expr[open_at] == '(' -> ([argument texts], index after the closing bracket)."""
    mask = code_only(expr)
    depth, start, args = 0, open_at + 1, []
    for k in range(open_at, len(expr)):
        ch = mask[k]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                last = expr[start:k].strip()
                if last or args:
                    args.append(last)
                return args, k + 1
        elif ch == "," and depth == 1:
            args.append(expr[start:k].strip())
            start = k + 1
    raise UdfError("a function call has no closing bracket")


# ---------------------------------------------------------------- inline mode
class _Counter:
    def __init__(self):
        self.n = 0

    def next(self):
        self.n += 1
        return self.n


def inline(expr, by, tokens, counter=None, stack=()):
    """Every library function call in `expr` replaced by its body (nested calls too): plain DAX that needs no UDF.
    VAL parameters become VARs bound to their argument; EXPR parameters are replaced by their argument text where
    they are used (so a measure is still evaluated per month); the function's own VARs get a unique suffix."""
    counter = counter or _Counter()
    out, pos = [], 0
    mask = code_only(expr)
    for m in CALL.finditer(mask):
        if m.start() < pos:
            continue
        name = find(by, m.group(1))
        if not name:
            continue
        if disabled_reason(by[name]):
            raise UdfError(f"{name}: {disabled_reason(by[name])}")
        if name in stack:
            raise UdfError(f"{name} calls itself: {' -> '.join(stack + (name,))}")
        args, end = call_args(expr, m.end() - 1)
        out.append(expr[pos:m.start()])
        out.append(expand(name, args, by, tokens, counter, stack))
        pos = end
    out.append(expr[pos:])
    return "".join(out)


def expand(name, args, by, tokens, counter, stack=()):
    f = by[name]
    params = f["params"]
    if len(args) > len(params):
        raise UdfError(f"{name} takes {len(params)} arguments; the call gives {len(args)}")
    args = list(args) + ["BLANK()"] * (len(params) - len(args))
    k = counter.next()
    _, _, body = split_tmdl(fill(text_of(f), tokens))
    body = body.strip()
    names = set(re.findall(r"(?i)\bVAR\s+([A-Za-z_]\w*)", code_only(body)))
    pnames = {p["name"] for p in params}
    rename = {v: f"{v}__i{k}" for v in names - pnames}
    binds, subst = [], {}
    for p, a in zip(params, args):
        a = inline(a, by, tokens, counter, stack + (name,))        # nested calls in the arguments first
        if p["mode"] == "VAL":
            var = f"__i{k}{p['name']}"
            binds.append(f"VAR {var} = {a}")
            subst[p["name"]] = var
        elif p["type"] in RAW_TYPES:
            subst[p["name"]] = a
        else:
            subst[p["name"]] = f"( {a} )"
    allnames = {**rename, **subst}
    if allnames:
        pat = re.compile(r"(?<![\w.@])(" + "|".join(re.escape(x) for x in sorted(allnames, key=len, reverse=True))
                         + r")(?!\w)")
        body = sub_code(body, pat, lambda m: allnames[m.group(1)])
    body = inline(body, by, tokens, counter, stack + (name,))
    if binds:
        return "(\n" + "\n".join(binds) + "\nRETURN\n" + body + "\n)"
    return "(\n" + body + "\n)"


def inline_problems(text, by):
    """Structural checks on inlined DAX (no Desktop needed): brackets balance, no library call is left, no token
    placeholder is left."""
    out = []
    mask = code_only(text)
    if mask.count("(") != mask.count(")"):
        out.append("brackets don't balance")
    left = calls_in(text, by)
    if left:
        out.append("calls left: " + ", ".join(left))
    if "{{" in text:
        out.append("a design token placeholder is left")
    return out


# ---------------------------------------------------------------- udfCard (layout.json)
FIELD_RE = re.compile(r"^\s*(?:'(?:[^']|'')+'|[A-Za-z_][\w ]*)?\s*\[[^\]]+\]\s*$")
MODES = ("calc", "measure", "inline")
REQUIRED = re.compile(r"Current|Past|Label|Date|Accent|Microchart", re.I)   # the rest may be left blank
FORMS = {"card": ("cardVisual", "cardVisual.svg-kpi-card"),
         "buttons": ("advancedSlicerVisual", "advancedSlicerVisual.svg-kpi-card-buttons")}


def arg_text(value, tokens, param):
    """A udfCard argument -> DAX text. "[Measure]" / "T[Col]" as written; "token:<colour>" the token's hex as text;
    "=<DAX>" the DAX after the =; a number as written; any other text as a DAX text literal; null BLANK()."""
    if value is None:
        return "BLANK()"
    if isinstance(value, bool):
        return "TRUE()" if value else "FALSE()"
    if isinstance(value, (int, float)):
        return repr(value)
    v = str(value)
    if v.startswith("icon:"):
        raise UdfError(f"{param}: icons are turned off in the kit (the icon pack's licence isn't recorded); leave "
                       "the icon out: the card draws no icon, or its own simple shape")
    if v.startswith("token:"):
        name = v[len("token:"):]
        try:
            hexv = token(tokens, name if "." in name else f"colors.{name}")
        except KeyError:
            raise UdfError(f"{param}: no design token {name}")
        return '"' + hexv + '"'
    if v.startswith("="):
        return v[1:].strip()
    if FIELD_RE.match(v):
        return v.strip()
    return '"' + v.replace('"', '""') + '"'


def measures_in(dax):
    """[Measure] references (no table) in DAX code, in order."""
    out = []
    segs = segments(dax)
    for i, (kind, t) in enumerate(segs):
        if kind != "bracket":
            continue
        prev = segs[i - 1] if i else ("code", "")
        if prev[0] == "quoted" or (prev[0] == "code" and re.search(r"[\w]\s*$", prev[1])):
            continue                                    # a column: T[Col] or 'T'[Col]
        if t[1:-1] not in out:
            out.append(t[1:-1])
    return out


def card_plan(vid, spec, by, tokens, installed=None):
    """A layout.json `udfCard` -> {"call", "expression", "mode", "form", "type", "template", "measures", "size",
    "name"}: what pbik build writes. Errors are plain sentences."""
    if not isinstance(spec, dict) or not spec.get("function"):
        raise UdfError(f"{vid}: udfCard needs a function (pbik udf list --role card)")
    name = find(by, spec["function"])
    if not name:
        raise UdfError(f"{vid}: there is no UDF called {spec['function']} in the kit's libraries")
    f = by[name]
    if disabled_reason(f):
        raise UdfError(f"{vid}: {name}: {disabled_reason(f)}")
    if f["role"] not in ("card", "chart"):
        raise UdfError(f"{vid}: {name} is a {f['role']}, not a card")
    mode = spec.get("mode", "inline")
    if mode not in MODES:
        raise UdfError(f"{vid}: udfCard mode is calc, measure or inline")
    form = spec.get("form", "card")
    if form not in FORMS:
        raise UdfError(f"{vid}: udfCard form is card or buttons")
    if form == "buttons" and mode == "calc":
        raise UdfError(f"{vid}: a button slicer can't hold a visual calculation: use mode measure or inline")
    args = dict(spec.get("args") or {})
    params = {p["name"]: p for p in f["params"]}
    unknown = [a for a in args if a not in params]
    if unknown:
        raise UdfError(f"{vid}: {name} has no argument {', '.join(unknown)} (it takes {', '.join(params)})")
    style = f.get("styleParams", {})
    missing = [p for p in params if p not in args and p not in style and REQUIRED.search(p)]
    if missing:
        raise UdfError(f"{vid}: {name} needs {', '.join(missing)}")
    if f.get("styles"):
        sp = next((p for p in params if re.search(r"Microchart|Chart|Style|Type", p) and p not in style
                   and params[p]["type"] == "STRING"), None)
        if sp and str(args.get(sp, "")) not in f["styles"]:
            raise UdfError(f"{vid}: {name} chart style {args.get(sp)!r} isn't one of {', '.join(f['styles'])}")
    if mode == "calc" and any(params[p]["type"] in RAW_TYPES for p in params):
        raise UdfError(f"{vid}: {name} takes columns, which a visual calculation can't pass: use mode inline or "
                       "measure")
    texts = []
    for p in f["params"]:
        n = p["name"]
        if n in args:
            texts.append(arg_text(args[n], tokens, n))
        elif re.search("icon", n, re.I):
            texts.append('""')                          # no icon: the card's own simple shape, or none
        else:
            texts.append("BLANK()")
    full = f"{name} ( " + ", ".join(texts) + " )"
    expression = full
    if mode == "inline":
        expression = inline(full, by, tokens)
        probs = inline_problems(expression, by)
        if probs:
            raise UdfError(f"{vid}: inlining {name} failed: {'; '.join(probs)}")
    vtype, template = FORMS[form]
    return {"function": name, "call": full, "expression": expression, "mode": mode, "form": form, "type": vtype,
            "template": spec.get("template", template), "measures": measures_in(full),
            "size": f.get("size"), "name": spec.get("name") or f"img {vid}",
            "hash": f["sha256"]}


def expand_layout(layout, by, tokens):
    """Every visual with `udfCard` -> the plain layout keys pbik build already knows, plus the report-level measures
    to write ({name: expression}). Returns (visuals, measures, errors)."""
    out, measures, errors = [], {}, []
    for v in layout.get("visuals", []):
        if "udfCard" not in v:
            out.append(v)
            continue
        try:
            p = card_plan(v["id"], v["udfCard"], by, tokens)
        except UdfError as e:
            errors.append(str(e))
            out.append(v)
            continue
        alt = (v.get("container") or {}).get("altText") if isinstance(v.get("container"), dict) else None
        if not (alt or v.get("altText")):
            errors.append(f"{v['id']}: a UDF card is an image, so it needs alt text that says the number and the "
                          "change in words (container.altText, A-01)")
        w = dict(v)
        w.setdefault("type", p["type"])
        w.setdefault("template", p["template"])
        props = dict(w.get("props") or {})
        props.setdefault("value.show@default", False)
        props.setdefault("label.show@default", False)
        if p["form"] == "card":
            props.setdefault("image.show@default", True)
            props.setdefault("image.imageType@default", "imageUrl")
            props.setdefault("image.position@default", "Bottom")
            props.setdefault("image.padding@default", {"int": 0})
        if p["mode"] == "calc":
            calc = {"calc": p["name"], "expression": p["call"], "dataType": "Text"}
            hidden = [{"field": f"[{m}]", "hidden": True} for m in p["measures"]]
            w["bindings"] = {"Data": [calc] + hidden}
            props["image.imageUrl@default"] = {"raw": {"expr": {"SelectRef": {"ExpressionName": p["name"]}}}}
            w.pop("sort", None)                         # an image card gets no saved sort (study F-05)
        else:
            measures[p["name"]] = p["expression"]
            if p["form"] == "card":
                w.setdefault("bindings", {"Data": [f"[{p['name']}]"]})
                props["image.imageUrl@default"] = {"expr": f"[{p['name']}]"}
            else:
                if "bindings" not in w:
                    errors.append(f"{v['id']}: a button-slicer UDF card needs bindings (the field whose members "
                                  "make the buttons)")
                props["image.image@*"] = {"expr": f"[{p['name']}]"}
        w["props"] = props
        b = dict(w.get("build") or {})
        b.setdefault("method", "svg")
        b.setdefault("step", 2)
        b.setdefault("reason", f"UDF card {p['function']}: a native card can't draw it")
        w["build"] = b
        w["udf"] = {"function": p["function"], "mode": p["mode"], "hash": p["hash"]}
        if p.get("size") and "h" in w and "w" in w:
            want = p["size"][1] / p["size"][0]
            have = w["h"] / w["w"] if w["w"] else want
            if abs(have - want) / want > 0.15:
                errors.append(f"{v['id']}: the box is {w['w']} x {w['h']}; {p['function']} draws "
                              f"{p['size'][0]} x {p['size'][1]}, so keep that shape (height about "
                              f"{round(w['w'] * want)} for this width)")
        out.append(w)
    return out, measures, errors


# ---------------------------------------------------------------- Desktop version check
def vt(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))[:2]) or (0,)


def desktop_check(root=".", version=None, model=None, uses=True):
    """(facts, problems): the Desktop version, whether its UDF switch is confirmed, the model's level."""
    from . import versions as V
    facts, problems = [], []
    if version is None:
        try:
            version = V.detect_desktop()
        except Exception:
            version = None
    if not version:
        facts.append("I couldn't find Power BI Desktop on this computer, so the UDF check is for the target only")
    else:
        if vt(version) < vt(FIRST_UDF_DESKTOP):
            problems.append(f"Power BI Desktop {version} is older than the first release with DAX functions "
                            f"({FIRST_UDF_DESKTOP}); use inline mode, or update Desktop")
        else:
            key = ".".join(str(x) for x in vt(version))
            note = PREVIEW_UNKNOWN.get(key)
            if note:
                facts.append(f"Power BI Desktop {version}: whether DAX functions still need the preview switch "
                             f"(File > Options > Preview features) is not confirmed: {note}")
            else:
                facts.append(f"Power BI Desktop {version} supports DAX functions; check the preview switch once")
    try:
        tv = V.target_for(root)[0].desktop
    except Exception:
        tv = "latest"
    if tv != "latest":
        if uses and vt(tv) < vt(FIRST_UDF_DESKTOP):
            problems.append(f"the project targets Desktop {tv}, older than {FIRST_UDF_DESKTOP}: UDF cards there need "
                            "inline mode")
    if model:
        lv = compatibility_level(model)
        if lv is not None and lv < MIN_LEVEL:
            facts.append(f"the model is at level {lv}; installing a function raises it to {MIN_LEVEL}")
    return facts, problems


def check_installed(rep, layout):
    """A calc- or measure-mode UDF card calls the function in the model: it must be there (inline mode needs none)."""
    folder = rep.model_folder()
    if not folder:
        return
    have = {n.lower() for n in model_functions(folder)}
    for v in layout.get("visuals", []):
        u = v.get("udf")
        if u and u.get("mode") != "inline" and u["function"].lower() not in have:
            raise UdfError(f"{v['id']} calls {u['function']} ({u['mode']} mode), but the model doesn't have it: add "
                           "it to the synthetic model, or use inline mode")


def write_measures(rep, measures, table=None):
    """The UDF cards' report-level measures (ImageUrl, Text) in reportExtensions.json; only a change is written.
    Returns [] (Report.write records the changed file itself)."""
    if not measures:
        return []
    from .objects import load as jload
    f = rep.ext_file()
    d = jload(f) if f.exists() else {"$schema": rep.schema_version("reportExtension"), "name": "extension",
                                     "entities": []}
    model = rep.model()
    if table is None:
        homes = sorted({m.table for m in model.all_measures()}) if model else []
        table = "_Measures" if model and "_Measures" in model.tables else (homes[0] if homes else None)
    if not table:
        raise UdfError("no measure table for the UDF cards' measures: set measureTable in layout.json")
    for name in measures:
        if model and model.measure_home(name):
            raise UdfError(f"{name!r} is already a model measure; give the card another name (udfCard.name)")
    ent = next((e for e in d["entities"] if e["name"] == table), None)
    if ent is None:
        ent = {"name": table, "measures": []}
        d["entities"].append(ent)
    lst = ent.setdefault("measures", [])
    for name, expr in measures.items():
        for e in d["entities"]:
            if e is not ent:
                e["measures"] = [m for m in e.get("measures", []) if m["name"] != name]
        m = {"name": name, "expression": expr, "dataType": "Text", "dataCategory": "ImageUrl"}
        pos = next((k for k, x in enumerate(lst) if x["name"] == name), None)
        if pos is None:
            lst.append(m)
        else:
            lst[pos] = {**lst[pos], **m}
    d["entities"] = [e for e in d["entities"] if e.get("measures")]
    rep.write(f, d)
    rep._ext = None
    return []
