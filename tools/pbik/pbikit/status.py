"""`pbik status`: where a project is, in one plain line (docs/design/phase1-usability.md, A7).

design/status.json (committed, no data) holds the path taken, the build mode, the report type, the model pack, the
data class, the approved plan's hash, the stages done and the next one, and the last polish score. Any new chat runs
`pbik status` first and says "You're at <stage>; next is <stage>." In the kit folder (several projects under
projects/), it lists them, the last one used first.
"""
import datetime, json, pathlib

STAGES = ["start", "model", "page purpose", "plan", "theme", "build", "checks", "polish", "result", "live", "wrap-up"]
GUIDED_PAUSES = ["page purpose", "plan", "theme", "build", "checks", "polish"]
QUICK_PAUSES = ["plan"]
PLAIN = {"start": "start (what the report is for, and what you have)", "model": "the model",
         "page purpose": "the page purpose", "plan": "the plan picture", "theme": "the colours", "build": "the build",
         "checks": "the checks", "polish": "the polish", "result": "the result",
         "live": "switching to the live model", "wrap-up": "the wrap-up"}
MODE_WORDS = {"guided": "guided build", "quick": "quick build"}


def status_file(root):
    return pathlib.Path(root) / "design" / "status.json"


def read(root):
    f = status_file(root)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        return {}


def write(root, doc):
    f = status_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    doc["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    f.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def next_stage(done):
    return next((s for s in STAGES if s not in done), None)


def update(root, done=None, **fields):
    """Mark a stage done (the next one follows from STAGES) and set any other field (mode, path, pack, ...)."""
    doc = read(root)
    doc.setdefault("project", pathlib.Path(root).resolve().name)
    doc.setdefault("done", [])
    if done:
        if done not in STAGES:
            raise ValueError(f"unknown stage {done!r}: one of {', '.join(STAGES)}")
        if done not in doc["done"]:
            doc["done"].append(done)
            doc["done"].sort(key=STAGES.index)
    for k, v in fields.items():
        if v is not None:
            if k == "mode" and doc.get("mode") and doc["mode"] != v:
                doc.setdefault("switches", []).append({"from": doc["mode"], "to": v, "after": doc["done"][-1:]})
            doc[k] = v
    doc["next"] = next_stage(doc["done"])
    return write(root, doc)


def pauses(doc):
    """The stages the build stops after, for its mode."""
    return GUIDED_PAUSES if doc.get("mode", "guided") == "guided" else QUICK_PAUSES


def line(root):
    """The plain status line a new chat starts with."""
    doc = read(root)
    if not doc:
        return "This folder has no report project yet. Tell me what the report should help people decide."
    done = doc.get("done", [])
    at = PLAIN.get(done[-1], done[-1]) if done else None
    nxt = doc.get("next")
    head = f"{doc.get('project', 'This project')}: "
    head += (f"you're past {at}; next is {PLAIN.get(nxt, nxt)}." if at and nxt else
             f"next is {PLAIN.get(nxt, nxt)}." if nxt else "every step is done.")
    extra = []
    if doc.get("mode"):
        extra.append(MODE_WORDS.get(doc["mode"], doc["mode"]))
    if doc.get("dataClass"):
        extra.append(f"data {doc['dataClass']}")
    if doc.get("score") is not None:
        extra.append(f"polish {doc['score']}/10")
    return head + (f" ({', '.join(extra)})" if extra else "")


def projects(kit):
    """[(name, folder, status doc)] under <kit>/projects, the last one used first."""
    base = pathlib.Path(kit) / "projects"
    out = [(p.name, p, read(p)) for p in base.iterdir() if p.is_dir()] if base.is_dir() else []
    return sorted(out, key=lambda x: x[2].get("updated", ""), reverse=True)


def show(root, out=print):
    """In a project: its line. In the kit folder: every project's line, the last one used first."""
    root = pathlib.Path(root).resolve()
    if status_file(root).exists() or not (root / "projects").is_dir():
        out(line(root))
        return
    ps = projects(root)
    if not ps:
        out("There are no report projects yet. Tell me what the report should help people decide.")
        return
    out(f"{len(ps)} project(s); the last one used first:")
    for name, folder, _ in ps:
        out("  " + line(folder))
