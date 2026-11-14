"""Person-only gates: an approval window the agent opens itself (docs/design/phase1-usability.md, A8 and B2).

    pbik gate prepare <gate> [--report R] [--pack P] [--from F | --workspace W --model M --id I] [--to-class C]
        the agent: writes .pbik/gates/<gate>.json (plain summary, args, a hash of what is approved)
    pbik gate open <gate>     the agent: opens the approval window in its own process and returns at once
    pbik gate wait <gate>     the agent: waits (up to 30 minutes) for the person's answer
    pbik gate run <gate>      shows the window and waits (the optional Command Palette tasks use this)

The window shows the summary and a plain Yes / No (v1.7 walkthrough: the typed code was the most disliked step). It
opens in front of every other window. Only when screen control is active (computer use in a Claude Code chat in the
last few minutes: the hook tools/hooks/guard_gates.py leaves a marker) does it also show a 4-character code drawn as a
picture (made inside the window's own process, never written to a file, stdout or the log) and a box to type it: Yes
then needs the code, and three wrong tries close it with nothing changed. PBIK_GATE_CODE=1 asks for the code always.
On Yes the step is applied, logged in design/reviews/approvals.md, and the answer written to
.pbik/gates/<gate>.result.json. Refusals: what is approved changed after it was prepared (hash); another approval
window is open. Honest limit: without screen control an agent can't click the window (the hook also blocks key and
window drivers while it is open); the code covers the case where it could. Neither is proof against a person who
scripts around it.
"""
import datetime, getpass, hashlib, json, os, pathlib, re, subprocess, sys, tempfile, time

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
             R.summary_line(c) + "." + (" The option tables' rows are shown below." if g["keep"] else "")]
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
        pack = pack or (DC.read_project(root).get("pack") or {}).get("path")
        df = specs(root) / "drift.json"
        df = df if df.exists() else (pathlib.Path(pack) / "drift.json" if pack else None)
        args.update(pack=pack, drift=str(df) if df else None)
        d = read_json(df) if df else None
        if not d:
            raise GateError("no model changes are waiting for approval")
        text = f"{len(d['changes'])} change(s) to {d['contract']['model']} since the last approval:\n" + "\n".join(
            f"  {x['change']} {x['kind']} {x['what']}" for x in d["changes"][:30])
        h = _h(d["contract"].get("model"), d["changes"], content_hash(d["contract"]))
    elif gate == "bind-live":
        from . import bind as BD
        if from_ == "picked":                              # the Desktop model picker (pbikit/picker.py)
            from . import picker as PK_
            ws, mdl, mi, rep_folder = PK_.picked(root)
            args["from_"] = from_ = str(rep_folder)
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
        from . import packs as PK
        c = read_json(specs(root) / "contract.json")
        to = to or next((str(p) for p, team in PK.pack_folders(root) if team), None)
        if not c or not to:
            raise GateError("there is no approved model to share, or no team folder")
        args["to"] = to
        if not PK.may_register(to, DC.data_class(root), approver(root)):
            raise GateError(f"only people approved for {DC.data_class(root)} data may share packs in the team folder")
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


# ---------------------------------------------------------------- the window
DIALOG_PS = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$text = [IO.File]::ReadAllText($args[1])
$withCode = ($args[2] -eq 'code')
Add-Type -Namespace PbikWin -Name Native -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
[DllImport("user32.dll")] public static extern bool FlashWindow(IntPtr h, bool invert);
'@
$letters = 'ACDEFHJKMNPRTUVWXY34679'
$rng = New-Object Security.Cryptography.RNGCryptoServiceProvider
$bytes = New-Object byte[] 4; $rng.GetBytes($bytes)
$code = -join ($bytes | ForEach-Object { $letters[$_ % $letters.Length] })
$f = New-Object Windows.Forms.Form
$f.Text = $args[0]; $f.Width = 780; $f.Height = 640; $f.StartPosition = 'CenterScreen'; $f.TopMost = $true
$f.FormBorderStyle = 'FixedDialog'; $f.MaximizeBox = $false; $f.MinimizeBox = $false
$t = New-Object Windows.Forms.TextBox
$t.Multiline = $true; $t.ReadOnly = $true; $t.ScrollBars = 'Vertical'; $t.Text = $text; $t.TabStop = $false
$t.SetBounds(16, 16, 732, 380); $t.Font = New-Object Drawing.Font('Segoe UI', 10)
$l = New-Object Windows.Forms.Label
$l.Text = if ($withCode) { 'Screen control is on in a chat, so: type the code in the picture, then click Yes, approve.' } else { 'Approve this? Click Yes, approve or No.' }
$l.SetBounds(16, 410, 732, 22); $l.Font = New-Object Drawing.Font('Segoe UI', 10)
$bmp = New-Object Drawing.Bitmap 220, 64
$g = [Drawing.Graphics]::FromImage($bmp); $g.SmoothingMode = 'AntiAlias'; $g.Clear([Drawing.Color]::White)
$r = New-Object Random
for ($i = 0; $i -lt 6; $i++) {
  $pen = New-Object Drawing.Pen ([Drawing.Color]::FromArgb(70, 120, 120, 120)), 2
  $g.DrawLine($pen, $r.Next(0, 220), $r.Next(0, 64), $r.Next(0, 220), $r.Next(0, 64))
}
$font = New-Object Drawing.Font('Consolas', 30, [Drawing.FontStyle]::Bold)
for ($i = 0; $i -lt 4; $i++) {
  $g.TranslateTransform(18 + 50 * $i, 8); $g.RotateTransform($r.Next(-12, 12))
  $g.DrawString([string]$code[$i], $font, [Drawing.Brushes]::Black, 0, 0); $g.ResetTransform()
}
$g.Dispose()
$pic = New-Object Windows.Forms.PictureBox; $pic.Image = $bmp; $pic.SetBounds(16, 440, 220, 64)
$pic.AccessibleName = 'approval code picture'
$box = New-Object Windows.Forms.TextBox; $box.SetBounds(256, 456, 120, 32); $box.MaxLength = 4
$box.Font = New-Object Drawing.Font('Consolas', 16); $box.CharacterCasing = 'Upper'
$msg = New-Object Windows.Forms.Label; $msg.SetBounds(392, 462, 356, 22); $msg.ForeColor = [Drawing.Color]::DarkRed
$y = New-Object Windows.Forms.Button; $y.Text = 'Yes, approve'; $y.SetBounds(476, 548, 132, 34)
$n = New-Object Windows.Forms.Button; $n.Text = 'No'; $n.SetBounds(620, 548, 128, 34)
$script:result = 1; $script:tries = 0
$y.Add_Click({
  if (-not $withCode) { $script:result = 0; $f.Close(); return }
  if ($box.Text.Trim().ToUpper() -eq $code) { $script:result = 0; $f.Close() }
  else {
    $script:tries++
    if ($script:tries -ge 3) { $script:result = 2; $f.Close() }
    else { $msg.Text = "That code doesn't match ($(3 - $script:tries) tries left)."; $box.Text = '' }
  }
})
$n.Add_Click({ $script:result = 1; $f.Close() })
if ($withCode) { $f.Controls.AddRange(@($t, $l, $pic, $box, $msg, $y, $n)); $f.ActiveControl = $box }
else { $f.Controls.AddRange(@($t, $l, $y, $n)); $f.Height = 520; $y.Top = 440; $n.Top = 440; $f.ActiveControl = $n }
$f.CancelButton = $n
# in front of every other window, even when opened from a background process (walkthrough fix 14)
$f.Add_Shown({ $f.TopMost = $true; $f.Activate(); $f.BringToFront()
  [void][PbikWin.Native]::ShowWindow($f.Handle, 9); [void][PbikWin.Native]::SetForegroundWindow($f.Handle)
  [void][PbikWin.Native]::FlashWindow($f.Handle, $true) })
[void]$f.ShowDialog()
exit $script:result
"""
ANSWERS = {0: "yes", 1: "no", 2: "code"}


def windows_dialog(title, text, code=False):
    """The approval window: a plain Yes / No; with `code` (screen control active) "yes" only when the person typed
    the code shown in the picture and clicked Yes. "no" (No, or closed) or "code" (three wrong tries)."""
    with tempfile.TemporaryDirectory() as d:
        script, body = pathlib.Path(d) / "gate.ps1", pathlib.Path(d) / "text.txt"
        script.write_text(DIALOG_PS, encoding="utf-8-sig")
        body.write_text(text.replace("\n", "\r\n"), encoding="utf-8-sig")
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(script),
                            title, str(body), "code" if code else "plain"])
    return ANSWERS.get(r.returncode, "no")


def _answer(x):
    """A window's answer: "yes", "no" or "code" (test stubs may return True / False)."""
    return ("yes" if x else "no") if isinstance(x, bool) or x is None else str(x)


# ---------------------------------------------------------------- refusals checked before a window opens
SCREEN_CONTROL_MINUTES = 10
WINDOW_MINUTES = 35


def user_dir():
    """Per-person pbik state outside every project (PBIK_HOME in tests): screen-control marker, window lock, history."""
    return pathlib.Path(os.environ.get("PBIK_HOME") or pathlib.Path.home() / ".pbik")


def _age_minutes(f):
    try:
        at = datetime.datetime.fromisoformat(json.loads(f.read_text(encoding="utf-8"))["at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (datetime.datetime.now() - at).total_seconds() / 60


def screen_control_active():
    """True when a screen-control tool was used in the last SCREEN_CONTROL_MINUTES (the Claude Code hook's marker).
    Other screen-control apps can't be detected: the window's typed code is then the only protection."""
    age = _age_minutes(user_dir() / "screen-control.json")
    return age is not None and age < SCREEN_CONTROL_MINUTES


def needs_code():
    """The typed code only when screen control is active (an agent could click Yes itself); otherwise a plain Yes / No
    (VS Code with Claude Code or Copilot, the Claude desktop app with computer use off). PBIK_GATE_CODE=1 or 0
    overrides, for a person who wants the code always, and for tests."""
    env = os.environ.get("PBIK_GATE_CODE")
    if env in ("0", "1"):
        return env == "1"
    return screen_control_active()


def window_open():
    age = _age_minutes(user_dir() / "gate-window.json")
    return age is not None and age < WINDOW_MINUTES


def _lock(gate, on):
    f = user_dir() / "gate-window.json"
    if on:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"gate": gate, "at": datetime.datetime.now().isoformat(timespec="seconds")}),
                     encoding="utf-8")
    else:
        try:
            f.unlink()
        except OSError:
            pass


def check_ready(gate, root):
    """Every refusal, checked before a window opens; returns the prepared doc."""
    doc = read_json(gate_dir(root) / f"{gate}.json")
    if not doc:
        raise GateError("nothing is waiting for this approval: ask the agent to prepare it")
    if window_open():
        raise GateError("another approval window is open: answer it first")
    if current_hash(gate, root, doc["args"]) != doc["hash"]:
        raise GateError("what you'd approve changed after it was prepared: ask the agent to prepare it again")
    return doc


# ---------------------------------------------------------------- run, open, wait
def confirm_from_dialog(prompt):
    """The typed confirmations the step asks for: the code and Yes in the window stand for them."""
    m = re.search(r"Type (.+) to confirm: $", prompt)
    return m.group(1) if m else ""


def run(gate, root=".", dialog=None, out=print, person=None):
    """Show the approval window; on Yes (with the typed code) apply the step. Returns "approved" or "declined".
    `person` is ignored (kept for older callers): the window's code is the person check (A8)."""
    root = pathlib.Path(root).resolve()
    doc = check_ready(gate, root)
    extra = run_time_details(gate, root)
    text = doc["summary"] + ("\n\n" + extra if extra else "") + "\n\nApprove?"
    code = needs_code()
    _lock(gate, True)
    try:
        d = dialog or windows_dialog
        try:
            ans = _answer(d(doc["task"], text, code=code))
        except TypeError:                                       # an older stub: (title, text)
            ans = _answer(d(doc["task"], text))
    finally:
        _lock(gate, False)
    if ans != "yes":
        why = "the code didn't match three times" if ans == "code" else "no"
        write_json(gate_dir(root) / f"{gate}.result.json", {"gate": gate, "result": "declined", "why": why})
        out("Not approved: nothing changed." + (" (The code didn't match three times.)" if ans == "code" else ""))
        return "declined"
    by = approver(root)
    apply(gate, root, doc["args"], by)
    log(root, gate, doc, by)
    write_json(gate_dir(root) / f"{gate}.result.json", {"gate": gate, "result": "approved", "by": by})
    out(f"Approved by {by}.")
    return "approved"


def open_window(gate, root=".", launch=None):
    """The agent opens the approval window in its own process and returns at once (A8)."""
    root = pathlib.Path(root).resolve()
    doc = check_ready(gate, root)
    res = gate_dir(root) / f"{gate}.result.json"
    if res.exists():
        res.unlink()
    cmd = [sys.executable, str(pathlib.Path(__file__).resolve().parents[1] / "pbik.py"), "gate", "run", gate,
           "--root", str(root)]
    if launch:
        launch(cmd)
        return doc
    logf = open(gate_dir(root) / f"{gate}.window.log", "w", encoding="utf-8")   # noqa: SIM115  the window keeps it
    flags = (0x00000008 | 0x00000200) if os.name == "nt" else 0              # DETACHED_PROCESS | NEW_PROCESS_GROUP
    subprocess.Popen(cmd, cwd=str(root), stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     creationflags=flags, close_fds=True)
    return doc


def wait(gate, root=".", timeout=30 * 60, poll=1.0):
    """Wait for the person's answer; the result doc, or {"result": "not answered"} after the timeout."""
    res = gate_dir(pathlib.Path(root).resolve()) / f"{gate}.result.json"
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        doc = read_json(res)
        if doc:
            return doc
        time.sleep(poll)
    return {"gate": gate, "result": "not answered"}


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
        PK.approve(a["pack"], by, ask=confirm_from_dialog, out=quiet, drift_file=a.get("drift"))
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
    head = "# Approvals\n\nPerson-only steps approved in the approval window (pbikit/gates.py).\n\n" \
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
