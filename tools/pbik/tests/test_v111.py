"""v1.11 tests (app-like visuals, the Desktop review of 2026-11-17) on made-up data only.

    python tools\\pbik\\tests\\test_v111.py
"""
import json, os, pathlib, shutil, sys, tempfile, unittest
os.environ.setdefault("PBIK_HOME", tempfile.mkdtemp(prefix="pbik_home_"))   # never the person's own settings

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from test_v17 import built_starter, pbik  # noqa: E402
from pbikit import tmdl, templates as TP  # noqa: E402


def col(entity, prop):
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def visual(folder, name, vtype, pos, query=None, sync=None):
    d = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
         "name": name, "position": {"x": pos[0], "y": pos[1], "z": pos[4], "width": pos[2], "height": pos[3]},
         "visual": {"visualType": vtype}}
    if query:
        d["visual"]["query"] = {"queryState": {"Values": {"projections": query}}}
    if sync:
        d["visual"]["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
    (folder / name).mkdir(parents=True)
    (folder / name / "visual.json").write_text(json.dumps(d), encoding="utf-8")


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_v111_"))
        self.work = self.tmp / "w"
        self.report, self.layout = built_starter(self.work)
        self.page = next(p for p in (self.report / "definition" / "pages").iterdir() if p.is_dir())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def validate(self):
        r = pbik("validate", self.report, "--layout", self.layout, cwd=self.work)
        return r.stdout + r.stderr


class ClickTrapTests(Tmp):
    """Slicer pills that did nothing (Desktop review 2026-11-17): validate names each way a click gets lost."""

    def test_shape_above_a_visual(self):
        visual(self.page / "visuals", "P1-V90_cover", "shape", (0, 0, 1920, 1080, 99999))
        out = self.validate()
        self.assertIn("P1-V90_cover", out)
        self.assertIn("catches its clicks", out)

    def test_shape_behind_is_fine(self):
        visual(self.page / "visuals", "P1-V90_band", "shape", (0, 0, 1920, 1080, 0))
        self.assertNotIn("catches its clicks", self.validate())

    def test_sync_group_across_fields(self):
        v = self.page / "visuals"
        visual(v, "P1-V91_a", "advancedSlicerVisual", (32, 900, 300, 48, 5000), [col("stores", "City")], sync="department")
        visual(v, "P1-V92_b", "advancedSlicerVisual", (400, 900, 300, 48, 5001), [col("products", "Category")], sync="department")
        out = self.validate()
        self.assertIn("sync group 'department'", out)
        self.assertIn("slicers on different fields share it", out)

    def test_slicer_without_a_relationship_path(self):
        visual(self.page / "visuals", "P1-V93_dict", "advancedSlicerVisual", (32, 960, 300, 48, 5002),
               [col("data_dictionary", "Column1")])
        out = self.validate()        # a disconnected table: deliberate (parameter tables), a note, not a warning
        self.assertIn("data_dictionary has no relationships: this slicer only changes measures that read it", out)
        self.assertNotIn("can't filter", out)

    def test_related_slicer_is_quiet(self):
        visual(self.page / "visuals", "P1-V94_city", "advancedSlicerVisual", (32, 960, 300, 48, 5003), [col("stores", "City")])
        self.assertNotIn("P1-V94_city: stores[City] can't filter", self.validate())


class FilterReachTests(unittest.TestCase):
    def test_one_side_to_many_side_only(self):
        m = tmdl.load(KIT / "tools" / "fixtures" / "rep4" / "Toy Sales.SemanticModel")
        self.assertIn("sales", tmdl.filter_reach(m, "stores"))
        self.assertIn("inventory", tmdl.filter_reach(m, "products"))
        self.assertNotIn("stores", tmdl.filter_reach(m, "sales"))       # many to one: no, unless both ways
        self.assertEqual(tmdl.filter_reach(m, "data_dictionary"), {"data_dictionary"})


class TemplateSyncTests(unittest.TestCase):
    """A template's sync group belonged to its report and tied every slicer made from it together."""

    def test_harvest_drops_sync_group(self):
        t = TP.strip({"name": "x", "position": {}, "visual": {"visualType": "advancedSlicerVisual",
                                                               "syncGroup": {"groupName": "department"}}})
        self.assertNotIn("syncGroup", t["visual"])

    def test_kit_templates_have_none(self):
        for f in (KIT / "design" / "templates").glob("*.json"):
            self.assertNotIn('"syncGroup"', f.read_text(encoding="utf-8"), f.name)


class ExportedPageTests(Tmp):
    """The export rule: a page marked `exported` gets native or Deneb only; validate warns on a custom visual."""

    def test_custom_visual_on_exported_page(self):
        lay = json.loads(self.layout.read_text(encoding="utf-8"))
        key = next(iter(lay["pages"]))
        lay["pages"][key]["exported"] = True
        self.layout.write_text(json.dumps(lay), encoding="utf-8")
        rj = self.report / "definition" / "report.json"
        rd = json.loads(rj.read_text(encoding="utf-8"))
        rd["resourcePackages"] = rd.get("resourcePackages", []) + [
            {"name": "pbikTestVisual0001", "type": "CustomVisual", "items": []}]
        rj.write_text(json.dumps(rd), encoding="utf-8")
        visual(self.page / "visuals", "P1-V95_kit", "pbikTestVisual0001", (32, 960, 300, 100, 5004))
        out = self.validate()
        self.assertIn("is exported / subscribed but this is a kit (private) visual", out)


class KitFilterSlicerTests(Tmp):
    """A kit visual's click filter shrank the slicer's pills (Desktop review 2026-11-17): validate names it."""

    def add_kit(self):
        rj = self.report / "definition" / "report.json"
        rd = json.loads(rj.read_text(encoding="utf-8"))
        rd["resourcePackages"] = rd.get("resourcePackages", []) + [{"name": "pbikTestVisual0002", "type": "CustomVisual", "items": []}]
        rj.write_text(json.dumps(rd), encoding="utf-8")
        visual(self.page / "visuals", "P1-V96_kit", "pbikTestVisual0002", (32, 700, 300, 100, 5005))
        visual(self.page / "visuals", "P1-V97_pills", "advancedSlicerVisual", (400, 700, 300, 48, 5006), [col("stores", "City")])

    def test_warns_without_nofilter(self):
        self.add_kit()
        self.assertIn("click filter also filters the slicer P1-V97_pills", self.validate())

    def test_quiet_with_nofilter(self):
        self.add_kit()
        pj = self.page / "page.json"
        d = json.loads(pj.read_text(encoding="utf-8"))
        d["visualInteractions"] = [{"source": "P1-V96_kit", "target": "P1-V97_pills", "type": "NoFilter"}]
        pj.write_text(json.dumps(d), encoding="utf-8")
        self.assertNotIn("click filter also filters the slicer", self.validate())


class TokenPropTests(Tmp):
    """A token name written as text ('control.tileRadius') left button slicers unclickable (Desktop 2026-11-17)."""

    def add_slicer(self, radius):
        lay = json.loads(self.layout.read_text(encoding="utf-8"))
        key = next(iter(lay["pages"]))
        lay["visuals"].append({"id": "P1-V98", "name": "pills", "page": key, "type": "advancedSlicerVisual",
                               "x": 32, "y": 960, "w": 400, "h": 48, "bindings": {"Values": ["stores[City]"]},
                               "props": {"shapeCustomRectangle.rectangleRoundedCurve@default": radius}})
        self.layout.write_text(json.dumps(lay), encoding="utf-8")
        return pbik("build", self.report, self.layout, cwd=self.work)

    def test_unknown_token_stops_the_build(self):
        r = self.add_slicer("control.tileRadius")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("token 'control.tileRadius' doesn't exist", r.stdout + r.stderr)

    def test_known_token_is_its_value(self):
        r = self.add_slicer("control.radius")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        f = next(self.report.glob("definition/pages/*/visuals/P1-V98_*/visual.json"))
        self.assertNotIn("control.radius", f.read_text(encoding="utf-8"))

    def test_validate_names_an_unresolved_token(self):
        visual(self.page / "visuals", "P1-V99_pills", "advancedSlicerVisual", (32, 960, 300, 48, 5007), [col("stores", "City")])
        f = self.page / "visuals" / "P1-V99_pills" / "visual.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        d["visual"]["objects"] = {"shapeCustomRectangle": [{"properties": {"rectangleRoundedCurve": {"expr": {"Literal": {"Value": "'control.tileRadius'"}}}},
                                                            "selector": {"id": "default"}}]}
        f.write_text(json.dumps(d), encoding="utf-8")
        self.assertIn("is the token name 'control.tileRadius'", self.validate())


class ResetIdsTests(Tmp):
    def test_reset_only_named_visuals(self):
        r = pbik("build", self.report, self.layout, "--reset-ids", "NOPE-V01", cwd=self.work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class RouteTests(Tmp):
    def test_html_route_off_stops_an_html_visual(self):
        proj = self.layout.parent / "project.json"
        proj.write_text(json.dumps({"routes": {"html": False}}), encoding="utf-8")
        lay = json.loads(self.layout.read_text(encoding="utf-8"))
        v = next(x for x in lay["visuals"] if x.get("bindings"))
        v["build"] = {"method": "html-measure", "step": 4, "reason": "test", "nativeTried": "card"}
        self.layout.write_text(json.dumps(lay), encoding="utf-8")
        r = pbik("build", self.report, self.layout, cwd=self.work)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("routes.html is false", r.stdout + r.stderr)


class CardImageSizeTests(unittest.TestCase):
    def test_svg_size_is_the_svg_elements(self):
        from pbikit.validate import _svg_size
        self.assertEqual(_svg_size("\"<svg xmlns='x' width='118' height='78'>\" & \"<rect width='22' height='9'/>\""), (118.0, 78.0))
        self.assertEqual(_svg_size("VAR _W = 524 VAR _H = 44 \"<svg width='\" & _W & \"'>\""), (524.0, 44.0))
        self.assertIsNone(_svg_size("VAR _BarW = 22"))


class HonestDataTests(unittest.TestCase):
    """v1.12: the small-sample threshold and privacy mode (docs/patterns/honest-data.md)."""
    def setUp(self):
        from pbikit import honest
        self.H = honest
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_honest_"))
        (self.tmp / "design" / "specs").mkdir(parents=True)
        self.vis = self.tmp / "visuals" / "v"
        self.vis.mkdir(parents=True)
        (self.vis / "capabilities.json").write_text(json.dumps({"objects": {"honest": {"properties": {}}}}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def project(self, doc):
        (self.tmp / "design" / "specs" / "project.json").write_text(json.dumps(doc), encoding="utf-8")

    def test_defaults_fade_at_home_suppress_at_work(self):
        self.project({"catalog": "home"})
        self.assertEqual(self.H.settings(self.tmp)["mode"], "fade")
        self.project({"catalog": "work"})
        self.assertEqual(self.H.settings(self.tmp), {"minSample": 11, "mode": "suppress", "source": "default"})

    def test_project_setting_wins(self):
        self.project({"catalog": "work", "honestData": {"minSample": 20, "mode": "fade"}})
        self.assertEqual(self.H.settings(self.tmp)["minSample"], 20)
        self.assertEqual(self.H.settings(self.tmp)["mode"], "fade")
        self.project({"honestData": {"mode": "hide"}})
        self.assertTrue(self.H.errors(self.tmp))

    def test_props_only_for_visuals_with_the_object_and_not_over_the_layout(self):
        self.project({"catalog": "work"})
        self.assertEqual(self.H.props_for({}, self.vis, self.tmp), {"honest.minSample@none": 11, "honest.mode@none": "suppress"})
        self.assertEqual(self.H.props_for({"props": {"honest.mode@none": "fade"}}, self.vis, self.tmp), {"honest.minSample@none": 11})
        (self.vis / "capabilities.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.H.props_for({}, self.vis, self.tmp), {})


class StarterTests(unittest.TestCase):
    """v1.12: kit visual starters (`pbik visual new <name> --from spatial-canvas`) and the shared court rule."""
    def test_new_from_starter(self):
        from pbikit import appvisual as AV
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_starter_"))
        try:
            self.assertIn("spatial-canvas", AV.starters())
            d = AV.new("shot-map", project=tmp, start="spatial-canvas")
            self.assertTrue((d / "src" / "settings.ts").exists(), "the starter's own settings")
            self.assertTrue((d / "src" / "kit" / "patterns" / "spatial.ts").exists(), "kit modules come from the template")
            self.assertTrue((d / "test" / "body.json").exists())
            self.assertFalse((d / "test" / "fetchmore.json").exists(), "the template's unit-chart scenarios are dropped")
            self.assertIn("honest", json.loads((d / "capabilities.json").read_text(encoding="utf-8"))["objects"])
            with self.assertRaises(AV.VisualError):
                AV.new("other", project=tmp, start="no-such-starter")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_court_rule_matches_the_starter_rows(self):
        sys.path.insert(0, str(KIT / "design" / "scripts"))
        import space_svg
        rows = json.loads((KIT / "tools" / "appvisuals" / "starters" / "spatial-canvas" / "test" / "data" / "shots.json").read_text(encoding="utf-8"))
        self.assertEqual([r for r in rows if space_svg.court_zone(r["X"], r["Y"]) != r["Zone"]], [])
        for name in space_svg.SPACES:
            text, rng = space_svg.svg(name, "#5B6474")
            self.assertTrue(text.startswith("<svg") and rng["x"][0] < rng["x"][1], name)

    def test_app_visual_patterns_are_known_to_plan(self):
        sys.path.insert(0, str(KIT / "design" / "scripts"))
        import pattern_choices
        k = pattern_choices.known_patterns()
        for p in ("spatial-canvas", "honest-data", "breakdown-wall", "focus-dim", "live-headline"):
            self.assertIn(p, k)
        self.assertNotIn("describe-a-visual", k)


class DocsTests(unittest.TestCase):
    def test_exported_setting_documented(self):
        self.assertIn("`exported: true`", (KIT / "tools" / "pbik" / "README.md").read_text(encoding="utf-8"))
        self.assertIn("Export rule", (KIT / "docs" / "design" / "app-visuals.md").read_text(encoding="utf-8"))

    def test_no_elkjs(self):
        self.assertNotIn('"elkjs"', (KIT / "tools" / "appvisuals" / "package.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- v1.12: the plan picture follows the model
def _desk_project(root):
    """A small made-up service-desk project: contract (tickets, an option table of channels written in DAX, a date
    template), planned measures and a planned top-4 column, as test 2 of the batch studies had."""
    spec = root / "design" / "specs"
    spec.mkdir(parents=True, exist_ok=True)
    c = {"version": 1, "model": "Desk", "source": "x", "flags": [], "rules": [], "approval": None,
         "relationships": [{"from": "T[Received]", "to": "Date[Date]"}, {"from": "T[Channel]", "to": "Channel[Channel]"}],
         "tables": {
             "T": {"source": "m", "columns": {"Ticket ID": {"type": "int64"}, "Channel": {"type": "string"},
                                              "Received": {"type": "dateTime"}, "Resolved": {"type": "dateTime"},
                                              "Category": {"type": "string"}, "Resolution Time (Days)": {"type": "double"},
                                              "SLA Threshold (Days)": {"type": "int64"}, "Within SLA": {"type": "string"}},
                   "measures": {
                       "Tickets": {"expression": "COUNTROWS ( 'T' )", "formatString": "#,0"},
                       "Tickets Within SLA": {"expression": "CALCULATE ( COUNTROWS ( 'T' ), 'T'[Resolution Time (Days)] <= 5 )",
                                              "formatString": "#,0"},
                       "SLA Breaches": {"expression": "VAR _n = [Tickets] RETURN IF ( NOT ISBLANK ( _n ), _n - [Tickets Within SLA] )",
                                        "formatString": "#,0"},
                       "SLA Compliance %": {"expression": "DIVIDE ( [Tickets Within SLA], [Tickets] )", "formatString": "0.0%"},
                       "Avg Days": {"expression": "AVERAGE ( 'T'[Resolution Time (Days)] )", "formatString": "0.00"},
                       "Median Days": {"expression": "MEDIAN ( 'T'[Resolution Time (Days)] )", "formatString": "0.0"}}},
             "Channel": {"source": "calculated", "columns": {"Channel": {"type": "string"}, "SLA Days": {"type": "string"}},
                         "measures": {}, "expression": 'DATATABLE ( "Channel", STRING, "SLA Days", INTEGER, '
                                                       '{ { "Calls", 5 }, { "Chats", 3 }, { "Emails", 5 } } )'},
             "Date": {"source": "calculated", "columns": {"Date": {"type": "string"}, "Year": {"type": "string"},
                                                          "Month": {"type": "string"}, "Month Number": {"type": "string"}},
                      "measures": {}, "expression": "DateAutoTemplate"}}}
    (spec / "contract.json").write_text(json.dumps(c), encoding="utf-8")
    g = {"seed": 1, "dateRange": ["2023-01-01", "2025-12-31"], "hints": {}, "deviations": [],
         "plannedMeasures": {
             "Breach rate": {"table": "T", "formatString": "0.0%",
                             "expression": "IF ( [Tickets] < 11, BLANK (), DIVIDE ( [SLA Breaches], [Tickets] ) )"},
             "Backing up title": {"table": "T", "dataType": "string",
                                  "expression": "VAR _n = COUNTROWS ( FILTER ( VALUES ( T[Category] ), [Breach rate] > 0.1 ) ) "
                                                "RETURN _n & \" categories\""}},
         "plannedColumns": {"T": {"Channel Group": {"dataType": "string", "expression":
                                                    'VAR _t = T[Channel] VAR _top = TOPN ( 2, VALUES ( T[Channel] ), 1 ) '
                                                    'RETURN IF ( _t IN _top, _t, "Other" )'}}}}
    (spec / "generate.json").write_text(json.dumps(g), encoding="utf-8")
    return c, g


def _ev():
    sys.path.insert(0, str(KIT / "design" / "scripts"))
    import example_values as EV
    return EV


class ExampleValuesFollowTheModel(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="pbik_ev_"))
        _desk_project(self.root)
        self.EV = _ev()
        self.EV.load_model(self.root)

    def test_compliance_and_breach_rate_add_up(self):
        EV = self.EV
        self.assertAlmostEqual(EV.value_for("SLA Compliance %") + EV.value_for("Breach rate"), 1, places=4)
        self.assertEqual(EV.value_for("SLA Breaches"), EV.value_for("Tickets") - EV.value_for("Tickets Within SLA"))

    def test_median_below_average(self):
        self.assertLess(self.EV.value_for("Median Days"), self.EV.value_for("Avg Days"))

    def test_cells_add_up_to_their_row(self):
        EV = self.EV
        cats = tuple(EV.members_of("Category", 6))
        chans = tuple(EV.members_of("Channel", 4))
        for c in cats[:3]:
            whole = EV.value_for("SLA Breaches", ((c, cats),))
            parts = sum(EV.value_for("SLA Breaches", ((c, cats), (m, chans))) for m in chans)
            self.assertLessEqual(abs(whole - parts), 2 * len(chans))      # rounding only (two rounded parts a cell)

    def test_option_labels_and_top_n(self):
        self.assertEqual(self.EV.members_of("Channel"), ["Calls", "Chats", "Emails"])
        self.assertEqual(self.EV.members_of("Channel Group"), ["Calls", "Chats", "Other"])

    def test_list_filter_sort_and_title_count(self):
        v = {"id": "P1-V01", "type": "tableEx", "bindings": {"Values": ["T[Category]", "[Tickets]", "[Breach rate]"]},
             "filters": [{"field": "[Breach rate]", "op": ">", "value": 0.18}],
             "sort": {"field": "[Breach rate]", "direction": "Descending"},
             "container": {"title": {"measure": "[Backing up title]", "preview": "{rows:category|categories} backing up"}}}
        e = self.EV.for_visual(v)
        rates = [r[2] for r in e["rows"]]
        self.assertTrue(all(x > 0.18 for x in rates))
        self.assertEqual(rates, sorted(rates, reverse=True))
        n = len(e["rows"])
        self.assertEqual(e["titles"]["title"], f"{n} {'category' if n == 1 else 'categories'} backing up")

    def test_drill_through_page_shows_the_first_row(self):
        lay = {"pages": {"P1": {}, "P2": {"drillthrough": {"fields": ["T[Category]"]}}},
               "visuals": [{"id": "P1-V01", "page": "P1", "type": "tableEx", "action": {"type": "Drillthrough", "page": "P2"},
                            "bindings": {"Values": ["T[Category]", "[Breach rate]"]},
                            "sort": {"field": "[Breach rate]", "direction": "Descending"}},
                           {"id": "P2-V01", "page": "P2", "type": "cardVisual", "bindings": {"Data": ["[Tickets]"]},
                            "preview": "Tickets in {top:T[Category]}"}]}
        d = self.EV.data_for(lay, root=self.root)
        first = d["visuals"]["P1-V01"]["rows"][0][0]
        self.assertEqual(d["visuals"]["P2-V01"]["preview"], f"Tickets in {first}")
        self.assertLess(d["visuals"]["P2-V01"]["rows"][0][0], self.EV.value_for("Tickets"))

    def test_detail_table_fills_every_column_in_agreement(self):
        v = {"id": "P2-V08", "type": "tableEx", "bindings": {"Values": [
            "T[Ticket ID]", "T[Channel]", "T[Received]", "T[Resolved]", "T[Resolution Time (Days)]",
            "T[SLA Threshold (Days)]", "T[Within SLA]"]}, "sort": {"field": "T[Resolution Time (Days)]", "direction": "Descending"}}
        e = self.EV.for_visual(v)
        days = [float(r[4]) for r in e["rows"]]
        self.assertEqual(days, sorted(days, reverse=True))
        for r in e["rows"]:
            self.assertTrue(r[0].isdigit())
            self.assertIn(r[1], ["Calls", "Chats", "Emails"])
            self.assertEqual(r[6], "Yes" if float(r[4]) <= float(r[5]) else "No")
            self.assertRegex(r[2], r"^\d{1,2}/\d{1,2}/\d{4}$")         # a short date, as the made-up model formats it

    def test_heat_gradient_and_format(self):
        v = {"id": "P1-V15", "type": "pivotTable", "bindings": {"Rows": ["T[Category]"], "Columns": ["T[Channel]"],
                                                                 "Values": ["[SLA Breaches]"]},
             "cf": [{"type": "gradient", "target": "[SLA Breaches]", "min": "#FFFFFF", "max": "#E3A6A6"}]}
        e = self.EV.for_visual(v)
        self.assertEqual(len(e["backs"]), len(e["rows"]))
        self.assertIn("#E3A6A6", e["backs"])
        self.assertEqual(self.EV.format_value(-2.68, "+0.00;-0.00;0.00"), "-2.68")
        self.assertEqual(self.EV.format_value(1.86, "+0.0;-0.0;0.0"), "+1.9")


class PolishRulesV1112(unittest.TestCase):
    def test_back_button_on_drill_through_header(self):
        from pbikit import polish as PO
        lay = {"pages": {"P2": {"drillthrough": {"fields": ["T[Category]"]}}},
               "visuals": [{"id": "P2-V01", "page": "P2", "type": "shape", "name": "header-band", "x": 0, "y": 0,
                            "w": 1920, "h": 96, "header": True, "style": {"fill": "primary"}},
                           {"id": "P2-V02", "page": "P2", "type": "textbox", "x": 32, "y": 24, "w": 600, "h": 48}]}
        said = PO.back_buttons(lay, {"primary": "#12343B"})
        back = next(v for v in lay["visuals"] if (v.get("action") or {}).get("type") == "Back")
        self.assertEqual(back["x"], 32)
        self.assertGreaterEqual(lay["visuals"][1]["x"], 32 + back["w"])
        self.assertEqual(back["props"]["text.fontColor@default"], "onDark")
        self.assertEqual(PO.back_buttons(lay, {"primary": "#12343B"}), [])          # again: no change
        self.assertTrue(said)

    def test_pickers_side_by_side_share_rows(self):
        from pbikit import polish as PO
        lay = {"visuals": [{"id": "P1-V01", "page": "P1", "type": "advancedSlicerVisual", "y": 112, "h": 80,
                            "props": {"layout.rowCount@none": 1}},
                           {"id": "P1-V02", "page": "P1", "type": "advancedSlicerVisual", "y": 112, "h": 80,
                            "props": {"layout.rowCount@none": 2}}]}
        PO.matching_pickers(lay)
        self.assertEqual(lay["visuals"][0]["props"]["layout.rowCount@none"], 2)

    def test_target_card_gets_last_year_and_a_plain_line(self):
        from pbikit import polish as PO
        planned = {"X PY": {"expression": "CALCULATE ( [X], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )"}}
        lay = {"visuals": [{"id": "P1-V10", "type": "cardVisual", "bindings": {"Data": ["[Avg Days]"]},
                            "referenceLabels": {"labels": [{"title": "SLA", "value": "[SLA Days]", "detail": "[Avg Days vs SLA]"}]}}]}
        PO.target_lines(lay, planned)
        labs = lay["visuals"][0]["referenceLabels"]["labels"]
        self.assertEqual(labs[0]["value"], "[Avg Days PY]")
        self.assertIn("Avg Days vs target text", planned)
        self.assertIn("{abs:[Avg Days vs SLA]|0.0} days", labs[1]["preview"])

    def test_count_title_must_use_the_list_filter(self):
        from pbikit import polish as PO
        expr = {"T": "COUNTROWS ( FILTER ( VALUES ( T[Category] ), [Breach rate] > 0.1 ) ) & \" categories\""}
        v = {"id": "P1-V14", "bindings": {"Values": ["T[Category]"]}, "container": {"title": {"measure": "[T]"}},
             "filters": [{"field": "[Breach rate]", "op": ">", "value": 0.1}]}
        self.assertEqual(PO.count_titles({"visuals": [v]}, expr), [])
        v["filters"][0]["value"] = 0.2
        self.assertEqual(len(PO.count_titles({"visuals": [v]}, expr)), 1)


class Test3DesktopFixes(unittest.TestCase):
    """v1.12, test 3 of the batch studies in Desktop: what the first open showed."""

    def test_dark_theme_pills_take_the_theme_colours(self):
        from pbikit import polish as PO
        lay = {"visuals": [{"id": "P1-V03", "type": "advancedSlicerVisual"},
                           {"id": "P1-V04", "type": "advancedSlicerVisual", "props": {"value.fontColor@default": "text"}}]}
        dark = {"colors": {"text": "#E6ECF5", "card": "#141D30", "selected": "#F2A541", "onSelected": "#0C1015"}}
        said = PO.pill_colours(lay, dark)
        self.assertEqual(len(said), 1)                                    # the picker with its own colours is kept
        self.assertEqual(lay["visuals"][0]["props"]["fillCustom.fillColor@default"], "card")
        self.assertEqual(lay["visuals"][0]["props"]["value.fontColor@selection:selected"], "onSelected")
        self.assertEqual(PO.pill_colours({"visuals": [{"id": "x", "type": "advancedSlicerVisual"}]},
                                         {"colors": {"text": "#1D2733"}}), [])   # light theme: Desktop's white pill

    def test_clearing_a_sorted_column_clears_its_sort_column(self):
        from pbikit import polish as PO
        g = {"plannedColumns": {"Shots": {"Quarter": {"sortBy": "Period", "expression": "x"}}},
             "plannedMeasures": {"Best": {"expression": "MAXX ( ALLSELECTED ( 'Shots'[Quarter] ), [FG %] )"},
                                 "Other": {"expression": "MAXX ( ALLSELECTED ( 'Shots'[Team] ), [FG %] )"}}}
        said = PO.sort_by_scope(g, {})
        self.assertEqual(g["plannedMeasures"]["Best"]["expression"],
                         "MAXX ( ALLSELECTED ( 'Shots'[Quarter], 'Shots'[Period] ), [FG %] )")
        self.assertEqual(g["plannedMeasures"]["Other"]["expression"], "MAXX ( ALLSELECTED ( 'Shots'[Team] ), [FG %] )")
        self.assertEqual(len(said), 1)
        self.assertEqual(PO.sort_by_scope(g, {}), [])                    # again: no change

    def test_rail_picker_title_room_follows_the_theme(self):
        from pbikit import polish as PO
        lay = {"pages": {"P1": {}}, "visuals": [
            {"id": "P1-V01", "page": "P1", "type": "shape", "pattern": "rail-panel", "x": 0, "y": 0, "w": 320, "h": 1080},
            {"id": "P1-V02", "page": "P1", "type": "advancedSlicerVisual", "x": 40, "y": 112, "w": 200, "h": 60,
             "props": {"layout.rowCount@none": 1}}]}
        PO.rail_pickers(lay, {"fontPt": {"chartTitle": 15}})
        self.assertEqual(lay["visuals"][1]["h"], 37 + PO.PILL)            # a 15 pt title: 37 px, then the pills

    def test_column_in_a_custom_value_well_is_summed(self):
        from pbikit import build as B
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "visuals" / "map").mkdir(parents=True)
        (tmp / "visuals" / "map" / "capabilities.json").write_text(json.dumps({"dataRoles": [
            {"name": "Item", "kind": "Grouping"}, {"name": "X", "kind": "Measure"}]}), encoding="utf-8")

        class Ctx:
            project = str(tmp)
        self.assertEqual(B.custom_measure_roles(Ctx(), {"custom": "map"}), {"X"})
        self.assertEqual(B.custom_measure_roles(Ctx(), {"type": "tableEx"}), set())


class PartDFixes(unittest.TestCase):
    """v1.12 Part D: the score, the reading order and the tab order on the three rebuilds and their originals."""

    def test_old_layout_is_scored_in_pbiks_form(self):
        from pbikit.score import flat_layout
        old = {"pages": [{"id": "sales", "visuals": [{"id": "a", "x": 0, "y": 0, "w": 10, "h": 10}]}]}
        new = flat_layout(old)
        self.assertEqual(list(new["pages"]), ["sales"])
        self.assertEqual(new["visuals"][0]["page"], "sales")
        cur = {"pages": {}}
        self.assertIs(flat_layout(cur), cur)                    # pbik's own form: returned as it is

    def test_reading_order_reads_the_band_then_each_panel(self):
        from pbikit.a11y import reading_order
        items = [("title", 32, 24, 289, 48), ("headline", 345, 24, 1500, 48), ("pick", 48, 128, 257, 76),
                 ("card", 345, 112, 289, 116), ("chart", 345, 600, 289, 116), ("pick2", 48, 700, 257, 76)]
        rail = [(32, 112, 289, 936)]
        self.assertEqual(reading_order(items, rail), ["title", "headline", "pick", "pick2", "card", "chart"])
        self.assertEqual(reading_order(items)[:3], ["title", "headline", "pick"])     # no panels: rows

    def test_tab_order_follows_reading_order(self):
        from pbikit import polish as PO
        lay = {"visuals": [
            {"id": "P1-V01", "page": "P1", "type": "shape", "x": 0, "y": 0, "w": 320, "h": 1080},
            {"id": "P1-V02", "page": "P1", "type": "cardVisual", "x": 400, "y": 100, "w": 300, "h": 100},
            {"id": "P1-V03", "page": "P1", "type": "slicer", "x": 32, "y": 100, "w": 256, "h": 76}]}
        self.assertTrue(PO.tab_order(lay))
        self.assertLess(lay["visuals"][2]["tabOrder"], lay["visuals"][1]["tabOrder"])   # the rail reads first
        self.assertEqual(PO.tab_order(lay), [])                                          # again: no change

    def test_drill_page_takes_the_source_pages_year(self):
        from pbikit.score import year_chosen
        lay = {"pages": {"P1": {}, "P2": {"drillthrough": {"fields": ["T[Category]"]}}},
               "visuals": [{"id": "P1-V01", "page": "P1", "type": "slicer", "bindings": {"Values": ["Date[Year]"]}}]}
        self.assertTrue(year_chosen(lay, "P2"))


class MadeUpModelV1112(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="pbik_synth1112_"))
        c, g = _desk_project(self.root)
        from pbikit import synth as S
        c["approval"] = {"by": "test", "hash": S.content_hash(c)}
        (self.root / "design" / "specs" / "contract.json").write_text(json.dumps(c), encoding="utf-8")
        lay = {"pages": {"P1": {}}, "visuals": [
            {"id": "P1-V01", "page": "P1", "type": "tableEx", "bindings": {"Values": [
                "T[Ticket ID]", "T[Channel]", "T[Received]", "T[Resolved]", "T[Resolution Time (Days)]",
                "T[SLA Threshold (Days)]", "T[Within SLA]", "Channel[SLA Days]", "Date[Year]", "[SLA Breaches]"]}}]}
        self.layout = self.root / "design" / "specs" / "layout.json"
        self.layout.write_text(json.dumps(lay), encoding="utf-8")

    def test_ensure_makes_then_keeps_the_model(self):
        from pbikit import synthgen as G
        self.assertEqual(G.ensure(self.root, "Desk", self.layout), "made")
        self.assertEqual(G.ensure(self.root, "Desk", self.layout), "current")
        tables = self.root / "Desk.SemanticModel" / "definition" / "tables"
        ch = (tables / "Channel.tmdl").read_text(encoding="utf-8")
        self.assertIn('{ "Calls", 5 }', ch)                       # the option table's own labels, kept
        self.assertIn('"SLA Days", INTEGER', ch)
        dt = (tables / "Date.tmdl").read_text(encoding="utf-8")
        self.assertIn('"Date", DATETIME', dt)                     # a date table from the date range
        rows = [ln for ln in (tables / "T.tmdl").read_text(encoding="utf-8").splitlines() if ln.strip().startswith("{ 1000")]
        self.assertTrue(rows)
        for ln in rows[:50]:
            cells = [x.strip().strip('"') for x in ln.strip().strip("{},").split(",")]
            self.assertIn(cells[1], ("Calls", "Chats", "Emails"))  # keys from the kept labels
        g = json.loads((self.root / "design" / "specs" / "generate.json").read_text(encoding="utf-8"))
        g["plannedMeasures"]["Extra"] = {"table": "T", "expression": "1"}
        (self.root / "design" / "specs" / "generate.json").write_text(json.dumps(g), encoding="utf-8")
        lay = json.loads(self.layout.read_text(encoding="utf-8"))
        lay["visuals"][0]["bindings"]["Values"].append("[Extra]")
        self.layout.write_text(json.dumps(lay), encoding="utf-8")
        self.assertEqual(G.ensure(self.root, "Desk", self.layout), "updated")

    def test_build_makes_the_model_first(self):
        r = pbik("build", "Desk", str(self.layout), cwd=self.root)
        self.assertIn("made the made-up model Desk.SemanticModel", r.stdout + r.stderr)
        self.assertTrue((self.root / "Desk.SemanticModel" / "definition" / "model.tmdl").exists())

    def test_never_touches_the_persons_own_model(self):
        from pbikit import synthgen as G
        own = self.root / "Desk.SemanticModel" / "definition"
        own.mkdir(parents=True)
        (own / "model.tmdl").write_text("model Model\n", encoding="utf-8")
        self.assertIsNone(G.ensure(self.root, "Desk", self.layout))
        self.assertEqual((own / "model.tmdl").read_text(encoding="utf-8"), "model Model\n")


# ---------------------------------------------------------------- v1.12: the panel style layout and its checks
class PanelStyleTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="pbik_panels_"))
        _desk_project(self.root)
        spec_dir = self.root / "design" / "specs"
        (self.root / "design" / "tokens.json").write_text(json.dumps({"colors": {"card": "#FFFFFF"}}), encoding="utf-8")
        (spec_dir / "layout.json").write_text(json.dumps({"pages": {"P1": {}}, "visuals": [
            {"id": "P1-V01", "page": "P1", "type": "tableEx", "name": "old-list", "x": 0, "y": 0, "w": 10, "h": 10}]}),
            encoding="utf-8")
        self.spec = {"page": "P1", "dimension": "Channel[Channel]", "members": ["Calls", "Chats", "Emails"],
                     "memberMeta": {"Emails": {"lowerIsBetter": True}},
                     "header": {"title": "Desk", "definition": "what is counted", "icon": "headset", "year": "Date[Year]"},
                     "count": "[Tickets]", "countNoun": "tickets", "measureTable": "T", "period": "Date[Quarter]",
                     "distribution": {"column": "T[Resolution Time (Days)]", "threshold": "[SLA Days]",
                                      "average": "[Avg Days]", "within": "[Tickets Within SLA]",
                                      "rate": "[SLA Compliance %]", "title": "Resolution time", "unit": "days",
                                      "thresholdName": "SLA"},
                     "top": {"field": "T[Category]", "n": 5}}
        (spec_dir / "panels.json").write_text(json.dumps(self.spec), encoding="utf-8")

    def run_panels(self):
        from pbikit import panelstyle as PS
        PS.run(self.root, self.root / "design" / "specs" / "panels.json", render_png=False)
        return json.loads((self.root / "design" / "specs" / "layout.json").read_text(encoding="utf-8"))

    def test_panels_ids_stable_and_old_visuals_retired(self):
        lay = self.run_panels()
        self.assertIn("P1-V01", lay["retired"])
        names = {v["name"]: v["id"] for v in lay["visuals"]}
        self.assertEqual(len(names), len(lay["visuals"]))
        for m in ("calls", "chats", "emails"):
            for part in ("panel", "kpi", "quarters", "histogram", "top"):
                self.assertIn(f"{m}-{part}", names)
        again = self.run_panels()
        self.assertEqual({v["name"]: v["id"] for v in again["visuals"]}, names)

    def test_member_colours_are_aa_and_rep9_by_default(self):
        from pbikit import panelstyle as PS
        cols = PS.member_colours(["A", "B", "C", "D"], {})
        self.assertEqual([c[0] for c in cols.values()], ["#3A63D8", "#1E9C77", "#1A93B8", "#E25751"])
        for mark, text, tint in cols.values():
            self.assertGreaterEqual(PS.contrast(mark, "#FFFFFF"), 3)
            self.assertGreaterEqual(PS.contrast(text, "#FFFFFF"), 4.5)
            self.assertGreaterEqual(PS.contrast(text, tint), 4.5)

    def test_too_many_members_refused(self):
        from pbikit import panelstyle as PS
        with self.assertRaises(PS.PanelError):
            PS.make({**self.spec, "members": list("ABCDEFG")}, {}, {"colors": {}})

    def test_chip_polarity_and_compact_quarters(self):
        lay = self.run_panels()
        g = json.loads((self.root / "design" / "specs" / "generate.json").read_text(encoding="utf-8"))
        self.assertIn('IN { "Emails" }, -1, 1', g["plannedMeasures"]["Tickets Change Font"]["expression"])
        q = next(v for v in lay["visuals"] if v["name"] == "calls-quarters")
        self.assertEqual(q["props"]["labels.labelDisplayUnits"], 0)           # Auto: 2.3K
        from pbikit import polish as PO
        self.assertEqual(PO.label_collisions(lay, {}), [])
        q["props"]["labels.labelDisplayUnits"] = 1
        q["w"] = 168                                                       # Rep 9's 168 px mini chart
        self.assertTrue(PO.label_collisions(lay, {}))

    def test_quote_tables(self):
        from pbikit import polish as PO
        self.assertEqual(PO.quote_tables('SELECTEDVALUE ( DataTable[C], "DataTable[x]" ) + Date[Year]', ["DataTable", "Date"]),
                         "SELECTEDVALUE ( 'DataTable'[C], \"DataTable[x]\" ) + 'Date'[Year]")

    def test_month_number_is_no_id(self):
        from pbikit import synthgen as G
        vals = {"Month Number": [1, 2], "Ticket ID": [5, 9]}
        G.consistent_rows(vals, {"Month Number": "int64", "Ticket ID": "int64"}, (), set(), 2, __import__("random").Random(1))
        self.assertEqual(vals["Month Number"], [1, 2])
        self.assertEqual(vals["Ticket ID"], [100000, 100001])

    def test_icons_are_the_kits_own(self):
        from pbikit import icons as IC
        self.assertEqual(IC.guess("Inpatient"), "bed")
        self.assertEqual(IC.guess("Calls"), "phone")
        self.assertIn("<circle", IC.svg("phone", fg="#000000", bg="#EEEEEE"))


if __name__ == "__main__":
    unittest.main()
