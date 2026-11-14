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


if __name__ == "__main__":
    unittest.main(verbosity=2)
