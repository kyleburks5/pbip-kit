"""Person-only gates as VS Code tasks with a Windows dialog (docs/design/phase1-usability.md, section 2).

    pbik gate prepare <gate> [--report R] [--pack P] [--from F | --workspace W --model M --id I] [--to-class C]
        the agent: writes .pbik/gates/<gate>.json (plain summary, args, a hash of what is approved)
    pbik gate run <gate>
        the person, through the Command Palette task: shows the summary in a dialog (Yes / No), applies on Yes,
        logs it in design/reviews/approvals.md and writes .pbik/gates/<gate>.result.json

`run` refuses in an agent's shell (CLAUDECODE) or without a terminal, and when what is approved changed after it was
prepared. An agent can type into a terminal but can't click a desktop dialog. This stops approvals by accident or on
an agent's own initiative; it is not proof against a person who scripts around it.
"""
import datetime, getpass, hashlib, json, pathlib, re, subprocess, tempfile

from . import dataclass_ as DC, summary as SM
from .synth import ContractError, content_hash, read_json, specs, write_json

GATES = list(SM.GATES)


class GateError(Exception):
    pass


def gate_dir(root):
    return pathlib.Path(root) / ".pbik" / "gates"


def _h(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def approver(root):
    r = subprocess.run(["git", "config", "user.name"], cwd=root, capture_output=True, text=True)
    name = (r.stdout or "").strip()
    try:
        login = getpass.getuser()
    except Exception:                                       # noqa: BLE001
        login = ""
    return f"{name or login} ({login})" if name and login and login.lower() not in name.lower() else (name or login)


# ---------------------------------------------------------------- what each gate approves
def _contract_summary(root):
    from . import rules as R
    c = read_json(specs(root) / "contract.json")
    if not c:
        raise GateError("there is no model to approve yet: drop the model first")
    g = R.groups(c)
    lines = [f"Model {c['model']}: {len(c['tables'])} tables, "
             f"{sum(len(t['measures']) for t in c['tables'].values())} measures, {len(c['relationships'])} relationships.",
             f"{len(g['rules'])} handled by rules, {len(g['keep'])} option table(s) to keep (their rows are shown "
             f"next), {len(g['you'])} need you."]
    if g["you"]:
        raise GateError(f"{len(g['you'])} item(s) still need a decision before approval: "
                        + "; ".join(R.plain(f) for f in g["you"][:5]))
    return c, "\n".join(lines), content_hash(c)


def prepare(gate, root=".", report=None, pack=None, from_=None, workspace=None, model=None, mid=None, to_class=None,
            to=None):
    """Write .pbik/gates/<gate>.json; returns it."""
    root = pathlib.Path(root).resolve()
    if gate not in SM.GATES:
        raise GateError(f"unknown gate {gate!r}")
    args = {k: v for k, v in dict(report=report, pack=pack, from_=from_, workspace=workspace, model=model, mid=mid,
                                  to_class=to_class, to=to).items() if v}
    if gate == "synth-approve":
        _, text, h = _contract_summary(root)
    elif gate == "map-approve":
        from . import bind as BD
        m = read_json(BD.map_file(root))
        if not m:
            raise GateError("there is no name map to approve")
        text = (f"{len(m.get('tables', {}))} table name(s) and {len(m.get('fields', {}))} field name(s) map to the live "
                "model:\n" + "\n".join(f"  {k} -> {v}" for k, v in list(m.get("tables", {}).items())
                                         + list(m.get("fields", {}).items())[:30]))
        h = BD.map_hash(m)
    elif gate == "model-approve":
        from . import packs as PK
        d = read_json(pathlib.Path(pack) / "drift.json") if pack else None
        if not d:
            raise GateError("no model changes are waiting for approval")
        text = f"{len(d['changes'])} change(s) to {d['contract']['model']} since the last approval:\n" + "\n".join(
            f"  {x['change']} {x['kind']} {x['what']}" for x in d["changes"][:30])
        h = _h(d["contract"].get("model"), d["changes"], content_hash(d["contract"]))
    elif gate == "bind-live":
        from . import bind as BD
        if from_:
            ws, mdl, mi, _ = BD.from_report(from_)
        else:
            ws, mdl, mi = workspace, model, BD.model_id(mid) if mid else None
        if not (ws and mdl and mi):
            raise GateError("pick the live model in Desktop first (the model picker), or give workspace, model and ID")
        args.update(workspace=ws, model=mdl, mid=mi)
        text = (f"Connect the report to the published model {mdl!r} in workspace {ws!r} (model ID {mi}). A backup is "
                "kept; 'Back to the synthetic model' undoes it.")
        h = _h(ws, mdl, mi, read_json(specs(root) / "bind-map.json", {}))
    elif gate == "bind-local":
        st = DC.bind_state(root)
        if not st or st.get("mode") != "live":
            raise GateError("the report isn't connected to a live model")
        text = (f"Point the report back at the synthetic model (it is connected to {st.get('model')!r} now). Files you "
                "didn't change while live come back exactly as they were.")
        h = _h(st)
    elif gate == "class-lower":
        old = DC.data_class(root)
        if not to_class or DC.CLASSES.index(to_class) >= DC.CLASSES.index(old):
            raise GateError(f"the data class is {old}; give a lower one to loosen it to")
        text = (f"Loosen this project's data class from {old} to {to_class}: "
                + ("live queries and screenshots are allowed again." if old == "restricted" else "fewer limits apply."))
        h = _h(old, to_class)
    else:                                                   # pack-register
        c = read_json(specs(root) / "contract.json")
        if not c or not to:
            raise GateError("there is no approved model to share, or no team folder")
        text = (f"Share the approved setup of {c['model']} (data class {DC.data_class(root)}) in the team folder. "
                "Only people approved for this data class may do this.")
        h = _h(content_hash(c), str(to))
    doc = {"gate": gate, "task": SM.GATES[gate][0], "summary": text, "hash": h, "args": args,
           "prepared": datetime.datetime.now().isoformat(timespec="seconds")}
    write_json(gate_dir(root) / f"{gate}.json", doc)
    (gate_dir(root).parent / ".gitignore").write_text("*\n", encoding="utf-8")
    return doc


def current_hash(gate, root, args):
    """The hash prepare would compute now (to refuse a gate whose content changed)."""
    tmp_root = pathlib.Path(root)
    saved = read_json(gate_dir(tmp_root) / f"{gate}.json")
    doc = prepare(gate, tmp_root, **{k: v for k, v in args.items() if k in (
        "report", "pack", "from_", "workspace", "model", "mid", "to_class", "to")})
    write_json(gate_dir(tmp_root) / f"{gate}.json", saved)       # prepare again must not move the prepared file
    return doc["hash"]


# ---------------------------------------------------------------- the dialog
DIALOG_PS = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$text = [IO.File]::ReadAllText($args[1])
$f = New-Object Windows.Forms.Form
$f.Text = $args[0]; $f.Width = 760; $f.Height = 520; $f.StartPosition = 'CenterScreen'; $f.TopMost = $true
$t = New-Object Windows.Forms.TextBox
$t.Multiline = $true; $t.ReadOnly = $true; $t.ScrollBars = 'Vertical'; $t.Text = $text
$t.SetBounds(12, 12, 720, 400); $t.Font = New-Object Drawing.Font('Segoe UI', 10)
$y = New-Object Windows.Forms.Button; $y.Text = 'Yes, approve'; $y.SetBounds(476, 428, 120, 32)
$y.DialogResult = [Windows.Forms.DialogResult]::Yes
$n = New-Object Windows.Forms.Button; $n.Text = 'No'; $n.SetBounds(612, 428, 120, 32)
$n.DialogResult = [Windows.Forms.DialogResult]::No
$f.Controls.AddRange(@($t, $y, $n)); $f.AcceptButton = $n; $f.CancelButton = $n
if ($f.ShowDialog() -eq [Windows.Forms.DialogResult]::Yes) { exit 0 } else { exit 1 }
"""


def windows_dialog(title, text):
    """True when the person clicks Yes in a desktop dialog."""
    with tempfile.TemporaryDirectory() as d:
        script, body = pathlib.Path(d) / "gate.ps1", pathlib.Path(d) / "text.txt"
        script.write_text(DIALOG_PS, encoding="utf-8-sig")
        body.write_text(text.replace("\n", "\r\n"), encoding="utf-8-sig")
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(script),
                            title, str(body)])
    return r.returncode == 0


# ---------------------------------------------------------------- run
def confirm_from_dialog(prompt):
    """The typed confirmations the step asks for: the Yes in the dialog stands for them."""
    m = re.search(r"Type (.+) to confirm: $", prompt)
    return m.group(1) if m else ""


def run(gate, root=".", dialog=None, out=print, person=None):
    """Show the prepared summary; on Yes apply the step. Returns "approved" or "declined"."""
    root = pathlib.Path(root).resolve()
    if not (person if person is not None else DC.person_present()):
        raise GateError("this step is yours: run it from the Command Palette (Tasks: Run Task), not from an agent")
    doc = read_json(gate_dir(root) / f"{gate}.json")
    if not doc:
        raise GateError("nothing is waiting for this approval: ask the agent to prepare it")
    if current_hash(gate, root, doc["args"]) != doc["hash"]:
        raise GateError("what you'd approve changed after it was prepared: ask the agent to prepare it again")
    extra = run_time_details(gate, root)
    text = doc["summary"] + ("\n\n" + extra if extra else "") + "\n\nApprove?"
    ok = (dialog or windows_dialog)(doc["task"], text)
    if not ok:
        write_json(gate_dir(root) / f"{gate}.result.json", {"gate": gate, "result": "declined"})
        out("Not approved: nothing changed.")
        return "declined"
    by = approver(root)
    apply(gate, root, doc["args"], by)
    log(root, gate, doc, by)
    write_json(gate_dir(root) / f"{gate}.result.json", {"gate": gate, "result": "approved", "by": by})
    out(f"Approved by {by}.")
    return "approved"


def run_time_details(gate, root):
    """What only the person sees, read at run time: the option-table rows a synth approval keeps."""
    if gate != "synth-approve":
        return ""
    from . import synth as S
    c = read_json(specs(root) / "contract.json")
    keep = [f for f in c["flags"] if f.get("resolution") == S.KEEP_ROWS]
    out = []
    for f in keep:
        x = S.kept_rows(c, root, f["table"])
        out.append(f"{f['table']} keeps {len(x['rows'])} row(s): " + "; ".join(" | ".join(map(str, r)) for r in x["rows"][:40]))
    return "\n".join(out)


def apply(gate, root, a, by):
    quiet = lambda *x: None                                 # noqa: E731
    if gate == "synth-approve":
        from . import synth as S
        S.approve(root, by, ask=confirm_from_dialog, out=quiet)
    elif gate == "map-approve":
        from . import bind as BD
        BD.map_approve(a["report"], by, root, ask=confirm_from_dialog, out=quiet)
    elif gate == "model-approve":
        from . import packs as PK
        PK.approve(a["pack"], by, ask=confirm_from_dialog, out=quiet)
    elif gate == "bind-live":
        from . import bind as BD
        BD.live(a["report"], by, a["workspace"], a["model"], a["mid"], a.get("from_"), root,
                ask=confirm_from_dialog, out=quiet)
    elif gate == "bind-local":
        from . import bind as BD
        BD.local(a["report"], root, out=quiet)
    elif gate == "class-lower":
        DC.set_class(root, a["to_class"], ask=confirm_from_dialog)
    else:
        from . import packs as PK
        PK.register(root, a["to"], out=quiet, allow_repo=True)


def log(root, gate, doc, by):
    f = pathlib.Path(root) / "design" / "reviews" / "approvals.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    head = "# Approvals\n\nPerson-only steps approved through the Command Palette tasks (pbikit/gates.py).\n\n" \
           "| When | Gate | Who | Hash | Summary |\n| --- | --- | --- | --- | --- |\n"
    text = f.read_text(encoding="utf-8") if f.exists() else head
    first = doc["summary"].splitlines()[0].replace("|", "/")
    text += (f"| {datetime.datetime.now().isoformat(timespec='minutes')} | {doc['task']} | {by} | {doc['hash']} "
             f"| {first} |\n")
    f.write_text(text, encoding="utf-8")


def tasks_json():
    """.vscode/tasks.json: one Command Palette task per gate."""
    tasks = [{"label": task, "type": "shell", "command": "python",
              "args": ["tools/pbik/pbik.py", "gate", "run", gate],
              "options": {"cwd": "${workspaceFolder}"}, "problemMatcher": [],
              "presentation": {"reveal": "always", "focus": True, "panel": "dedicated", "clear": True},
              "detail": f"pbik person-only step ({gate}): shows a summary, then Yes / No"}
             for gate, (task, _) in SM.GATES.items()]
    return {"version": "2.0.0", "tasks": tasks}
