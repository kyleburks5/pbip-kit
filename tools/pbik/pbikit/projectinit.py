"""`pbik project init <name>`: a new report project, set up by the agent (docs/design/phase1-usability.md, section 1).

Copies the kit's git-tracked files into projects/<name> inside the kit (or --parent), so the agent keeps working in the
same chat (v1.7, A7); the kit git-ignores projects/ and each project has its own git repository. Sets the data class,
writes design/status.json, makes a first commit, and, with --from-pack, starts from a model pack at the plan step. Raising the data class
is an agent step; lowering it later is the "Loosen the data class" task (a person).
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
    target = pathlib.Path(parent or kit / "projects") / slug(name)
    if target.exists() and any(target.iterdir()):
        raise InitError(f"a folder named {target.name!r} already exists and isn't empty: pick another name")
    files = kit_files(kit)
    for f in files:
        src, dst = kit / f, target / f
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    DC.set_class(target, cls)
    if from_pack:
        from . import packs
        pack = pathlib.Path(from_pack)
        if not (pack / "pack.json").exists():         # a model name: look in the kit's pack folders
            pack = packs.find(kit, from_pack)
        packs.project_new(target, pack, out=lambda *a: None)
    from . import status as ST
    ST.update(target, done="start" if from_pack else None, dataClass=cls, path="model pack" if from_pack else None,
              **({"pack": pathlib.Path(from_pack).name} if from_pack else {}))
    if from_pack:
        ST.update(target, done="model")
    git(target, "init", "-q")
    git(target, "add", "-A")
    r = git(target, "commit", "-q", "-m", f"project start: {target.name} (pbip-kit, data class {cls})")
    inside = target.parent == kit / "projects"
    where = "in the projects folder of this kit" if inside else f"in {target.parent.name}"
    out(f"Your project {target.name} is ready {where} (data class {cls}"
        + (", started from an approved model" if from_pack else "") + "). I can open it in File Explorer."
        + ("" if r.returncode == 0 else " (First save point not made: set your name and email for git.)"))
    out("next: tell me what the report should help people decide, and share any wireframe, screenshot, report or "
        "requirements you have" if not from_pack else
        "next: tell me what the report should help people decide; I'll draw the plan as a picture")
    return target
