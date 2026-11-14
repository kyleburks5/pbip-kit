"""One folder = one project (v1.7): the person copies or clones the master kit into a new folder and opens it there;
that folder is the project. No projects subfolder, no second folder, no chat switch.

    pbik project setup [--name N] [--class restricted]    first run in a fresh copy: turn it into a project
    pbik project master --here                             (the maintainer, once) mark this folder as the master kit

`pbik status` tells the three apart: the master kit (`.pbik/master-here` holds this folder's own path, so a copy or a
clone, which lives somewhere else, isn't the master), a fresh copy (no design/status.json yet: setup runs), and a
project. Setup, in place:
- removes the master-only files listed in tools/master-only.txt (kit development notes and tools a project never
  uses; every one of them stays in the master kit) and the master marker;
- makes the two drop folders, Model and Reference (pbikit/drops.py), git-ignored;
- sets the data class (restricted unless the person said otherwise) and writes design/status.json;
- gives the project its own git: a new repository when the copy has none; a clone keeps its history, and its
  `origin` (the master kit) is renamed `kit`, so nothing is ever pushed to the master by mistake;
- commits "project start".
A `projects` folder copied over from the old setup is never deleted (git ignores it; setup says so).
"""
import pathlib, shutil, subprocess

from . import dataclass_ as DC, drops

KIT = pathlib.Path(__file__).resolve().parents[3]
MARK = pathlib.Path(".pbik") / "master-here"
LIST = pathlib.Path("tools") / "master-only.txt"


class SetupError(Exception):
    pass


def git(folder, *args):
    return subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8")


def is_kit(root):
    root = pathlib.Path(root)
    return (root / "CLAUDE.md").exists() and (root / "tools" / "pbik" / "pbikit").is_dir()


def is_master(root):
    f = pathlib.Path(root) / MARK
    try:
        return pathlib.Path(f.read_text(encoding="utf-8").strip()).resolve() == pathlib.Path(root).resolve()
    except OSError:
        return False


def is_project(root):
    from . import status as ST
    return bool(ST.read(root).get("project"))


def kind(root="."):
    """"master", "project", "fresh copy" or "not the kit"."""
    if not is_kit(root):
        return "project" if is_project(root) else "not the kit"
    if is_master(root):
        return "master"
    return "project" if is_project(root) else "fresh copy"


def mark_master(root="."):
    f = pathlib.Path(root) / MARK
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(str(pathlib.Path(root).resolve()) + "\n", encoding="utf-8")
    return f


def master_only(root):
    """The master-only paths that exist in this folder (tools/master-only.txt: one glob per line, # comments)."""
    root = pathlib.Path(root)
    f = root / LIST
    if not f.exists():
        return []
    found = []
    for ln in f.read_text(encoding="utf-8").splitlines():
        g = ln.split("#", 1)[0].strip()
        if g:
            found += [p for p in sorted(root.glob(g)) if p.exists()]
    return found


def setup(root=".", name=None, cls="restricted", out=print):
    """Turn a fresh copy of the kit into a project, in place. Returns the project's name."""
    from . import status as ST
    root = pathlib.Path(root).resolve()
    k = kind(root)
    if k == "master":
        raise SetupError("this is the master kit: copy it to a new folder, open that folder, and ask me there")
    if k == "project":
        raise SetupError("this folder is already a project")
    if k != "fresh copy":
        raise SetupError("this folder isn't a copy of the kit")
    if cls not in DC.CLASSES:
        raise SetupError(f"data class must be one of {', '.join(DC.CLASSES)}")
    old_projects = (root / "projects").is_dir() and any((root / "projects").iterdir())
    name = name or root.name
    removed = []
    for p in master_only(root):
        removed.append(str(p.relative_to(root)).replace("\\", "/"))
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for p in (root / MARK, root / LIST):
        if p.exists():
            p.unlink()
    made = drops.make(root)
    gi = root / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    for want in ("Model/", "Reference/"):
        if want not in lines:
            lines.append(want)
    gi.write_text("\n".join(lines) + "\n", encoding="utf-8")
    DC.set_class(root, cls)
    ST.update(root, project=name, dataClass=cls, setup="one folder")
    if not (root / ".git").exists():
        git(root, "init", "-q")
        how = "a new git repository"
    else:
        remotes = git(root, "remote").stdout.split()
        if "origin" in remotes and "kit" not in remotes:
            git(root, "remote", "rename", "origin", "kit")
        how = "the clone's history, its link to the master renamed so nothing is pushed there"
    git(root, "add", "-A")
    r = git(root, "commit", "-q", "-m", f"project start: {name} (pbip-kit, data class {cls})")
    out(f"This folder is now your project {name} (data class {cls}; {how}).")
    out("It has two folders for your files: Model (a copy of your semantic model export) and Reference (a "
        "wireframe, screenshots, requirements or an existing report).")
    if removed:
        out(f"Removed {len(removed)} kit-only item(s) a project doesn't use; the master kit keeps them.")
    if old_projects:
        out("note: this copy also holds a projects folder from the old setup. It isn't part of this project and git "
            "ignores it; I left it as it is (you can delete it once you know nothing in it is needed).")
    if r.returncode:
        out("warning: the first save point wasn't made: set your name and email for git")
    out("next: tell me what the report should help people decide, and put your files in Model and Reference")
    return name
