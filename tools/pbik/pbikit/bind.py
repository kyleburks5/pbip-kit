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
        self.root = pathlib.Path(root) if root else self.rep.path.parent
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
        return not self.errors


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
            if kind == "Entity" or prop is None:
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
    for (t, n), m in ext.items():
        check_dax(ctx, res, f"reportExtensions.json {t}[{n}]", m.get("expression", ""), planned)
        if not N.find(ctx.contract["tables"], ctx.mapper.table(t)):
            res.errors.append(f"reportExtensions.json: entity {t} (live {ctx.mapper.table(t)}) is not in the contract")
    return res


def check_field(ctx, res, where, kind, ent, prop, planned):
    if N.ci_in(prop, planned) and kind in ("Measure", "ref"):
        res.errors.append(f"{where}: planned measure [{prop}] isn't in the live model: run `pbik bind prepare`")
        return
    if not ctx.synthetic_has(ent, prop) and not ctx.mapper.entry(ent, prop):
        res.errors.append(f"{where}: {ent}[{prop}] is not in the synthetic model")
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
            res.errors.append(f"{where}: {ent}[{prop}] is {st} here, {ct} in the contract")


def check_dax(ctx, res, where, expr, planned):
    refs, variables, strings = tmdl.references(expr)
    for t, name in refs:
        if t and N.ci_in(t, variables):
            continue
        if t is None and name in ("Value",) or re.fullmatch(r"Value\d+", name or "") or name in strings:
            continue
        if t is None:
            lt, ln = ctx.mapper.field(None, name)
            ok = any(ctx.contract_has(tt, ln) for tt in ctx.contract["tables"])
        else:
            lt, ln = ctx.mapper.field(t, name)
            ok = ctx.contract_has(lt, ln)
        if N.ci_in(name, planned):
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
        raise BindError("bind check failed:\n  " + "\n  ".join(res.errors))
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
    labels = {}
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
    state = {"mode": "live", "workspace": workspace, "model": model, "id": mid, **st,
             "synthetic": str(ctx.model_folder.relative_to(ctx.root)).replace("\\", "/") if ctx.model_folder else None,
             "report": ctx.rep.path.name, "labels": labels,
             "files": {rel: sha((ctx.rep.path / rel).read_bytes()) for rel in report_files(ctx.rep)}}
    write_json(sd / "state.json", state)
    out(f"Live. Backup in {backup}. Open the report in Desktop; `pbik bind local` goes back.")
    return state


def pre_live_checks(ctx, out):
    """Hook for the bind map's approval (item 1)."""


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
def local(report, root=None, out=print, desktop_open=None):
    """Put the synthetic connection back. Refuses while Desktop is open."""
    from .desktop import desktop_open as _open
    rep = Report(report)
    root = pathlib.Path(root) if root else rep.path.parent
    state = DC.bind_state(root)
    if not state or state.get("mode") != "live":
        raise BindError("the report isn't bound live (no .pbik/bind/state.json)")
    if (desktop_open or _open)():
        raise BindError("Power BI Desktop is open: close it first (File > Close; save in Desktop beforehand if you "
                        "want its changes kept), then run `pbik bind local` again")
    backup = state_dir(root) / "backup"
    restore_local(rep, root, state, backup, out)
    (state_dir(root) / "state.json").unlink()
    out("Local again: the report is on the synthetic model.")


def restore_local(rep, root, state, backup, out):
    """Part 0: definition.pbir from the backup; every other file reverse-mapped (batch 3 item 3 restores exactly)."""
    ctx_map = read_json(specs(root) / "bind-map.json", {})
    syn = tmdl.load(root / state["synthetic"]) if state.get("synthetic") else None
    measures = [(t.name, m) for t in (syn.tables.values() if syn else []) for m in t.measures]
    rev = BR.Mapper.from_map(ctx_map, measures).reverse()
    tables = [BR.Mapper.from_map(ctx_map).table(t) for t in (syn.tables if syn else [])]
    for rel, doc in json_docs(rep):
        if remap_doc(rel, doc, rev, tables, keep_labels=False):
            BR.drop_labels(doc, state.get("labels", {}).get(rel, []))
            rep.write(rep.path / rel, doc)
    shutil.copy2(backup / "definition.pbir", rep.path / "definition.pbir")
