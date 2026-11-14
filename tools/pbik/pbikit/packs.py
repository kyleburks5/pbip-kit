"""Model packs (batch 3 item 15): reuse an approved contract and its synthetic model across projects.

    pbik model register <project> --to <packs folder>    save the approved contract (resolutions and the rules behind
                                                          them), generate.json (settings, deviations), the synthetic
                                                          model and any bind map, as a new version (date, approver)
    pbik project new <folder> --from-pack <pack>          a project at the plan step, with the pack's data class
    pbik model drift <pack> <new TMDL>                    only what changed, resolutions pre-filled from the rules
    pbik model approve <pack> --by <name>                 person-only: approve the short list, regenerate only the
                                                          affected tables, bump the version

A pack is <packs>/<model>/{pack.json, v<N>/{contract.json, generate.json, bind-map.json, model/<Name>.SemanticModel},
drift.json}. Packs live outside the kit and every git repository (register refuses otherwise; `--allow-repo` lets a
repository that isn't the kit's or the project's hold one) and are never committed (a .gitignore of "*" is written).
"""
import datetime, json, pathlib, shutil, subprocess, tempfile

from . import dataclass_ as DC, names as N
from .synth import ContractError, apply_rules, approved, build_contract, content_hash, read_json, specs, write_json


class PackError(Exception):
    pass


def _git_top(path):
    p = pathlib.Path(path).resolve()
    while not p.exists():
        p = p.parent
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=p, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return pathlib.Path(r.stdout.strip()).resolve() if r.returncode == 0 and r.stdout.strip() else None


def _outside(to, project, kit=None, allow_repo=False):
    """Packs live outside the kit and the project, and outside every git repository unless allow_repo (--allow-repo);
    never inside the kit's or the project's own repository."""
    to = pathlib.Path(to).resolve()
    roots = [pathlib.Path(project).resolve()] + ([pathlib.Path(kit).resolve()] if kit else [])
    for root in roots:
        if to == root or root in to.parents:
            raise PackError(f"{to} is inside {root}: packs live outside the kit and the project")
    top = _git_top(to)
    if not top:
        return
    if top in {t for t in (_git_top(r) for r in roots) if t}:
        raise PackError(f"{to} is inside the git repository {top} of the kit or the project: packs are never "
                        "committed; pick a folder outside it")
    if not allow_repo:
        raise PackError(f"{to} is inside the git repository {top}: packs are never committed; pick a folder outside "
                        "any repository, or pass --allow-repo if that repository is meant to hold it")


def pack_info(pack):
    info = read_json(pathlib.Path(pack) / "pack.json")
    if not info:
        raise PackError(f"{pack}: no pack.json (not a model pack)")
    return info


def version_dir(pack, version=None):
    info = pack_info(pack)
    return pathlib.Path(pack) / f"v{version or info['current']}"


def synthetic_folder(project):
    found = DC.synthetic_models(project)
    return found[0] if found else None


def register(project, to, kit=None, out=print, allow_repo=False):
    """Save the project's approved contract, generate settings, synthetic model and bind map as a new version."""
    project = pathlib.Path(project)
    c = read_json(specs(project) / "contract.json")
    if not c or not approved(c):
        raise PackError("the contract isn't approved: a person runs `pbik synth approve --by` first")
    _outside(to, project, kit, allow_repo)
    pack = pathlib.Path(to) / c["model"]
    info = read_json(pack / "pack.json") or {"name": c["model"], "versions": [], "current": 0}
    v = info["current"] + 1
    vd = pack / f"v{v}"
    vd.mkdir(parents=True)
    pathlib.Path(to, ".gitignore").write_text("*\n", encoding="utf-8")
    for name in ("contract.json", "generate.json", "bind-map.json"):
        f = specs(project) / name
        if f.exists():
            shutil.copy2(f, vd / name)
    sm = synthetic_folder(project)
    if sm:
        shutil.copytree(sm, vd / "model" / sm.name)
    entry = {"version": v, "date": datetime.date.today().isoformat(), "approver": c["approval"]["by"],
             "approved": c["approval"]["date"], "contractHash": content_hash(c), "from": project.resolve().name}
    info.update(versions=info["versions"] + [entry], current=v, dataClass=DC.data_class(project),
                rules=len(c.get("rules", [])))
    write_json(pack / "pack.json", info)
    out(f"registered {c['model']} v{v} in {pack} (approved by {entry['approver']}, data class {info['dataClass']})")
    return pack, v


def project_new(folder, pack, out=print):
    """A project at the plan step from a pack: contract, generate settings, bind map, synthetic model, data class."""
    folder = pathlib.Path(folder)
    if (specs(folder) / "contract.json").exists():
        raise PackError(f"{folder} already has a contract")
    info = pack_info(pack)
    vd = version_dir(pack)
    specs(folder).mkdir(parents=True, exist_ok=True)
    for name in ("contract.json", "generate.json", "bind-map.json"):
        if (vd / name).exists():
            shutil.copy2(vd / name, specs(folder) / name)
    for sm in (vd / "model").glob("*.SemanticModel") if (vd / "model").is_dir() else []:
        if (folder / sm.name).exists():
            raise PackError(f"{folder / sm.name} exists")
        shutil.copytree(sm, folder / sm.name)
    proj = DC.read_project(folder)
    proj.update(dataClass=info.get("dataClass", DC.DEFAULT),
                pack={"name": info["name"], "version": info["current"], "path": str(pathlib.Path(pack).resolve())})
    write_json(DC.project_file(folder), proj)
    out(f"project at the plan step from {info['name']} v{info['current']} (data class {proj['dataClass']})")
    out("next: I'll draw the plan as a picture")
    return folder


# ---------------------------------------------------------------- drift
def _sig(c):
    """{key: value} of everything a change could touch, keys readable."""
    out = {}
    for t, tb in c["tables"].items():
        out[("table", N.key(t))] = t
        for col, x in tb["columns"].items():
            out[("column", N.key(t), N.key(col))] = (f"{t}[{col}]", x.get("type"), x.get("sortBy"), x.get("expression"))
        for m, x in tb["measures"].items():
            out[("measure", N.key(t), N.key(m))] = (f"{t}[{m}]", " ".join((x.get("expression") or "").split()),
                                                    x.get("formatString"))
    for r in c["relationships"]:
        out[("relationship", N.key(r["from"]), N.key(r["to"]))] = (f"{r['from']} -> {r['to']}",)
    return out


def changes(old, new):
    """[{kind, what, change, table}] between two contracts: added, removed, changed."""
    a, b = _sig(old), _sig(new)
    out = []
    for k in sorted(set(a) | set(b), key=str):
        if k in a and k in b and a[k] == b[k]:
            continue
        label = (b.get(k) or a.get(k))
        label = label[0] if isinstance(label, tuple) else label
        change = "added" if k not in a else "removed" if k not in b else "changed"
        detail = ""
        if change == "changed" and k[0] == "column":
            detail = f"type {a[k][1]} -> {b[k][1]}" if a[k][1] != b[k][1] else "sort-by or expression"
        elif change == "changed" and k[0] == "measure":
            detail = "DAX or format"
        table = None if k[0] == "relationship" else (b.get(("table", k[1])) or a.get(("table", k[1])))
        out.append({"kind": k[0], "what": label, "change": change, "detail": detail, "table": table})
    return out


def drift(pack, tmdl_source, out=print, drift_file=None):
    """Compare a new TMDL with the pack's contract: list only what changed; flags pre-filled from the saved rules."""
    vd = version_dir(pack)
    old = read_json(vd / "contract.json")
    new = build_contract(tmdl_source, pathlib.Path(tmdl_source).parent)
    new["source"] = str(pathlib.Path(tmdl_source).resolve())
    if new["model"] != old["model"]:
        out(f"note: the new TMDL is named {new['model']!r}; it is drift of {old['model']!r} and keeps that name")
        new["model"] = old["model"]
    new["rules"] = old.get("rules", [])
    old_res = {(f["kind"], N.key(f.get("table"))): f for f in old["flags"]}
    for f in new["flags"]:                           # same flag as before: same resolution
        prev = old_res.get((f["kind"], N.key(f.get("table"))))
        if prev and prev.get("resolution"):
            f["resolution"], f["rule"] = prev["resolution"], prev.get("rule")
    filled = apply_rules(new)
    from . import rules as R
    filled += R.apply_library(new)                    # what the pack's rules don't cover, the kit's library may
    for t, tb in old["tables"].items():              # kept option rows carry over while the table is unchanged
        if tb.get("rows") and t in new["tables"] and new["tables"][t]["columns"] == tb["columns"]:
            new["tables"][t]["rows"] = tb["rows"]
    ch = changes(old, new)
    new_flags = [f for f in new["flags"] if (f["kind"], N.key(f.get("table"))) not in old_res]
    d = {"base": pack_info(pack)["current"], "contract": new, "changes": ch,
         "newFlags": [f["id"] for f in new_flags], "prefilled": [f["id"] for f in filled]}
    write_json(pathlib.Path(drift_file) if drift_file else pathlib.Path(pack) / "drift.json", d)
    for x in ch:
        out(f"{x['change']:8} {x['kind']:12} {x['what']}" + (f" ({x['detail']})" if x["detail"] else ""))
    for f in new_flags:
        out(f"new flag {f['id']} {f['kind']} {f.get('table') or '(model)'}: {f['detail']} -> "
            f"{f.get('resolution') or 'UNRESOLVED'}" + (" (from the saved rules)" if f in filled else ""))
    if not ch and not new_flags:
        out("no drift: the model matches the pack")
    return d


def affected_tables(c, ch, slice_):
    """Tables whose synthetic data changes: changed tables in the slice, and tables pointing at them."""
    hit = {N.key(x["table"]) for x in ch if x["table"]}
    for x in ch:
        if x["kind"] == "relationship":
            for side in x["what"].split(" -> "):
                hit.add(N.key(side.split("[")[0]))
    grew = True
    while grew:                                       # facts draw keys from changed dimensions
        grew = False
        for r in c["relationships"]:
            ft, tt = N.key(r["from"].split("[")[0]), N.key(r["to"].split("[")[0])
            if tt in hit and ft not in hit:
                hit.add(ft)
                grew = True
    return sorted(t for t in slice_ if N.key(t) in hit)


def approve(pack, by, ask=None, out=print, drift_file=None):
    """Person-only: approve the drift list, regenerate only the affected tables, bump the version."""
    from . import synthgen as G
    pack = pathlib.Path(pack)
    st = DC.stamp(by)
    df = pathlib.Path(drift_file) if drift_file else pack / "drift.json"
    d = read_json(df)
    if not d:
        raise PackError("no drift.json: run `pbik model drift <pack> <new TMDL>` first")
    info = pack_info(pack)
    if d["base"] != info["current"]:
        raise PackError(f"drift.json is against v{d['base']}, the pack is at v{info['current']}: run drift again")
    c = d["contract"]
    open_ = [f["id"] for f in c["flags"] if not f.get("resolution")]
    if open_:
        raise ContractError(f"unresolved flag(s): {', '.join(open_)} (edit drift.json, or add a rule)")
    for x in d["changes"]:
        out(f"{x['change']:8} {x['kind']:12} {x['what']}" + (f" ({x['detail']})" if x["detail"] else ""))
    DC.confirm(f"Approve these {len(d['changes'])} change(s) to {c['model']} as {st['by']}?", c["model"], ask)
    c["approval"] = dict(st, hash=content_hash(c))
    old_v = version_dir(pack)
    g = read_json(old_v / "generate.json", {})
    sl = g.get("slice", {})
    for t in list(sl):                                # fields that left the model leave the slice
        nt = N.find(c["tables"], t)
        if not nt:
            sl.pop(t)
            continue
        sl[t]["columns"] = [x for x in sl[t]["columns"] if N.ci_in(x, c["tables"][nt]["columns"])]
        sl[t]["measures"] = [x for x in sl[t]["measures"] if N.ci_in(x, c["tables"][nt]["measures"])
                             or N.ci_in(x, g.get("plannedMeasures", {}))]
    g["contractHash"] = content_hash(c)
    new_v = pack / f"v{info['current'] + 1}"
    new_v.mkdir()
    write_json(new_v / "contract.json", c)
    write_json(new_v / "generate.json", g)
    if (old_v / "bind-map.json").exists():
        shutil.copy2(old_v / "bind-map.json", new_v / "bind-map.json")
    affected = affected_tables(c, d["changes"], sl)
    old_models = list((old_v / "model").glob("*.SemanticModel")) if (old_v / "model").is_dir() else []
    if old_models:
        dst = new_v / "model" / old_models[0].name
        shutil.copytree(old_models[0], dst)
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "design" / "specs").mkdir(parents=True)
            write_json(pathlib.Path(tmp) / "design" / "specs" / "contract.json", c)
            write_json(pathlib.Path(tmp) / "design" / "specs" / "generate.json", g)
            fresh = G.generate(tmp, "x", pathlib.Path(tmp) / "fresh.SemanticModel")
            for t in affected:
                shutil.copy2(fresh / "definition" / "tables" / f"{t}.tmdl", dst / "definition" / "tables" / f"{t}.tmdl")
            for t in sl:                              # a table new to the slice
                if not (dst / "definition" / "tables" / f"{t}.tmdl").exists():
                    shutil.copy2(fresh / "definition" / "tables" / f"{t}.tmdl", dst / "definition" / "tables")
            for f in (dst / "definition" / "tables").glob("*.tmdl"):
                if f.stem not in sl:
                    f.unlink()
            for name in ("model.tmdl", "relationships.tmdl"):
                shutil.copy2(fresh / "definition" / name, dst / "definition" / name)
    info["versions"].append({"version": info["current"] + 1, "date": st["date"], "approver": st["by"],
                             "approved": st["date"], "contractHash": content_hash(c), "from": f"drift of v{d['base']}",
                             "changes": len(d["changes"]), "regenerated": affected})
    info["current"] += 1
    write_json(pack / "pack.json", info)
    df.unlink()
    out(f"{c['model']} v{info['current']}: {len(d['changes'])} change(s), regenerated {', '.join(affected) or 'nothing'}")
    return info["current"], affected


# ---------------------------------------------------------------- pack folders (Phase 1, stage d)
def pack_folders(root):
    """[(path, team?)] from project.json `packFolders` (strings, or {"path", "team"})."""
    out = []
    for x in DC.read_project(root).get("packFolders", []):
        p, team = (x, False) if isinstance(x, str) else (x.get("path"), bool(x.get("team")))
        if p:
            out.append((pathlib.Path(p), team))
    return out


def list_packs(root):
    """[(name, current version, data class, folder, team?)] of every pack in the project's pack folders."""
    out = []
    for folder, team in pack_folders(root):
        for pj in sorted(folder.glob("*/pack.json")) if folder.is_dir() else []:
            info = read_json(pj)
            out.append((info["name"], info["current"], info.get("dataClass"), pj.parent, team))
    return out


def find(root, name):
    """The pack folder of a model by name (case-insensitive), from the project's pack folders."""
    hits = [p for p in list_packs(root) if N.same(p[0], name)]
    if not hits:
        raise PackError(f"no model pack named {name!r} in the pack folders")
    return hits[0][3]


def may_register(folder, cls, who):
    """Team folders list who may register per data class in team.json {"registrars": {class: [names]}}."""
    t = read_json(pathlib.Path(folder) / "team.json")
    if not t:
        return True
    allowed = (t.get("registrars") or {}).get(cls, [])
    return any(N.same(a, who) or N.key(a) in N.key(who) for a in allowed)


# ---------------------------------------------------------------- recognising a model (v1.7, A2)
def fingerprint(c):
    """The model's shape, no values: sorted table and column names (case-insensitive)."""
    import hashlib
    return hashlib.sha1(json.dumps(sorted(_names(c))).encode("utf-8")).hexdigest()[:16]


def _names(c):
    return {f"{t.lower()}|{col.lower()}" for t, x in c.get("tables", {}).items() for col in x.get("columns", {})} | {
        f"{t.lower()}|" for t in c.get("tables", {})}


def match(root, c, near=0.8):
    """The pack this model is, from the project's pack folders: ("same" | "newer", pack folder, info) or None.
    "same": the same tables and columns; "newer": at least `near` of them shared (a changed model: drift)."""
    mine, best = _names(c), None
    for name, ver, cls, folder, team in list_packs(root):
        pc = read_json(version_dir(folder) / "contract.json")
        if not pc:
            continue
        theirs = _names(pc)
        if theirs == mine:
            return ("same", folder, pack_info(folder))
        share = len(mine & theirs) / max(1, len(mine | theirs))
        if share >= near and (not best or share > best[0]):
            best = (share, folder)
    return ("newer", best[1], pack_info(best[1])) if best else None
