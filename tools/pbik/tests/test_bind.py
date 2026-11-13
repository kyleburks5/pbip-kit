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


RENAMES = {"tables": {"Orders": "Order Lines", "Plan Option": "Option Picker"},
           "fields": {("Order Lines", "Amount"): "Net Amount", ("_Measures", "Total Units"): "Units Sold",
                      ("Option Picker", "Option Label"): "Label"}}


def rename_contract(root):
    """The live model, as the contract describes it, uses other names than the synthetic one (made-up renames)."""
    f = root / "design/specs/contract.json"
    c = json.loads(f.read_text(encoding="utf-8"))
    for old, new in RENAMES["tables"].items():
        c["tables"][new] = c["tables"].pop(old)
        for r in c["relationships"]:
            for k in ("from", "to"):
                if r[k].startswith(old + "["):
                    r[k] = new + r[k][len(old):]
    for (t, old), new in RENAMES["fields"].items():
        tb = c["tables"][t]
        for part in ("columns", "measures"):
            if old in tb[part]:
                tb[part][new] = tb[part].pop(old)
    c["approval"] = None
    S.write_json(f, c)
    S.approve(root, "Sample Person", ask=TS.say("Example Live"), out=lambda *a: None)


def read(f):
    return pathlib.Path(f).read_text(encoding="utf-8")


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


class StaleReferenceTests(BindBase):
    """Item 2: names in neither the synthetic model nor the map are stale references, with where they are."""

    def test_stale_references_listed_with_their_place(self):
        v = self.rep / "definition/pages/p1/visuals/P1-V02_amount-by-month/visual.json"
        d = json.loads(read(v))
        d["visual"]["query"]["sortDefinition"]["sort"][0]["field"] = bind_sample.col("Orders", "Old Column")
        bind_sample.write(v, d)
        p = self.rep / "definition/pages/p1/page.json"
        d = json.loads(read(p))
        d["filterConfig"]["filters"].append({"name": "pf2", "field": bind_sample.col("Gone Table", "X"),
                                             "type": "Categorical"})
        bind_sample.write(p, d)
        e = self.rep / "definition/reportExtensions.json"
        d = json.loads(read(e))
        d["entities"][0]["measures"][0]["expression"] = "[Total Units] + [Retired Measure]"
        bind_sample.write(e, d)
        r = self.check()
        self.assertEqual(r.errors, [], "stale references aren't map errors")
        stale = " | ".join(r.stale)
        self.assertIn("P1-V02_amount-by-month/visual.json /visual/query/sortDefinition/sort/0/field/Column: "
                      "Orders[Old Column]", stale)
        self.assertIn("pages/p1/page.json /filterConfig/filters/1/field/Column: Gone Table[X]", stale)
        self.assertIn("reportExtensions.json _Measures[Per Unit]: [Retired Measure]", stale)
        self.assertFalse(r.ok())
        with self.assertRaises(BD.BindError) as cm:
            self.go_live()
        self.assertIn("stale reference", str(cm.exception))


class BindMapTests(BindBase):
    """Item 1: bind-map.json drafted from similar names, approved by a person, applied by bind live everywhere."""

    def setUp(self):
        super().setUp()
        rename_contract(self.root)

    def draft_and_approve(self):
        m = BD.map_draft(self.rep, self.root, out=self.quiet)
        m["acceptDax"] = ["Per Unit"]
        S.write_json(BD.map_file(self.root), m)
        return BD.map_approve(self.rep, "Sample Person", self.root, ask=TS.say("Example Live"), out=self.quiet)

    def test_draft_matches_similar_names(self):
        self.assertTrue(any("not in the contract" in e for e in self.check().errors), "names differ: no map, no bind")
        m = BD.map_draft(self.rep, self.root, out=self.quiet)
        self.assertEqual(m["tables"], {"Orders": "Order Lines", "Plan Option": "Option Picker"})
        self.assertEqual(m["fields"]["Orders[Amount]"], "Net Amount")
        self.assertEqual(m["fields"]["_Measures[Total Units]"], "Units Sold")
        self.assertEqual(m["fields"]["Plan Option[Option Label]"], "Label")
        self.assertEqual(m["unmatched"], [])
        errs = self.check().errors
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("acceptDax", errs[0], "changed DAX fails until it is accepted")

    def test_approve_is_person_only_and_live_needs_it(self):
        BD.map_draft(self.rep, self.root, out=self.quiet)
        with self.assertRaises(BD.BindError):
            self.go_live()                                         # draft, not approved
        with self.assertRaises(BD.BindError):                      # the DAX change isn't accepted: check fails
            BD.map_approve(self.rep, "Sample Person", self.root, ask=TS.say("Example Live"), out=self.quiet)
        m = S.read_json(BD.map_file(self.root))
        m["acceptDax"] = ["Per Unit"]
        S.write_json(BD.map_file(self.root), m)
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), self.assertRaises(DC.Refused):
            BD.map_approve(self.rep, "Sample Person", self.root, out=self.quiet)
        with self.assertRaises(DC.Refused):
            BD.map_approve(self.rep, "Sample Person", self.root, ask=TS.say("Example Synthetic"), out=self.quiet)
        BD.map_approve(self.rep, "Sample Person", self.root, ask=TS.say("Example Live"), out=self.quiet)
        m = S.read_json(BD.map_file(self.root))
        m["fields"]["Orders[Status]"] = "Status"
        S.write_json(BD.map_file(self.root), m)
        with self.assertRaises(BD.BindError):
            self.go_live()                                         # changed after approval

    def test_live_rewrites_every_reference(self):
        self.draft_and_approve()
        self.go_live()
        d = self.rep / "definition"
        line = read(d / "pages/p1/visuals/P1-V02_amount-by-month/visual.json")
        for want in ('"Entity": "Order Lines"', '"Property": "Net Amount"', '"Sum(Order Lines.Net Amount)"',
                     '"displayName": "Sum of Amount"', '"_Measures.Units Sold"', '"displayName": "Total Units"'):
            self.assertIn(want, line)
        slicer = json.loads(read(d / "pages/p1/visuals/P1-V03_option-slicer/visual.json"))
        flt = slicer["visual"]["objects"]["general"][0]["properties"]["filter"]["filter"]
        self.assertEqual(flt["From"][0]["Entity"], "Option Picker")
        self.assertEqual(flt["Where"][0]["Condition"]["In"]["Expressions"][0]["Column"]["Property"], "Label")
        self.assertIn('"Option Picker.Label"', json.dumps(slicer))
        self.assertIn('"Entity": "Order Lines"', read(d / "bookmarks/bm1.bookmark.json"))
        ext = json.loads(read(d / "reportExtensions.json"))
        self.assertEqual(ext["entities"][0]["measures"][0]["expression"],
                         "DIVIDE ( SUM ( 'Order Lines'[Net Amount] ), [Units Sold] )")
        for f in d.rglob("*.json"):
            self.assertNotIn('"Entity": "Orders"', read(f), f)
            self.assertNotIn('"Entity": "Plan Option"', read(f), f)
        self.assertEqual(self.check().errors, [], "the live names are all in the contract")

    def test_live_labels_option(self):
        m = self.draft_and_approve()
        m["liveLabels"] = True
        m["approval"] = None
        S.write_json(BD.map_file(self.root), m)
        BD.map_approve(self.rep, "Sample Person", self.root, ask=TS.say("Example Live"), out=self.quiet)
        self.go_live()
        self.assertNotIn("displayName", read(self.rep / "definition/pages/p1/visuals/P1-V02_amount-by-month/visual.json"))


class LocalRestoreTests(BindBase):
    """Item 3: live -> local through a renamed table and field restores the report byte for byte; files changed while
    live are mapped back; --restore-backup restores everything after a typed confirmation."""

    def setUp(self):
        super().setUp()
        rename_contract(self.root)
        m = BD.map_draft(self.rep, self.root, out=self.quiet)
        m["acceptDax"] = ["Per Unit"]
        S.write_json(BD.map_file(self.root), m)
        BD.map_approve(self.rep, "Sample Person", self.root, ask=TS.say("Example Live"), out=self.quiet)

    def test_round_trip_byte_for_byte(self):
        before = tree(self.rep)
        slicer = "definition/pages/p1/visuals/P1-V03_option-slicer/visual.json"
        self.assertIn('"Entity": "Plan Option"', before[slicer.replace("/", os.sep)].decode())
        self.go_live()
        self.assertIn('"Entity": "Option Picker"', read(self.rep / slicer), "stored slicer filter, renamed table")
        out = BD.local(self.rep, self.root, out=self.quiet, desktop_open=CLOSED)
        self.assertEqual(out["remapped"], [])
        self.assertEqual(before, tree(self.rep))

    def test_files_changed_while_live_are_mapped_back(self):
        before = tree(self.rep)
        self.go_live()
        f = self.rep / "definition/pages/p1/visuals/P1-V02_amount-by-month/visual.json"
        d = json.loads(read(f))
        d["position"]["x"] = 40                                    # a hand polish in Desktop while live
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        out = BD.local(self.rep, self.root, out=self.quiet, desktop_open=CLOSED)
        self.assertEqual(out["remapped"], ["definition/pages/p1/visuals/P1-V02_amount-by-month/visual.json"])
        back = json.loads(read(f))
        self.assertEqual(back["position"]["x"], 40, "the polish is kept")
        text = json.dumps(back)
        for want in ('"Entity": "Orders"', '"Property": "Amount"', '"Sum(Orders.Amount)"', '"_Measures.Total Units"'):
            self.assertIn(want, text)
        self.assertNotIn("displayName", text, "the labels bind live added are gone")
        after = tree(self.rep)
        for k in before:
            if not k.endswith("P1-V02_amount-by-month" + os.sep + "visual.json"):
                self.assertEqual(before[k], after[k], k)

    def test_restore_backup_needs_typed_restore(self):
        before = tree(self.rep)
        self.go_live()
        f = self.rep / "definition/pages/p1/visuals/P1-V02_amount-by-month/visual.json"
        f.write_text(read(f).replace('"x": 32', '"x": 48'), encoding="utf-8")
        (self.rep / "definition/pages/p1/visuals/P1-V09_new").mkdir()
        (self.rep / "definition/pages/p1/visuals/P1-V09_new/visual.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(DC.Refused):
            BD.local(self.rep, self.root, out=self.quiet, desktop_open=CLOSED, restore_backup=True, ask=TS.say("yes"))
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), self.assertRaises(DC.Refused):
            BD.local(self.rep, self.root, out=self.quiet, desktop_open=CLOSED, restore_backup=True)
        BD.local(self.rep, self.root, out=self.quiet, desktop_open=CLOSED, restore_backup=True, ask=TS.say("restore"))
        self.assertEqual(before, {k: v for k, v in tree(self.rep).items()})


class FalseAlarmTests(BindBase):
    """Item 4: virtual-table columns, report-level measures used as filters, recorded type deviations."""

    def set_ext(self, expr):
        e = self.rep / "definition/reportExtensions.json"
        d = json.loads(read(e))
        d["entities"][0]["measures"][0]["expression"] = expr
        bind_sample.write(e, d)

    def test_virtual_table_columns_are_not_model_fields(self):
        self.set_ext(
            'VAR t = ADDCOLUMNS ( VALUES ( Area[Region] ), "@Amt", [Total Amount], "Share", 1 ) '
            'VAR s = SELECTCOLUMNS ( t, "Picked", [@Amt] ) '
            'VAR g = SUMX ( GENERATESERIES ( 1, 3 ), [Value] ) '
            'VAR c = SUMX ( { ( 1, 2 ), ( 3, 4 ) }, [Value1] + [Value2] ) '
            'VAR w = SUMX ( { ( 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 ) }, [Value12] ) '
            'VAR r = SUMX ( ROW ( "Label", 1 ), [Label] ) + SUMX ( DATATABLE ( "Col", INTEGER, { { 1 } } ), [col] ) '
            'VAR u = SUMX ( SUMMARIZE ( Orders, Area[Region], "Total", [Total Amount] ), [Total] ) '
            'RETURN SUMX ( s, [Picked] ) + SUMX ( t, [Share] ) + g + c + w + r + u')
        r = self.check()
        self.assertEqual((r.errors, r.stale), ([], []))
        from pbikit import tmdl
        m = tmdl.load(self.root / "Example Synthetic.SemanticModel")
        self.assertEqual(tmdl.check_references(m, "SUMX ( { ( 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 ) }, [Value11] )"), [])
        self.assertEqual(tmdl.check_references(m, "[Value] + [Nope]"), ["[Nope]"])

    def test_report_level_measure_as_a_visual_filter(self):
        v = self.rep / "definition/pages/p1/visuals/P1-V01_amount-card/visual.json"
        d = json.loads(read(v))
        d["filterConfig"] = {"filters": [{"name": "mf1", "type": "Advanced",
                                          "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures",
                                                    "Schema": "extension"}}, "Property": "Per Unit"}},
                                          "filter": {"Version": 2, "From": [{"Name": "m", "Entity": "_Measures",
                                                                             "Schema": "extension", "Type": 0}],
                                                     "Where": [{"Condition": {"Comparison": {"ComparisonKind": 1,
                                                               "Left": {"Measure": {"Expression": {"SourceRef": {
                                                                   "Source": "m"}}, "Property": "Per Unit"}},
                                                               "Right": {"Literal": {"Value": "1D"}}}}}]}}]}
        bind_sample.write(v, d)
        r = self.check()
        self.assertEqual((r.errors, r.stale), ([], []))
        import contextlib, io
        from pbikit import validate as VAL
        with contextlib.redirect_stdout(io.StringIO()):
            fd = VAL.validate(self.rep, use_catalog=False, use_a11y=False)
        self.assertFalse([e for e in fd.errors if "Per Unit" in e], fd.errors)

    def test_recorded_type_deviation_is_a_note(self):
        t = self.root / "Example Synthetic.SemanticModel/definition/tables/Orders.tmdl"
        t.write_text(read(t).replace("column Status\n\t\tdataType: string", "column Status\n\t\tdataType: int64"),
                     encoding="utf-8")
        self.assertTrue(any("Status" in e and "int64" in e for e in self.check().errors))
        g = S.read_json(self.root / "design/specs/generate.json")
        g["deviations"] = [{"table": "orders", "column": "STATUS", "contract": "string", "synthetic": "int64",
                            "why": "sample codes"}]
        S.write_json(self.root / "design/specs/generate.json", g)
        r = self.check()
        self.assertEqual(r.errors, [])
        self.assertTrue(any("deviation: sample codes" in x for x in r.notes))


class FilterTypeTests(BindBase):
    """Item 5: text on a number column, or a number on a text column, in any saved filter."""

    def test_wrong_literal_types_flagged_everywhere(self):
        rf = self.rep / "definition/report.json"
        d = json.loads(read(rf))
        d["filterConfig"]["filters"][0]["filter"] = bind_sample.in_filter("c", "Calendar", "Year", ["'2024'"])
        bind_sample.write(rf, d)
        bm = self.rep / "definition/bookmarks/bm1.bookmark.json"
        bind_sample.write(bm, json.loads(read(bm).replace("'Status 2'", "2L")))
        sl = self.rep / "definition/pages/p1/visuals/P1-V03_option-slicer/visual.json"
        bind_sample.write(sl, json.loads(read(sl).replace("'Option Label 1'", "1D")))
        r = self.check()
        msgs = " | ".join(r.errors)
        self.assertIn("Calendar[Year] (int64) has text values [\"'2024'\"]: write numbers as 2024L", msgs)
        self.assertIn("Orders[Status] (string) has number values ['2L']", msgs)
        self.assertIn("Plan Option[Option Label] (string) has number values ['1D']", msgs)
        import contextlib, io
        from pbikit import validate as VAL
        with contextlib.redirect_stdout(io.StringIO()):
            fd = VAL.validate(self.rep, use_catalog=False, use_a11y=False)
        joined = " | ".join(fd.errors)
        for want in ("Calendar[Year] (int64) has text", "Orders[Status] (string) has number",
                     "Plan Option[Option Label] (string) has number"):
            self.assertIn(want, joined)

    def test_correct_literals_pass(self):
        self.assertEqual(self.check().errors, [])


class ModelIdTests(BindBase):
    """Item 6: the model ID from a link or the bare ID; a mistyped workspace name warns and points to --from."""

    def test_model_id_forms(self):
        for text in (MID, MID.upper(), f"https://app.powerbi.com/groups/{'1' * 8}-1111-4111-8111-{'1' * 12}/datasets/{MID}/details",
                     f"https://app.powerbi.com/groups/me/semanticmodels/{MID}?experience=power-bi",
                     f"https://app.powerbi.com/groups/me/modeling/{MID}/modelView"):
            self.assertEqual(BD.model_id(text), MID, text)
        for bad in ("https://app.powerbi.com/groups/me/reports/" + MID, "not-an-id", ""):
            with self.assertRaises(BD.BindError):
                BD.model_id(bad)

    def test_workspace_warnings(self):
        self.assertEqual(BD.workspace_warnings("Sample Workspace"), [])
        self.assertTrue(BD.workspace_warnings("Sample_Workspace-Dev"))           # mixed separators
        self.assertTrue(BD.workspace_warnings(" Sample Workspace"))
        self.assertTrue(BD.workspace_warnings("sample_workspace", ["Sample Workspace"]))
        self.assertEqual(BD.workspace_warnings("Other Space", ["Sample Workspace"]), [])

    def test_live_warns_and_recommends_desktop_route(self):
        S.write_json(DC.project_file(self.root), {"workspaces": ["Sample-Workspace"]})
        said = []
        self.go_live(workspace="Sample_Workspace", out=said.append)
        text = " ".join(said)
        self.assertIn("looks like 'Sample-Workspace'", text)
        self.assertIn("--from", text)
        self.assertIn("Sample_Workspace", DC.read_project(self.root)["workspaces"])


class NameCaseTests(BindBase):
    """Item 9: names compare case-insensitively everywhere, as in DAX."""

    def test_model_lookups(self):
        from pbikit import names as NM, tmdl
        m = tmdl.load(self.root / "Example Synthetic.SemanticModel")
        self.assertEqual(m.tables["orders"].columns["AMOUNT"].data_type, "decimal")
        self.assertIn("Orders", list(m.tables), "the TMDL spelling is kept")
        self.assertTrue(m.has_field("ORDERS", "amount"))
        self.assertEqual(m.measure_home("total amount"), ["_Measures"])
        self.assertEqual(tmdl.check_references(m, "SUM ( orders[amount] ) + [total AMOUNT] + 'calendar'[DATE]"), [])
        d = NM.CIDict({"Orders": 1})
        d["ORDERS"] = 2
        self.assertEqual((list(d), d["orders"], d.get("x")), (["Orders"], 2, None))

    def test_report_and_layout_names_in_other_case(self):
        v = self.rep / "definition/pages/p1/visuals/P1-V02_amount-by-month/visual.json"
        bind_sample.write(v, json.loads(read(v).replace('"Entity": "Orders"', '"Entity": "ORDERS"')
                                        .replace('"Property": "Amount"', '"Property": "amount"')))
        r = self.check()
        self.assertEqual((r.errors, r.stale), ([], []))
        import contextlib, io
        from pbikit import validate as VAL
        with contextlib.redirect_stdout(io.StringIO()):
            fd = VAL.validate(self.rep, use_catalog=False, use_a11y=False)
        self.assertFalse([e for e in fd.errors if "ORDERS" in e or "amount" in e], fd.errors)
        lay = layout()
        lay["visuals"][0]["bindings"]["Data"] = ["[TOTAL AMOUNT]", "orders[status]"]
        sl, missing = S.slice_contract(S.read_json(self.root / "design/specs/contract.json"), lay, TS.PLANNED)
        self.assertEqual(missing, [])
        self.assertIn("Status", sl["Orders"]["columns"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
