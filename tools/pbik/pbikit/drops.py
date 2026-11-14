"""The project's two drop folders (one folder = one project, v1.7):

    Model\\       a copy of the semantic model export (git-ignored; `pbik model intake` deletes data files before reading)
    Reference\\   a wireframe, screenshot, requirements or an existing report's folder (git-ignored)

Both sit at the top of the project folder with plain names, made on first run (`pbik project setup`). The agent never
opens File Explorer: it says which folder to put a file in, and `pbik start check` says what each folder holds and
what is missing, in one line each. Only these two folders are read (v1.7 live walkthrough fix 5): files left in the
old places (design/reference/model and design/reference/inputs) are never read; `old_lines` names them so the agent
can ask the person to move them. The live-model pick (pbikit/picker.py) is saved in Reference's "Live pick" folder,
which is never read as a layout input.
"""
import pathlib

MODEL = "Model"
REFERENCE = "Reference"
OLD_MODEL = pathlib.Path("design") / "reference" / "model"
OLD_REFERENCE = pathlib.Path("design") / "reference" / "inputs"
README = {
    MODEL: "Put a copy of your semantic model export here (a .SemanticModel folder, a TMDL folder or script, or a "
           "TMSL export), never your only file.\nThe kit deletes any data files in it before reading anything, and "
           "nothing in this folder is saved to git.\n",
    REFERENCE: "Put a copy of what the report should look like here: a wireframe (HTML), screenshots or pictures, "
               "requirements (text, Markdown or Word), or an existing report's .Report folder.\nNothing in this "
               "folder is saved to git. Leave it empty to choose from starter layouts.\n",
}
NOT_INPUTS = {"readme.txt", ".gitignore", ".gitkeep", "desktop.ini", "thumbs.db"}


LIVE_PICK = "Live pick"


def model_dir(root="."):
    return pathlib.Path(root) / MODEL


def reference_dir(root="."):
    return pathlib.Path(root) / REFERENCE


def old_files(root="."):
    """{"Model": [names], "Reference": [names]}: what a person left in the old places, which nothing reads."""
    root = pathlib.Path(root)
    out = {}
    for name, old in ((MODEL, OLD_MODEL), (REFERENCE, OLD_REFERENCE)):
        got = entries(root / old)
        if got:
            out[name] = [p.name for p in got]
    return out


def old_lines(root="."):
    """Plain warnings for files in the old places (never read): move them into the named folder."""
    out = []
    for name, names in old_files(root).items():
        one = len(names) == 1
        out.append(f"warning: {', '.join(names[:3])}{' and more' if len(names) > 3 else ''} "
                   f"{'is' if one else 'are'} in the old place for {name.lower()} files (inside the design folder), "
                   f"which I no longer read: move {'it' if one else 'them'} into the {name} folder and say done")
    return out


def make(root="."):
    """Make both folders with a short README each (git-ignored). Returns [(name, path)]."""
    out = []
    for name, d in ((MODEL, model_dir(root)), (REFERENCE, reference_dir(root))):
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitignore").write_text("*\n", encoding="utf-8")
        if d.name == name:
            (d / "README.txt").write_text(README[name], encoding="utf-8")
        out.append((name, d))
    return out


def entries(folder):
    """What a person put in a drop folder (top level only, the kit's own README and ignore files and the live-model
    pick left out)."""
    folder = pathlib.Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.name.lower() not in NOT_INPUTS and p.name != LIVE_PICK)
