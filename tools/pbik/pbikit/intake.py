"""`pbik model intake`: the model drop folder (docs/design/phase1-usability.md, section 3).

The user drops a copy of the model into design/reference/model/: a TMDL folder, a single TMDL createOrReplace script, a
.SemanticModel folder or a TMSL / JSON export (.bim, .json). Intake first deletes every data file in the folder
(permanently: cache.abf and any .abf, .pbi folders, data folders, .pbix / .pbit, .parquet, .csv, .xlsx, .xls, .cache)
before anything reads it, then detects the format, git-ignores the folder, writes the contract (synth contract) and
logs what it did in design/reviews/model-intake.md. Users drop a copy, never their only file.
"""
import datetime, json, pathlib, shutil

from . import dataclass_ as DC

DROP = pathlib.Path("design") / "reference" / "model"
DATA_SUFFIX = {".abf", ".pbix", ".pbit", ".parquet", ".csv", ".xlsx", ".xls", ".cache"}
DATA_DIRS = {".pbi", "data"}


class IntakeError(Exception):
    pass


def data_files(folder):
    """Files to delete, found from names only (nothing is opened)."""
    out = []
    for f in sorted(folder.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(folder)
        if f.suffix.lower() in DATA_SUFFIX or any(p.lower() in DATA_DIRS for p in rel.parts[:-1]):
            out.append(f)
    return out


def remove_data(folder):
    """Delete the data files and the folders they leave empty; return their relative names."""
    gone = []
    for f in data_files(folder):
        gone.append(str(f.relative_to(folder)).replace("\\", "/"))
        f.unlink()
    for d in sorted((x for x in folder.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)):
        if d.name.lower() in DATA_DIRS or not any(d.iterdir()):
            if not any(p.is_file() for p in d.rglob("*")):
                shutil.rmtree(d, ignore_errors=True)
    return gone


def detect(folder):
    """[(format, path)] of the models in the drop folder."""
    found = []
    for p in sorted(folder.iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_dir():
            if p.name.endswith(".SemanticModel"):
                found.append(("semantic model folder", p))
            elif list(p.glob("*.tmdl")) or list((p / "definition").glob("*.tmdl")):
                found.append(("TMDL folder", p))
        elif p.suffix.lower() == ".tmdl":
            head = p.read_text(encoding="utf-8-sig")[:4000].lstrip()
            if head.startswith("createOrReplace"):
                found.append(("TMDL script", p))
        elif p.suffix.lower() in (".bim", ".json"):
            try:
                d = json.loads(p.read_text(encoding="utf-8-sig"))
            except ValueError:
                continue
            body = (d.get("createOrReplace") or {}).get("database") or d.get("database") or d
            if isinstance(body, dict) and isinstance(body.get("model"), dict):
                found.append(("TMSL export", p))
    return found


def drop_dir(root="."):
    """The Model folder (pbikit/drops.py; design/reference/model in projects made before the one-folder setup)."""
    from . import drops
    return drops.model_dir(pathlib.Path(root).resolve())


def open_drop(root=".", open_folder=False):
    """Make the Model folder (git-ignored); nothing in it is read. It never opens File Explorer (walkthrough fix 10):
    the agent names the folder."""
    from . import drops
    drops.make(root)
    d = drop_dir(root)
    (d / ".gitignore").write_text("*\n", encoding="utf-8")
    return d


def intake(root=".", folder=None, out=print):
    """Delete data files, detect the model, write the contract. Returns {format, removed, contract}."""
    from . import synth as S
    root = pathlib.Path(root).resolve()
    folder = pathlib.Path(folder) if folder else drop_dir(root)
    if not folder.is_dir():
        raise IntakeError("put a copy of the model in the Model folder first")
    (folder / ".gitignore").write_text("*\n", encoding="utf-8")
    removed = remove_data(folder)                   # before anything reads the folder
    if removed:
        out(f"warning: the model folder held {len(removed)} data file(s); they were deleted before anything read "
            "them. Always drop a copy of the model, never your only file.")
    models = detect(folder)
    if not models:
        raise IntakeError("no model found: drop a TMDL folder, a TMDL script, a .SemanticModel folder or a TMSL "
                          "export (a .pbix or .pbit can't be read: save the report as a Power BI project first)")
    if len(models) > 1:
        raise IntakeError(f"{len(models)} models found; drop one at a time")
    fmt, path = models[0]
    pack = (DC.read_project(root).get("pack") or {}).get("path")
    if pack and pathlib.Path(pack, "pack.json").exists():  # reuse: only what changed since the pack
        from . import packs as PK
        d = PK.drift(pack, path, out=lambda *a: None, drift_file=S.specs(root) / "drift.json")
        log(root, fmt, path.name, removed, d["contract"])
        out(f"read the model ({fmt}): {len(d['changes'])} change(s) since the model pack"
            + ("; I'll open the approval window Approve model changes" if d["changes"] or d["newFlags"] else
               "; nothing to approve"))
        return {"format": fmt, "removed": removed, "contract": d["contract"], "drift": d}
    c, _ = S.contract(path, root)
    log(root, fmt, path.name, removed, c)
    seen = recognise(root, c, out)                    # a model approved before: its pack, no model approval (A2)
    if seen:
        return intake(root, folder, out) if seen == "newer" else {"format": fmt, "removed": removed,
                                                                  "contract": S.read_json(S.specs(root) /
                                                                                          "contract.json"),
                                                                  "pack": True}
    out(f"read the model ({fmt}): {len(c['tables'])} tables, "
        f"{sum(len(t['measures']) for t in c['tables'].values())} measures, {len(c['flags'])} flag(s)")
    for ln in grouped_lines(c):                      # grouped by default, never a list by technical kind (A9)
        out(ln)
    return {"format": fmt, "removed": removed, "contract": c}


def recognise(root, c, out=print):
    """Match the model against the pack folders by its tables and columns (no values). A match starts the project
    from that pack: its approved setup, synthetic model and data class (never lower than the project's own: loosening
    stays the person's approval). Returns "same", "newer" or None."""
    from . import packs as PK, status as ST
    try:
        m = PK.match(root, c)
    except (PK.PackError, OSError, ValueError):
        return None
    if not m:
        return None
    kind, folder, info = m
    before = DC.data_class(root)
    (pathlib.Path(root) / "design" / "specs" / "contract.json").unlink(missing_ok=True)
    PK.project_new(root, folder, out=lambda *a: None)
    after = DC.data_class(root)
    if DC.CLASSES.index(after) < DC.CLASSES.index(before):
        DC.set_class(root, before)
        note = (f" Its data class is {after}; this project stays {before} unless you loosen it in the approval "
                "window.")
    else:
        note = ""
    ST.update(root, done="model" if kind == "same" else None, pack=info["name"], dataClass=DC.data_class(root))
    if kind == "same":
        out(f"This is {info['name']}, the model you approved before (version {info['current']}): no model approval "
            f"needed.{note}")
        out("next: I'll draw the plan as a picture")
    else:
        out(f"This looks like a newer version of {info['name']} (approved before); I'll check only what changed.{note}")
    return kind


def grouped_lines(c, most=10):
    """The plain, grouped summary of a model's flags: the counts, then each item that needs the person and why,
    then the next step in words (never a slash command; v1.7 A9, walkthrough notes 8-10)."""
    from . import rules as R
    g = R.groups(c)
    out = [R.summary_line(c) + "."]
    if g["keep"]:
        out.append(f"The {len(g['keep'])} option table(s) keep their exact labels and order; you'll see their rows in "
                   "the approval window and just check them.")
    if g["you"]:
        out.append(f"{len(g['you'])} need you:")
        out += [f"  - {R.plain(f)}" for f in g["you"][:most]]
        if len(g["you"]) > most:
            out.append(f"  - and {len(g['you']) - most} more of the same kinds")
        out.append("next: tell me for each whether to make up values for it or leave it out; then I'll open the "
                   "approval window")
    else:
        out.append("next: I'll open the approval window (Approve the model): check it, then click Yes or No")
    return out


def log(root, fmt, name, removed, c):
    f = root / "design" / "reviews" / "model-intake.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    text = f.read_text(encoding="utf-8") if f.exists() else ("# Model intake\n\nWhat `pbik model intake` read and "
                                                              "deleted (file names only).\n")
    text += (f"\n## {datetime.datetime.now().isoformat(timespec='minutes')}: {fmt} `{name}`\n\n"
             f"- Contract: {len(c['tables'])} tables, {len(c['flags'])} flags.\n"
             f"- Deleted before reading: {', '.join(f'`{x}`' for x in removed) if removed else 'nothing'}.\n")
    f.write_text(text, encoding="utf-8")
