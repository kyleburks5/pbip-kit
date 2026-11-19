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
    """v1.11.2: the small-sample threshold and privacy mode (docs/patterns/honest-data.md)."""
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
    """v1.11.2: kit visual starters (`pbik visual new <name> --from spatial-canvas`) and the shared court rule."""
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


if __name__ == "__main__":
    unittest.main()
