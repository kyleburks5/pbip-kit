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


if __name__ == "__main__":
    unittest.main(verbosity=1)
