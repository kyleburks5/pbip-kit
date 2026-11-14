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


if __name__ == "__main__":
    unittest.main(verbosity=2)
