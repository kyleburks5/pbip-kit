"""Phase 1 usability tests (docs/design/phase1-usability.md) on made-up data only.

    python tools\\pbik\\tests\\test_phase1.py
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile, unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
PBIK = HERE.parent / "pbik.py"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import big_model as BM  # noqa: E402
from pbikit import dataclass_ as DC, summary as SM, synth as S  # noqa: E402


def pbik(*args, cwd=None):
    return subprocess.run([sys.executable, str(PBIK), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_p1_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class SummaryTests(Tmp):
    """Stage (a): `pbik --report json` gives facts, needs (errors, warnings, gates by task name) and next steps."""

    def test_classify(self):
        facts, needs, nxt = SM.classify([
            "contract.json: 7 table(s)", "warning catalog: something odd", "error   a field is missing",
            "stale reference x.json: Orders[Old]", "Approval cleared: a person runs `pbik synth approve --by <name>`",
            "Next: python make_smoke.py build"])
        self.assertIn("contract.json: 7 table(s)", facts)
        self.assertEqual([n["kind"] for n in needs if n["kind"] != "gate"], ["warning", "error", "error"])
        self.assertIn({"kind": "gate", "gate": "synth-approve", "task": "Approve the model"}, needs)
        self.assertEqual(nxt, ["Next: python make_smoke.py build"])

    def test_cli_json(self):
        r = pbik("--report", "json", "project", "class", "--root", self.tmp)
        doc = json.loads(r.stdout)
        self.assertEqual((doc["ok"], doc["command"], doc["facts"]), (True, "project class", ["data class: internal"]))
        r = pbik("--report", "json", "synth", "approve", "--by", "x", "--root", self.tmp)
        doc = json.loads(r.stdout)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["needs"][0]["kind"], "error")

    def test_plain_words_cover_every_flag_kind_and_gate(self):
        text = (KIT / "docs" / "PLAIN-WORDS.md").read_text(encoding="utf-8")
        for kind in S.RESOLUTIONS:
            self.assertIn(f"| `{kind}` |", text, kind)
        for gate, (task, _) in SM.GATES.items():
            self.assertIn(f"| `{gate}` | {task} |", text, gate)
        claude = (KIT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("never\n  show me a path or a command", claude)


class ProjectInitTests(Tmp):
    """Stage (a): `pbik project init` copies the kit, sets the data class and starts git with a first commit."""

    def test_init(self):
        from pbikit import projectinit as PI
        said = []
        target = PI.init("Sample Dashboard", self.tmp, "restricted", out=said.append)
        self.assertTrue((target / "CLAUDE.md").exists())
        self.assertTrue((target / "tools" / "pbik" / "pbik.py").exists())
        self.assertEqual(DC.data_class(target), "restricted")
        log = subprocess.run(["git", "log", "--oneline"], cwd=target, capture_output=True, text=True).stdout
        self.assertIn("project start: Sample Dashboard", log)
        self.assertIn("is ready", said[0])
        with self.assertRaises(PI.InitError):
            PI.init("Sample Dashboard", self.tmp, out=said.append)              # exists and isn't empty
        with self.assertRaises(PI.InitError):
            PI.init("///", self.tmp, out=said.append)


def big_project(root, resolve=True):
    """A project whose contract comes from the large made-up model (TMDL folder in root/src)."""
    (root / "design" / "specs").mkdir(parents=True, exist_ok=True)
    src = BM.write(root / "src", "tmdl")
    S.contract(src, root)
    if resolve:
        for kind, res in (("m-code", "synthesize"), ("connection", "synthesize"), ("entity", "synthesize"),
                          ("rls", "not reproduced"), ("enter-data", "synthesize")):
            S.resolve(root, kind, res, why="test rule", every=True, out=lambda *a: None)
    return src


class GateTests(Tmp):
    """Stage (b): gates prepared by the agent, run by the person through a Command Palette task and a dialog."""

    def setUp(self):
        super().setUp()
        from pbikit import gates as GT
        self.GT = GT
        big_project(self.tmp)
        self.shown = []

    def dialog(self, answer):
        def d(title, text):
            self.shown.append((title, text))
            return answer
        return d

    def test_synth_approve_through_the_gate(self):
        c = S.read_json(self.tmp / "design/specs/contract.json")
        opt = next(f["id"] for f in c["flags"] if f["table"] == "Option 03")
        S.resolve(self.tmp, opt, S.KEEP_ROWS, out=lambda *a: None)
        doc = self.GT.prepare("synth-approve", self.tmp)
        self.assertIn("61 tables, 400 measures", doc["summary"])
        self.assertIn("106 handled by rules, 1 option table(s) to keep", doc["summary"])
        self.assertNotIn("Choice 1", json.dumps(doc), "the agent's prepared file never holds the rows")
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), self.assertRaises(self.GT.GateError):
            self.GT.run("synth-approve", self.tmp, dialog=self.dialog(True))
        self.assertEqual(self.GT.run("synth-approve", self.tmp, dialog=self.dialog(True), person=True,
                                     out=lambda *a: None), "approved")
        self.assertEqual(self.shown[0][0], "Approve the model")
        self.assertIn("Option 03 keeps 6 row(s): Choice 1 | 1", self.shown[0][1])
        c = S.read_json(self.tmp / "design/specs/contract.json")
        self.assertTrue(S.approved(c))
        self.assertEqual(c["tables"]["Option 03"]["rows"]["rows"][0], ["Choice 1", 1])
        log = (self.tmp / "design/reviews/approvals.md").read_text(encoding="utf-8")
        self.assertIn("| Approve the model |", log)
        self.assertEqual(S.read_json(self.tmp / ".pbik/gates/synth-approve.result.json")["result"], "approved")

    def test_no_changed_and_unresolved(self):
        self.GT.prepare("synth-approve", self.tmp)
        self.assertEqual(self.GT.run("synth-approve", self.tmp, dialog=self.dialog(False), person=True,
                                     out=lambda *a: None), "declined")
        self.assertFalse(S.approved(S.read_json(self.tmp / "design/specs/contract.json")))
        cf = self.tmp / "design/specs/contract.json"
        c = S.read_json(cf)
        c["tables"]["Calendar"]["columns"]["Year"]["type"] = "string"
        S.write_json(cf, c)
        with self.assertRaises(self.GT.GateError) as cm:
            self.GT.run("synth-approve", self.tmp, dialog=self.dialog(True), person=True)
        self.assertIn("changed after it was prepared", str(cm.exception))
        c["flags"][0]["resolution"] = None
        S.write_json(cf, c)
        with self.assertRaises(self.GT.GateError) as cm:
            self.GT.prepare("synth-approve", self.tmp)
        self.assertIn("need a decision", str(cm.exception))

    def test_class_lower_and_tasks(self):
        DC.set_class(self.tmp, "restricted")
        with self.assertRaises(self.GT.GateError):
            self.GT.prepare("class-lower", self.tmp, to_class="restricted")
        self.GT.prepare("class-lower", self.tmp, to_class="internal")
        self.GT.run("class-lower", self.tmp, dialog=self.dialog(True), person=True, out=lambda *a: None)
        self.assertEqual(DC.data_class(self.tmp), "internal")
        tasks = json.loads((KIT / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual(tasks, self.GT.tasks_json(), "run `pbik gate tasks` after changing the gates")
        self.assertEqual([t["label"] for t in tasks["tasks"]], [t for t, _ in SM.GATES.values()])
        self.assertTrue(all(t["args"][-1] in SM.GATES for t in tasks["tasks"]))


class IntakeTests(Tmp):
    """Stage (c): the model drop folder: data files deleted before anything reads it, every format detected."""

    def drop(self):
        d = self.tmp / "design" / "reference" / "model"
        d.mkdir(parents=True)
        (self.tmp / "design" / "specs").mkdir(parents=True, exist_ok=True)
        return d

    def test_every_format(self):
        from pbikit import intake as IN
        for fmt, name in (("tmdl", "TMDL folder"), ("script", "TMDL script"), ("semanticmodel", "semantic model folder"),
                          ("tmsl", "TMSL export")):
            shutil.rmtree(self.tmp, ignore_errors=True)
            d = self.drop()
            BM.write(d, fmt)
            r = IN.intake(self.tmp, out=lambda *a: None)
            self.assertEqual(r["format"], name)
            self.assertEqual(len(r["contract"]["tables"]), 61, fmt)
            self.assertEqual((d / ".gitignore").read_text(encoding="utf-8").strip(), "*")

    def test_data_deleted_before_any_read(self):
        from pbikit import intake as IN
        d = self.drop()
        BM.write(d, "semanticmodel")
        (d / "Example Big.SemanticModel" / "data").mkdir()
        (d / "Example Big.SemanticModel" / "data" / "rows.parquet").write_bytes(b"PAR1")
        (d / "old report.pbix").write_bytes(b"PK made up")
        events = []
        real_unlink, real_read = pathlib.Path.unlink, pathlib.Path.read_text

        def unlink(p, *a, **k):
            events.append(("delete", p.name))
            return real_unlink(p, *a, **k)

        def read(p, *a, **k):
            events.append(("read", p.name))
            return real_read(p, *a, **k)
        said = []
        with mock.patch.object(pathlib.Path, "unlink", unlink), mock.patch.object(pathlib.Path, "read_text", read):
            r = IN.intake(self.tmp, out=said.append)
        self.assertEqual(sorted(r["removed"]), sorted(["Example Big.SemanticModel/.pbi/cache.abf",
                                                       "Example Big.SemanticModel/.pbi/localSettings.json",
                                                       "Example Big.SemanticModel/data/rows.parquet",
                                                       "old report.pbix"]))
        first_read = next(k for k, e in enumerate(events) if e[0] == "read")
        self.assertTrue(all(e[0] == "delete" for e in events[:first_read]))
        self.assertEqual(sum(1 for e in events[:first_read]), 4, "all four deleted before the first read")
        self.assertFalse((d / "Example Big.SemanticModel" / ".pbi").exists())
        self.assertIn("never your only file", said[0])
        log = (self.tmp / "design/reviews/model-intake.md").read_text(encoding="utf-8")
        self.assertIn("`old report.pbix`", log)

    def test_refusals(self):
        from pbikit import intake as IN
        d = self.drop()
        (d / "only.pbix").write_bytes(b"PK made up")
        with self.assertRaises(IN.IntakeError) as cm:
            IN.intake(self.tmp, out=lambda *a: None)
        self.assertIn("Power BI project", str(cm.exception))
        BM.write(d, "tmdl")
        BM.write(d, "tmsl")
        with self.assertRaises(IN.IntakeError):
            IN.intake(self.tmp, out=lambda *a: None)

    def test_hook_blocks_the_agent(self):
        hook = KIT / "tools" / "hooks" / "guard_model_folder.py"
        for event, code in ((("Read", {"file_path": "C:/p/design/reference/model/x.tmdl"}), 2),
                            (("Grep", {"pattern": "measure", "path": r"design\reference\model"}), 2),
                            (("Bash", {"command": r"type design\reference\model\x.bim"}), 2),
                            (("Bash", {"command": "python tools/pbik/pbik.py model intake"}), 0),
                            (("Read", {"file_path": "C:/p/design/reference/brd.md"}), 0)):
            r = subprocess.run([sys.executable, str(hook)], input=json.dumps({"tool_name": event[0],
                                                                              "tool_input": event[1]}),
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, code, event)
        r = subprocess.run([sys.executable, str(hook)], input=json.dumps({"tool_name": "Edit", "tool_input": {
            "file_path": "tools/x.py", "new_string": "see design/reference/model"}}), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, "file contents mentioning the folder aren't blocked")
        settings = json.loads((KIT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("guard_model_folder.py", json.dumps(settings["hooks"]["PreToolUse"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
