"""Synthetic-to-live tests (docs/design/synth-to-live.md) on made-up sample data only.

    python tools\\pbik\\tests\\test_synth.py

The sample model (tests/synth_sample/Example Live.SemanticModel) is invented: no real names, IDs, values or colours.
"""
import json, os, pathlib, shutil, sys, tempfile, unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
SAMPLE = HERE / "synth_sample"
LIVE = SAMPLE / "Example Live.SemanticModel"
sys.path.insert(0, str(HERE.parent))

from pbikit import dataclass_ as DC  # noqa: E402


def say(text):
    return lambda prompt: text


class Tmp(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="pbik_synth_"))
        (self.root / "design" / "specs").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class DataClassTests(Tmp):
    """0a: data classes, the restricted guard and person-only confirmation."""

    def test_default_set_and_lowering_is_person_only(self):
        self.assertEqual(DC.data_class(self.root), "internal")
        DC.set_class(self.root, "restricted")
        self.assertEqual(DC.data_class(self.root), "restricted")
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), self.assertRaises(DC.Refused):
            DC.set_class(self.root, "public")
        with self.assertRaises(DC.Refused):
            DC.set_class(self.root, "public", ask=say("yes"))
        DC.set_class(self.root, "public", ask=say("PUBLIC"))
        self.assertEqual(DC.data_class(self.root), "public")

    def test_restricted_guard(self):
        self.assertIsNone(DC.guard(self.root, "dax"))
        DC.set_class(self.root, "restricted")
        self.assertIn("no synthetic model", DC.guard(self.root, "dax"))
        m = self.root / "X.SemanticModel" / "definition"
        m.mkdir(parents=True)
        (m / "model.tmdl").write_text(f"model Model\n\nannotation {DC.SYNTH_MARK} = 1\n", encoding="utf-8")
        self.assertIsNone(DC.guard(self.root, "screenshot"))
        st = self.root / ".pbik" / "bind"
        st.mkdir(parents=True)
        (st / "state.json").write_text(json.dumps({"mode": "live", "model": "Example"}), encoding="utf-8")
        self.assertIn("bound to the live model", DC.guard(self.root, "screenshot"))

    def test_agent_shell_is_never_a_person(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            self.assertFalse(DC.person_present())
            with self.assertRaises(DC.Refused):
                DC.confirm("ok?", "YES")


if __name__ == "__main__":
    unittest.main(verbosity=2)
