"""pbik templates harvest --clean: any page, nothing of the source left, colours mapped to tokens (study 2026-11-15)."""
import json, pathlib, shutil, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "pbik"))

from pbikit.harvestclean import harvest_clean, role_of_hex  # noqa: E402

SECRET = "Secret Team Name"


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


VISUAL = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
    "name": "abc123", "position": {"x": 1, "y": 2, "width": 300, "height": 100, "z": 0}, "howCreated": "User",
    "filterConfig": {"filters": [{"name": "f", "field": {}, "type": "Categorical"}]},
    "visual": {
        "visualType": "cardVisual",
        "query": {"queryState": {"Data": {"projections": [{"field": {"Measure": {"Property": "Hidden Measure"}}}]}}},
        "objects": {
            "value": [{"properties": {"fontSize": lit("20D"),
                                      "fontFamily": lit("'''Segoe UI Semibold'', wf_segoe-ui_semibold, sans-serif'"),
                                      "fontColor": {"solid": {"color": lit("'#111111'")}}},
                       "selector": {"id": "default"}}],
            "label": [{"properties": {"text": lit(f"'{SECRET}'")}, "selector": {"metadata": "Sales.Total"}}],
            "general": [{"properties": {"filter": {"filter": {"Where": [{"Condition": {"In": {"Values": [[lit(f"'{SECRET}'")]]}}}]}}}}],
            "fillCustom": [{"properties": {"fillColor": {"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": 0, "Percent": 0}}}}},
                                           "transparency": lit("95D")}, "selector": {"id": "selection:selected"}},
                           {"properties": {"fillColor": {"solid": {"color": {"expr": {"Measure": {"Property": "Colour"}}}}}},
                            "selector": {"id": "default"}}],
            "layout": [{"properties": {"style": lit("'Cards'"), "caption": lit(f"'{SECRET} again'")}}],
        },
        "visualContainerObjects": {
            "title": [{"properties": {"text": lit(f"'{SECRET}'"), "show": lit("true")}}],
            "general": [{"properties": {"altText": lit(f"'{SECRET} alt'")}}],
            "dropShadow": [{"properties": {"color": {"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": 0, "Percent": -0.6}}}}}}}],
        },
    },
}


class HarvestCleanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        rep = self.tmp / "Src.Report" / "definition" / "pages" / "p1"
        (rep / "visuals" / "abc123").mkdir(parents=True)
        (rep / "page.json").write_text(json.dumps({"name": "p1", "displayName": "Any Page"}), encoding="utf-8")
        (rep / "visuals" / "abc123" / "visual.json").write_text(json.dumps(VISUAL), encoding="utf-8")
        self.out = self.tmp / "templates"
        self.out.mkdir()
        shutil.copy(ROOT / "design" / "templates" / "palette.json", self.out)
        (self.out / "cardVisual.json").write_text('{"keep": true}', encoding="utf-8")
        self.pick = self.tmp / "pick.json"
        self.pick.write_text(json.dumps({"templates": {"abc123": "my card"}}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_it(self):
        log = self.tmp / "log.md"
        harvest_clean(self.tmp / "Src.Report", self.out, page="Any Page", pick=self.pick, log=log, label="t")
        return json.loads((self.out / "cardVisual.my-card.json").read_text(encoding="utf-8")), log.read_text(encoding="utf-8")

    def test_strips_text_selections_bindings_and_names(self):
        t, log = self.run_it()
        s = json.dumps(t)
        self.assertNotIn(SECRET, s)
        self.assertNotIn("Hidden Measure", s)
        self.assertNotIn("Sales.Total", s)
        for k in ("name", "position", "filterConfig", "howCreated"):
            self.assertNotIn(k, t)
        self.assertEqual(t["visual"]["query"], {"queryState": {}})
        self.assertNotIn("general", t["visual"]["objects"], "saved selection removed")
        self.assertNotIn("label", t["visual"]["objects"], "per-field entry removed")
        self.assertEqual(len(t["visual"]["objects"]["fillCustom"]), 1, "measure-bound entry removed")
        self.assertNotIn("caption", t["visual"]["objects"]["layout"][0]["properties"], "free text removed")
        self.assertEqual(t["visual"]["objects"]["layout"][0]["properties"]["style"], lit("'Cards'"), "enums kept")
        self.assertIn("Segoe UI Semibold", s, "font families kept")
        self.assertNotIn(SECRET, log)
        self.assertIn("saved selection", log)
        self.assertEqual(json.loads((self.out / "cardVisual.json").read_text()), {"keep": True}, "defaults untouched")
        idx = json.loads((self.out / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(idx["templates"]["cardVisual.my-card"]["source"], "t")

    def test_colours_map_to_palette_roles(self):
        t, log = self.run_it()
        pal = json.loads((ROOT / "design" / "templates" / "palette.json").read_text(encoding="utf-8"))["colors"]
        val = t["visual"]["objects"]["value"][0]["properties"]["fontColor"]["solid"]["color"]["expr"]["Literal"]["Value"]
        self.assertEqual(pal[val.strip("'")]["text"], "text")
        fill = t["visual"]["objects"]["fillCustom"][0]["properties"]["fillColor"]["solid"]["color"]["expr"]["Literal"]["Value"]
        self.assertEqual(pal[fill.strip("'")]["fill"], "card")
        sh = t["visual"]["visualContainerObjects"]["dropShadow"][0]["properties"]["color"]["solid"]["color"]["expr"]["Literal"]["Value"]
        self.assertEqual(pal[sh.strip("'")].get("shadow"), "shadow")
        self.assertNotIn("ThemeDataColor", json.dumps(t))
        self.assertIn("-> `text`", log)

    def test_hex_roles(self):
        self.assertEqual(role_of_hex("#FFFFFF", "fill")[0], "card")
        self.assertEqual(role_of_hex("#F5F5F5", "line")[0], "border")
        self.assertEqual(role_of_hex("#000000", "text")[0], "text")
        self.assertEqual(role_of_hex("#718297", "text")[0], "textMuted")
        self.assertEqual(role_of_hex("#1348DD", "fill")[0], "brand")

    def test_every_page_without_page_and_missing_pick_fails(self):
        self.pick.write_text(json.dumps({"templates": {"abc123": "x", "nope": "y"}}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            harvest_clean(self.tmp / "Src.Report", self.out, pick=self.pick, label="t")
        self.assertTrue((self.out / "cardVisual.x.json").exists(), "found on any page without --page")


if __name__ == "__main__":
    unittest.main()
