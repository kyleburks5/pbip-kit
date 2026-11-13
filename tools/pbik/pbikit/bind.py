"""bind: move a report from its synthetic model to the published one and back (docs/design/synth-to-live.md).

check    every field the report uses exists in the contract (through bind-map.json when there is one)
prepare  planned measures (synthetic-only) become report-level measures, planned dependencies inlined
live     person-only: back up, rewrite field references per the map, write definition.pbir byConnection
local    put the synthetic connection back (refuses while Desktop is open)
"""
import datetime, hashlib, json, pathlib, re, shutil

from . import bindrefs as BR, dataclass_ as DC, names as N, tmdl
from .objects import dumps, load
from .report import Report
from .synth import ContractError, read_json, specs, write_json

GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
PBIR_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"


class BindError(Exception):
    pass


def state_dir(root):
    return pathlib.Path(root) / ".pbik" / "bind"


def sha(b):
    return hashlib.sha1(b).hexdigest()


def report_files(rep):
    """Every file of the report folder except .pbi (Desktop's local settings), relative paths."""
    out = []
    for f in sorted(rep.path.rglob("*")):
        if f.is_file() and ".pbi" not in f.relative_to(rep.path).parts:
            out.append(str(f.relative_to(rep.path)).replace("\\", "/"))
    return out


def json_docs(rep):
    """[(relative path, doc)] for every JSON file under definition/."""
    out = []
    for f in sorted(rep.defn.rglob("*.json")):
        try:
            out.append((str(f.relative_to(rep.path)).replace("\\", "/"), load(f)))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------- context
class Context:
    def __init__(self, report, root=None):
        self.rep = Report(report)
        self.root = (pathlib.Path(root) if root else self.rep.path.parent).resolve()
        self.contract = read_json(specs(self.root) / "contract.json")
        if self.contract is None:
            raise ContractError("no contract: run `pbik synth contract` first")
        self.gen = read_json(specs(self.root) / "generate.json", {})
        self.state = DC.bind_state(self.root)
        self.map = read_json(specs(self.root) / "bind-map.json", {})
        mf = self.rep.model_folder()
        if self.state and self.state.get("mode") == "live":
            mf = self.root / self.state["synthetic"]
        self.model_folder = mf
        self.model = tmdl.load(mf) if mf else None
        measures = [(t.name, m) for t in (self.model.tables.values() if self.model else []) for m in t.measures]
        self.mapper = BR.Mapper.from_map(self.map, measures)
        self.tables = list(self.model.tables) if self.model else list(self.contract["tables"])

    def planned(self):
        prepared = {N.key(x) for x in self.gen.get("prepared", [])}
        return {k: v for k, v in self.gen.get("plannedMeasures", {}).items() if N.key(k) not in prepared}

    def synthetic_has(self, t, name):
        if not self.model:
            return True
        mt = N.find(self.model.tables, t)
        return bool(mt) and (N.ci_in(name, self.model.tables[mt].columns) or N.ci_in(name, self.model.tables[mt].measures))

    def contract_has(self, t, name, kind=None):
        ct = N.find(self.contract["tables"], t)
        if not ct:
            return False
        tb = self.contract["tables"][ct]
        if kind == "Measure":
            return N.ci_in(name, tb["measures"])
        if kind == "Column":
            return N.ci_in(name, tb["columns"])
        return N.ci_in(name, tb["columns"]) or N.ci_in(name, tb["measures"])

    def contract_type(self, t, name):
        ct = N.find(self.contract["tables"], t)
        col = N.find(self.contract["tables"][ct]["columns"], name) if ct else None
        return self.contract["tables"][ct]["columns"][col]["type"] if col else None

    def synthetic_type(self, t, name):
        mt = N.find(self.model.tables, t) if self.model else None
        col = N.find(self.model.tables[mt].columns, name) if mt else None
        return self.model.tables[mt].columns[col].data_type if col else None


# ---------------------------------------------------------------- check
class Result:
    def __init__(self):
        self.errors, self.stale, self.notes = [], [], []

    def ok(self):
        return not self.errors and not self.stale

    def lines(self):
        return self.errors + [f"stale reference {x}" for x in self.stale]


def check(report, root=None, ctx=None):
    """Every field the report uses against the synthetic model and the contract (through the map)."""
    ctx = ctx or Context(report, root)
    res = Result()
    ext = ctx.rep.extensions()
    planned = ctx.planned()
    seen = set()
    live = ctx.state and ctx.state.get("mode") == "live"
    for rel, doc in json_docs(ctx.rep):
        if rel.endswith("reportExtensions.json"):
            continue
        for kind, ent, prop, schema, path in BR.sites(doc, ctx.tables):
            if kind == "Entity":
                if not live and schema != "extension" and ctx.model and not N.find(ctx.model.tables, ent)                         and ctx.mapper.table(ent) == ent and (rel, N.key(ent)) not in seen:
                    seen.add((rel, N.key(ent)))
                    res.stale.append(f"{rel} {path}: table {ent}")
                continue
            if prop is None:
                continue
            key = (rel, kind, N.key(ent), N.key(prop), schema)
            if key in seen:
                continue
            seen.add(key)
            where = f"{rel} {path}"
            if kind == "ref" and any(N.same(t, ent) and N.same(n, prop) for t, n in ext):
                continue                                  # the queryRef of a report-level measure
            if schema == "extension":
                if not any(N.same(t, ent) and N.same(n, prop) for t, n in ext):
                    res.errors.append(f"{where}: extension measure {ent}[{prop}] is not in reportExtensions.json")
                continue
            if live:                            # names are live now: check them against the contract directly
                if not ctx.contract_has(ent, prop, kind if kind != "ref" else None):
                    res.errors.append(f"{where}: {ent}[{prop}] is not in the contract")
                continue
            check_field(ctx, res, where, kind, ent, prop, planned)
    from . import filtertypes as FT
    # the live column types decide (contract, through the map): the filters are what goes live
    types = (lambda e, col: ctx.contract_type(e, col)) if live else         (lambda e, col: ctx.contract_type(*ctx.mapper.field(e, col)))
    for rel, doc in json_docs(ctx.rep):
        for msg in FT.issues(doc, types):
            res.errors.append(f"{rel}: {msg}")
    for (t, n), m in ext.items():
        check_dax(ctx, res, f"reportExtensions.json {t}[{n}]", m.get("expression", ""), planned)
    accepted = ctx.map.get("acceptDax", []) if not live else []
    for n, old, new in ([] if live else dax_changes(ctx)):
        if not N.ci_in(n, accepted):
            res.errors.append(f"reportExtensions.json [{n}]: the map changes its DAX to {new!r}; check it, then "
                              "list it in bind-map.json acceptDax")
        if not N.find(ctx.contract["tables"], ctx.mapper.table(t)):
            res.errors.append(f"reportExtensions.json: entity {t} (live {ctx.mapper.table(t)}) is not in the contract")
    return res


def check_field(ctx, res, where, kind, ent, prop, planned):
    if N.ci_in(prop, planned) and kind in ("Measure", "ref"):
        res.errors.append(f"{where}: planned measure [{prop}] isn't in the live model: run `pbik bind prepare`")
        return
    if not ctx.synthetic_has(ent, prop) and not ctx.mapper.entry(ent, prop):
        res.stale.append(f"{where}: {ent}[{prop}]")      # in neither the synthetic model nor the map
        return
    lt, ln = ctx.mapper.field(ent, prop)
    if not ctx.contract_has(lt, ln, kind if kind != "ref" else None):
        mapped = (lt, ln) != (ent, prop)
        res.errors.append(f"{where}: {ent}[{prop}]" + (f" -> live {lt}[{ln}]" if mapped else "") +
                          " is not in the contract" + (" (map error)" if mapped else ""))
        return
    if kind == "Column":
        st, ct = ctx.synthetic_type(ent, prop), ctx.contract_type(lt, ln)
        if st and ct and st != ct:
            dev = next((d for d in ctx.gen.get("deviations", []) if N.same(d.get("table"), ent)
                        and N.same(d.get("column"), prop)), None)
            if dev:                                    # a synthetic-only change generate.json records
                res.notes.append(f"{where}: {ent}[{prop}] is {st} in the synthetic model, {ct} live "
                                 f"(deviation: {dev.get('why', 'recorded in generate.json')})")
            else:
                res.errors.append(f"{where}: {ent}[{prop}] is {st} here, {ct} in the contract")


def check_dax(ctx, res, where, expr, planned):
    refs, variables, strings = tmdl.references(expr)
    virtual = tmdl.virtual_names(expr)
    for t, name in refs:
        if t and N.ci_in(t, variables):
            continue                                   # a column of a VAR table
        if virtual(name) and (t is None or not N.find(ctx.tables, t)):
            continue                                   # a column DAX defines (virtual tables, @names)
        if t is None:
            lt, ln = ctx.mapper.field(None, name)
            ok = any(ctx.contract_has(tt, ln) for tt in ctx.contract["tables"])
            known = any(ctx.synthetic_has(tt, name) for tt in ctx.tables) or ctx.mapper.entry(None, name)
        else:
            lt, ln = ctx.mapper.field(t, name)
            ok = ctx.contract_has(lt, ln)
            known = ctx.synthetic_has(t, name) or ctx.mapper.entry(t, name)
        if not known and not N.ci_in(name, planned) and not ctx.state:
            res.stale.append(f"{where}: {(t or '')}[{name}]")
        elif N.ci_in(name, planned):
            res.errors.append(f"{where}: uses planned measure [{name}]: run `pbik bind prepare`")
        elif not ok:
            res.errors.append(f"{where}: {(t or '')}[{name}] is not in the contract")


# ---------------------------------------------------------------- prepare
MEASURE_TOKEN = re.compile(r"(?:(?:'(?:[^']|'')+'|[A-Za-z_][\w\.]*)\s*)?\[([^\]]+)\]")


def inline(expr, planned, stack=()):
    """Planned measure references replaced by CALCULATE ( <their DAX> ), recursively (a measure reference is an
    implicit CALCULATE, so this keeps their meaning inside iterators too)."""
    def sub(m):
        name = N.find(planned, m.group(1))
        if not name or m.group(0).lstrip()[:1] not in ("[",):
            return m.group(0)
        if name in stack:
            raise BindError(f"planned measures reference each other in a loop: {' -> '.join(stack + (name,))}")
        return "CALCULATE ( " + inline(planned[name]["expression"].strip(), planned, stack + (name,)) + " )"
    return BR.sub_code(expr, MEASURE_TOKEN, sub)


def prepare(report, root=None, query=None, out=print):
    """Planned measures the report uses -> reportExtensions.json; the synthetic model drops them.
    query(dax) -> [[before, after]] checks the values first (None: not checked, said so)."""
    from . import extensions as X
    ctx = Context(report, root)
    planned = ctx.planned()
    used = []
    for rel, doc in json_docs(ctx.rep):
        for kind, ent, prop, schema, path in BR.sites(doc, ctx.tables):
            if kind in ("Measure", "ref") and schema != "extension" and N.ci_in(prop, planned):
                name = N.find(planned, prop)
                if name not in used:
                    used.append(name)
    if not used:
        out("no planned measures in the report")
        return []
    bodies = {n: inline(planned[n]["expression"].strip(), planned, (n,)) for n in used}
    if query:
        dax = "EVALUATE ROW ( " + ", ".join(f'"b{k}", [{n}], "a{k}", {bodies[n]}' for k, n in enumerate(used)) + " )"
        row = query(dax)
        for k, n in enumerate(used):
            if str(row[2 * k]) != str(row[2 * k + 1]):
                raise BindError(f"[{n}]: {row[2 * k]} before, {row[2 * k + 1]} inlined: nothing written")
            out(f"[{n}]: same value before and after ({row[2 * k]})")
    else:
        out("values not checked (no --port): run `pbik bind prepare --port auto` with the synthetic model open, "
            "or compare the cards by eye after the rebuild")
    g = ctx.gen                                    # the synthetic model drops them first (one name per report)
    g["prepared"] = sorted(set(g.get("prepared", [])) | set(used), key=N.key)
    write_json(specs(ctx.root) / "generate.json", g)
    if DC.is_synthetic(ctx.model_folder):
        from . import synthgen as G
        G.generate(ctx.root, ctx.model_folder.name[:-len(".SemanticModel")], ctx.model_folder)
        ctx.rep._model = None
    for n in used:
        X_add(X, ctx.rep, n, bodies[n], planned[n])
        for rel, doc in json_docs(ctx.rep):
            if mark_extension(doc, n):
                ctx.rep.write(ctx.rep.path / rel, doc)
    return used


def port_query(report, port):
    """query(dax) -> first row's values, through run-dax.ps1 on the open Desktop model (restricted guard first)."""
    import shutil as sh, subprocess, tempfile
    from . import slicerfit as SF
    rep = Report(report)
    why = DC.guard(rep.path.parent, "dax")
    if why:
        raise BindError(why)

    def query(dax):
        script = SF.find_run_dax(rep.path)
        ps = sh.which("powershell") or sh.which("pwsh")
        if not ps or not script:
            raise BindError("PowerShell or .claude/scripts/run-dax.ps1 not found")
        q = pathlib.Path(tempfile.gettempdir()) / "pbik_bind_prepare.dax"
        q.write_text(dax, encoding="utf-8")
        r = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-File", str(q),
                            "-Port", str(SF.require_port(port))], capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        line = (r.stdout or "").strip().splitlines()[:1]
        if not line or line[0].startswith("ERROR"):
            raise BindError(f"value check failed: {(line or [r.stderr])[0]}")
        return line[0].split(SF.SEP)
    return query


def X_add(X, rep, name, expr, p):
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        X.add(str(rep.path), name, expr, None, p.get("dataType", "Double"), p.get("table", "_Measures"),
              p.get("formatString"), p.get("description"))
    rep.reset_cache()


def mark_extension(doc, name):
    """Point every reference to measure `name` at the report extension (SourceRef / From Schema "extension")."""
    changed = False

    def walk(node, froms):
        nonlocal changed
        if isinstance(node, dict):
            if isinstance(node.get("From"), list):
                froms = dict(froms)
                for fr in node["From"]:
                    if isinstance(fr, dict) and "Entity" in fr:
                        froms[fr.get("Name")] = (fr, node["From"])
            x = node.get("Measure")
            if isinstance(x, dict) and N.same(x.get("Property"), name):
                sr = x.get("Expression", {}).get("SourceRef", {})
                if "Entity" in sr and sr.get("Schema") != "extension":
                    sr["Schema"] = "extension"
                    changed = True
                elif sr.get("Source") in froms:
                    fr, lst = froms[sr["Source"]]
                    if fr.get("Schema") != "extension":
                        twin = next((f for f in lst if f.get("Entity") == fr["Entity"] and f.get("Schema") == "extension"), None)
                        if twin is None:
                            twin = dict(fr, Name=fr["Name"] + "x", Schema="extension")
                            lst.append(twin)
                        sr["Source"] = twin["Name"]
                        changed = True
            for v in node.values():
                walk(v, froms)
        elif isinstance(node, list):
            for v in node:
                walk(v, froms)
    walk(doc, {})
    return changed


# ---------------------------------------------------------------- live
def model_id(text):
    """The semantic model ID from a /datasets/<id>/, /semanticmodels/<id>/ or /modeling/<id>/ link, or the ID."""
    text = (text or "").strip()
    m = re.search(r"/(?:datasets|semanticmodels|modeling)/(" + GUID + r")(?:[/?#]|$)", text, re.I)
    if m:
        return m.group(1).lower()
    if re.fullmatch(GUID, text):
        return text.lower()
    raise BindError(f"no semantic model ID in {text!r}: pass the ID, or a link with /datasets/<id>/, "
                    "/semanticmodels/<id>/ or /modeling/<id>/")


def workspace_warnings(ws, known=()):
    """Signs a typed workspace name is wrong (item 6)."""
    out = []
    if ws != ws.strip() or "  " in ws:
        out.append("has leading, trailing or double spaces")
    seps = {c for c in ws if c in "_- "}
    if len(seps) > 1:
        out.append(f"mixes separators ({' '.join(repr(c) for c in sorted(seps))})")
    canon = lambda s: re.sub(r"[\s_\-]+", "", s).casefold()                      # noqa: E731
    for k in known:
        if k != ws and canon(k) == canon(ws):
            out.append(f"looks like {k!r} (differs only in case, spaces, '_' or '-')")
    return out


def connection_string(workspace, model, mid):
    return (f'Data Source="powerbi://api.powerbi.com/v1.0/myorg/{workspace}";initial catalog={model};'
            f"access mode=readonly;integrated security=ClaimsToken;semanticmodelid={mid}")


def parse_connection(cs):
    ws = re.search(r'Data Source="?powerbi://[^"]*/myorg/([^";]+)"?', cs or "", re.I)
    cat = re.search(r"initial catalog=([^;]+)", cs or "", re.I)
    mid = re.search(r"semanticmodelid=(" + GUID + ")", cs or "", re.I)
    return (ws.group(1) if ws else None, cat.group(1).strip('"') if cat else None, mid.group(1) if mid else None)


def from_report(path):
    """(workspace, model, id, connection string) from a Desktop-saved report connected to the live model."""
    p = pathlib.Path(path)
    if p.suffix.lower() == ".pbip":
        p = p.with_suffix(".Report")
    f = p / "definition.pbir" if p.is_dir() else p
    cs = load(f).get("datasetReference", {}).get("byConnection", {}).get("connectionString")
    if not cs:
        raise BindError(f"{f}: no byConnection (open the live model in Desktop, save the report, then use it)")
    ws, model, mid = parse_connection(cs)
    if not mid:
        raise BindError(f"{f}: the connection has no semanticmodelid")
    return ws, model, mid, cs


def live(report, by, workspace=None, model=None, mid=None, from_=None, root=None, ask=None, out=print,
         desktop_open=None):
    """Person-only. Check, back up, rewrite field references per the map, then write definition.pbir byConnection."""
    from .desktop import desktop_open as _open
    ctx = Context(report, root)
    st = DC.stamp(by)
    if ctx.state and ctx.state.get("mode") == "live":
        raise BindError(f"already live ({ctx.state.get('model')}): run `pbik bind local` first")
    if (desktop_open or _open)():
        raise BindError("Power BI Desktop is open: close it (File > Close, don't save) so it doesn't overwrite the "
                        "files bind live rewrites")
    from .synth import approved
    if not approved(ctx.contract):
        raise BindError("the contract isn't approved: a person runs `pbik synth approve --by`")
    pre_live_checks(ctx, out)
    res = check(report, ctx.root, ctx)
    for x in res.notes:
        out(f"note  {x}")
    if not res.ok():
        raise BindError("bind check failed:\n  " + "\n  ".join(res.lines()))
    if from_:
        workspace, model, mid, cs = from_report(from_)
    else:
        if not (workspace and model and mid):
            raise BindError("give --workspace, --model and --id (a link or the ID), or --from <Desktop-saved report>")
        mid = model_id(mid)
        warns = workspace_warnings(workspace, known_workspaces(ctx.root))
        for w in warns:
            out(f"warning: workspace name {workspace!r} {w}. Safer: connect Desktop to the model (Get data > Power BI "
                "semantic models), save that report, and run `pbik bind live --from <that report>`")
        cs = connection_string(workspace, model, mid)
    out(f"Bind {ctx.rep.path.name} to {model!r} in workspace {workspace!r} (semantic model {mid})")
    DC.confirm(f"Bind live as {st['by']}?", model, ask)
    # back up every file, byte for byte
    sd = state_dir(ctx.root)
    backup = sd / "backup"
    if backup.exists():
        shutil.rmtree(backup)
    for rel in report_files(ctx.rep):
        dst = backup / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ctx.rep.path / rel, dst)
    (sd / ".gitignore").write_text("*\n", encoding="utf-8")
    synthetic = None
    if ctx.model_folder:
        try:
            synthetic = str(pathlib.Path(ctx.model_folder).resolve().relative_to(ctx.root)).replace("\\", "/")
        except ValueError:
            synthetic = str(pathlib.Path(ctx.model_folder).resolve())
    labels = {}
    try:
        for rel, doc in json_docs(ctx.rep):
            lab = []
            if remap_doc(rel, doc, ctx.mapper, ctx.tables, ctx.map.get("liveLabels") is not True, lab):
                ctx.rep.write(ctx.rep.path / rel, doc)
            if lab:
                labels[rel] = lab
        pbir = ctx.rep.path / "definition.pbir"
        d = load(pbir) if pbir.exists() else {"$schema": PBIR_SCHEMA, "version": "4.0"}
        d["datasetReference"] = {"byConnection": {"connectionString": cs}}
        pbir.write_text(dumps(d), encoding="utf-8")
    except Exception:                                  # nothing half-done: the backup goes back as it was
        for f in sorted(backup.rglob("*")):
            if f.is_file():
                shutil.copy2(f, ctx.rep.path / f.relative_to(backup))
        raise
    state = {"mode": "live", "workspace": workspace, "model": model, "id": mid, **st, "synthetic": synthetic,
             "report": ctx.rep.path.name, "labels": labels,
             "files": {rel: sha((ctx.rep.path / rel).read_bytes()) for rel in report_files(ctx.rep)}}
    write_json(sd / "state.json", state)
    remember_workspace(ctx.root, workspace)
    out(f"Live. Backup in {backup}. Open the report in Desktop; `pbik bind local` goes back.")
    return state


def pre_live_checks(ctx, out):
    """A bind map must be approved, unchanged since."""
    if ctx.map and not map_approved(ctx.map):
        raise BindError("bind-map.json isn't approved (or changed since): a person runs `pbik bind map approve --by`")


def remember_workspace(root, ws):
    """project.json `workspaces`: names bound before, so a later typo is caught."""
    if not ws:
        return
    d = DC.read_project(root)
    lst = d.setdefault("workspaces", [])
    if ws not in lst:
        lst.append(ws)
        write_json(DC.project_file(root), d)


def known_workspaces(root):
    st = DC.read_project(root)
    return [w for w in st.get("workspaces", []) if isinstance(w, str)]


def remap_doc(rel, doc, mapper, tables, keep_labels=True, labels=None, dax=None):
    """Rewrite one report JSON document through the mapper. reportExtensions.json: entity names and DAX."""
    if mapper.empty():
        return False
    before = json.dumps(doc, sort_keys=True)
    if rel.endswith("reportExtensions.json"):
        for e in doc.get("entities", []):
            e["name"] = mapper.table(e["name"])
            for m in e.get("measures", []):
                new = BR.rewrite_dax(m.get("expression", ""), mapper, tables)
                if dax is not None and new != m.get("expression"):
                    dax.append((m["name"], m.get("expression"), new))
                m["expression"] = new
    else:
        BR.rewrite(doc, mapper, tables, keep_labels, labels)
    return json.dumps(doc, sort_keys=True) != before


# ---------------------------------------------------------------- local
def local(report, root=None, out=print, desktop_open=None, restore_backup=False, ask=None):
    """Put the synthetic connection back. Refuses while Desktop is open. Files unchanged since bind live come back
    from the backup byte for byte; files changed while live are mapped back. restore_backup: the whole backup, after
    a typed "restore" (changes made while live are lost)."""
    from .desktop import desktop_open as _open
    rep = Report(report)
    root = (pathlib.Path(root) if root else rep.path.parent).resolve()
    state = DC.bind_state(root)
    if not state or state.get("mode") != "live":
        raise BindError("the report isn't bound live (no .pbik/bind/state.json)")
    if (desktop_open or _open)():
        raise BindError("Power BI Desktop is open: close it first (File > Close; save in Desktop beforehand if you "
                        "want its changes kept), then run `pbik bind local` again")
    backup = state_dir(root) / "backup"
    if not (backup / "definition.pbir").exists():
        raise BindError(f"no backup in {backup}: can't restore")
    if restore_backup:
        changed = [r for r in report_files(rep) if state["files"].get(r) != sha((rep.path / r).read_bytes())]
        out(f"Restore the backup of {rep.path.name}: {len(changed)} file(s) changed while live are lost"
            + (f" ({', '.join(changed[:5])}{', ...' if len(changed) > 5 else ''})" if changed else ""))
        DC.confirm("Restore the whole backup?", "restore", ask)
        for r in report_files(rep):
            if not (backup / r).exists():
                (rep.path / r).unlink()
        for d in sorted((x for x in rep.path.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)):
            if not any(d.iterdir()) and not (backup / d.relative_to(rep.path)).exists():
                d.rmdir()                                  # folders made while live
        for f in sorted(backup.rglob("*")):
            if f.is_file():
                dst = rep.path / f.relative_to(backup)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
        summary = {"restored": "all"}
    else:
        summary = restore_local(rep, root, state, backup, out)
    (state_dir(root) / "state.json").unlink()
    out("Local again: the report is on the synthetic model.")
    return summary


def restore_local(rep, root, state, backup, out):
    """Unchanged files: the backup copy, byte for byte. Changed or new files: mapped back. definition.pbir: backup."""
    ctx_map = read_json(specs(root) / "bind-map.json", {})
    syn = tmdl.load(root / state["synthetic"]) if state.get("synthetic") else None
    measures = [(t.name, m) for t in (syn.tables.values() if syn else []) for m in t.measures]
    fwd = BR.Mapper.from_map(ctx_map, measures)
    rev = fwd.reverse()
    tables = [fwd.table(t) for t in (syn.tables if syn else [])]
    restored, remapped, gone = [], [], []
    for r in report_files(rep):
        f = rep.path / r
        if r == "definition.pbir":
            continue
        if state["files"].get(r) == sha(f.read_bytes()) and (backup / r).exists():
            if f.read_bytes() != (backup / r).read_bytes():
                shutil.copy2(backup / r, f)
            restored.append(r)
        elif r.endswith(".json") and r.startswith("definition/"):
            try:
                doc = load(f)
            except json.JSONDecodeError:
                continue
            a = remap_doc(r, doc, rev, tables, keep_labels=False)
            b = BR.drop_labels(doc, state.get("labels", {}).get(r, []))
            if a or b:
                rep.write(f, doc)
            remapped.append(r)
    for r in state["files"]:
        if not (rep.path / r).exists():
            gone.append(r)
    shutil.copy2(backup / "definition.pbir", rep.path / "definition.pbir")
    out(f"{len(restored)} file(s) restored from the backup, {len(remapped)} changed while live mapped back"
        + (f", {len(gone)} deleted while live stay deleted" if gone else ""))
    for r in remapped:
        out(f"  mapped back: {r}")
    return {"restored": restored, "remapped": remapped, "gone": gone}


# ---------------------------------------------------------------- bind map (batch 3 item 1)
def map_file(root):
    return specs(root) / "bind-map.json"


def _tokens(name):
    return [t for t in re.split(r"[\s_\-\.]+", N.key(name)) if t]


def similarity(a, b):
    """0..1: how alike two names are (case, spaces, '_' and '-' ignored; shared words count)."""
    import difflib
    ca, cb = "".join(_tokens(a)), "".join(_tokens(b))
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    ta, tb = set(_tokens(a)), set(_tokens(b))
    words = len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0
    return max(difflib.SequenceMatcher(None, ca, cb).ratio(), words * 0.9)


def best(name, candidates, taken=(), floor=0.5):
    scored = sorted(((similarity(name, c), c) for c in candidates if c not in taken), key=lambda x: (-x[0], x[1]))
    return scored[0] if scored and scored[0][0] >= floor else (None, None)


def used_names(ctx):
    """[(table, name)] the report uses: field sites and report-level measure DAX, synthetic names."""
    out = []
    ext = ctx.rep.extensions()
    for rel, doc in json_docs(ctx.rep):
        if rel.endswith("reportExtensions.json"):
            continue
        for kind, ent, prop, schema, path in BR.sites(doc, ctx.tables):
            if prop is None or schema == "extension" or any(N.same(t, ent) and N.same(n, prop) for t, n in ext):
                continue
            out.append((ent, prop))
    for (t, n), m in ext.items():
        out.append((t, None))
        refs, variables, _ = tmdl.references(m.get("expression", ""))
        virtual = tmdl.virtual_names(m.get("expression", ""))
        for rt, rn in refs:
            if not (rt and N.ci_in(rt, variables)) and not virtual(rn):
                out.append((rt, rn))
    return list(dict.fromkeys(out))


def map_draft(report, root=None, out=print):
    """bind-map.json from similar names: every synthetic name the report uses that the contract lacks."""
    ctx = Context(report, root)
    c = ctx.contract
    old = read_json(map_file(ctx.root), {})
    tables, fields, unmatched = dict(old.get("tables", {})), dict(old.get("fields", {})), []
    ctables = list(c["tables"])
    for t, _ in used_names(ctx):
        if t and not N.find(ctables, t) and not N.find(tables, t):
            score, hit = best(t, ctables, set(tables.values()))
            if hit:
                tables[t] = hit
                out(f"table  {t} -> {hit} ({score:.2f})")
            else:
                unmatched.append(t)
    mapper = BR.Mapper.from_map({"tables": tables})
    for t, n in used_names(ctx):
        if n is None:
            continue
        key = f"{t}[{n}]" if t else f"[{n}]"
        if N.find(fields, key) or (not t and any(N.same(BR.split(k)[1], n) for k in fields)):
            continue                                  # [Measure] in DAX: its Table[Measure] entry covers it
        lt = mapper.table(t) if t else None
        if t and N.find(c["tables"], lt) and ctx.contract_has(lt, n):
            continue
        if not t and any(ctx.contract_has(x, n) for x in ctables):
            continue
        if not t and not any(ctx.synthetic_has(x, n) for x in ctx.tables):
            continue                                  # a name DAX defines (row context, virtual table)
        ct = N.find(c["tables"], lt) if lt else None
        if ct:
            pool = list(c["tables"][ct]["columns"]) + list(c["tables"][ct]["measures"])
        else:
            pool = [m for tb in c["tables"].values() for m in tb["measures"]]
        # a contract name the synthetic model already has is that field's own match, not a candidate
        own = {N.key(x) for st in (ctx.model.tables.values() if ctx.model else [])
               for x in list(st.columns) + list(st.measures)}
        taken = {x for x in pool if N.key(x) in own} | set(fields.values())
        score, hit = best(n, pool, taken)
        if hit:
            fields[key] = hit
            out(f"field  {key} -> {hit} ({score:.2f})")
        else:
            unmatched.append(key)
    m = {"tables": tables, "fields": fields, "acceptDax": old.get("acceptDax", []),
         "liveLabels": old.get("liveLabels", False), "draft": True, "unmatched": unmatched, "approval": None}
    write_json(map_file(ctx.root), m)
    for u in unmatched:
        out(f"no match: {u} (edit bind-map.json by hand)")
    return m


def map_hash(m):
    from .synth import content_hash
    return content_hash(m, skip=("approval", "draft", "unmatched"))


def map_approved(m):
    return not m or (bool(m.get("approval")) and m["approval"].get("hash") == map_hash(m))


def map_approve(report, by, root=None, ask=None, out=print):
    """Person-only: rerun the check through the map, show it, ask for the contract's model name typed."""
    ctx = Context(report, root)
    st = DC.stamp(by)
    if not ctx.map:
        raise BindError("no bind-map.json: run `pbik bind map draft` (or bind without a map: names must match)")
    if ctx.map.get("unmatched"):
        raise BindError(f"unmatched names left: {', '.join(ctx.map['unmatched'])} (map them, or clear `unmatched`)")
    res = check(report, ctx.root, ctx)
    if not res.ok():
        raise BindError("bind check fails through this map:\n  " + "\n  ".join(res.lines()))
    for k, v in ctx.map.get("tables", {}).items():
        out(f"table {k} -> {v}")
    for k, v in ctx.map.get("fields", {}).items():
        out(f"field {k} -> {v}")
    for n in ctx.map.get("acceptDax", []):
        out(f"DAX change accepted: [{n}]")
    DC.confirm(f"Approve this map as {st['by']}?", ctx.contract["model"], ask)
    m = dict(ctx.map)
    m.pop("draft", None)
    m.pop("unmatched", None)
    m["approval"] = dict(st, hash=map_hash(m))
    write_json(map_file(ctx.root), m)
    return m


def dax_changes(ctx):
    """[(measure, old, new)] report-level measures whose DAX the map changes."""
    out = []
    for (t, n), m in ctx.rep.extensions().items():
        new = BR.rewrite_dax(m.get("expression", ""), ctx.mapper, ctx.tables)
        if new != m.get("expression", ""):
            out.append((n, m.get("expression", ""), new))
    return out
