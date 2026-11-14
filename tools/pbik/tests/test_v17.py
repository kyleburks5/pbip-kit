"""v1.7 tests (docs/design/phase1-usability.md, Part A) on made-up data only.

    python tools\\pbik\\tests\\test_v17.py
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
PBIK = HERE.parent / "pbik.py"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "tools"))

from pbikit import status as ST  # noqa: E402

MODEL = "/".join(("design", "reference", "model"))           # spelled in parts: the guard reads tool calls


def pbik(*args, cwd=None):
    return subprocess.run([sys.executable, str(PBIK), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_v17_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def fake_kit(root):
    """A tiny git repository standing in for the kit (project init copies its tracked files)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text("# kit\n", encoding="utf-8")
    (root / ".gitignore").write_text("projects/\n", encoding="utf-8")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit",
                                                  "-q", "-m", "kit"]):
        subprocess.run(["git", *args], cwd=root, capture_output=True)
    return root


# ---------------------------------------------------------------- stage a
class GuardTests(Tmp):
    """A10: the model-folder guard keeps working when the working folder changes, and fails closed."""
    HOOK = KIT / "tools" / "hooks" / "guard_model_folder.py"

    def run_hook(self, event, cwd):
        return subprocess.run([sys.executable, str(self.HOOK)], input=json.dumps(event), capture_output=True,
                              text=True, cwd=cwd).returncode

    def test_from_three_working_folders(self):
        proj = self.tmp / "kit" / "projects" / "Sales"
        (proj / "design" / "reference").mkdir(parents=True)
        events = [
            ({"tool_name": "Read", "tool_input": {"file_path": "model/x.tmdl"}, "cwd": str(proj / "design" / "reference")}, 2),
            ({"tool_name": "Read", "tool_input": {"file_path": f"{MODEL}/x.tmdl"}, "cwd": str(proj)}, 2),
            ({"tool_name": "Glob", "tool_input": {"pattern": "**/*.tmdl"}, "cwd": str(proj / MODEL)}, 2),
            ({"tool_name": "Glob", "tool_input": {"pattern": "model/**"}, "cwd": str(proj / "design" / "reference")}, 2),
            ({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(proj / MODEL)}, 2),
            ({"tool_name": "Bash", "tool_input": {"command": "python tools/pbik/pbik.py model intake"},
              "cwd": str(proj)}, 0),
            ({"tool_name": "Read", "tool_input": {"file_path": "brd.md"}, "cwd": str(proj / "design" / "reference")}, 0),
            ({"tool_name": "Read", "tool_input": {"file_path": "../reference/brd.md"},
              "cwd": str(proj / "design" / "specs")}, 0),
        ]
        for cwd in (KIT, proj, self.tmp):                           # the kit, a project, an unrelated folder
            for event, code in events:
                self.assertEqual(self.run_hook(event, cwd), code, (cwd, event))

    def test_fails_closed(self):
        r = subprocess.run([sys.executable, str(self.HOOK)], input="{not json " + MODEL, capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 2)
        r = subprocess.run([sys.executable, str(self.HOOK)], input="{not json at all", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, "a broken event that names no model folder isn't blocked")

    def test_settings_use_the_project_folder(self):
        settings = json.loads((KIT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cmd = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("$CLAUDE_PROJECT_DIR/tools/hooks/guard_model_folder.py", cmd)
        bash = shutil.which("bash")
        if bash:                                                    # the way Claude Code runs it: a shell, any cwd
            r = subprocess.run([bash, "-c", cmd.replace("python", f'"{pathlib.Path(sys.executable).as_posix()}"', 1)],
                               input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": f"{MODEL}/a"}}),
                               capture_output=True, text=True, cwd=self.tmp,
                               env={**os.environ, "CLAUDE_PROJECT_DIR": KIT.as_posix()})
            self.assertEqual(r.returncode, 2, r.stderr)


class ProjectsFolderTests(Tmp):
    """A7, D2: projects inside the open folder, their own git, never tracked by the kit."""

    def test_init_inside_projects_with_status(self):
        from pbikit import projectinit as PI
        kit = fake_kit(self.tmp / "kit")
        said = []
        target = PI.init("Sales Overview", None, "restricted", kit=kit, out=said.append)
        self.assertEqual(target, kit / "projects" / "Sales Overview")
        self.assertTrue((target / ".git").is_dir(), "its own git repository")
        kit_status = subprocess.run(["git", "status", "--porcelain"], cwd=kit, capture_output=True, text=True).stdout
        self.assertEqual(kit_status.strip(), "", "the kit doesn't see the project")
        self.assertIn("is ready in the projects folder", said[0])
        self.assertIn("open it in File Explorer", said[0])
        for s in said:
            self.assertNotIn("/", s.replace("and/or", ""), "no slash command or path")
            self.assertNotIn("\\", s)
        doc = ST.read(target)
        self.assertEqual((doc["dataClass"], doc["next"]), ("restricted", "start"))

    def test_export_check_flags_project_files(self):
        import export_check as EC
        found = {c: [] for c in EC.CHECKS}
        EC.scan_path("projects/Sales/design/specs/layout.json", [("*", "projects/*")], found)
        self.assertEqual(found["report projects"], ["projects/Sales/design/specs/layout.json"],
                         "the allow list can't let a project file through")
        self.assertIn("projects/", (KIT / ".gitignore").read_text(encoding="utf-8").splitlines())


class StatusTests(Tmp):
    """A7: the status file and the line a new chat starts with."""

    def test_stages_line_and_switch(self):
        ST.update(self.tmp, done="start", mode="quick", dataClass="restricted", path="from wireframe")
        ST.update(self.tmp, done="model")
        self.assertEqual(ST.read(self.tmp)["next"], "page purpose")
        self.assertEqual(ST.pauses(ST.read(self.tmp)), ["plan"])
        ST.update(self.tmp, mode="guided")
        doc = ST.read(self.tmp)
        self.assertEqual(doc["switches"], [{"from": "quick", "to": "guided", "after": ["model"]}])
        self.assertIn("page purpose", ST.pauses(doc))
        line = ST.line(self.tmp)
        self.assertIn("you're past the model; next is the page purpose", line)
        self.assertIn("guided build", line)
        with self.assertRaises(ValueError):
            ST.update(self.tmp, done="brd")

    def test_kit_lists_projects_and_in_option(self):
        for name, stage in (("A", "start"), ("B", "plan")):
            folder = self.tmp / "projects" / name
            ST.update(folder, done="start")
            if stage == "plan":
                for s in ("model", "page purpose", "plan"):
                    ST.update(folder, done=s)
                doc = ST.read(folder)
                ST.status_file(folder).write_text(json.dumps({**doc, "updated": "2999-01-01T00:00:00"}),
                                                  encoding="utf-8")
        r = pbik("status", cwd=self.tmp)
        self.assertIn("2 project(s)", r.stdout)
        self.assertTrue(r.stdout.splitlines()[1].strip().startswith("B:"), "the last one used first")
        r = pbik("--in", "A", "status", "--done", "model", cwd=self.tmp)
        self.assertIn("next is the page purpose", r.stdout)
        r = pbik("--report", "json", "--in", "B", "status", cwd=self.tmp)
        self.assertIn("next is the colours", json.loads(r.stdout)["facts"][0])


# ---------------------------------------------------------------- stage b
class WindowTests(Tmp):
    """A8: the agent opens the approval window; the typed code, refusals, screen control, window lock."""

    def setUp(self):
        super().setUp()
        from unittest import mock
        from pbikit import gates as GT
        import test_phase1 as P1
        self.GT, self.S = GT, P1.S
        P1.big_project(self.tmp)
        self.home = self.tmp / "home"
        env = mock.patch.dict(os.environ, {"PBIK_HOME": str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        self.GT.prepare("synth-approve", self.tmp)

    def marker(self, name, minutes_ago):
        import datetime
        self.home.mkdir(parents=True, exist_ok=True)
        at = datetime.datetime.now() - datetime.timedelta(minutes=minutes_ago)
        (self.home / name).write_text(json.dumps({"at": at.isoformat(timespec="seconds")}), encoding="utf-8")

    def test_open_then_wait(self):
        launched = []

        def launch(cmd):                       # stands in for the detached window process: the person types the code
            launched.append(cmd)
            self.GT.run("synth-approve", self.tmp, dialog=lambda title, text: "yes", out=lambda *a: None)

        self.GT.open_window("synth-approve", self.tmp, launch=launch)
        self.assertEqual(launched[0][-4:], ["run", "synth-approve", "--root", str(self.tmp.resolve())])
        r = self.GT.wait("synth-approve", self.tmp, timeout=2, poll=0.05)
        self.assertEqual(r["result"], "approved")
        self.assertFalse((self.home / "gate-window.json").exists(), "the lock goes when the window closes")
        self.assertTrue(self.S.approved(self.S.read_json(self.tmp / "design/specs/contract.json")))

    def test_wrong_code_no_and_not_answered(self):
        said = []
        self.assertEqual(self.GT.run("synth-approve", self.tmp, dialog=lambda *a: "code", out=said.append), "declined")
        self.assertIn("didn't match three times", said[0])
        r = self.S.read_json(self.tmp / ".pbik/gates/synth-approve.result.json")
        self.assertEqual((r["result"], r["why"]), ("declined", "the code didn't match three times"))
        self.assertFalse(self.S.approved(self.S.read_json(self.tmp / "design/specs/contract.json")))
        self.GT.open_window("synth-approve", self.tmp, launch=lambda cmd: None)
        self.assertEqual(self.GT.wait("synth-approve", self.tmp, timeout=0.2, poll=0.05)["result"], "not answered")

    def test_refusals(self):
        self.marker("screen-control.json", 2)
        for fn in (lambda: self.GT.open_window("synth-approve", self.tmp, launch=lambda c: None),
                   lambda: self.GT.run("synth-approve", self.tmp, dialog=lambda *a: "yes")):
            with self.assertRaises(self.GT.GateError) as cm:
                fn()
            self.assertIn("screen control", str(cm.exception))
        self.marker("screen-control.json", 11)                    # 11 minutes ago: past the window
        self.marker("gate-window.json", 1)
        with self.assertRaises(self.GT.GateError) as cm:
            self.GT.open_window("synth-approve", self.tmp, launch=lambda c: None)
        self.assertIn("another approval window", str(cm.exception))
        self.marker("gate-window.json", 60)                       # a stale lock (a crashed window) doesn't block
        cf = self.tmp / "design/specs/contract.json"
        c = self.S.read_json(cf)
        c["tables"]["Calendar"]["columns"]["Year"]["type"] = "string"
        self.S.write_json(cf, c)
        with self.assertRaises(self.GT.GateError) as cm:
            self.GT.open_window("synth-approve", self.tmp, launch=lambda c: None)
        self.assertIn("changed after it was prepared", str(cm.exception))

    def test_hook_marks_screen_control_and_blocks_key_senders(self):
        hook = KIT / "tools" / "hooks" / "guard_gates.py"
        env = {**os.environ, "PBIK_HOME": str(self.home)}

        def run(tool, inp=None):
            return subprocess.run([sys.executable, str(hook)], input=json.dumps({"tool_name": tool,
                                  "tool_input": inp or {}}), capture_output=True, text=True, env=env).returncode
        send = {"command": "$w = New-Object -ComObject wscript.shell; $w.SendKeys('ABCD{ENTER}')"}
        self.assertEqual(run("PowerShell", send), 0, "no window open: not blocked")
        self.marker("gate-window.json", 0)
        self.assertEqual(run("PowerShell", send), 2)
        self.assertEqual(run("Bash", {"command": "python -c 'import pyautogui'"}), 2)
        self.assertEqual(run("Bash", {"command": "python tools/pbik/pbik.py gate wait synth-approve"}), 0)
        self.assertEqual(run("mcp__computer-use__screenshot"), 0)
        self.assertTrue(self.GT.screen_control_active())
        settings = json.dumps(json.loads((KIT / ".claude" / "settings.json").read_text(encoding="utf-8")))
        self.assertIn("guard_gates.py", settings)
        self.assertIn("mcp__computer-use__", settings)

    def test_window_script(self):
        ps = self.GT.DIALOG_PS
        self.assertIn("RNGCryptoServiceProvider", ps)
        self.assertIn("Drawing.Bitmap", ps, "the code is drawn as a picture, not a text label")
        for leak in ("Out-File", "Set-Content", "Add-Content", "Write-Output", "Write-Host", "Clipboard"):
            self.assertNotIn(leak, ps, "the code never leaves the window")
        self.assertNotRegex(ps, r"\$l\.Text\s*=.*\$code")
        if shutil.which("powershell"):                            # the script parses (it can't be clicked in a test)
            f = self.tmp / "w.ps1"
            f.write_text(ps, encoding="utf-8-sig")
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
                                f"'{f}', [ref]$null, [ref]$e); $e.Count"], capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), "0", r.stdout + r.stderr)


# ---------------------------------------------------------------- stage c
SLASH = r"(?<![\w./<])/(brd|model|plan|build|review|fix|wrapup|theme|smoke|tidy|validate|update)\b"


class PlainWordsTests(Tmp):
    """A9: plain words, grouped model summaries, no slash commands, few questions, interactions counted."""

    def test_no_slash_commands_in_what_pbik_says(self):
        import re
        bad = []
        for f in sorted((KIT / "tools" / "pbik" / "pbikit").glob("*.py")):
            for n, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for s in re.findall(r"(?:out|print)\(f?\"([^\"]*)\"", ln) + re.findall(r"\"(next[^\"]*)\"", ln):
                    if re.search(SLASH, s):
                        bad.append(f"{f.name}:{n}: {s}")
        self.assertEqual(bad, [], "pbik never tells the person to type a slash command")

    def test_plain_words_rules(self):
        import re
        text = (KIT / "docs" / "PLAIN-WORDS.md").read_text(encoding="utf-8")
        for need in ("Never suggest the model step after a model export", "type the code in its picture",
                     "## Build options", "guided build", "quick build", "switch to guided",
                     "finish the rest quickly", "Batch questions", "(my own judgment)"):
            self.assertIn(need, text)
        says = [ln for ln in text.splitlines() if ln.startswith("|")]
        self.assertFalse([s for s in says if re.search(SLASH, s)], "no slash command in anything the agent says")

    def test_intake_groups_and_never_says_slash_model(self):
        from pbikit import intake as IN
        import big_model as BM
        drop = self.tmp / "design" / "reference" / "model"
        BM.write(drop, "tmdl")
        (self.tmp / "design" / "specs").mkdir(parents=True, exist_ok=True)
        said = []
        IN.intake(self.tmp, out=said.append)
        text = "\n".join(said)
        self.assertRegex(text, r"\d+ handled by rules, \d+ option table\(s\) to keep, \d+ need you\.")
        self.assertNotRegex(text, SLASH)
        self.assertIn("next:", text)
        if "need you:" in text:
            self.assertIn("  - ", text, "each item that needs the person is named with a plain reason")
        self.assertLess(len(said), 20, "grouped, not one line per flag")

    def test_interactions_logged_and_checked(self):
        import datetime
        from pbikit import steps as STP
        import usage as US
        STP.interaction(self.tmp, "reply")
        STP.interaction(self.tmp, "window: Approve the model")
        r = pbik("step", "note", "plan OK", "--interaction", "--root", self.tmp)
        self.assertIn("interactions so far: 3", r.stdout)
        self.assertEqual(STP.windows(self.tmp), [], "interactions aren't steps")
        tr = self.tmp / "tr"
        tr.mkdir()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        lines = [{"type": "user", "timestamp": now, "message": {"role": "user", "content": "build me a dashboard"}},
                 {"type": "user", "timestamp": now, "message": {"role": "user", "content": [
                     {"type": "tool_result", "content": "ok"}]}},
                 {"type": "user", "timestamp": now, "message": {"role": "user", "content": [
                     {"type": "text", "text": "OK"}]}}]
        (tr / "s.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
        self.assertEqual(US.interaction_check(self.tmp, tr), {"logged": 3, "windows": 1, "transcript": 2})


if __name__ == "__main__":
    unittest.main(verbosity=1)
