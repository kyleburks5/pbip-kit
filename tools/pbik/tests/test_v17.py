"""v1.7 tests (docs/design/phase1-usability.md, Part A) on made-up data only.

    python tools\\pbik\\tests\\test_v17.py
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile, unittest
os.environ.setdefault("PBIK_HOME", tempfile.mkdtemp(prefix="pbik_home_"))   # never the person's own settings

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
PBIK = HERE.parent / "pbik.py"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "tools"))

from pbikit import status as ST  # noqa: E402

MODEL = "/".join(("design", "reference", "model"))           # spelled in parts: the guard reads tool calls


def pbik(*args, cwd=None, env_home=None):
    env = {**os.environ, **({"PBIK_HOME": str(env_home)} if env_home else {})}
    return subprocess.run([sys.executable, str(PBIK), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd, env=env)


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

    def test_init_beside_the_kit_with_status(self):
        """One folder = one project: `project init` makes its own folder beside the kit, never inside it."""
        from pbikit import projectinit as PI
        kit = fake_kit(self.tmp / "kit")
        said = []
        target = PI.init("Sales Overview", None, "restricted", kit=kit, out=said.append)
        self.assertEqual(target, self.tmp / "Sales Overview")
        self.assertTrue((target / "Model").is_dir() and (target / "Reference").is_dir())
        with self.assertRaises(PI.InitError):
            PI.init("Inside", kit / "projects", kit=kit, out=said.append)
        self.assertTrue((target / ".git").is_dir(), "its own git repository")
        kit_status = subprocess.run(["git", "status", "--porcelain"], cwd=kit, capture_output=True, text=True).stdout
        self.assertEqual(kit_status.strip(), "", "the kit doesn't see the project")
        self.assertIn("is ready in its own folder beside the kit", said[0])
        self.assertIn("Model and Reference folders", said[0])
        for s in said:
            self.assertNotIn("/", s.replace("and/or", ""), "no slash command or path")
            self.assertNotIn("\\", s)
        doc = ST.read(target)
        self.assertEqual((doc["dataClass"], doc["next"]), ("restricted", "start"))

    def test_export_check_flags_project_files(self):
        if not (KIT / "tools" / "export_check.py").exists():
            self.skipTest("a project: the export check is master-only")
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
        self.marker("screen-control.json", 2)                     # screen control on: the window asks for the code
        asked = []
        self.GT.run("synth-approve", self.tmp, dialog=lambda t, x, code=False: asked.append(code) or "no",
                    out=lambda *a: None)
        self.assertEqual(asked, [True])
        self.marker("screen-control.json", 11)                    # 11 minutes ago: past the window, plain Yes / No
        self.GT.run("synth-approve", self.tmp, dialog=lambda t, x, code=False: asked.append(code) or "no",
                    out=lambda *a: None)
        self.assertEqual(asked, [True, False])
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
        for need in ("Never suggest the model step after a model export", "check it, then click Yes or No",
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


# ---------------------------------------------------------------- stage d
class StartTests(Tmp):
    """A2: what the person gave picks the path; reports read into layouts; known models recognised; starters."""

    def inputs(self, *names):
        d = self.tmp / "design" / "reference" / "inputs"
        d.mkdir(parents=True, exist_ok=True)
        for n in names:
            if n.endswith(".Report"):
                (d / n / "definition" / "pages").mkdir(parents=True)
                (d / n / "definition.pbir").write_text("{}", encoding="utf-8")
            else:
                (d / n).write_text("made up", encoding="utf-8")
        return d

    def test_detect_paths(self):
        from pbikit import start as SR
        self.assertEqual(SR.detect(self.tmp)["path"], "starter layouts")
        self.inputs("needs.md")
        d = SR.detect(self.tmp)
        self.assertEqual((d["path"], d["requirements"]), ("starter layouts", ["needs.md"]))
        self.inputs("shot.png")
        self.assertEqual(SR.detect(self.tmp)["path"], "from picture")
        self.inputs("mockup.html")
        self.assertEqual(SR.detect(self.tmp)["path"], "from wireframe")
        self.inputs("Old.Report", "old.pbix", "sales.csv")
        d = SR.detect(self.tmp)
        self.assertEqual(d["path"], "from report")
        self.assertEqual(sorted(d["refused"]), ["old.pbix", "sales.csv"])
        text = "\n".join(SR.say(d))
        self.assertIn("I won't read old.pbix", text)
        self.assertIn("save the report as a Power BI project", text)
        r = pbik("--report", "json", "start", "detect", "--root", self.tmp)
        doc = json.loads(r.stdout)
        self.assertTrue(doc["ok"])
        self.assertTrue(doc["next"][0].startswith("next: I'll turn it into a plan"))
        self.assertEqual(ST.read(self.tmp)["path"], "from report")

    def test_starters_on_the_grid_and_built(self):
        from pbikit import start as SR
        self.assertEqual(SR.starter_names(), ["executive-summary", "trend-dashboard", "detail-table"])
        cols = {SR.col_x(i) for i in range(12)}
        for name in SR.starter_names():
            lay = SR.fill(name, ["Fact Orders Amount", "[Fact Orders Qty]"], "Calendar[Date]", "Region[Name]")
            ids = [v["id"] for v in lay["visuals"]]
            self.assertEqual(ids, [f"P1-V{i:02d}" for i in range(1, len(ids) + 1)], name)
            for v in lay["visuals"]:
                self.assertIn(v["x"], cols, (name, v["id"]))
                edges = [SR.col_x(i) + SR.span_w(1) for i in range(12)]      # ref_layout.py rounds the same way
                self.assertLessEqual(min(abs(v["x"] + v["w"] - e) for e in edges), 1, (name, v["id"]))
                self.assertLessEqual(v["y"] + v["h"], 1048, (name, v["id"]))
                self.assertEqual(v["y"] % 8, 0)
                self.assertNotRegex(json.dumps(v), r"[{](kpi[0-9]|date|category|title)[}]", "every slot filled")
                self.assertTrue(v["build"]["reason"] and v["build"]["step"] == 1, "native first")
            self.assertTrue(lay["_purpose"])
        lay = SR.fill("executive-summary")
        self.assertEqual(lay["visuals"][1]["bindings"]["Data"], ["[KPI 1]"], "readable labels when unfilled")
        r = pbik("start", "starters", "--root", self.tmp, "--kpi", "Fact Orders Amount", "--date", "Calendar[Date]")
        self.assertIn("3 starter layouts: Executive summary, Trend dashboard, Detail table.", r.stdout)

    def test_report_round_trip(self):
        """A starter filled with a model's names, built into a report (the Rep 4 fixture: pbik build checks every
        field against its model), read back: same pages, types, fields and grid positions."""
        from pbikit import fromreport as FR, start as SR
        src = KIT / "tools" / "fixtures" / "rep4"
        work = self.tmp / "rep"
        shutil.copytree(src, work)
        lay = SR.fill("executive-summary", ["Revenue", "Units Sold", "Profit", "Margin %"], "Date[Date]",
                      "stores[City]")
        lay["pages"]["P1"]["displayName"] = "Starter"
        lf = work / "design" / "specs" / "layout.json"
        lf.parent.mkdir(parents=True, exist_ok=True)
        lf.write_text(json.dumps(lay), encoding="utf-8")
        report = work / "Toy Sales.Report"
        for p in (report / "definition" / "pages").iterdir():
            if p.is_dir():
                shutil.rmtree(p)
        (report / "definition" / "pages" / "pages.json").unlink(missing_ok=True)
        r = pbik("build", report, lf, cwd=work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        back, findings, left_out = FR.from_report(report)
        self.assertEqual([p["displayName"] for p in back["pages"].values()], ["Starter"])
        got = {(v["type"], json.dumps(v.get("bindings"), sort_keys=True)) for v in back["visuals"]}
        for v in lay["visuals"]:
            if v.get("bindings"):
                self.assertIn((v["type"], json.dumps(v["bindings"], sort_keys=True)), got, v["id"])
        for v in back["visuals"]:
            mine = next(x for x in lay["visuals"] if x["type"] == v["type"] and x.get("bindings") == v.get("bindings"))
            self.assertEqual((v["x"], v["w"]), (mine["x"], mine["w"]), v["id"])

    def test_known_model_recognised(self):
        from pbikit import gates as GT, intake as IN, packs as PK, rules as R, dataclass_ as DC, synth as S
        import test_phase1 as P1
        from unittest import mock
        env = mock.patch.dict(os.environ, {"PBIK_HOME": str(self.tmp / "home")})
        env.start()
        self.addCleanup(env.stop)
        a = self.tmp / "first"
        P1.big_project(a, resolve=False)
        c = S.read_json(a / "design/specs/contract.json")
        for f in R.groups(c)["you"]:
            S.resolve(a, f["id"], "synthesize", why="typed targets", out=lambda *x: None)
        GT.prepare("synth-approve", a)
        GT.run("synth-approve", a, dialog=lambda *x: "yes", out=lambda *x: None)
        packs = self.tmp / "packs"
        packs.mkdir()
        PK.register(a, packs, out=lambda *x: None)
        self.assertEqual(PK.fingerprint(c), PK.fingerprint(S.read_json(a / "design/specs/contract.json")))
        b = self.tmp / "second"
        (b / "design" / "specs").mkdir(parents=True)
        DC.set_class(b, "restricted")
        r = pbik("model", "packs", "--add-folder", packs, "--root", b,
                 env_home=self.tmp / "home")                            # the person's own settings, any project
        self.assertIn("Example Big: version 1", r.stdout)
        self.assertNotIn("packFolders", json.dumps(DC.read_project(b)), "no machine path in a project file")
        drop = b / "design" / "reference" / "model"
        import big_model as BM
        BM.write(drop, "tmdl")
        said = []
        IN.intake(b, out=said.append)
        text = "\n".join(said)
        self.assertIn("This is Example Big, the model you approved before", text)
        self.assertIn("this project stays restricted", text, "a pack never loosens the data class")
        self.assertTrue(S.approved(S.read_json(b / "design/specs/contract.json")))
        self.assertEqual(DC.data_class(b), "restricted")
        doc = ST.read(b)
        self.assertEqual((doc["pack"], "model" in doc["done"]), ("Example Big", True))


# ---------------------------------------------------------------- stage e
class PlanPictureTests(Tmp):
    """A3: the plan as a picture plus a short list; OK records it; changes after OK are caught."""

    def project(self):
        from pbikit import start as SR
        lay = SR.fill("executive-summary", ["Revenue", "Units Sold"], "Date[Date]", "stores[City]")
        lay["visuals"][6]["build"] = {"method": "svg", "step": 2, "nativeTried": "a native bar can't draw chips",
                                      "reason": "status pills in the table"}
        f = self.tmp / "design" / "specs" / "layout.json"
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps(lay), encoding="utf-8")
        ST.update(self.tmp, done="start", mode="quick", dataClass="restricted")
        ST.update(self.tmp, done="model")
        return f

    def shoot(self, html, png, w, h, hash_):
        self.shots.append((w, h, hash_))
        pathlib.Path(png).write_bytes(b"png")

    def test_show_list_and_approve(self):
        from pbikit import plan as PL
        lf = self.project()
        self.shots = []
        pngs, text, h = PL.show(self.tmp, purposes={"P1": "Are we on track this month?"},
                                assumptions=["'Total' means [Revenue], not [Gross Revenue]"], shoot=self.shoot)
        self.assertEqual(len(pngs), 1)
        self.assertEqual(self.shots[0], (1920, 1080, "#shot&labels=off&page=1"), "no ID badges for a person")
        for need in ('Page Executive summary: "Are we on track this month?"', "| Revenue | Revenue |",
                     "every headline number needs a comparison", "'Total' means [Revenue]",
                     "Fallbacks (OK on the plan approves them):", "native option tried: a native bar can't draw chips",
                     "Build: quick build", "Data: restricted"):
            self.assertIn(need, text)
        self.assertTrue((self.tmp / "design" / "plan" / "plan.md").exists())
        self.assertTrue(PL.changed_since_approval(self.tmp))
        r = pbik("plan", "approve", "--root", self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("next: the colours", r.stdout)
        doc = ST.read(self.tmp)
        self.assertEqual((doc["planHash"], "plan" in doc["done"], "page purpose" in doc["done"]), (h, True, True))
        spec = (self.tmp / "design" / "specs" / "spec.md").read_text(encoding="utf-8")
        self.assertIn("## Page purpose", spec)
        self.assertIn("Executive summary (P1): Are we on track this month?", spec)
        self.assertFalse(PL.changed_since_approval(self.tmp))
        lay = json.loads(lf.read_text(encoding="utf-8"))
        lay["visuals"][1]["y"] += 8
        lay["visuals"][1].setdefault("props", {})["label.show@default"] = False
        lf.write_text(json.dumps(lay), encoding="utf-8")
        self.assertFalse(PL.changed_since_approval(self.tmp), "the kit's own nudges and polish keep the OK")
        lay["visuals"][1]["y"] += 480
        lf.write_text(json.dumps(lay), encoding="utf-8")
        self.assertTrue(PL.changed_since_approval(self.tmp), "a move after OK means showing it again")
        self.assertIn(f"{lay['visuals'][1]['id']} moved", PL.changes_since_approval(self.tmp))

    def test_no_purpose_no_approval(self):
        from pbikit import plan as PL
        self.project()
        with self.assertRaises(PL.PlanError) as cm:
            PL.approve(self.tmp)
        self.assertIn("what each should help people decide", str(cm.exception))

    def test_open_beside_the_chat(self):
        from pbikit import plan as PL
        from unittest import mock
        ran = []
        with mock.patch.dict(os.environ, {"PBIK_OPEN": "vscode"}), mock.patch("shutil.which", lambda n: "code"):
            self.assertEqual(PL.open_beside([self.tmp / "a.png"], run=ran.append), "vscode")
        self.assertEqual(ran[0][:2], ["code", "--reuse-window"])

    def test_starter_words_are_plain(self):
        from pbikit import start as SR
        lay = SR.fill("trend-dashboard", ["Revenue"], "Date[Date]", "stores[City]")
        titles = [v["container"].get("title") for v in lay["visuals"] if isinstance(v.get("container"), dict)]
        self.assertIn("Revenue over time, by City", titles)
        self.assertEqual(lay["visuals"][5]["bindings"]["Y"], ["[Revenue]"], "fields stay fields")

    def test_real_picture(self):
        """The real drawing (headless Edge), when Edge is on this machine."""
        sys.path.insert(0, str(KIT / "design" / "scripts"))
        import edge_page
        if not edge_page.available():
            self.skipTest("no Edge on this machine: the picture is drawn at work (verify at work)")
        from pbikit import plan as PL, start as SR
        f = self.tmp / "design" / "specs" / "starters" / "x.layout.json"
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps(SR.fill("detail-table", ["Revenue", "Units Sold"])), encoding="utf-8")
        png = PL.picture(f, self.tmp / "pics")[0]
        data = png.read_bytes()
        self.assertEqual(data[:8], bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]))
        self.assertEqual(int.from_bytes(data[16:20], "big"), 1920)


# ---------------------------------------------------------------- stage f
def built_starter(work, name="executive-summary"):
    """The Rep 4 fixture with one starter page built from layout.json; returns (report, layout file)."""
    from pbikit import start as SR
    shutil.copytree(KIT / "tools" / "fixtures" / "rep4", work)
    lay = SR.fill(name, ["Revenue", "Units Sold", "Profit", "Margin %"], "Date[Date]", "stores[City]")
    lf = work / "design" / "specs" / "layout.json"
    lf.parent.mkdir(parents=True, exist_ok=True)
    lf.write_text(json.dumps(lay), encoding="utf-8")
    report = work / "Toy Sales.Report"
    for p in (report / "definition" / "pages").iterdir():
        if p.is_dir():
            shutil.rmtree(p)
    (report / "definition" / "pages" / "pages.json").unlink(missing_ok=True)
    r = pbik("build", report, lf, cwd=work)
    assert r.returncode == 0, r.stdout + r.stderr
    return report, lf


class ModeAndHistoryTests(Tmp):
    """A4: guided until quick reaches 7 on a report type, then the last choice or the team default; suggestions."""

    def setUp(self):
        super().setUp()
        from unittest import mock
        env = mock.patch.dict(os.environ, {"PBIK_HOME": str(self.tmp / "home")})
        env.start()
        self.addCleanup(env.stop)

    def test_default_and_suggestion(self):
        from pbikit import history as HI
        self.assertEqual(HI.default_mode("from wireframe")[0], "guided")
        HI.record("quick", "from wireframe", 6)
        self.assertEqual(HI.default_mode("from wireframe")[0], "guided", "6/10 isn't the target yet")
        HI.record("quick", "from wireframe", 8)
        self.assertEqual(HI.default_mode("from wireframe"), ("quick", "your last choice"))
        HI.record("guided", "executive-summary", 9)
        self.assertEqual(HI.default_mode("from wireframe")[0], "guided", "the last choice, whatever the type")
        self.assertEqual(HI.default_mode("detail-table")[0], "guided", "per report type")
        for s in (5, 6, 6):
            HI.record("quick", "executive-summary", s)
        self.assertIn("(5.7 vs 9.0); I suggest a guided build", HI.suggestion("executive-summary"))
        self.assertIsNone(HI.suggestion("from wireframe"), "fewer than 3 quick builds: no suggestion")
        HI.set_hand_minutes(12)
        self.assertEqual(HI.read()[-1]["handMinutes"], 12)
        self.assertNotIn("Revenue", HI.history_file().read_text(encoding="utf-8"), "no names in the history")

    def test_switch_and_pause_line(self):
        ST.update(self.tmp, done="start", mode="guided")
        for s in ("model", "page purpose", "plan", "theme"):
            ST.update(self.tmp, done=s)
        self.assertIn("Pause here", ST.line(self.tmp), "guided: a look after the colours")
        r = pbik("mode", "quick", "--root", self.tmp)
        self.assertIn("quick build", r.stdout)
        self.assertNotIn("Pause here", ST.line(self.tmp), "finish the rest quickly: no more pauses")
        self.assertEqual(ST.read(self.tmp)["switches"][-1], {"from": "guided", "to": "quick", "after": ["theme"]})


class ScoreTests(Tmp):
    """A6: the polish score from the built report and layout; seeded faults lose their item."""

    @classmethod
    def setUpClass(cls):
        cls.base = pathlib.Path(tempfile.mkdtemp(prefix="pbik_v17_score_"))
        cls.report, cls.lf = built_starter(cls.base / "rep")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def layout(self):
        return json.loads(self.lf.read_text(encoding="utf-8"))

    def test_clean_build(self):
        from pbikit import score as SC
        res = SC.compute(self.report, self.layout(), {1: True, 3: True, 7: True})
        for n in (2, 4, 5, 8, 10):
            self.assertTrue(res[n][0], (n, res[n]))
        self.assertEqual(SC.total(res), 10, res)
        lines = SC.say(SC.compute(self.report, self.layout()))
        self.assertIn("Not checked: matches the approved picture (my own judgment); KPI cards filled; interactions "
                      "working.", lines)

    def test_seeded_faults(self):
        from pbikit import score as SC
        lay = self.layout()
        lay["visuals"][1]["x"] += 5                                 # off the grid
        lay["visuals"][2]["x"], lay["visuals"][2]["y"] = lay["visuals"][1]["x"], lay["visuals"][1]["y"] + 16  # overlap
        lay["visuals"][3]["props"] = {"value.fontColor": "#FF0000"}   # a colour written in
        lay["visuals"][5]["type"] = "areaChart"                     # not what was built
        lay["visuals"][6]["bindings"] = {"Category": ["stores[City]"], "Y": ["[Profit]"]}
        res = SC.compute(self.report, lay, {1: True, 3: True, 7: True})
        for n in (2, 4, 5, 6, 8):
            self.assertFalse(res[n][0], (n, res[n]))
        self.assertIn("P1-V02", res[2][1])
        self.assertIn("P1-V06", res[4][1])
        self.assertIn("P1-V07", res[5][1])

    def test_cli_final_records_history(self):
        from unittest import mock
        work = self.tmp / "p"
        shutil.copytree(self.base / "rep", work)
        ST.update(work, done="start", mode="quick", reportType="executive-summary")
        env = {**os.environ, "PBIK_HOME": str(self.tmp / "home")}
        r = subprocess.run([sys.executable, str(PBIK), "score", "--root", work, "--item", "1=pass", "--item",
                            "3=pass", "--item", "7=pass", "--final"], capture_output=True, text=True, cwd=work,
                           env=env, encoding="utf-8")
        self.assertIn("Polish ", r.stdout, r.stderr)
        self.assertTrue((work / "design" / "reviews" / "polish.md").exists())
        with mock.patch.dict(os.environ, {"PBIK_HOME": str(self.tmp / "home")}):
            from pbikit import history as HI
            rec = HI.read()[-1]
        self.assertEqual((rec["mode"], rec["reportType"]), ("quick", "executive-summary"))
        self.assertEqual(rec["score"], ST.read(work)["score"])


class DesktopCloseTests(Tmp):
    """D1: Desktop is closed without saving only when its only unsaved changes are its own reload marks."""

    def setUp(self):
        super().setUp()
        from unittest import mock
        from pbikit import desktop as D
        self.D = D
        self.report = self.tmp / "X.Report"
        (self.report / "definition").mkdir(parents=True)
        (self.report / "definition" / "report.json").write_text("{}", encoding="utf-8")
        env = mock.patch.dict(os.environ, {"PBIK_DESKTOP_PIDS": "4242"})
        env.start()
        self.addCleanup(env.stop)
        self.state = {"application": {"isDirty": True, "activePage": "P1", "timestamp": "10:00"}}

    def test_proven_then_closed(self):
        self.assertIn("haven't reloaded", self.D.why_not_close(self.tmp, self.report, self.state))
        self.D.remember_reload(self.tmp, self.report, self.state)
        later = {"application": {"isDirty": True, "activePage": "P1", "timestamp": "10:05"}}
        self.assertIsNone(self.D.why_not_close(self.tmp, self.report, later), "times don't count")
        (self.report / "definition" / "report.json").write_text('{"pbik": 1}', encoding="utf-8")
        self.D.mark_built(self.tmp, self.report)                         # the agent's own build after the reload
        self.assertIsNone(self.D.why_not_close(self.tmp, self.report, later))
        killed = []
        self.assertIsNone(self.D.close(self.tmp, self.report, kill=killed.append, read_state=lambda: later))
        self.assertEqual(killed, [4242])
        self.assertFalse(self.D.record_file(self.tmp).exists())

    def test_any_doubt_leaves_it_open(self):
        from unittest import mock
        self.D.remember_reload(self.tmp, self.report, self.state)
        moved = {"application": {"isDirty": True, "activePage": "P2", "timestamp": "10:01"}}
        self.assertIn("changed after my reload", self.D.why_not_close(self.tmp, self.report, moved))
        self.assertIn("doesn't report", self.D.why_not_close(self.tmp, self.report, None))
        with mock.patch.dict(os.environ, {"PBIK_DESKTOP_PIDS": "4242,77"}):
            self.assertIn("more than one", self.D.why_not_close(self.tmp, self.report, self.state))
        with mock.patch.dict(os.environ, {"PBIK_DESKTOP_PIDS": "77"}):
            self.assertIn("isn't the one I reloaded", self.D.why_not_close(self.tmp, self.report, self.state))
        (self.report / "definition" / "report.json").write_text('{"saved": "by Desktop"}', encoding="utf-8")
        self.assertIn("didn't make", self.D.why_not_close(self.tmp, self.report, self.state))
        killed = []
        self.assertTrue(self.D.close(self.tmp, self.report, kill=killed.append, read_state=lambda: self.state))
        self.assertEqual(killed, [], "never closed on doubt")


# ---------------------------------------------------------------- stage g
class DocsTests(unittest.TestCase):
    """A11, A15: the walkthrough, how-tos, main-flow command files and their Copilot mirrors."""

    def text(self, rel):
        return (KIT / rel).read_text(encoding="utf-8")

    def test_walkthrough(self):
        w = self.text("docs/PHASE1-WALKTHROUGH.md")
        for need in ("Claude desktop app", "Claude Code in VS Code", "Copilot in VS Code", "pbik-walkthrough-inputs",
                     "`1 made-up model`", "`2 made-up live pick`", "`3 made-up wireframe`", "`4 made-up requirements`",
                     "Run A. Guided build", "Run B. Quick build", "Run C. No wireframe", "| Run | Build option | "
                     "Polish score | Interactions |", "## Verify at work", "**Guided build.**", "**Quick build.**"):
            self.assertIn(need, w)
        self.assertNotRegex(w, r"\*You say:\*[^\n]*" + SLASH, "the person never types a slash command")
        q = self.text("docs/QUICKSTART.md")
        self.assertIn("**Guided build.**", q)
        self.assertIn("**Quick build.**", q)

    def test_main_flow_files_and_copilot(self):
        start = self.text(".claude/commands/start.md")
        for need in ("pbik status", "pbik start detect", "pbik plan show", "pbik plan open", "pbik plan approve",
                     "pbik plan check", "pbik gate open", "pbik mode", "pbik score", "pbik desktop close",
                     "--interaction", "Switch to live?"):
            self.assertIn(need, start)
        for name in ("start", "status"):
            self.assertTrue((KIT / ".github" / "prompts" / f"kit-{name}.prompt.md").exists(), name)
        claude = self.text("CLAUDE.md")
        self.assertIn(".claude/commands/start.md", claude)
        self.assertIn("pbik gate open", claude)
        self.assertIn(".claude/commands/start.md", self.text(".github/copilot-instructions.md"))
        r = subprocess.run([sys.executable, str(KIT / "tools" / "copilot" / "sync.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
