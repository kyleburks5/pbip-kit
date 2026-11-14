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


if __name__ == "__main__":
    unittest.main(verbosity=2)
