"""bind tests (docs/design/synth-to-live.md) on the made-up sample model and report (bind_sample.py).

    python tools\\pbik\\tests\\test_bind.py
"""
import copy, json, os, pathlib, shutil, sys, tempfile, unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import bind_sample  # noqa: E402
import test_synth as TS  # noqa: E402
from pbikit import bind as BD, dataclass_ as DC, synth as S, synthgen as G  # noqa: E402

MID = "00000000-0000-4000-8000-0000000000aa"
CLOSED = lambda: False      # noqa: E731  Desktop closed
OPEN = lambda: True         # noqa: E731


def layout():
    lay = json.loads(TS.LAYOUT.read_text(encoding="utf-8"))
    lay["visuals"].append({"id": "P1-V06", "name": "extra", "page": "P1", "type": "tableEx",
                           "fields": ["Orders[Status]", "Calendar[Year]", "Area[Region]", "[Total Units]"]})
    return lay


def tree(folder):
    return {str(f.relative_to(folder)): f.read_bytes() for f in sorted(pathlib.Path(folder).rglob("*")) if f.is_file()}


class BindBase(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="pbik_bind_"))
        (self.root / "design" / "specs").mkdir(parents=True)
        TS.approved_project(self.root)
        lf = self.root / "design" / "specs" / "layout.json"
        lf.write_text(json.dumps(layout()), encoding="utf-8")
        S.slice_(self.root, lf)
        G.generate(self.root, "Example Synthetic")
        self.rep = bind_sample.make_report(self.root, "Example Synthetic.SemanticModel")
        self.quiet = lambda *a: None

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def check(self):
        return BD.check(self.rep, self.root)

    def go_live(self, **kw):
        args = dict(workspace="Sample Workspace", model="Example Live", mid=MID, root=self.root,
                    ask=TS.say("Example Live"), out=self.quiet, desktop_open=CLOSED)
        args.update(kw)
        return BD.live(self.rep, "Sample Person", **args)


class PartZeroTests(BindBase):
    """0e-0h: check, prepare, live and local without a map (names match)."""

    def test_check_passes_on_matching_names(self):
        r = self.check()
        self.assertEqual(r.errors, [], r.errors)

    def test_planned_measure_needs_prepare(self):
        v = self.rep / "definition/pages/p1/visuals/P1-V01_amount-card/visual.json"
        d = json.loads(v.read_text(encoding="utf-8"))
        d["visual"]["query"]["queryState"]["Data"]["projections"].append(
            bind_sample.proj(bind_sample.mea("_Measures", "Amount Share"), "_Measures.Amount Share", "Amount Share"))
        bind_sample.write(v, d)
        self.assertTrue(any("bind prepare" in e for e in self.check().errors))
        seen = []
        used = BD.prepare(self.rep, self.root, query=lambda dax: seen.append(dax) or ["0.25", "0.25"], out=self.quiet)
        self.assertEqual(used, ["Amount Share"])
        self.assertIn("ALL ( Area )", seen[0])
        ext = json.loads((self.rep / "definition/reportExtensions.json").read_text(encoding="utf-8"))
        names = [m["name"] for e in ext["entities"] for m in e["measures"]]
        self.assertIn("Amount Share", names)
        self.assertIn('"Schema": "extension"', v.read_text(encoding="utf-8"))
        syn = (self.root / "Example Synthetic.SemanticModel/definition/tables/_Measures.tmdl").read_text(encoding="utf-8")
        self.assertNotIn("Amount Share", syn, "the synthetic model drops the prepared measure")
        self.assertEqual(self.check().errors, [])
        self.assertEqual(G.verify(self.root, self.root / "Example Synthetic.SemanticModel")[0], [])

    def test_prepare_inlines_planned_dependencies_and_refuses_changed_values(self):
        g = S.read_json(self.root / "design/specs/generate.json")
        g["plannedMeasures"]["Share Pct"] = {"table": "_Measures", "expression": "[Amount Share] * 100"}
        S.write_json(self.root / "design/specs/generate.json", g)
        self.assertEqual(BD.inline("[Share Pct] + 1", g["plannedMeasures"]),
                         "CALCULATE ( CALCULATE ( DIVIDE ( [Total Amount], CALCULATE ( [Total Amount], ALL ( Area ) )"
                         " ) ) * 100 ) + 1")
        v = self.rep / "definition/pages/p1/visuals/P1-V01_amount-card/visual.json"
        d = json.loads(v.read_text(encoding="utf-8"))
        d["visual"]["query"]["queryState"]["Data"]["projections"][0] = bind_sample.proj(
            bind_sample.mea("_Measures", "Share Pct"), "_Measures.Share Pct", "Share Pct")
        bind_sample.write(v, d)
        before = tree(self.rep)
        with self.assertRaises(BD.BindError):
            BD.prepare(self.rep, self.root, query=lambda dax: ["25", "24"], out=self.quiet)
        self.assertEqual(before, tree(self.rep), "nothing written when the values differ")

    def test_live_and_local(self):
        before = tree(self.rep)
        with self.assertRaises(BD.BindError):
            self.go_live(desktop_open=OPEN)
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), self.assertRaises(DC.Refused):
            self.go_live(ask=None)
        st = self.go_live(mid=f"https://app.powerbi.com/groups/me/datasets/{MID}/details")
        pbir = json.loads((self.rep / "definition.pbir").read_text(encoding="utf-8"))
        cs = pbir["datasetReference"]["byConnection"]["connectionString"]
        self.assertIn(f"semanticmodelid={MID}", cs)
        self.assertIn("initial catalog=Example Live", cs)
        self.assertNotIn("byPath", pbir["datasetReference"])
        self.assertEqual(st["id"], MID)
        DC.set_class(self.root, "restricted")
        self.assertIn("bound to the live model", DC.guard(self.root, "dax"))
        with self.assertRaises(BD.BindError):
            self.go_live()                                  # already live
        with self.assertRaises(BD.BindError):
            BD.local(self.rep, self.root, out=self.quiet, desktop_open=OPEN)
        BD.local(self.rep, self.root, out=self.quiet, desktop_open=CLOSED)
        self.assertEqual(before, tree(self.rep), "local restores the report exactly")
        self.assertIsNone(DC.guard(self.root, "dax"))

    def test_live_from_a_desktop_saved_report(self):
        other = self.root / "Saved.Report"
        bind_sample.write(other / "definition.pbir", {"version": "4.0", "datasetReference": {"byConnection": {
            "connectionString": BD.connection_string("Sample Workspace", "Example Live", MID)}}})
        st = self.go_live(workspace=None, model=None, mid=None, from_=other)
        self.assertEqual((st["workspace"], st["model"], st["id"]), ("Sample Workspace", "Example Live", MID))


if __name__ == "__main__":
    unittest.main(verbosity=2)
