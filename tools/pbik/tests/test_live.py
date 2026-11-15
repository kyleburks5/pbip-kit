"""The switch to live and back (v1.7 live walkthrough, CRITICAL 1-4), made-up model and report only.

    python tools\\pbik\\tests\\test_live.py

Prepared before the window opens; all or nothing, checked before "done"; failures forced mid-way leave the report
exactly as it was and say so; never silent; plain names only in the window.
"""
import json, os, pathlib, sys, tempfile, unittest
os.environ.setdefault("PBIK_HOME", tempfile.mkdtemp(prefix="pbik_home_"))
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import bind_sample  # noqa: E402
import test_bind as TB  # noqa: E402
from pbikit import bind as BD, dataclass_ as DC, gates as GT, status as ST, steps as STP, synth as S  # noqa: E402

YES = lambda t, x, code=False, details="": "yes"      # noqa: E731
CLOSED = lambda: False                                 # noqa: E731
QUIET = lambda *a: None                                # noqa: E731


def pick(root):
    """A Desktop-saved report connected to the made-up published model, in the picker folder."""
    from pbikit import picker as PK
    d = PK.prepare(root)
    bind_sample.write(d / "Pick.Report" / "definition.pbir", {"version": "4.0", "datasetReference": {"byConnection": {
        "connectionString": BD.connection_string("Sample Workspace", "Example Live", TB.MID)}}})
    return d


class LiveBase(TB.BindBase):
    def setUp(self):
        super().setUp()
        os.environ["PBIK_DESKTOP_OPEN"] = "0"
        pick(self.root)

    def tearDown(self):
        os.environ.pop("PBIK_DESKTOP_OPEN", None)
        super().tearDown()

    def add_planned_measure(self):
        v = self.rep / "definition/pages/p1/visuals/P1-V01_amount-card/visual.json"
        d = json.loads(v.read_text(encoding="utf-8"))
        d["visual"]["query"]["queryState"]["Data"]["projections"].append(
            bind_sample.proj(bind_sample.mea("_Measures", "Amount Share"), "_Measures.Amount Share", "Amount Share"))
        bind_sample.write(v, d)

    def go_live(self):
        GT.prepare("bind-live", self.root, from_="picked")
        return GT.run("bind-live", self.root, dialog=YES, out=QUIET)


class PrepareFirstTests(LiveBase):
    """1. Bind check and prepare succeed before the window opens; otherwise it says why and opens nothing."""

    def test_report_only_measures_move_before_the_window(self):
        self.add_planned_measure()
        self.assertTrue(any("bind prepare" in e for e in BD.check(self.rep, self.root).errors))
        doc = GT.prepare("bind-live", self.root, from_="picked")
        ext = json.loads((self.rep / "definition/reportExtensions.json").read_text(encoding="utf-8"))
        self.assertIn("Amount Share", [m["name"] for e in ext["entities"] for m in e["measures"]])
        self.assertTrue(BD.check(self.rep, self.root).ok(), "the check passes before the person is asked")
        self.assertEqual(doc["args"]["report"], str(self.rep))
        self.assertEqual(self.go_live(), "approved")

    def test_kit_colour_measures_move_as_text(self):
        g = S.read_json(self.root / "design/specs/generate.json")
        g["plannedMeasures"]["Amount Share"]["dataType"] = "string"          # as layout polish writes colour measures
        S.write_json(self.root / "design/specs/generate.json", g)
        self.add_planned_measure()
        GT.prepare("bind-live", self.root, from_="picked")
        ext = json.loads((self.rep / "definition/reportExtensions.json").read_text(encoding="utf-8"))
        m = next(m for e in ext["entities"] for m in e["measures"] if m["name"] == "Amount Share")
        self.assertEqual(m.get("dataType"), "Text")

    def test_a_failed_prepare_changes_nothing(self):
        self.add_planned_measure()
        before = TB.tree(self.rep)
        gen = (self.root / "design/specs/generate.json").read_bytes()
        model = TB.tree(self.root / "Example Synthetic.SemanticModel")
        from pbikit import extensions as X
        with mock.patch.object(X, "add", side_effect=SystemExit("pbik: table '_Measures' is not in the model")), \
                self.assertRaises(GT.GateError) as cm:
            GT.prepare("bind-live", self.root, from_="picked")
        self.assertIn("nothing was changed", str(cm.exception))
        self.assertEqual(before, TB.tree(self.rep))
        self.assertEqual(gen, (self.root / "design/specs/generate.json").read_bytes())
        self.assertEqual(model, TB.tree(self.root / "Example Synthetic.SemanticModel"))

    def test_a_check_that_would_fail_opens_no_window(self):
        v = self.rep / "definition/pages/p1/visuals/P1-V01_amount-card/visual.json"
        d = json.loads(v.read_text(encoding="utf-8"))
        d["visual"]["query"]["queryState"]["Data"]["projections"].append(
            bind_sample.proj(bind_sample.col("Orders", "No Such Column"), "Orders.No Such Column", "x"))
        bind_sample.write(v, d)
        with self.assertRaises(GT.GateError) as cm:
            GT.prepare("bind-live", self.root, from_="picked")
        self.assertIn("I can't switch to live yet, so I didn't open the window", str(cm.exception))
        self.assertFalse((GT.gate_dir(self.root) / "bind-live.json").exists(), "nothing prepared, nothing to open")
        with self.assertRaises(GT.GateError):
            GT.open_window("bind-live", self.root, launch=lambda c: self.fail("no window may open"))

    def test_desktop_open_is_said_plainly(self):
        with mock.patch.dict(os.environ, {"PBIK_DESKTOP_OPEN": "1"}), self.assertRaises(GT.GateError) as cm:
            GT.prepare("bind-live", self.root, from_="picked")
        self.assertIn("Power BI Desktop has the report open", str(cm.exception))

    def test_unapproved_model_and_no_pick(self):
        c = S.read_json(self.root / "design/specs/contract.json")
        c["approval"] = None
        S.write_json(self.root / "design/specs/contract.json", c)
        with self.assertRaises(GT.GateError) as cm:
            GT.prepare("bind-live", self.root, from_="picked")
        self.assertIn("the model isn't approved yet", str(cm.exception))

    def test_window_shows_plain_names_never_the_id(self):
        doc = GT.prepare("bind-live", self.root, from_="picked")
        self.assertIn("You picked Example Live in workspace Sample Workspace", doc["summary"])
        self.assertNotIn(TB.MID, doc["summary"])
        self.assertNotIn("model ID", doc["summary"])
        self.assertNotIn("'", doc["summary"].split("\n")[0], "no quoted names either")


class AllOrNothingTests(LiveBase):
    """2. Live and back complete fully or roll back fully; "done" only after the result is checked."""

    def test_live_and_back_checked(self):
        before = TB.tree(self.rep)
        self.assertEqual(self.go_live(), "approved")
        self.assertEqual(GT.read_json(GT.gate_dir(self.root) / "bind-live.result.json")["result"], "approved")
        self.assertEqual(BD.verify_live(self.rep, self.root, TB.MID), [])
        st = ST.read(self.root)
        self.assertIn("live", st["done"])
        self.assertTrue(st["connection"].startswith("live"))
        GT.prepare("bind-local", self.root)
        self.assertEqual(GT.run("bind-local", self.root, dialog=YES, out=QUIET), "approved")
        self.assertEqual(before, TB.tree(self.rep))
        self.assertEqual(ST.read(self.root)["connection"], "synthetic")

    def test_forced_failure_writing_live(self):
        before = TB.tree(self.rep)
        GT.prepare("bind-live", self.root, from_="picked")
        real = BD.remap_doc
        calls = []

        def boom(*a, **k):                     # the first file is rewritten, the third fails
            calls.append(1)
            if len(calls) == 3:
                raise OSError("disk full")
            return real(*a, **k)
        with mock.patch.object(BD, "remap_doc", boom), mock.patch.object(BD.Context, "__init__", wraps_init()):
            r = GT.run("bind-live", self.root, dialog=YES, out=QUIET)
        self.assert_failed_and_restored(r, before, "bind-live")

    def test_forced_failure_at_the_check_after_writing(self):
        before = TB.tree(self.rep)
        GT.prepare("bind-live", self.root, from_="picked")
        with mock.patch.object(BD, "verify_live", lambda *a: ["the report's connection doesn't point at the live "
                                                               "model"]):
            r = GT.run("bind-live", self.root, dialog=YES, out=QUIET)
        self.assert_failed_and_restored(r, before, "bind-live")
        self.assertIn("connection doesn't point at the live model",
                      GT.read_json(GT.gate_dir(self.root) / "bind-live.result.json")["why"])

    def test_forced_failure_switching_back(self):
        self.go_live()
        live_tree = TB.tree(self.rep)
        live_state = DC.bind_state(self.root)
        GT.prepare("bind-local", self.root)
        real = BD.restore_local

        def boom(*a, **k):                      # every file goes back, then it fails before the switch is recorded
            real(*a, **k)
            raise OSError("the file is locked")
        with mock.patch.object(BD, "restore_local", boom):
            r = GT.run("bind-local", self.root, dialog=YES, out=QUIET)
        self.assertEqual(r, "failed")
        self.assertEqual(live_tree, TB.tree(self.rep), "still on the live model, exactly as it was")
        self.assertEqual(DC.bind_state(self.root), live_state)
        res = GT.read_json(GT.gate_dir(self.root) / "bind-local.result.json")
        self.assertEqual(res["result"], "failed")
        self.assertIn("still on the live model", res["why"])
        line = ST.line(self.root)
        self.assertIn("didn't work", line)
        self.assertNotIn("Traceback", line)

    def test_forced_failure_at_the_check_switching_back(self):
        self.go_live()
        live_tree = TB.tree(self.rep)
        GT.prepare("bind-local", self.root)
        with mock.patch.object(BD, "verify_local", lambda *a: ["some fields the report uses aren't in the synthetic "
                                                                "model"]):
            self.assertEqual(GT.run("bind-local", self.root, dialog=YES, out=QUIET), "failed")
        self.assertEqual(live_tree, TB.tree(self.rep))
        self.assertEqual(DC.bind_state(self.root)["mode"], "live")
        GT.prepare("bind-local", self.root)                  # and it still works afterwards
        self.assertEqual(GT.run("bind-local", self.root, dialog=YES, out=QUIET), "approved")

    def assert_failed_and_restored(self, r, before, gate):
        self.assertEqual(r, "failed")
        self.assertEqual(before, TB.tree(self.rep), "the report is exactly as it was")
        self.assertIsNone(DC.bind_state(self.root), "no switch recorded")
        res = GT.read_json(GT.gate_dir(self.root) / f"{gate}.result.json")
        self.assertEqual(res["result"], "failed")
        self.assertIn("the report is exactly as it was", res["why"])
        self.assertNotIn("`", res["why"])
        st = ST.read(self.root)
        self.assertEqual(st["lastApproval"]["result"], "failed")
        self.assertNotIn("live", st.get("done", []))
        self.assertIn("didn't work", ST.line(self.root))


def wraps_init():
    real = BD.Context.__init__

    def init(self, *a, **k):
        return real(self, *a, **k)
    return init


class NeverSilentTests(unittest.TestCase):
    """3. After every approval: success or failure within a minute, a line every minute while waiting."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="pbik_wait_"))
        GT.gate_dir(self.root).mkdir(parents=True)
        self.t = [0.0]

    def clock(self):
        return self.t[0]

    def sleep(self, s):
        self.t[0] += s

    def write(self, doc):
        S.write_json(GT.gate_dir(self.root) / "bind-live.result.json", doc)

    def test_a_closed_window_without_an_answer_is_a_failure(self):
        S.write_json(GT.gate_dir(self.root) / "bind-live.window.json", {"pid": 4242})
        (GT.gate_dir(self.root) / "bind-live.window.log").write_text("pbik: GateError: the backup is missing\n",
                                                                     encoding="utf-8")
        r = GT.wait("bind-live", self.root, alive=lambda pid: False, clock=self.clock, sleep=self.sleep)
        self.assertEqual(r["result"], "failed")
        self.assertIn("the backup is missing", r["why"])
        self.assertLess(self.t[0], 10)

    def test_applying_longer_than_a_minute_is_reported(self):
        self.write({"result": "applying"})
        said = []
        r = GT.wait("bind-live", self.root, alive=lambda pid: True, clock=self.clock, sleep=self.sleep,
                    out=said.append)
        self.assertEqual(r["result"], "failed")
        self.assertIn("within a minute", r["why"])
        self.assertLessEqual(self.t[0], 62)

    def test_still_waiting_every_minute(self):
        said = []
        r = GT.wait("bind-live", self.root, timeout=185, alive=lambda pid: True, clock=self.clock, sleep=self.sleep,
                    out=said.append)
        self.assertEqual(r["result"], "not answered")
        self.assertEqual(len(said), 3)
        self.assertIn("Still waiting for your answer", said[0])

    def test_a_failed_apply_is_written_and_counted(self):
        root = self.root
        (root / "design" / "specs").mkdir(parents=True)
        S.write_json(GT.gate_dir(root) / "class-lower.json", {"gate": "class-lower", "task": "Loosen the data class",
                                                             "summary": "x", "hash": "h", "args": {"to_class": "x"}})
        with mock.patch.object(GT, "check_ready", lambda g, r: S.read_json(GT.gate_dir(root) / f"{g}.json")), \
                mock.patch.object(GT, "apply", side_effect=RuntimeError("no such class `pbik project class`")):
            self.assertEqual(GT.run("class-lower", root, dialog=YES, out=QUIET), "failed")
        r = S.read_json(GT.gate_dir(root) / "class-lower.result.json")
        self.assertEqual(r["result"], "failed")
        self.assertNotIn("`", r["why"])
        self.assertEqual(len(STP.interactions(root)), 1, "the window answer counts once")



# ---------------------------------------------------------------- HIGH 5-7 (and the status, MEDIUM 13)
import shutil, subprocess  # noqa: E402
KIT = HERE.parents[2]


def pbik(*args, cwd=None):
    return subprocess.run([sys.executable, str(HERE.parent / "pbik.py"), *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", cwd=cwd)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_high_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class OneReferenceFolderTests(Tmp):
    """5. Intake and the start read only the Model and Reference folders; files in the old place are named."""

    def test_old_places_are_warned_never_read(self):
        from pbikit import drops, intake as IN, start as SR
        old_model = self.tmp / "design" / "reference" / "model"
        shutil.copytree(HERE / "synth_sample" / "Example Live.SemanticModel", old_model / "Old.SemanticModel")
        old_ref = self.tmp / "design" / "reference" / "inputs"
        old_ref.mkdir(parents=True)
        (old_ref / "Wireframe.html").write_text("<html></html>", encoding="utf-8")
        said = []
        with self.assertRaises(IN.IntakeError):
            IN.intake(self.tmp, out=said.append)
        self.assertTrue(any("old place for model files" in x and "Old.SemanticModel" in x for x in said), said)
        self.assertFalse((self.tmp / "design/specs/contract.json").exists(), "the old place was never read")
        lines = SR.check(self.tmp)
        self.assertTrue(any("old place for reference files" in x for x in lines), lines)
        self.assertEqual(SR.detect(self.tmp)["inputs"], [], "the old wireframe isn't a layout input")
        self.assertFalse(any("design/reference" in x or "design\\reference" in x for x in lines), "no paths")
        self.assertEqual(drops.model_dir(self.tmp), self.tmp / "Model")

    def test_the_live_pick_sits_in_reference_and_is_no_layout(self):
        from pbikit import picker as PK, start as SR
        with mock.patch("os.startfile", side_effect=AssertionError("never File Explorer"), create=True):
            d = PK.prepare(self.tmp, open_folder=True)
        self.assertEqual(d, self.tmp / "Reference" / "Live pick")
        bind_sample.write(d / "Pick.Report" / "definition.pbir", {"version": "4.0", "datasetReference": {
            "byConnection": {"connectionString": BD.connection_string("Sample Workspace", "Example Live", TB.MID)}}})
        self.assertEqual(SR.detect(self.tmp)["path"], "starter layouts", "the pick is not an existing report")
        self.assertEqual(PK.picked(self.tmp)[1], "Example Live")
        r = pbik("bind", "picker", "--scan", "--root", self.tmp)
        self.assertNotIn("Command Palette", r.stdout)
        self.assertNotIn("Example Live'", r.stdout)

    def test_pbik_open_names_the_folder_and_opens_nothing(self):
        r = pbik("open", "--root", self.tmp) if "--root" in pbik("open", "--help").stdout else pbik("open", cwd=self.tmp)
        self.assertNotIn("File Explorer", r.stdout)


class ThemeAlwaysTests(Tmp):
    """6. The theme is applied with every build, also when layout.json doesn't name it."""

    def test_build_applies_the_project_theme(self):
        import test_walkthrough as TW
        p = TW.project(self.tmp)
        (p / "design" / "themes").mkdir(parents=True)
        shutil.copy2(KIT / "design" / "themes" / "pbip-polish.json", p / "design" / "themes" / "pbip-polish.json")
        lay = json.loads((p / "design/specs/layout.json").read_text(encoding="utf-8"))
        lay.pop("theme", None)
        (p / "design/specs/layout.json").write_text(json.dumps(lay), encoding="utf-8")
        ST.update(p, done="plan")
        r = pbik("build", "Demo", "design/specs/layout.json", cwd=p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rep = json.loads((p / "Demo.Report/definition/report.json").read_text(encoding="utf-8"))
        self.assertIn("customTheme", rep["themeCollection"], "the theme is on the report")
        st = ST.read(p)
        self.assertIn("theme", st["done"])
        self.assertIn("build", st["done"])
        self.assertNotIn("next is the colours", ST.line(p))
        self.assertIn("No changes", pbik("build", "Demo.Report", "design/specs/layout.json", cwd=p).stdout)

    def test_polish_and_plan_approval_put_the_theme_in_the_plan(self):
        from pbikit import polish as PO
        (self.tmp / "design" / "specs").mkdir(parents=True)
        (self.tmp / "design" / "themes").mkdir(parents=True)
        (self.tmp / "design" / "themes" / "pbip-polish.json").write_text("{}", encoding="utf-8")
        (self.tmp / "design/specs/layout.json").write_text(json.dumps({"pages": {}, "visuals": []}), encoding="utf-8")
        said, _ = PO.run(self.tmp)
        self.assertEqual(json.loads((self.tmp / "design/specs/layout.json").read_text(encoding="utf-8"))["theme"],
                         "design/themes/pbip-polish.json")
        self.assertIn("the project's theme applied to the report", said)


class DesktopWindowTests(Tmp):
    """7. One Desktop window, the one the kit opened; reload or close it only when its only marks are its own."""

    def setUp(self):
        super().setUp()
        rep = self.tmp / "Demo.Report"
        (rep / "definition").mkdir(parents=True)
        (rep / "definition" / "report.json").write_text("{}", encoding="utf-8")
        self.pbip = self.tmp / "Demo.pbip"
        self.pbip.write_text("{}", encoding="utf-8")
        self.started = []

    def open(self, before, after, state=None):
        from pbikit import desktop as D
        seq = [before, after]
        return D.open_report(self.tmp, self.pbip, start=self.started.append,
                             pids=lambda: seq.pop(0) if len(seq) > 1 else seq[0], ready=lambda b: True,
                             read_state=lambda: state or {"isDirty": True, "pages": 1}, settle=lambda s: None)

    def test_opens_once_and_records_the_window(self):
        from pbikit import desktop as D
        code, lines = self.open([], [4100])
        self.assertEqual((code, self.started), (0, [self.pbip]))
        rec = S.read_json(D.record_file(self.tmp))
        self.assertEqual(rec["pid"], 4100)
        self.assertTrue(rec["opened"])
        st = {"isDirty": True, "pages": 1}
        self.assertIsNone(D.why_not_close(self.tmp, self.tmp / "Demo.Report", st, pids=[4100]),
                          "only Desktop's on-open marks: the kit may reload or close it")
        self.assertIn("changed", D.why_not_close(self.tmp, self.tmp / "Demo.Report", {"isDirty": True, "pages": 2},
                                                 pids=[4100]))
        code, lines = self.open([4100], [4100])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.started), 1, "never a second window: the kit's own is used")
        self.assertIn("already has the report open", lines[0])

    def test_another_desktop_window_is_never_doubled(self):
        code, lines = self.open([999], [999])
        self.assertEqual(code, 4)
        self.assertEqual(self.started, [])
        self.assertIn("won't open a second one", lines[0])
        self.assertNotIn("`", lines[0])


class StatusTests(Tmp):
    """13. Each stage updates the status file itself; "Where am I?" is right after the build and after a switch."""

    def test_mark_only_in_a_project(self):
        self.assertIsNone(ST.mark(self.tmp, "build"))
        self.assertFalse(ST.status_file(self.tmp).exists())
        for d in ("start", "model", "page purpose", "plan"):
            ST.update(self.tmp, done=d)
        ST.mark(self.tmp, "theme", "build")
        ST.mark(self.tmp, "checks")
        ST.mark(self.tmp, "polish", "result")
        line = ST.line(self.tmp)
        self.assertIn("past the result", line)
        self.assertIn("switching to the live model", line)


# ---------------------------------------------------------------- MEDIUM 8-12, 14-17
class ApprovalWindowTests(Tmp):
    """8. Every approval window: the summary first, one screen; the full list behind "Show details"."""

    def test_model_window_summary_and_details(self):
        import test_phase1 as T1
        T1.big_project(self.tmp)
        doc = GT.prepare("synth-approve", self.tmp)
        lines = doc["summary"].splitlines()
        self.assertLessEqual(len(lines), 10, "one screen")
        self.assertTrue(lines[0].startswith("Model Example Big: 66 tables"))
        self.assertTrue(any(x.startswith("92 handled automatically: ") for x in lines))
        self.assertTrue(any(x.startswith("20 option table(s) keep their labels, e.g. ") for x in lines))
        self.assertIn("0 need you.", lines)
        self.assertTrue(any(x.startswith("No real data is copied") for x in lines))
        self.assertNotIn("Choice 1", json.dumps(doc), "the agent's prepared file never holds the labels")
        shown = []
        GT.run("synth-approve", self.tmp, dialog=lambda t, x, code=False, details="": shown.append((x, details))
               or "no", out=QUIET)
        text, details = shown[0]
        self.assertIn("e.g. Option 01 (Choice 1, Choice 2); Option 02 (Choice 1, Choice 2, Choice 3 +1 more)", text)
        rows = details.splitlines()
        self.assertEqual(len(rows), 20, "one line per option table")
        self.assertEqual(rows[9], "Option 10: 20 row(s): Choice 1, Choice 2, Choice 3 +17 more")

    def test_every_window_puts_long_lists_behind_details(self):
        S.write_json(self.tmp / "design/specs/bind-map.json", {"tables": {f"T{i}": f"Live {i}" for i in range(40)},
                                                              "fields": {}})
        with mock.patch("pbikit.bind.map_hash", lambda m: "h"):
            doc = GT.prepare("map-approve", self.tmp)
        self.assertEqual(len(doc["summary"].splitlines()), 1)
        self.assertEqual(len(doc["details"].splitlines()), 40)
        self.assertIn("Show details", GT.DIALOG_PS)
        self.assertIn("$sd.Visible = [bool]$details", GT.DIALOG_PS)


class ScopedAnswerTests(Tmp):
    """11. The answer for the typed-in target tables never changes the option tables."""

    def test_every_answer_leaves_option_tables_kept(self):
        import test_phase1 as T1
        T1.big_project(self.tmp, resolve=False)
        S.resolve(self.tmp, "enter-data", "synthesize", every=True, out=QUIET)
        c = S.read_json(self.tmp / "design/specs/contract.json")
        opts = [f for f in c["flags"] if f["table"].startswith("Option")]
        self.assertEqual(len(opts), 20)
        self.assertTrue(all(f["resolution"] == S.KEEP_ROWS for f in opts), "option tables keep their labels")
        self.assertTrue(all(f["resolution"] == "synthesize" for f in c["flags"]
                            if f["table"].startswith("Manual Targets")))
        T1.BM.write(self.tmp / "src", "tmdl")                # the model read again: the saved answer stays scoped
        S.contract(self.tmp / "src", self.tmp)
        c = S.read_json(self.tmp / "design/specs/contract.json")
        self.assertTrue(all(f["resolution"] == S.KEEP_ROWS for f in c["flags"] if f["table"].startswith("Option")))


class LowerIsBetterTests(Tmp):
    """10. "Lower is better" per measure: ▼ is green for returns and costs, in the measures and the picture."""

    def layout(self, lower=None):
        lay = {"pages": {"P1": {}}, "visuals": [
            {"id": "P1-V01", "name": "returns", "page": "P1", "type": "cardVisual", "x": 32, "y": 96, "w": 444,
             "h": 160, "bindings": {"Data": ["[Returns]"]},
             "referenceLabels": {"labels": [{"title": "vs last year", "value": "[Returns vs LY]"}]}},
            {"id": "P1-V02", "name": "sales", "page": "P1", "type": "cardVisual", "x": 500, "y": 96, "w": 444,
             "h": 160, "bindings": {"Data": ["[Sales]"]},
             "referenceLabels": {"labels": [{"title": "vs last year", "value": "[Sales vs LY]"}]}}]}
        if lower is not None:
            lay["lowerIsBetter"] = lower
        planned = {"Returns vs LY": {"table": "_Measures", "expression": "DIVIDE ( [Returns] - CALCULATE ( [Returns], "
                                     "SAMEPERIODLASTYEAR ( 'Calendar'[Date] ) ), 1 )"},
                   "Sales vs LY": {"table": "_Measures", "expression": "DIVIDE ( [Sales] - CALCULATE ( [Sales], "
                                   "SAMEPERIODLASTYEAR ( 'Calendar'[Date] ) ), 1 )"}}
        return lay, planned

    def test_returns_fall_is_green_and_the_picture_agrees(self):
        from pbikit import polish as PO
        sys.path.insert(0, str(KIT / "design" / "scripts"))
        import example_values as EV
        lay, planned = self.layout()
        said, notes = PO.polish(lay, {"colors": {"good": "#00AA00", "bad": "#AA0000"}}, planned)
        self.assertIn("Returns", lay["lowerIsBetter"])
        self.assertTrue(any("lower is better for Returns" in n for n in notes))
        self.assertIn('[Returns vs LY] <= 0, "#00AA00"', planned["Returns vs LY colour"]["expression"])
        self.assertIn('[Sales vs LY] >= 0, "#00AA00"', planned["Sales vs LY colour"]["expression"])
        r_lab = lay["visuals"][0]["referenceLabels"]["labels"][0]
        self.assertTrue(r_lab["lowerIsBetter"])
        for v, lower in ((lay["visuals"][0], True), (lay["visuals"][1], False)):
            e = EV.for_visual(v)
            det = e["refDetails"][0]
            up = det["text"].startswith("▲")
            self.assertEqual(det["good"], up != lower, (v["id"], det))

    def test_the_setting_wins_and_is_kept_on_a_second_run(self):
        from pbikit import polish as PO
        lay, planned = self.layout({"Returns": False})
        PO.polish(lay, {}, planned)
        self.assertIn(">= 0", planned["Returns vs LY colour"]["expression"], "the person said higher is better")
        lay["lowerIsBetter"] = {"Returns": True}
        PO.polish(lay, {}, planned)
        self.assertIn("<= 0", planned["Returns vs LY colour"]["expression"], "a changed setting reaches the measure")


class KitFixesKeepTheOkTests(Tmp):
    """12. A taller table or slicer after the OK, and the visuals it nudges down, need no new OK."""

    def test_taller_table_needs_no_new_ok(self):
        from pbikit import plan as PL
        (self.tmp / "design" / "specs").mkdir(parents=True)
        lay = {"pages": {"P1": {"displayName": "Orders"}}, "visuals": [
            {"id": "P1-V01", "page": "P1", "type": "tableEx", "x": 32, "y": 96, "w": 900, "h": 300,
             "bindings": {"Values": ["[Orders]"]}},
            {"id": "P1-V02", "page": "P1", "type": "barChart", "x": 32, "y": 420, "w": 900, "h": 300,
             "bindings": {"Y": ["[Orders]"]}}]}
        lf = self.tmp / "design/specs/layout.json"
        lf.write_text(json.dumps(lay), encoding="utf-8")
        PL.save(PL.plan_file(self.tmp), {"purposes": {"P1": "orders"}})
        PL.approve(self.tmp)
        lay["visuals"][0]["h"] = 420                         # the kit's table fix: taller
        lay["visuals"][1]["y"] = 540                         # the chart below nudged down
        lf.write_text(json.dumps(lay), encoding="utf-8")
        self.assertEqual(PL.changes_since_approval(self.tmp), [])
        self.assertFalse(PL.changed_since_approval(self.tmp))
        lay["visuals"][1]["x"] = 980                         # a real move: another column
        lf.write_text(json.dumps(lay), encoding="utf-8")
        self.assertEqual(PL.changes_since_approval(self.tmp), ["P1-V02 moved"])


class PlainWordsTests(Tmp):
    """14. No VS Code-only steps, no File Explorer, raw Desktop errors in plain words."""

    def test_raw_desktop_errors_are_translated(self):
        from pbikit import desktop as D, summary as SM
        self.assertEqual(D.plain_desktop_error("System.TimeoutException: The operation has timed out.\n at X"),
                         "error: Power BI Desktop didn't answer in time. I'll check it before going on.")
        self.assertIn("couldn't do that step", D.plain_desktop_error("HRESULT 0x80004005"))
        code, js = SM.run_json("desktop reload", lambda: (print(D.plain_desktop_error("weird")),
                                                         print("[raw] HRESULT 0x80004005"), 1)[-1])
        doc = json.loads(js)
        self.assertNotIn("HRESULT", json.dumps({k: doc[k] for k in ("facts", "needs", "next")}))
        self.assertIn("[raw] HRESULT 0x80004005", doc["agent"]["raw"])

    def test_no_vs_code_only_steps_or_file_explorer_in_what_pbik_says(self):
        import re as _re
        for f in (HERE.parent / "pbikit").glob("*.py"):
            text = f.read_text(encoding="utf-8")
            for m in _re.finditer(r"(?:print|out)\((?:f?\"|f?')([^\n]*)", text):
                self.assertNotIn("Command Palette", m.group(1), f.name)
                self.assertNotIn("Run Task", m.group(1), f.name)
            self.assertNotRegex(text, r"os\.startfile\(str\((?:folder|d)\)\)", f.name)


class ReportNameTests(Tmp):
    """15. A sensible report name, not the folder's."""

    def test_names(self):
        from pbikit import projectsetup as PS
        root = self.tmp / "Orders Guided"
        (root / "Reference").mkdir(parents=True)
        self.assertEqual(PS.report_name(root), ("Orders Guided", "the folder name"))
        (root / "Reference" / "needs.md").write_text("# Returns check: requirements\n\ntext", encoding="utf-8")
        self.assertEqual(PS.report_name(root), ("Returns check", "the requirements' heading"))
        (root / "Reference" / "Orders overview.html").write_text(
            "<html><head><title>Orders overview - wireframe</title></head></html>", encoding="utf-8")
        self.assertEqual(PS.report_name(root), ("Orders overview", "the wireframe's title"))
        ST.update(root, reportName="Order health")
        self.assertEqual(PS.report_name(root)[0], "Order health")
        bare = self.tmp / "Copy of pbip-kit"
        (bare / "design" / "specs").mkdir(parents=True)
        S.write_json(bare / "design/specs/contract.json", {"model": "Example Big"})
        self.assertEqual(PS.report_name(bare), ("Example Big report", "the model's name"))


class StricterScoreTests(Tmp):
    """16. Interactions "not checked" unless tested; lost elements; last-year comparisons without a year."""

    def test_item_7_needs_how_it_was_tested(self):
        from pbikit import score as SC
        self.assertEqual(SC.parse_items(["7=pass"]), {7: True})
        self.assertEqual(SC.parse_items(["7=pass:clicked Region, cards changed"]), {7: "clicked Region, cards changed"})
        self.assertEqual(SC.parse_items(["1=pass", "3=no"]), {1: True, 3: False})

    def test_lost_total_row_and_comparison_line(self):
        from pbikit import score as SC
        rep = self.tmp / "R.Report"
        vf = rep / "definition/pages/p1/visuals/P1-V01_t/visual.json"
        vf.parent.mkdir(parents=True)
        vf.write_text(json.dumps({"visual": {"visualType": "tableEx", "objects": {"total": [{"properties": {
            "totals": {"expr": {"Literal": {"Value": "false"}}}}}]}}}), encoding="utf-8")
        (rep / "definition/pages/p1/visuals/P1-V02_c").mkdir(parents=True)
        (rep / "definition/pages/p1/visuals/P1-V02_c/visual.json").write_text(
            json.dumps({"visual": {"visualType": "cardVisual"}}), encoding="utf-8")
        approved = {"visuals": [{"id": "P1-V01", "type": "tableEx"},
                                {"id": "P1-V02", "type": "cardVisual", "referenceLabels": {"labels": [{"value": "[LY]"}]}},
                                {"id": "P1-V03", "type": "barChart"}]}
        now = {"visuals": [{"id": "P1-V01", "type": "tableEx"}, {"id": "P1-V02", "type": "cardVisual"}]}
        lost = SC.lost_since_approval(rep, now, approved)
        self.assertEqual(lost, ["P1-V01 lost its total row", "P1-V02 lost its comparison line",
                                "P1-V03 (barChart) is gone"])

    def test_last_year_without_a_year_is_flagged(self):
        from pbikit import score as SC
        lay = {"pages": {"P1": {}}, "visuals": [
            {"id": "P1-V01", "page": "P1", "type": "cardVisual",
             "referenceLabels": {"labels": [{"title": "last year", "value": "[Sales LY]"}]}}]}
        self.assertFalse(SC.year_chosen(lay, "P1"))
        lay["visuals"].append({"id": "P1-V02", "page": "P1", "type": "advancedSlicerVisual",
                               "bindings": {"Values": ["Calendar[Year]"]}})
        self.assertTrue(SC.year_chosen(lay, "P1"))


class InteractionCountTests(Tmp):
    """17. Every message and every window answer counts once."""

    def test_hook_window_and_agent_notes(self):
        hook = KIT / "tools" / "hooks" / "count_messages.py"
        run = lambda: subprocess.run([sys.executable, str(hook)], input=json.dumps({"cwd": str(self.tmp)}),  # noqa
                                     capture_output=True, text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": ""})
        run()
        self.assertEqual(STP.interactions(self.tmp), [], "not a project yet: nothing counted")
        ST.update(self.tmp, done="start")
        for _ in range(3):
            self.assertEqual(run().returncode, 0)
        STP.interaction(self.tmp, "reply")                       # the agent's own note: not counted twice
        STP.interaction(self.tmp, "window: Approve the model", source="window")
        STP.interaction(self.tmp, "window: Approve the model")   # the agent's window note: not counted twice
        got = [w for w, _ in STP.interactions(self.tmp)]
        self.assertEqual(got, ["message", "message", "message", "window: Approve the model"])

    def test_without_the_hook_the_agent_counts(self):
        STP.interaction(self.tmp, "reply")
        STP.interaction(self.tmp, "reply")
        self.assertEqual(len(STP.interactions(self.tmp)), 2)

    def test_the_hook_is_registered(self):
        d = json.loads((KIT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("count_messages.py", json.dumps(d["hooks"]["UserPromptSubmit"]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
