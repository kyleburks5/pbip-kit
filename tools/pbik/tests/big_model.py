"""A large made-up semantic model for the Phase 1 tests: nothing real, written fresh into a temp folder.

    write(folder, fmt) with fmt "tmdl" (a definition folder), "script" (one createOrReplace TMDL file), "semanticmodel"
    (a .SemanticModel folder with a fake cache.abf and .pbi folder) or "tmsl" (a .bim JSON export).

66 tables: a calculated calendar, 10 facts, 8 dimensions, 6 account / member-like tables, 20 option tables (Enter
data, 2-40 rows, a label and an order column), 15 other query tables, 5 typed
tables that aren't option lists; 400 measures; 3 RLS roles; M partitions with
invented servers; relationships from every fact to the calendar and the dimensions.
"""
import base64, json, pathlib, zlib

ENTITIES = ["Account", "Member", "Customer", "Client", "Vendor", "Contact"]
DIMS = [f"Dim {x}" for x in ("Region", "Product", "Channel", "Segment", "Store", "Team", "Plan", "Category")]
FACTS = [f"Fact {x}" for x in ("Orders", "Returns", "Visits", "Budget", "Forecast", "Tickets", "Shipments",
                                "Payments", "Claims", "Surveys")]
OPTIONS = [f"Option {k:02d}" for k in range(1, 21)]
OTHER = [f"Lookup {k:02d}" for k in range(1, 16)]
ROLES = [("Region Leads", "Dim Region"), ("Store Managers", "Dim Store"), ("Account Owners", "Account")]


def q(n):
    return n if n.replace("_", "").isalnum() else "'" + n + "'"


def deflate(rows):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(c.compress(json.dumps(rows).encode()) + c.flush()).decode()


def m_source(table):
    return (f'let Source = Sql.Database("server-{abs(hash(table)) % 97}.example.invalid", "example-db"),\n'
            f'\t\t\t\t    Data = Source{{[Schema="dbo",Item="{table.lower().replace(" ", "_")}"]}}[Data]\n\t\t\t\tin Data')


def tables():
    """[(name, [(column, type)], partition kind, partition source, [measures])]"""
    out = [("Calendar", [("Date", "dateTime"), ("Year", "int64"), ("Month No", "int64"), ("Month", "string")],
            "calculated", 'ADDCOLUMNS ( CALENDAR ( DATE ( 2023, 1, 1 ), DATE ( 2025, 12, 31 ) ), "Year", YEAR ( [Date] ), '
                          '"Month No", MONTH ( [Date] ), "Month", FORMAT ( [Date], "MMM" ) )', [])]
    for d in DIMS + ENTITIES:
        key = d.replace("Dim ", "") + "Key"
        cols = [(key, "int64"), (f"{d.replace('Dim ', '')} Name", "string"), ("Group", "string")]
        out.append((d, cols, "m", m_source(d), []))
    for f in FACTS:
        cols = [("Date", "dateTime"), ("Amount", "decimal"), ("Quantity", "int64"), ("Status", "string")]
        cols += [(d.replace("Dim ", "") + "Key", "int64") for d in DIMS[:4]] + [("AccountKey", "int64")]
        out.append((f, cols, "m", m_source(f), []))
    for k, o in enumerate(OPTIONS):
        n = 2 + (k * 2) % 39
        rows = [[f"Choice {i + 1}", str(i + 1)] for i in range(n)]
        src = (f'Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("{deflate(rows)}", '
               f'BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = '
               f'true]) in type table [#"Label" = _t, #"Sort Order" = _t])')
        out.append((o, [("Label", "string"), ("Sort Order", "int64")], "m", src, []))
    for o in OTHER:
        out.append((o, [("Code", "string"), ("Description", "string")], "m", m_source(o), []))
    for k in range(1, 6):                                      # typed tables that aren't option lists: a person decides
        rows = [[f"Region {i}", str(100 * i)] for i in range(1, 4)]
        src = (f'Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("{deflate(rows)}", '
               f'BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = '
               f'true]) in type table [#"Region Code" = _t, #"Target" = _t])')
        out.append((f"Manual Targets {k}", [("Region Code", "string"), ("Target", "int64")], "m", src, []))
    measures = []
    for i in range(400):
        f = FACTS[i % len(FACTS)]
        layer = i // len(FACTS)
        if layer == 0:
            measures.append((f"{f} Amount", f"SUM ( {q(f)}[Amount] )"))
        elif layer == 1:
            measures.append((f"{f} Qty", f"SUM ( {q(f)}[Quantity] )"))
        elif layer == 2:
            measures.append((f"{f} Avg", f"DIVIDE ( [{f} Amount], [{f} Qty] )"))
        else:
            base = f"{f} Amount"
            measures.append((f"{f} M{layer:02d}",
                             f"CALCULATE ( [{base}], DATEADD ( Calendar[Date], -{layer}, MONTH ) )"))
    out.append(("_Measures", [], "m", "#table({}, {})", measures))
    return out


def tmdl_texts():
    """{relative file: text} of the TMDL definition folder."""
    files = {"model.tmdl": "model Model\n\tculture: en-US\n\n" + "".join(f"ref table {q(t[0])}\n" for t in tables()),
             "database.tmdl": "database\n\tcompatibilityLevel: 1606\n"}
    for name, cols, kind, src, measures in tables():
        L = [f"table {q(name)}", ""]
        for c, typ in cols:
            L += [f"\tcolumn {q(c)}", f"\t\tdataType: {typ}", f"\t\tsourceColumn: {c}", ""]
        for m, e in measures:
            L += [f"\tmeasure {q(m)} = {e}", ""]
        L += [f"\tpartition {q(name)} = {kind}", "\t\tmode: import", "\t\tsource ="]
        L += ["\t\t\t\t" + ln.strip() for ln in src.splitlines()]
        files[f"tables/{name}.tmdl"] = "\n".join(L) + "\n"
    rels = []
    for k, f in enumerate(FACTS):
        rels += [f"relationship 0b{k:06d}-0000-4000-8000-000000000001", f"\tfromColumn: {q(f)}.Date",
                 "\ttoColumn: Calendar.Date", ""]
        for j, d in enumerate(DIMS[:4]):
            key = d.replace("Dim ", "") + "Key"
            rels += [f"relationship 0b{k:06d}-0000-4000-8000-0000000001{j:02d}", f"\tfromColumn: {q(f)}.{key}",
                     f"\ttoColumn: {q(d)}.{key}", ""]
    files["relationships.tmdl"] = "\n".join(rels)
    for role, table in ROLES:
        files[f"roles/{role}.tmdl"] = f"role {q(role)}\n\tmodelPermission: read\n\n\ttablePermission {q(table)} = TRUE ()\n"
    return files


def write(folder, fmt="tmdl", name="Example Big"):
    folder = pathlib.Path(folder)
    files = tmdl_texts()
    if fmt in ("tmdl", "semanticmodel"):
        root = folder / f"{name}.SemanticModel" if fmt == "semanticmodel" else folder / name
        d = root / "definition"
        for rel, text in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text(text, encoding="utf-8")
        if fmt == "semanticmodel":
            (root / "definition.pbism").write_text(json.dumps({"version": "4.2", "settings": {}}), encoding="utf-8")
            (root / ".pbi").mkdir()
            (root / ".pbi" / "cache.abf").write_bytes(b"MADE-UP CACHE " * 64)
            (root / ".pbi" / "localSettings.json").write_text("{}", encoding="utf-8")
        return root
    if fmt == "script":
        parts = [t for rel, t in files.items() if rel.startswith(("tables/", "relationships", "roles/"))]
        text = "createOrReplace\n\n" + "\n".join("\t" + ln if ln.strip() else ln for p in parts for ln in p.splitlines())
        f = folder / f"{name}.tmdl"
        f.write_text(text + "\n", encoding="utf-8")
        return f
    if fmt == "tmsl":
        tabs = []
        for tname, cols, kind, src, measures in tables():
            tabs.append({"name": tname, "columns": [{"name": c, "dataType": typ} for c, typ in cols],
                         "measures": [{"name": m, "expression": e} for m, e in measures],
                         "partitions": [{"name": tname, "source": {"type": kind, "expression": src.splitlines()}}]})
        rels = [{"fromTable": f, "fromColumn": "Date", "toTable": "Calendar", "toColumn": "Date"} for f in FACTS]
        roles = [{"name": r, "tablePermissions": [{"name": t, "filterExpression": "TRUE ()"}]} for r, t in ROLES]
        doc = {"name": name, "compatibilityLevel": 1606,
               "model": {"tables": tabs, "relationships": rels, "roles": roles}}
        f = folder / f"{name}.bim"
        f.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        return f
    raise ValueError(fmt)
