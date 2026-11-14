"""Walkthrough fixes (v1.7, Phase 1 walkthrough of 2026-11-14), made-up data only.

    python tools\\pbik\\tests\\test_walkthrough.py

One class per finding group: HIGH (new report folder, colours, plan picture, progress), MEDIUM, the one-folder
project setup, LOW, and the output polish rules.
"""
import io, json, os, pathlib, shutil, subprocess, sys, tempfile, unittest
os.environ.setdefault("PBIK_HOME", tempfile.mkdtemp(prefix="pbik_home_"))

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
PBIK = HERE.parent / "pbik.py"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(KIT / "design" / "scripts"))

from pbikit import desktop as D, newreport as NR, plan as PL, progress as PR, recolour as RC, summary as SM  # noqa


def pbik(*args, cwd=None):
    return subprocess.run([sys.executable, str(PBIK), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd)


def lum(hex_):
    h = hex_.strip("'#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = (lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def project(tmp, name="Demo", tokens_patch=None):
    """A project with a model and a layout but no report folder yet (as after the plan OK)."""
    shutil.copytree(HERE / "synth_sample" / "Example Live.SemanticModel", tmp / f"{name}.SemanticModel")
    (tmp / "design" / "specs").mkdir(parents=True)
    lay = json.loads((HERE / "synth_sample" / "layout.json").read_text(encoding="utf-8"))
    lay["visuals"] = [v for v in lay["visuals"] if v["id"] != "P1-V02"]       # [Amount Share] is a planned measure
    (tmp / "design" / "specs" / "layout.json").write_text(json.dumps(lay), encoding="utf-8")
    shutil.copytree(KIT / "design" / "templates", tmp / "design" / "templates")
    tokens = json.loads((KIT / "design" / "tokens.json").read_text(encoding="utf-8"))
    for k, v in (tokens_patch or {}).items():
        tokens["colors"][k] = v
    (tmp / "design" / "tokens.json").write_text(json.dumps(tokens), encoding="utf-8")
    return tmp


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_wt_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ---------------------------------------------------------------- HIGH 1: a clean report folder
class NewReportTests(Tmp):
    def test_build_makes_a_clean_report_folder(self):
        p = project(self.tmp)
        r = pbik("build", "Demo", "design/specs/layout.json", cwd=p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("made a new, empty report", r.stdout)
        rep = p / "Demo.Report"
        self.assertTrue((rep / "definition" / "report.json").exists())
        self.assertTrue((p / "Demo.pbip").exists())
        pbir = json.loads((rep / "definition.pbir").read_text(encoding="utf-8"))
        self.assertEqual(pbir["datasetReference"]["byPath"]["path"], "../Demo.SemanticModel")
        report = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        self.assertNotIn("customTheme", report["themeCollection"])           # nothing from an old report
        self.assertEqual(len(list(rep.glob("definition/pages/*/visuals/*/visual.json"))), 4)
        again = pbik("build", "Demo.Report", "design/specs/layout.json", cwd=p)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("No changes", again.stdout)
        v = pbik("validate", "Demo.Report", cwd=p)
        self.assertIn("0 error(s)", v.stdout + v.stderr)

    def test_never_touches_an_existing_folder(self):
        (self.tmp / "Old.Report").mkdir()
        folder, made = NR.ensure(self.tmp / "Old.Report", quiet=True)
        self.assertFalse(made)
        self.assertEqual(list((self.tmp / "Old.Report").iterdir()), [])
        with self.assertRaises(FileExistsError):
            NR.create(self.tmp / "Old.Report")

    def test_names(self):
        self.assertEqual(NR.report_folder("A B").name, "A B.Report")
        self.assertEqual(NR.report_folder("A B.pbip").name, "A B.Report")
        self.assertEqual(NR.report_folder("A B.Report").name, "A B.Report")


# ---------------------------------------------------------------- HIGH 2: colours
class ColourTests(Tmp):
    def test_background_colour_is_a_fill(self):
        self.assertEqual(RC.category("background", "color"), "fill")
        self.assertEqual(RC.category("visualHeader", "background"), "fill")
        self.assertEqual(RC.category("title", "fontColor"), "text")
        self.assertEqual(RC.category("labels", "color"), "text")
        self.assertEqual(RC.category("values", "fontColorPrimary"), "text")
        self.assertEqual(RC.category("border", "color"), "line")

    def test_backgrounds_stay_light_on_a_light_theme(self):
        # the walkthrough's palette: "text on dark" is near-black, so a background mapped as text turns black
        p = project(self.tmp, tokens_patch={"onDark": "#0A191A", "onDarkMuted": "#011A1C"})
        r = pbik("build", "Demo", "design/specs/layout.json", cwd=p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        seen = 0
        for f in (p / "Demo.Report").glob("definition/pages/*/visuals/*/visual.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            for e in d["visual"].get("visualContainerObjects", {}).get("background", []):
                col = (e.get("properties", {}).get("color", {}).get("solid", {}).get("color", {})
                       .get("expr", {}).get("Literal", {}).get("Value"))
                if col:
                    seen += 1
                    self.assertGreater(lum(col), 0.7, f"{f.parent.name}: background {col} is dark on a light theme")
        self.assertGreater(seen, 0)


# ---------------------------------------------------------------- HIGH 3: the plan picture
LAYOUT = {"pages": {"P1": {"displayName": "Overview"}},
          "visuals": [{"id": "P1-V01", "name": "kpi", "page": "P1", "type": "cardVisual", "x": 32, "y": 32, "w": 446,
                       "h": 160, "bindings": {"Data": ["_Measures[Orders]"]}}]}


class PlanPictureTests(Tmp):
    def setUp(self):
        super().setUp()
        (self.tmp / "design" / "specs").mkdir(parents=True)
        (self.tmp / "design" / "specs" / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)
        super().tearDown()

    def test_the_browser_gets_a_full_path(self):
        got = []
        os.chdir(self.tmp)
        PL.picture("design/specs/layout.json", "design/plan", shoot=lambda h, png, *a: (got.append(png),
                                                                                        png.write_bytes(b"x")))
        self.assertTrue(got[0].is_absolute(), got[0])

    def test_a_failed_drawing_gives_a_reason_and_a_simple_preview(self):
        def hang(*a):
            raise SystemExit("Edge didn't write design\\plan\\page-1.png within 30s (set EDGE_WAIT ...)")
        notes = []
        pngs = PL.show(self.tmp, purposes={"P1": "Are orders growing?"}, shoot=hang, notes=notes)[0]
        self.assertTrue(pngs[0].read_bytes().startswith(b"\x89PNG"))
        self.assertTrue(any("simpler preview" in n and "didn't finish in time" in n for n in notes), notes)
        self.assertNotIn("EDGE_WAIT", " ".join(notes))

    def test_the_plain_words_report_is_never_empty(self):
        def boom():
            raise SystemExit("Edge didn't write page-1.png within 30s")
        code, text = SM.run_json("plan show", boom)
        doc = json.loads(text)
        self.assertEqual(code, 1)
        self.assertTrue(doc["facts"] or doc["needs"])

        def silent():
            return 1
        doc = json.loads(SM.run_json("x", silent)[1])
        self.assertTrue(doc["needs"])

        def crash():
            raise ValueError("bad")
        doc = json.loads(SM.run_json("x", crash)[1])
        self.assertTrue(doc["needs"] and "Traceback" not in json.dumps(doc))


# ---------------------------------------------------------------- HIGH 4: progress during waits
class ProgressTests(Tmp):
    def test_a_line_while_waiting(self):
        import time
        lines = []
        old = sys.__stderr__
        sys.__stderr__ = io.StringIO()
        try:
            with PR.still("drawing the plan picture", every=0.05, root=self.tmp, lines=lines):
                time.sleep(0.2)
        finally:
            sys.__stderr__ = old
        self.assertTrue(lines and lines[0].startswith("Still drawing the plan picture"))
        self.assertIn("Still drawing", (self.tmp / ".pbik" / "progress.txt").read_text(encoding="utf-8")
                      + "".join(lines))

    def _fake(self, answers):
        calls = []

        def call(ps, script, action, args):
            calls.append(action)
            return answers[min(len(calls) - 1, len(answers) - 1)]
        return call, calls

    def test_desktop_still_opening_is_waited_out(self):
        bridge = self.tmp / "pbi-bridge.ps1"
        bridge.write_text("", encoding="utf-8")
        not_ready = (1, "", 'application.state.get/v1 failed: {"data":{"reason":"HostNotReady"}}')
        call, calls = self._fake([not_ready, not_ready, (0, '{"hasUnsavedChanges": false}', "")])
        old = D._call
        D._call = call
        try:
            out = D.run("state", bridge=bridge, wait=5, sleep=lambda s: None)
        finally:
            D._call = old
        self.assertIn("hasUnsavedChanges", out)
        self.assertEqual(len(calls), 3)

    def test_desktop_still_opening_says_so(self):
        bridge = self.tmp / "pbi-bridge.ps1"
        bridge.write_text("", encoding="utf-8")
        call, _ = self._fake([(1, "", "Host is not ready to accept operations")])
        old = D._call
        D._call = call
        buf = io.StringIO()
        try:
            with self.assertRaises(SystemExit) as cm, __import__("contextlib").redirect_stdout(buf):
                D.run("state", bridge=bridge, wait=0, sleep=lambda s: None)
        finally:
            D._call = old
        self.assertEqual(cm.exception.code, D.NOT_READY)
        self.assertIn("still opening", buf.getvalue())
        self.assertNotIn("not ready", buf.getvalue().lower())


if __name__ == "__main__":
    unittest.main(verbosity=1)
