"""Read a semantic model's TMDL folder (tables, columns, measures, relationships) and check DAX references.

Based on Microsoft's TMDL overview: objects are declared as `<keyword> <name>` (names with spaces in single quotes,
'' inside), properties as `name: value` one level deeper, expressions after `=` (on the same line, on deeper lines, or
inside ``` fences), descriptions as `///` lines above the object. Indentation is tabs (4 spaces count as one level).
Only what pbik needs is read; everything else is skipped.
"""
import pathlib, re

KEYWORDS = {"table", "column", "measure", "partition", "hierarchy", "level", "annotation", "extendedProperty",
            "calculationGroup", "calculationItem", "relationship", "expression", "role", "perspective", "culture",
            "model", "database", "ref", "formatStringDefinition", "detailRowsDefinition", "tablePermission",
            "relatedColumnDetails", "groupByColumn", "variation", "linguisticMetadata", "function", "calendar",
            "dataSource", "queryGroup", "member", "alternateOf", "changedProperty", "refreshPolicy"}
NUMERIC = {"int64", "double", "decimal"}


class Measure:
    def __init__(self, table, name, expression, file, line):
        self.table, self.name, self.expression, self.file, self.line = table, name, expression, file, line
        self.description = None
        self.format_string = None
        self.format_string_definition = False
        self.data_category = None
        self.data_type = None
        self.display_folder = None
        self.hidden = False

    def is_text(self):
        """Declared as text (dataType string) or as an image URL (dataCategory ImageUrl): no number format applies."""
        return (self.data_type or "").lower() in ("string", "text") or (self.data_category or "").lower() == "imageurl"


class Column:
    def __init__(self, table, name, expression, file, line):
        self.table, self.name, self.expression, self.file, self.line = table, name, expression, file, line
        self.data_type = None
        self.sort_by = None
        self.description = None
        self.hidden = False


class Table:
    def __init__(self, name, file):
        self.name, self.file = name, file
        self.columns, self.measures, self.partitions = {}, {}, []   # partitions: (kind, expression, line)
        self.description = None


class Relationship:
    def __init__(self, name, file, line):
        self.name, self.file, self.line = name, file, line
        self.from_column = self.to_column = None    # (table, column)


class Model:
    def __init__(self, folder):
        self.folder = pathlib.Path(folder)
        self.tables, self.relationships, self.functions = {}, [], set()

    # lookups
    def measure_home(self, name):
        """Tables that hold a measure of this name."""
        return [t.name for t in self.tables.values() if name in t.measures]

    def column_type(self, table, column):
        t = self.tables.get(table)
        c = t.columns.get(column) if t else None
        return c.data_type if c else None

    def has_field(self, table, name):
        t = self.tables.get(table)
        return bool(t) and (name in t.columns or name in t.measures)

    def all_measures(self):
        for t in self.tables.values():
            yield from t.measures.values()


def unquote(name):
    name = name.strip()
    if len(name) >= 2 and name[0] == "'" and name[-1] == "'":
        return name[1:-1].replace("''", "'")
    return name


def split_decl(rest):
    """'Name = expr' / "'A b' = expr" / 'Name' -> (name, expr or None)."""
    rest = rest.strip()
    if rest.startswith("'"):
        k = 1
        while k < len(rest):
            if rest[k] == "'":
                if k + 1 < len(rest) and rest[k + 1] == "'":
                    k += 2
                    continue
                break
            k += 1
        name, tail = rest[:k + 1], rest[k + 1:].strip()
    else:
        m = re.match(r"([^=]*?)\s*(=.*)?$", rest)
        name, tail = m.group(1), (m.group(2) or "")
    expr = tail[1:].strip() if tail.startswith("=") else None
    return unquote(name), expr


def split_ref(text):
    """'Table'.'Column' / Table.Column -> (table, column)."""
    text = text.strip()
    m = re.fullmatch(r"('(?:[^']|'')+'|[^.']+)\.('(?:[^']|'')+'|.+)", text)
    if not m:
        return None, text
    return unquote(m.group(1)), unquote(m.group(2))


def level(line):
    ws = re.match(r"[ \t]*", line).group(0)
    return ws.count("\t") + ws.count(" ") // 4


def load(folder):
    """Parse <X>.SemanticModel/definition (or the folder itself) into a Model."""
    folder = pathlib.Path(folder)
    if (folder / "definition").is_dir():
        folder = folder / "definition"
    model = Model(folder)
    files = sorted(folder.glob("*.tmdl")) + sorted((folder / "tables").glob("*.tmdl"))
    for f in files:
        _parse(model, f)
    return model


def _parse(model, f):
    lines = f.read_text(encoding="utf-8-sig").splitlines()
    rel = str(f.relative_to(model.folder.parent)).replace("\\", "/") if model.folder.parent in f.parents else f.name
    table = obj = None          # current table, current level-1 object (column / measure / partition / relationship)
    doc = []
    k = 0
    while k < len(lines):
        raw = lines[k]
        line = raw.strip()
        lv = level(raw)
        k += 1
        if not line:
            continue
        if line.startswith("///"):
            doc.append(line[3:].strip())
            continue
        desc, doc = (" ".join(doc) or None), []
        word, _, rest = line.partition(" ")
        if word in KEYWORDS and rest and ":" not in word:
            name, expr = split_decl(rest)
            # expression continuation: ``` fence, or lines deeper than the object's properties
            if expr == "```" or (expr or "").startswith("```"):
                body = []
                while k < len(lines) and lines[k].strip() != "```":
                    body.append(lines[k]); k += 1
                k += 1
                expr = "\n".join(body)
            elif expr is not None:
                body = [expr] if expr else []
                while k < len(lines) and (not lines[k].strip() or level(lines[k]) >= lv + 2):
                    body.append(lines[k]); k += 1
                expr = "\n".join(body).strip()
            if word == "table" and lv == 0:
                table = model.tables.setdefault(name, Table(name, rel))
                table.description = desc
                obj = None
            elif word == "relationship" and lv == 0:
                obj = Relationship(name, rel, k)
                model.relationships.append(obj)
                table = None
            elif word == "function" and lv == 0:
                model.functions.add(name)
                obj = None
            elif table and lv == 1 and word == "measure":
                obj = Measure(table.name, name, expr or "", rel, k)
                obj.description = desc
                table.measures[name] = obj
            elif table and lv == 1 and word == "column":
                obj = Column(table.name, name, expr, rel, k)
                obj.description = desc
                table.columns[name] = obj
            elif table and lv == 1 and word == "partition":
                kind = (expr or "").strip()
                obj = ("partition", kind)
                # the source expression is a property of the partition: `source = ...`
                table.partitions.append([kind, None, k])
            elif table and lv == 1:
                obj = None
            elif lv == 2 and word == "formatStringDefinition" and isinstance(obj, Measure):
                obj.format_string_definition = True
            continue
        # properties
        m = re.match(r"([A-Za-z]+)\s*(:|=)\s*(.*)$", line)
        if not m:
            if line == "isHidden" and isinstance(obj, (Measure, Column)):
                obj.hidden = True
            continue
        key, sep, val = m.group(1), m.group(2), m.group(3).strip()
        if sep == "=":           # expression property (partition source, formatStringDefinition, ...)
            body = [val] if val and val != "```" else []
            if val.startswith("```"):
                while k < len(lines) and lines[k].strip() != "```":
                    body.append(lines[k]); k += 1
                k += 1
            else:
                while k < len(lines) and (not lines[k].strip() or level(lines[k]) >= lv + 1):
                    body.append(lines[k]); k += 1
            text = "\n".join(body).strip()
            if key == "source" and isinstance(obj, tuple) and table and table.partitions:
                table.partitions[-1][1] = text
            elif key == "formatStringDefinition" and isinstance(obj, Measure):
                obj.format_string_definition = True
            continue
        if isinstance(obj, Measure):
            if key == "formatString":
                obj.format_string = val
            elif key == "dataCategory":
                obj.data_category = val
            elif key == "dataType":
                obj.data_type = val
            elif key == "displayFolder":
                obj.display_folder = val
        elif isinstance(obj, Column):
            if key == "dataType":
                obj.data_type = val
            elif key == "sortByColumn":
                obj.sort_by = unquote(val)
        elif isinstance(obj, Relationship):
            if key == "fromColumn":
                obj.from_column = split_ref(val)
            elif key == "toColumn":
                obj.to_column = split_ref(val)


# ---------------------------------------------------------------- DAX references
DAX_WORDS = {"RETURN", "VAR", "IN", "NOT", "AND", "OR", "TRUE", "FALSE", "DEFINE", "EVALUATE", "MEASURE", "ORDER",
             "BY", "ASC", "DESC", "START", "AT", "COLUMN", "TABLE", "THEN", "ELSE"}


def strip_dax(expr):
    """Remove comments and string literals; return (code, [string literal values])."""
    out, strings, k, n = [], [], 0, len(expr)
    while k < n:
        c = expr[k]
        if expr.startswith("//", k) or expr.startswith("--", k):
            j = expr.find("\n", k)
            k = n if j < 0 else j
        elif expr.startswith("/*", k):
            j = expr.find("*/", k + 2)
            k = n if j < 0 else j + 2
        elif c == '"':
            j, buf = k + 1, []
            while j < n:
                if expr[j] == '"':
                    if j + 1 < n and expr[j + 1] == '"':
                        buf.append('"'); j += 2; continue
                    break
                buf.append(expr[j]); j += 1
            strings.append("".join(buf))
            out.append('""')
            k = j + 1
        else:
            out.append(c)
            k += 1
    return "".join(out), strings


def references(expr):
    """[(table or None, name)] referenced by a DAX expression, plus the VAR names and string values in it."""
    code, strings = strip_dax(expr or "")
    refs = []
    for m in re.finditer(r"'((?:[^']|'')+)'\s*\[([^\]]+)\]", code):
        refs.append((m.group(1).replace("''", "'"), m.group(2)))
    code2 = re.sub(r"'(?:[^']|'')+'\s*\[[^\]]+\]", " ", code)
    for m in re.finditer(r"(?<![\w\]\.])([A-Za-z_][\w\.]*)\s*\[([^\]]+)\]", code2):
        if m.group(1).upper() in DAX_WORDS:
            refs.append((None, m.group(2)))
        else:
            refs.append((m.group(1), m.group(2)))
    code3 = re.sub(r"(?<![\w\]\.])[A-Za-z_][\w\.]*\s*\[[^\]]+\]", " ", code2)
    for m in re.finditer(r"\[([^\]]+)\]", code3):
        refs.append((None, m.group(1)))
    variables = set(re.findall(r"\bVAR\s+([A-Za-z_][\w]*)", code, flags=re.I))
    return refs, variables, strings


def check_references(model, expr):
    """Unresolved references in a DAX expression, as readable strings."""
    refs, variables, strings = references(expr)
    names_anywhere = {c for t in model.tables.values() for c in list(t.columns) + list(t.measures)}
    generated = set(strings) | {"Value"} | {f"Value{k}" for k in range(1, 10)}
    bad = []
    for table, name in refs:
        if table is None:
            if name not in names_anywhere and name not in generated:
                bad.append(f"[{name}]")
        elif table in variables:
            continue
        elif table not in model.tables:
            bad.append(f"'{table}'[{name}] (no table {table})")
        elif not model.has_field(table, name) and name not in generated:
            bad.append(f"'{table}'[{name}]")
    return list(dict.fromkeys(bad))
