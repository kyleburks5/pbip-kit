"""The project's two drop folders (one folder = one project, v1.7):

    Model\\       a copy of the semantic model export (git-ignored; `pbik model intake` deletes data files before reading)
    Reference\\   a wireframe, screenshot, requirements or an existing report's folder (git-ignored)

Both sit at the top of the project folder with plain names, made on first run (`pbik project setup`). The agent never
opens File Explorer: it says which folder to put a file in, and `pbik start check` says what each folder holds and
what is missing, in one line each. Projects made before this (design/reference/model and design/reference/inputs)
keep working: the old folder is used when it exists and the new one doesn't.
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


def _pick(root, new, old):
    root = pathlib.Path(root)
    if (root / new).is_dir() or not (root / old).is_dir():
        return root / new
    return root / old


def model_dir(root="."):
    return _pick(root, MODEL, OLD_MODEL)


def reference_dir(root="."):
    return _pick(root, REFERENCE, OLD_REFERENCE)


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
    """What a person put in a drop folder (top level only, the kit's own README and ignore files left out)."""
    folder = pathlib.Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.name.lower() not in NOT_INPUTS)
