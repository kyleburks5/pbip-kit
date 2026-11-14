"""`pbik project init <name>`: a new report project, set up by the agent (docs/design/phase1-usability.md, section 1).

Copies the kit's git-tracked files into a new folder beside the kit (or --parent), sets the data class, starts a git
repository with a first commit, and, with --from-pack, starts from a model pack at the plan step. Raising the data class
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
    target = pathlib.Path(parent or kit.parent) / slug(name)
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
    git(target, "init", "-q")
    git(target, "add", "-A")
    r = git(target, "commit", "-q", "-m", f"project start: {target.name} (pbip-kit, data class {cls})")
    out(f"project {target.name!r} is ready: {len(files)} kit file(s), data class {cls}"
        + (", started from a model pack at the plan step" if from_pack else "")
        + ("" if r.returncode == 0 else " (first commit not made: set your git name and email)"))
    out("next: open the new folder in VS Code and say what the report is for (/brd)")
    return target
