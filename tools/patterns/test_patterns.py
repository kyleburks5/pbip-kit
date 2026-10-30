"""Tests for tools/patterns/build_patterns.py on a scratch copy of Rep 8 (the source is only read).

    python tools\\patterns\\test_patterns.py        (source: %PATTERNS_TEST_SOURCE%, default tools\\fixtures\\rep8)

The Rep 4, 5 and 8 visuals come from the fixtures in the kit (tools/fixtures/README.md), not from the `sources` in
patterns.json, so the tests run on a clean clone; a missing source fails the run, never skips it.
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "tools" / "pbik"))
FIXTURES = KIT / "tools" / "fixtures"
SOURCE = pathlib.Path(os.environ.get("PATTERNS_TEST_SOURCE", FIXTURES / "rep8"))

import build_patterns as BP  # noqa: E402

WANTED = {"cardVisual", "lineChart", "clusteredBarChart", "clusteredColumnChart", "lineStackedColumnComboChart",
          "donutChart", "gauge", "tableEx", "pivotTable", "advancedSlicerVisual", "slicer", "pageNavigator",
          "actionButton", "textbox", "shape", "image"}


def tree(folder):
    return {str(f.relative_to(folder)): f.read_bytes() for f in pathlib.Path(folder).rglob("*") if f.is_file()}


class PatternsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = BP.load(HERE / "patterns.json")
        spec["sources"] = {"rep4": str(FIXTURES / "rep4"), "rep5": str(FIXTURES / "rep5"), "rep8": str(SOURCE)}
        missing = [p for p in spec["sources"].values() if not list(pathlib.Path(p).glob("*.Report"))]
        if missing:
            raise RuntimeError(f"test source(s) with no *.Report: {', '.join(missing)} (restore tools/fixtures)")
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="patterns-test-"))
        cls.dest = cls.tmp / "patterns"
        cls.spec = cls.tmp / "patterns.json"
        BP.save(cls.spec, spec)
        cls.src_before = tree(next(SOURCE.glob("*.Report")))
        BP.main(["--src", str(SOURCE), "--dest", str(cls.dest), "--spec", str(cls.spec)])
        cls.report = next(cls.dest.glob("*.Report"))
        cls.page = next(p.parent for p in cls.report.glob("definition/pages/*/page.json")
                        if json.loads(p.read_text(encoding="utf-8"))["displayName"] == "Patterns")
        cls.visuals = {f.parent.name: json.loads(f.read_text(encoding="utf-8"))
                       for f in cls.page.glob("visuals/*/visual.json")}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_type_and_id(self):
        types = {d["visual"]["visualType"] for d in self.visuals.values()}
        self.assertEqual(WANTED - types, set())
        for name, d in self.visuals.items():
            self.assertRegex(name, r"^P4-V\d{2}_")
            self.assertEqual(d["name"], name)
            self.assertNotIn("parentGroupName", d)
            self.assertNotIn("visualLink", d["visual"].get("visualContainerObjects", {}))

    def test_validate_has_no_patterns_errors(self):
        r = subprocess.run([sys.executable, str(KIT / "tools" / "pbik" / "pbik.py"), "validate", str(self.report)],
                           capture_output=True, text=True, encoding="utf-8")
        bad = [x for x in r.stdout.splitlines() if x.startswith("error") and "Patterns" in x]
        self.assertEqual(bad, [], r.stdout)

    def test_rebound_visuals_use_rep8_fields_and_palette(self):
        combo = next(d for n, d in self.visuals.items() if n.startswith("P4-V16"))
        text = json.dumps(combo)
        self.assertIn("Hires Shown", text)
        self.assertNotIn("Terminations (down)", text)
        bar = json.dumps(next(d for n, d in self.visuals.items() if n.startswith("P4-V19")))
        self.assertNotIn("#1E2A2B", bar)          # Rep 4's text colour became Rep 8's
        self.assertIn("#1D2733", bar)

    def test_page_only_rerun_changes_nothing(self):
        before = tree(self.report)
        BP.main(["--dest", str(self.dest), "--page-only", "--spec", str(self.spec)])
        self.assertEqual(before, tree(self.report))

    def test_refuses_to_overwrite_a_saved_page(self):
        f = next(self.page.glob("visuals/P4-V13_*/visual.json"))
        saved = f.read_text(encoding="utf-8").rstrip()          # Desktop drops the final newline
        f.write_text(saved, encoding="utf-8")
        with self.assertRaises(SystemExit):
            BP.main(["--dest", str(self.dest), "--page-only", "--spec", str(self.spec)])
        self.assertEqual(f.read_text(encoding="utf-8"), saved)
        BP.main(["--dest", str(self.dest), "--page-only", "--force", "--spec", str(self.spec)])
        self.assertNotEqual(f.read_text(encoding="utf-8"), saved)

    def test_baseline_commit_and_source_untouched(self):
        log = subprocess.run(["git", "-C", str(self.dest), "log", "--oneline"], capture_output=True, text=True).stdout
        self.assertIn("baseline", log)
        self.assertEqual(self.src_before, tree(next(SOURCE.glob("*.Report"))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
