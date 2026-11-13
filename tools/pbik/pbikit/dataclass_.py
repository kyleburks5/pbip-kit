"""Project data classes (public / internal / restricted), the restricted guard, and person-only confirmation.

docs/design/synth-to-live.md. The class is project.json `dataClass` (default internal). Restricted means the report
works on the synthetic model only: while it is bound live, or with no synthetic model in the project, live DAX
queries (run-dax.ps1) and screenshots refuse.
"""
import datetime, json, os, pathlib, sys

CLASSES = ("public", "internal", "restricted")
DEFAULT = "internal"
SYNTH_MARK = "PBIK_Synthetic"


class Refused(Exception):
    """A person-only step was refused (not a person at a terminal, or the typed text didn't match)."""


def project_file(root):
    return pathlib.Path(root) / "design" / "specs" / "project.json"


def read_project(root):
    f = project_file(root)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def data_class(root):
    return read_project(root).get("dataClass", DEFAULT)


def set_class(root, cls, ask=None):
    """Set dataClass. Lowering it (restricted -> internal, ...) is person-only."""
    if cls not in CLASSES:
        raise ValueError(f"data class must be one of {', '.join(CLASSES)}")
    old = data_class(root)
    if CLASSES.index(cls) < CLASSES.index(old):
        confirm(f"Lower the data class from {old} to {cls}?", cls.upper(), ask)
    f = project_file(root)
    d = read_project(root)
    d["dataClass"] = cls
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    return old


def bind_state(root):
    f = pathlib.Path(root) / ".pbik" / "bind" / "state.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def is_synthetic(model_folder):
    if not model_folder:
        return False
    f = pathlib.Path(model_folder) / "definition" / "model.tmdl"
    return f.exists() and SYNTH_MARK in f.read_text(encoding="utf-8")


def synthetic_models(root):
    return [p for p in pathlib.Path(root).glob("*.SemanticModel") if is_synthetic(p)]


def guard(root, action):
    """None when `action` (dax, screenshot) may run, else the reason it may not."""
    if data_class(root) != "restricted":
        return None
    st = bind_state(root)
    if st and st.get("mode") == "live":
        return (f"restricted project: the report is bound to the live model ({st.get('model')}); no {action} "
                "while live. Run `pbik bind local` first")
    if not synthetic_models(root):
        return f"restricted project: no synthetic model (`pbik synth generate`), so no {action}"
    return None


def person_present():
    """True when a person is at the terminal: stdin is a TTY and this isn't an agent's shell (CLAUDECODE)."""
    return sys.stdin is not None and sys.stdin.isatty() and not os.environ.get("CLAUDECODE")


def confirm(prompt, expected, ask=None):
    """Ask a person to type `expected` (case-sensitive). `ask` (tests) replaces the terminal prompt."""
    if ask is None:
        if not person_present():
            raise Refused("person-only step: run it yourself in a terminal (an agent can't approve it)")
        ask = input
    got = ask(f"{prompt}\nType {expected} to confirm: ")
    if (got or "").strip() != expected:
        raise Refused(f"not confirmed (expected {expected!r})")
    return True


def stamp(by):
    if not (by or "").strip():
        raise Refused("--by <name> is required")
    return {"by": by.strip(), "date": datetime.date.today().isoformat()}
