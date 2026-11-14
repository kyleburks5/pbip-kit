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


# ---------------------------------------------------------------- MEDIUM 5: quick build approval
WT = {"pages": {"P1": {"displayName": "Orders overview"}},
      "visuals": [
          {"id": "P1-V01", "name": "slicer", "page": "P1", "type": "slicer", "x": 1599, "y": 24, "w": 289, "h": 56,
           "bindings": {"Values": ["Dim Region[Region Name]"]}},
          {"id": "P1-V02", "name": "orders-amount", "page": "P1", "type": "cardVisual", "x": 32, "y": 120, "w": 446,
           "h": 160, "container": {"title": "Orders amount"}, "bindings": {"Data": ["_Measures[Fact Orders Amount]"]},
           "referenceLabels": {"labels": [{"title": "vs last year", "value": "_Measures[Orders Amount vs LY %]"}]}},
          {"id": "P1-V03", "name": "regions", "page": "P1", "type": "tableEx", "x": 32, "y": 760, "w": 1856,
           "h": 288, "bindings": {"Values": ["Dim Region[Region Name]", "_Measures[Fact Orders Amount]",
                                             "_Measures[Orders Amount vs LY %]", "_Measures[Fact Orders Qty]",
                                             "_Measures[Fact Orders Avg]", "_Measures[Fact Returns Amount]",
                                             "_Measures[Returns Share %]"]}}]}


class ApprovalTests(Tmp):
    def setUp(self):
        super().setUp()
        from pbikit import status as ST
        self.ST = ST
        self.lf = self.tmp / "design" / "specs" / "layout.json"
        self.lf.parent.mkdir(parents=True)
        self.lf.write_text(json.dumps(WT), encoding="utf-8")
        PL.show(self.tmp, purposes={"P1": "Are orders growing?"}, shoot=lambda h, png, *a: png.write_bytes(b"x"),
                measure=lambda h: [])
        PL.approve(self.tmp)
        ST.update(self.tmp, mode="quick")

    def change(self, fn):
        lay = json.loads(self.lf.read_text(encoding="utf-8"))
        fn({v["id"]: v for v in lay["visuals"]}, lay)
        self.lf.write_text(json.dumps(lay), encoding="utf-8")

    def test_the_kits_own_changes_keep_the_ok(self):
        def polish(v, lay):
            v["P1-V01"]["h"] = 76                                          # the slicer made taller (S-03)
            v["P1-V02"]["props"] = {"label.show@default": False, "value.labelDisplayUnits@default": 1000000}
            v["P1-V02"]["bindings"]["Data"] = [{"field": "_Measures[Fact Orders Amount]", "displayName": "Orders"}]
            v["P1-V03"]["columnWidths"] = "fit"
            v["P1-V02"]["container"]["title"] = "Orders amount (all years)"
        self.change(polish)
        self.assertFalse(PL.changed_since_approval(self.tmp))

    def test_changes_to_what_was_approved_need_it_again(self):
        self.change(lambda v, lay: v["P1-V02"]["bindings"].update(Data=["_Measures[Fact Orders Qty]"]))
        self.assertTrue(PL.changed_since_approval(self.tmp))
        self.assertIn("P1-V02 shows different numbers", PL.changes_since_approval(self.tmp))
        self.change(lambda v, lay: lay["visuals"].pop())
        self.assertIn("the tableEx P1-V03 is gone", PL.changes_since_approval(self.tmp))

    def test_quick_build_never_says_pause(self):
        for stage in ("plan", "theme", "build", "checks", "polish"):
            self.ST.update(self.tmp, done=stage)
            self.assertNotIn("Pause here", self.ST.line(self.tmp))
        self.ST.update(self.tmp, mode="guided")
        self.assertIn("Pause here", self.ST.line(self.tmp))


# ---------------------------------------------------------------- MEDIUM 6: checks
class CleanBuildTests(Tmp):
    def test_main_flow_spec_satisfies_the_id_checks(self):
        p = project(self.tmp)
        lay = json.loads((p / "design" / "specs" / "layout.json").read_text(encoding="utf-8"))
        PL.show(p, purposes={"P1": "Is the amount growing?"}, shoot=lambda h, png, *a: png.write_bytes(b"x"),
                measure=lambda h: [])
        PL.approve(p)
        spec = (p / "design" / "specs" / "spec.md").read_text(encoding="utf-8")
        for v in lay["visuals"]:
            self.assertIn(v["id"], spec)
        self.assertIn("## Fallback register", spec)
        r = pbik("build", "Demo", "design/specs/layout.json", cwd=p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        shutil.copytree(KIT / "design" / "scripts", p / "design" / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__", "test_*"))
        a = subprocess.run([sys.executable, str(p / "design" / "scripts" / "audit_ids.py")], cwd=p,
                           capture_output=True, text=True, encoding="utf-8")
        out = a.stdout + a.stderr
        self.assertIn("main flow", out)
        self.assertEqual([x for x in out.splitlines() if "spec:" in x and "main flow" not in x], [], out)

    def test_a_clean_build_reports_no_problems(self):
        p = project(self.tmp)
        f = p / "design" / "specs" / "layout.json"
        lay = json.loads(f.read_text(encoding="utf-8"))
        for v in lay["visuals"]:
            v.setdefault("container", {})["altText"] = f"{v['name']} (made-up sample)"
            if v["type"] in ("lineChart", "barChart"):
                v["sort"] = {"field": v["bindings"]["Category"][0], "direction": "Ascending"}
        f.write_text(json.dumps(lay), encoding="utf-8")
        self.assertEqual(pbik("build", "Demo", "design/specs/layout.json", cwd=p).returncode, 0)
        r = pbik("validate", "Demo.Report", "--layout", "design/specs/layout.json", cwd=p)
        self.assertIn("0 error(s), 0 warning(s)", r.stdout, r.stdout)

    def test_unpublished_schema_and_confirmed_writes_are_notes(self):
        from pbikit import validate as V, catalog as CAT
        self.assertTrue(V._newer_than_published(
            "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/99.0.0/schema.json"))
        self.assertFalse(V._newer_than_published(
            "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json"))
        self.assertTrue(CAT.confirmed("cardVisual referenceLabelTitle.titleText never seen in a Desktop-saved file"))
        self.assertFalse(CAT.confirmed("cardVisual value.madeUp never seen in a Desktop-saved file"))

    def test_score_compares_measures_by_name(self):
        from pbikit import score as SC
        self.assertEqual(SC._fields({"Data": ["_Measures[Orders]"]}), SC._fields({"Data": ["[Orders]"]}))
        self.assertNotEqual(SC._fields({"Data": ["_Measures[Orders]"]}), SC._fields({"Data": ["[Qty]"]}))


# ---------------------------------------------------------------- MEDIUM 7: plan list and picture
class PlanListTests(Tmp):
    def setUp(self):
        super().setUp()
        self.lf = self.tmp / "design" / "specs" / "layout.json"
        self.lf.parent.mkdir(parents=True)
        self.lf.write_text(json.dumps(WT), encoding="utf-8")

    def show(self, **kw):
        return PL.show(self.tmp, purposes={"P1": "Are orders growing?"},
                       shoot=lambda h, png, *a: png.write_bytes(b"x"), **kw)

    def test_compared_with_last_year_and_plain_names(self):
        text = self.show(measure=lambda h: [])[1]
        self.assertIn("| Orders amount | Fact Orders Amount | last year |", text)
        self.assertNotIn("_Measures[", text)
        self.assertNotIn("field, labels", text)

    def test_assumptions_reset_on_each_redraw(self):
        self.show(assumptions=["first"], measure=lambda h: [])
        text = self.show(assumptions=["second"], measure=lambda h: [])[1]
        self.assertIn("- second", text)
        self.assertNotIn("- first", text)

    def test_contrast_is_checked_on_the_picture(self):
        notes = []
        rows = [{"text": "Orders amount", "id": "P1-V07", "ratio": 3.53, "need": 4.5}]
        text = self.show(measure=lambda h: rows, notes=notes)[1]
        self.assertIn("Too faint to read", text)
        self.assertTrue(any("3.5:1" in n for n in notes))

    def test_preview_draws_example_values_every_column_and_no_raw_names(self):
        import example_values as EV
        d = EV.data_for(WT)["visuals"]
        table = d["P1-V03"]
        self.assertEqual(table["groups"], ["Region Name"])
        self.assertEqual(len(table["values"]), 6, "every measure column, not 2 of 7")
        self.assertTrue(all(isinstance(x, float) for x in table["rows"][0][1:]))
        self.assertEqual(d["P1-V02"]["refs"][0][0] in "+-", True)
        page = subprocess.run([sys.executable, str(KIT / "design" / "scripts" / "gen_wireframe_hf.py"), "--layout",
                               str(self.lf), "--tokens", str(KIT / "design" / "tokens.json"), "--data", "example",
                               "--out", str(self.tmp / "p.html"), "--vega", "offline"], capture_output=True, text=True)
        self.assertEqual(page.returncode, 0, page.stderr)
        html_ = (self.tmp / "p.html").read_text(encoding="utf-8")
        self.assertIn("Example values", html_)
        self.assertIn('"measure": true', html_)

    def test_months_in_calendar_order(self):
        import example_values as EV
        self.assertEqual(EV.categories("Month")[:3], ["Jan", "Feb", "Mar"])
        self.assertEqual(EV.categories("Region Name")[0], "Region 1")

    def test_wireframe_cards_are_named_by_label_not_number(self):
        import ref_layout as RL                                         # noqa: F401  (the JS is checked below)
        src = (KIT / "design" / "scripts" / "ref_layout.py").read_text(encoding="utf-8")
        self.assertIn("label: lab", src)
        self.assertIn('m.get("label") or m.get("text")', src)


# ---------------------------------------------------------------- MEDIUM 8: polish the kit does itself
class PolishFixTests(Tmp):
    def test_thousands_separators(self):
        from pbikit import synthgen as G
        self.assertEqual(G.thousands("0"), "#,0")
        self.assertEqual(G.thousands("0.00"), "#,0.00")
        self.assertEqual(G.thousands("0.0%"), "0.0%")
        self.assertEqual(G.thousands("#,0"), "#,0")
        self.assertIn("formatString: #,0", "\n".join(G.measure_lines("Orders Qty", {"expression": "1"}, False)))
        self.assertNotIn("formatString", "\n".join(G.measure_lines("Returns Share %", {"expression": "1"}, False)))

    def test_month_sorts_by_month_number(self):
        from pbikit import synthgen as G
        c = {"tables": {"Calendar": {"columns": {"Date": {"type": "dateTime"}, "Month": {"type": "string"},
                                                 "Month No": {"type": "int64"}}}}}
        g = {"slice": {"Calendar": {"columns": ["Date", "Month"], "measures": []}}}
        said = G.month_sorts(c, g)
        self.assertEqual(c["tables"]["Calendar"]["columns"]["Month"]["sortBy"], "Month No")
        self.assertIn("Month No", g["slice"]["Calendar"]["columns"])
        self.assertIn("month order", said[0])
        c2 = {"tables": {"Calendar": {"columns": {"Month": {"type": "string"}}}}}
        said = G.month_sorts(c2, {"slice": {"Calendar": {"columns": ["Month"], "measures": []}}})
        self.assertIn("no month-number column", said[0])

    def test_number_headers_right_aligned(self):
        p = project(self.tmp)
        lay = json.loads((p / "design" / "specs" / "layout.json").read_text(encoding="utf-8"))
        lay["visuals"].append({"id": "P1-V06", "name": "areas", "page": "P1", "type": "tableEx", "x": 500, "y": 640,
                               "w": 900, "h": 300, "bindings": {"Values": ["Area[Area Name]", "[Total Amount]"]}})
        (p / "design" / "specs" / "layout.json").write_text(json.dumps(lay), encoding="utf-8")
        r = pbik("build", "Demo", "design/specs/layout.json", cwd=p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = json.loads(next(p.glob("Demo.Report/definition/pages/*/visuals/P1-V06_*/visual.json")).read_text(
            encoding="utf-8"))
        cf = d["visual"]["objects"]["columnFormatting"]
        right = [e["selector"]["metadata"] for e in cf if e["properties"].get("alignment")]
        self.assertEqual(len(right), 1)
        self.assertIn("Total Amount", right[0])
        self.assertEqual(cf[0]["properties"]["styleHeader"]["expr"]["Literal"]["Value"], "true")
        tf = p / "design" / "tokens.json"                    # an older rep's tokens: builds exactly as before
        t = json.loads(tf.read_text(encoding="utf-8"))
        t["table"].pop("alignNumberHeaders")
        tf.write_text(json.dumps(t), encoding="utf-8")
        self.assertEqual(pbik("build", "Demo", "design/specs/layout.json", cwd=p).returncode, 0)
        d = json.loads(next(p.glob("Demo.Report/definition/pages/*/visuals/P1-V06_*/visual.json")).read_text(
            encoding="utf-8"))
        self.assertNotIn("columnFormatting", d["visual"].get("objects", {}))


# ---------------------------------------------------------------- MEDIUM 9: Desktop updated
class DesktopUpdateTests(Tmp):
    def test_a_changed_desktop_runs_the_after_update_checks_first(self):
        from pbikit import versions as VS
        md = self.tmp / "VERSIONS.md"
        md.write_text("| Power BI Desktop | 2.159.883.0 (Microsoft Store), /smoke 2026-10-23 | x | Yes |\n",
                      encoding="utf-8")
        self.assertEqual(VS.tested_desktop(md), "2.159.883.0")
        buf = io.StringIO()
        with __import__("contextlib").redirect_stdout(buf):
            code = VS.check(self.tmp / "project.json", "2.159.1231.0", versions_md=md)
        self.assertEqual(code, VS.UPDATED)
        self.assertIn("2.159.883.0 to 2.159.1231.0", buf.getvalue())
        self.assertIsNone(VS.update_check("2.159.883.0", md))


# ---------------------------------------------------------------- one folder = one project
def git(folder, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=folder,
                          capture_output=True, text=True)


def mini_kit(root):
    """A small stand-in for the master kit: CLAUDE.md, the pbik package folder, a master-only file, its own git."""
    (root / "tools" / "pbik" / "pbikit").mkdir(parents=True)
    (root / "tools" / "pbik" / "pbikit" / "__init__.py").write_text("", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# kit\n", encoding="utf-8")
    (root / "tools" / "export_check.py").write_text("# master only\n", encoding="utf-8")
    (root / "tools" / "master-only.txt").write_text("# list\ntools/export_check.py\n", encoding="utf-8")
    (root / ".gitignore").write_text("projects/\n.pbik/\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "kit")
    return root


class OneFolderTests(Tmp):
    def setUp(self):
        super().setUp()
        from pbikit import projectsetup as PS, status as ST
        self.PS, self.ST = PS, ST
        self.kit = mini_kit(self.tmp / "kit")
        PS.mark_master(self.kit)

    def test_master_copy_and_project_are_told_apart(self):
        self.assertEqual(self.PS.kind(self.kit), "master")
        copy = self.tmp / "Orders Dashboard"
        shutil.copytree(self.kit, copy)                         # a File Explorer copy: the marker comes along
        self.assertEqual(self.PS.kind(copy), "fresh copy")
        said = []
        self.ST.show(self.kit, out=said.append)
        self.assertIn("This is the master kit", said[0])
        said = []
        self.ST.show(copy, out=said.append)
        self.assertIn("fresh copy of the kit", said[0])
        with self.assertRaises(self.PS.SetupError):
            self.PS.setup(self.kit, out=lambda *a: None)

    def test_setup_turns_a_copy_into_the_project(self):
        copy = self.tmp / "Orders Dashboard"
        r = git(self.tmp, "clone", "-q", str(self.kit), str(copy))      # a clone: origin is the master
        self.assertEqual(r.returncode, 0, r.stderr)
        (copy / "projects" / "Old").mkdir(parents=True)                # left over from the old setup: never deleted
        said = []
        self.PS.setup(copy, out=said.append)
        self.assertEqual(self.PS.kind(copy), "project")
        for name in ("Model", "Reference"):
            self.assertTrue((copy / name / "README.txt").exists())
        self.assertFalse((copy / "tools" / "export_check.py").exists(), "master-only files go")
        self.assertTrue((self.kit / "tools" / "export_check.py").exists(), "the master keeps them")
        self.assertTrue((copy / "projects" / "Old").is_dir())
        self.assertEqual(git(copy, "remote").stdout.split(), ["kit"], "nothing is pushed to the master by mistake")
        self.assertIn("project start", git(copy, "log", "-1", "--format=%s").stdout)
        self.assertEqual(git(copy, "status", "--porcelain").stdout.strip(), "")
        doc = self.ST.read(copy)
        self.assertEqual((doc["project"], doc["dataClass"]), ("Orders Dashboard", "restricted"))
        text = " ".join(said)
        self.assertIn("Model", text)
        self.assertIn("Reference", text)
        self.assertNotIn("\\", text)
        with self.assertRaises(self.PS.SetupError):
            self.PS.setup(copy, out=lambda *a: None)

    def test_a_plain_copy_gets_its_own_git(self):
        copy = self.tmp / "Plain Copy"
        shutil.copytree(self.kit, copy, ignore=shutil.ignore_patterns(".git"))
        self.PS.setup(copy, out=lambda *a: None)
        self.assertTrue((copy / ".git").is_dir())
        self.assertEqual(git(copy, "rev-list", "--count", "HEAD").stdout.strip(), "1")


class DropFolderTests(Tmp):
    def test_start_check_says_what_each_folder_holds_and_opens_nothing(self):
        from pbikit import start as SR
        from unittest import mock
        with mock.patch("os.startfile", create=True, side_effect=AssertionError("File Explorer opened")):
            lines = SR.check(self.tmp)
            self.assertTrue(lines[0].startswith("Model: empty. Put a copy"))
            self.assertIn("Reference: empty", lines[1])
            self.assertIn("Model folder", lines[-1])
            import big_model as BM
            BM.write(self.tmp / "Model", "semanticmodel")
            shutil.copy(HERE.parent.parent.parent / "docs" / "layouts" / "grid.html",
                        self.tmp / "Reference" / "Orders overview.html")
            lines = SR.check(self.tmp)
            self.assertIn("Model: Example Big.SemanticModel", lines[0])
            self.assertIn("Reference: Orders overview.html (a wireframe page), kept in the Reference folder", lines[1])
            self.assertIn("plan", lines[-1])
            SR.open_inputs(self.tmp)
            from pbikit import intake as IN
            IN.open_drop(self.tmp)

    def test_intake_reads_the_model_folder_and_deletes_the_cache_first(self):
        from pbikit import intake as IN, drops
        import big_model as BM
        drops.make(self.tmp)
        BM.write(self.tmp / "Model", "semanticmodel")
        said = []
        r = IN.intake(self.tmp, out=said.append)
        self.assertIn(".pbi/cache.abf", " ".join(r["removed"]))
        self.assertTrue(said[0].startswith("warning: the model folder held"))
        self.assertFalse((self.tmp / "Model" / "Example Big.SemanticModel" / ".pbi").exists())

    def test_old_projects_keep_their_folders(self):
        from pbikit import drops
        old = self.tmp / "design" / "reference" / "model"
        old.mkdir(parents=True)
        self.assertEqual(drops.model_dir(self.tmp), self.tmp / "design" / "reference" / "model")
        self.assertEqual(drops.reference_dir(self.tmp), self.tmp / "Reference")

    def test_the_guard_covers_the_model_folder(self):
        sys.path.insert(0, str(KIT / "tools" / "hooks"))
        import guard_model_folder as G
        ev = lambda tool, inp, cwd="C:/p": G.blocked({"tool_name": tool, "tool_input": inp, "cwd": cwd})  # noqa
        self.assertTrue(ev("Read", {"file_path": "C:/p/Model/x.tmdl"}))
        self.assertTrue(ev("Glob", {"pattern": "**/*", "path": "C:/p/Model"}))
        self.assertTrue(ev("PowerShell", {"command": "Get-ChildItem Model"}))
        self.assertTrue(ev("Bash", {"command": "ls"}, "C:/p/Model"))
        self.assertFalse(ev("PowerShell", {"command": "git commit -m \"Model approved\""}))
        self.assertFalse(ev("Read", {"file_path": "C:/p/Demo.SemanticModel/definition/model.tmdl"}))
        self.assertFalse(ev("PowerShell", {"command": "python tools/pbik/pbik.py model intake"}))

    def test_export_check_keeps_projects_out_of_the_master(self):
        if not (KIT / "tools" / "export_check.py").exists():
            self.skipTest("a project: the export check is master-only")
        sys.path.insert(0, str(KIT / "tools"))
        import export_check as EC
        self.assertEqual(EC.folder_findings(self.tmp), [])
        (self.tmp / "projects" / "Sales").mkdir(parents=True)
        (self.tmp / "Model").mkdir()
        (self.tmp / "Model" / "x.bim").write_text("{}", encoding="utf-8")
        found = EC.folder_findings(self.tmp)
        self.assertEqual(len(found), 2)
        f = {c: [] for c in EC.CHECKS}
        EC.scan_path("Reference/Orders overview.html", [("*", "Reference/*")], f)
        self.assertEqual(f["report projects"], ["Reference/Orders overview.html"])


class ApprovalWindowTests(Tmp):
    """Plain Yes / No unless screen control is active; No and a wrong code change nothing; the window comes forward."""

    def setUp(self):
        super().setUp()
        from unittest import mock
        from pbikit import gates as GT
        sys.path.insert(0, str(HERE))
        import test_phase1 as P1
        self.GT, self.S = GT, P1.S
        P1.big_project(self.tmp)
        self.home = self.tmp / "home"
        env = mock.patch.dict(os.environ, {"PBIK_HOME": str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("PBIK_GATE_CODE", None)
        GT.prepare("synth-approve", self.tmp)

    def screen_control(self):
        import datetime
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "screen-control.json").write_text(json.dumps(
            {"at": datetime.datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")

    def ask(self, answer):
        seen = []
        res = self.GT.run("synth-approve", self.tmp, dialog=lambda t, x, code=False: seen.append(code) or answer,
                          out=lambda *a: None)
        return res, seen[0]

    def test_plain_yes_no_without_screen_control(self):
        self.assertEqual(self.ask("no"), ("declined", False))
        self.assertFalse(self.S.approved(self.S.read_json(self.tmp / "design/specs/contract.json")))
        self.assertEqual(self.ask("yes"), ("approved", False))

    def test_code_only_with_screen_control_and_a_wrong_code_declines(self):
        self.screen_control()
        self.assertEqual(self.ask("code"), ("declined", True))
        r = self.S.read_json(self.tmp / ".pbik/gates/synth-approve.result.json")
        self.assertEqual(r["why"], "the code didn't match three times")
        self.assertFalse(self.S.approved(self.S.read_json(self.tmp / "design/specs/contract.json")))

    def test_the_window_script(self):
        ps = self.GT.DIALOG_PS
        self.assertIn("SetForegroundWindow", ps)
        self.assertIn("$withCode = ($args[2] -eq 'code')", ps)
        self.assertIn("if (-not $withCode) { $script:result = 0", ps)
        with __import__("unittest").mock.patch.dict(os.environ, {"PBIK_GATE_CODE": "1"}):
            self.assertTrue(self.GT.needs_code())


class WalkthroughInputTests(Tmp):
    def test_the_made_up_inputs_fit_together(self):
        sys.path.insert(0, str(KIT / "tools" / "walkthrough"))
        import make_inputs as MI, big_model as BM
        out = MI.make(self.tmp / "inputs")
        html_ = (out / "3 made-up wireframe" / "Orders overview.html").read_text(encoding="utf-8")
        self.assertNotIn("Store", html_)
        for col in MI.TABLE:
            self.assertIn(f">{col}</th>", html_)
        self.assertTrue((out / "1 made-up model" / "Example Big.SemanticModel" / ".pbi" / "cache.abf").exists())
        rels = BM.tmdl_texts()["relationships.tmdl"]
        _, table, key = MI.EXAMPLE_CHANGE
        self.assertIn(f"'Fact Orders'.{key}", rels.replace('"', "'"))
        self.assertIn("Model folder", (out / "README.txt").read_text(encoding="utf-8"))
        doc = " ".join((KIT / "docs" / "PHASE1-WALKTHROUGH.md").read_text(encoding="utf-8").split())
        self.assertIn(MI.EXAMPLE_CHANGE[0], doc)
        self.assertNotIn("rank stores", doc)


if __name__ == "__main__":
    unittest.main(verbosity=1)
