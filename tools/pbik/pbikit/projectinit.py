"""`pbik project init <name>`: a new report project in its own folder beside the kit (or --parent).

One folder = one project (v1.7): the usual way is that the person copies the kit to a new folder and opens it, and
`pbik project setup` turns that copy into the project on first run. `project init` does the same from the master kit
for someone who'd rather the agent made the copy: the kit's git-tracked files, minus the master-only ones, in
<parent>/<name>, with the Model and Reference folders and its own git repository. Never inside the master kit. Sets
the data class, writes design/status.json, makes a first commit, and, with --from-pack, starts from a model pack at
the plan step. Raising the data class is an agent step; lowering it later is the "Loosen the data class" task (a
person).
"""
import pathlib, re, shutil, subprocess

from . import dataclass_ as DC

KIT = pathlib.Path(__file__).resolve().parents[3]


class InitError(Exception):
    pass


def slug(name):
    s = re.sub(r"[^A-Za-z0-9 _-]+", "", name or "").strip()
    if not s:
        raise InitError("give the project a name (letters, digits, spaces, '-' or '_')")
    return s


def kit_files(kit=KIT):
    r = subprocess.run(["git", "ls-files", "-z"], cwd=kit, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise InitError("the kit isn't a git repository: copy it by hand")
    return [f for f in r.stdout.split("\0") if f]


def git(folder, *args):
    return subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8")


def init(name, parent=None, cls="internal", from_pack=None, kit=KIT, out=print):
    """Create the project folder; returns its path."""
    if cls not in DC.CLASSES:
        raise InitError(f"data class must be one of {', '.join(DC.CLASSES)}")
    target = pathlib.Path(parent or kit.parent) / slug(name)
    if kit.resolve() in [target.resolve(), *target.resolve().parents]:
        raise InitError("a project never goes inside the master kit: pick a folder outside it")
    if target.exists() and any(target.iterdir()):
        raise InitError(f"a folder named {target.name!r} already exists and isn't empty: pick another name")
    files = kit_files(kit)
    for f in files:
        src, dst = kit / f, target / f
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    from . import drops, projectsetup as PS
    for p in PS.master_only(target):                  # kit development files a project never uses
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for p in (target / PS.MARK, target / PS.LIST):
        if p.exists():
            p.unlink()
    drops.make(target)
    gi = target / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    gi.write_text("\n".join(lines + [x for x in ("Model/", "Reference/") if x not in lines]) + "\n", encoding="utf-8")
    DC.set_class(target, cls)
    if from_pack:
        from . import packs
        pack = pathlib.Path(from_pack)
        if not (pack / "pack.json").exists():         # a model name: look in the kit's pack folders
            pack = packs.find(kit, from_pack)
        packs.project_new(target, pack, out=lambda *a: None)
    from . import status as ST
    ST.update(target, done="start" if from_pack else None, dataClass=cls, path="model pack" if from_pack else None,
              setup="one folder",
              **({"pack": pathlib.Path(from_pack).name} if from_pack else {}))
    if from_pack:
        ST.update(target, done="model")
    git(target, "init", "-q")
    git(target, "add", "-A")
    r = git(target, "commit", "-q", "-m", f"project start: {target.name} (pbip-kit, data class {cls})")
    where = "in its own folder beside the kit" if target.parent == kit.parent else f"in {target.parent.name}"
    out(f"Your project {target.name} is ready {where} (data class {cls}"
        + (", started from an approved model" if from_pack else "") + "). Open that folder and ask me there; "
        "put your files in its Model and Reference folders."
        + ("" if r.returncode == 0 else " (First save point not made: set your name and email for git.)"))
    out("next: tell me what the report should help people decide, and share any wireframe, screenshot, report or "
        "requirements you have" if not from_pack else
        "next: tell me what the report should help people decide; I'll draw the plan as a picture")
    return target
