"""Design-flexibility tests: /theme (colour.py, gen_tokens.py, ref_palette.py, presets, template recolouring,
check_contrast.py) and /plan from a reference of any layout style (ref_layout.py, docs/layouts/).

    python design/scripts/test_design.py

The Rep 8 tests build the regression case's layout and model (tools/regression/cases/rep8) with three palettes and
check that `pbik validate` reports no contrast warning. Tests that draw pages need Microsoft Edge (headless) and are
skipped without it.
"""
import json, pathlib, shutil, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "tools" / "pbik"))

import colour as K  # noqa: E402
import gen_tokens as G  # noqa: E402
import ref_layout as RL  # noqa: E402
from pbikit import recolour  # noqa: E402

CASE = KIT / "tools" / "regression" / "cases" / "rep8" / "project"
LAYOUTS = KIT / "docs" / "layouts"
DARK = "#0E1A2B,#F2B705,#E4572E"
PASTEL = "#A8DADC,#F4C2C2,#CDB4DB,#FFE5B4"


def edge():
    try:
        import edge_page
        return edge_page.available()
    except Exception:
        return False


class ColourTests(unittest.TestCase):
    def test_contrast_matches_wcag(self):
        self.assertAlmostEqual(K.contrast("#FFFFFF", "#000000"), 21.0, places=1)
        self.assertAlmostEqual(K.contrast("#038D96", "#FFFFFF"), 4.0, places=1)

    def test_norm_reads_css_colours(self):
        self.assertEqual(K.norm("#abc"), "#AABBCC")
        self.assertEqual(K.norm("rgb(18, 52, 59)"), "#12343B")
        self.assertEqual(K.norm("rgba(255,255,255,0.5)"), "#FFFFFF")
        self.assertIsNone(K.norm("teal"))

    def test_oklch_round_trip(self):
        for c in ("#12343B", "#F2B705", "#A8DADC", "#E4572E"):
            self.assertEqual(K.from_oklch(*K.oklch(c)), c)

    def test_reach_keeps_hue_and_passes(self):
        out = K.reach("#F4C2C2", ["#FFFFFF"], 4.5)
        self.assertGreaterEqual(K.contrast(out, "#FFFFFF"), 4.5)
        self.assertLess(K.hue_distance(out, "#F4C2C2"), 12)
        self.assertEqual(K.reach("#1D2733", ["#FFFFFF"], 4.5), "#1D2733")       # passes already: unchanged

    def test_reach_on_both_sides_is_impossible(self):
        self.assertIsNone(K.reach("#777777", ["#FFFFFF", "#000000"], 15))


class TokensTests(unittest.TestCase):
    def base(self):
        return json.loads((KIT / "design" / "tokens.json").read_text(encoding="utf-8"))

    def test_clean_preset_is_the_shipped_palette(self):
        t, changes, checks, failures, _, _ = G.run(preset="clean", base=self.base())
        shipped = json.loads((KIT / "design" / "themes" / "presets" / "clean.json").read_text())["colors"]
        for k, v in shipped.items():
            if not k.startswith("_"):
                self.assertEqual(t["colors"][k], v, k)
        self.assertEqual([x for x in changes if x["origin"] == "given"], [])
        self.assertEqual(failures, [])

    def test_every_preset_passes_every_check(self):
        for p in sorted((KIT / "design" / "themes" / "presets").glob("*.json")):
            t, _, checks, failures, _, _ = G.run(preset=p.stem, base=self.base())
            self.assertEqual(failures, [], p.stem)
            self.assertTrue(all(x["pass"] for x in checks), p.stem)
            self.assertEqual(t["theme"]["preset"], p.stem)

    def test_default_is_the_clean_preset(self):
        t = G.run(base=self.base())[0]
        self.assertEqual(t["theme"]["source"], "preset clean")

    def test_dark_brand_palette(self):
        t, changes, checks, failures, _, _ = G.run(brand=DARK, mode="dark", base=self.base())
        c = t["colors"]
        self.assertEqual(failures, [])
        self.assertEqual(c["primary"], "#0E1A2B")
        self.assertEqual(c["brand"], "#F2B705")
        self.assertEqual(c["badMark"], "#E4572E")                         # the brand colour stays for marks
        self.assertGreaterEqual(K.contrast(c["bad"], c["card"]), 4.5)      # and moves for text
        self.assertTrue(K.is_dark(c["card"]) and not K.is_dark(c["text"]))
        self.assertGreaterEqual(K.contrast(c["onSelected"], c["selected"]), 4.5)
        self.assertIn("bad: #E4572E ->", " ".join(t["theme"]["changed"]))

    def test_pastel_palette_moves_text_keeps_light_fills(self):
        t, changes, checks, failures, _, _ = G.run(brand=PASTEL, base=self.base())
        c = t["colors"]
        self.assertEqual(failures, [])
        self.assertEqual(c["primary"], "#A8DADC")                          # a pastel band with dark text on it
        self.assertGreaterEqual(K.contrast(c["onDark"], c["primary"]), 4.5)
        self.assertEqual(c["badLight"], "#F4C2C2")                         # the pastel itself is the light fill
        given = {x["name"] for x in changes if x["origin"] == "given"}
        self.assertTrue({"bad", "brandText", "warning"} <= given)

    def test_named_roles_and_hue_assignment(self):
        free, named = G.parse_brand("primary=#1F3864,bad=#C00000,#2E75B6")
        roles, extras = G.assign(free, named, "light")
        self.assertEqual((roles["primary"], roles["bad"], roles["brand"]), ("#1F3864", "#C00000", "#2E75B6"))
        roles, _ = G.assign(["#2E7D32", "#123456", "#D32F2F", "#7B1FA2"], {}, "light")
        self.assertEqual((roles["good"], roles["bad"], roles["primary"]), ("#2E7D32", "#D32F2F", "#123456"))
        with self.assertRaises(SystemExit):
            G.parse_brand("#12345")

    def test_aliases_follow_their_roles_and_base_is_kept(self):
        base = self.base()
        base["colors"]["regionNorth"] = "#9AA0A6"                           # a rep colour the theme doesn't make
        t = G.run(brand=DARK, mode="dark", base=base)[0]
        c = t["colors"]
        for old, role in G.ALIASES.items():
            self.assertEqual(c[old], c[role], old)
        self.assertEqual(t["canvas"], base["canvas"])
        self.assertTrue(t["theme"]["recolourTemplates"])
        self.assertGreaterEqual(K.contrast(c["regionNorth"], c["card"]), 4.5)   # kept, and checked as text
        self.assertEqual(set(t["chart"]["series"]) - set(c), set())

    def test_layout_roles_rename_out_of_role_colours(self):
        lay = {"visuals": [
            {"id": "P1-V01", "props": {"fillCustom.fillColor@{\"id\": \"selection:selected\"}": "teal",
                                       "value.fontColor@{\"id\": \"selection:selected\"}": "card",
                                       "text.fontColor": "primary", "dataPoint.fill": "teal"}},
            {"id": "P1-V02", "referenceLines": [{"color": "primary", "dataLabel": True}],
             "navigator": {"colors": {"selected": "primary", "default": "onDarkMuted"}}}]}
        colors = G.run(preset="clean", base=self.base())[0]["colors"]
        roles = G.layout_roles(lay, colors)
        got = {(i, w.split("@")[0], n) for i, w, o, n in roles}
        self.assertIn(("P1-V01", "props fillCustom.fillColor", "selected"), got)
        self.assertIn(("P1-V01", "props value.fontColor", "onSelected"), got)
        self.assertIn(("P1-V01", "props text.fontColor", "primaryText"), got)
        self.assertIn(("P1-V02", "referenceLines[0].color", "primaryText"), got)
        self.assertIn(("P1-V02", "navigator.colors.selected", "primaryText"), got)
        self.assertNotIn("dataPoint", " ".join(w for _, w, _, _ in roles))  # marks keep their mark colour
        fixed = G.fix_layout(lay, roles)
        self.assertEqual(G.layout_roles(fixed, colors), [])


class RecolourTests(unittest.TestCase):
    def test_template_colours_follow_tokens_by_role(self):
        lit = lambda c: {"solid": {"color": {"expr": {"Literal": {"Value": f"'{c}'"}}}}}   # noqa: E731
        d = {"visual": {"objects": {
            "text": [{"properties": {"fontColor": lit("#12343B")}}],
            "fill": [{"properties": {"fillColor": lit("#12343B")}}],
            "outline": [{"properties": {"lineColor": lit("#DCE2EA")}}],
            "dataPoint": [{"properties": {"fill": lit("#ABCDEF")}}]},
            "visualContainerObjects": {"dropShadow": [{"properties": {"color": lit("#12343B")}}]}}}
        names = {"primary": "#0E1A2B", "primaryText": "#8594AB", "border": "#384459", "shadow": "#000000"}
        changed = recolour.apply(d, recolour.load_palette(KIT / "design" / "templates"), lambda n: names[n])
        o = d["visual"]["objects"]
        val = lambda e: e["properties"][next(iter(e["properties"]))]["solid"]["color"]["expr"]["Literal"]["Value"]  # noqa: E731
        self.assertEqual(val(o["text"][0]), "'#8594AB'")                   # text: primaryText
        self.assertEqual(val(o["fill"][0]), "'#0E1A2B'")                   # fill: primary
        self.assertEqual(val(o["outline"][0]), "'#384459'")
        self.assertEqual(val(o["dataPoint"][0]), "'#ABCDEF'")               # not in the palette: kept
        self.assertEqual(val(d["visual"]["visualContainerObjects"]["dropShadow"][0]), "'#000000'")
        self.assertEqual(len(changed), 4)


class Rep8ThemeTests(unittest.TestCase):
    """Rep 8's layout and model, built with templates under three palettes: no contrast warning from pbik validate."""

    @classmethod
    def setUpClass(cls):
        if not CASE.exists():
            raise RuntimeError(f"regression case {CASE} missing: a missing source fails the run, never skips it")

    def build(self, args):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik-theme-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        w = tmp / "p"
        shutil.copytree(CASE, w)
        shutil.copytree(KIT / "design" / "templates", w / "design" / "templates")
        lay = w / "design" / "specs" / "layout.json"
        shutil.move(w / "design" / "specs" / "rep8.layout.json", lay)
        tok = w / "design" / "tokens.json"
        py = [sys.executable]
        r = subprocess.run(py + [str(HERE / "gen_tokens.py"), *args, "--base", str(tok), "--out", str(tok),
                                 "--report", str(w / "theme.md"), "--layout", str(lay), "--fix-layout"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        subprocess.run(py + [str(HERE / "gen_theme.py"), "--tokens", str(tok), "--out",
                             str(w / "design" / "themes" / "pbip-polish.json")], check=True, capture_output=True)
        rep = next(w.glob("*.Report"))
        pbik = [*py, str(KIT / "tools" / "pbik" / "pbik.py")]
        r = subprocess.run(pbik + ["build", str(rep), str(lay), "--tokens", str(tok), "--templates",
                                   str(w / "design" / "templates")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run(pbik + ["validate", str(rep), "--layout", str(lay)], capture_output=True, text=True,
                           encoding="utf-8")
        return [x for x in (r.stdout + r.stderr).splitlines() if "WCAG" in x], w

    def test_three_palettes_pass_aa_in_the_built_report(self):
        for args in (["--preset", "bento"], ["--brand", DARK, "--mode", "dark"], ["--brand", PASTEL]):
            with self.subTest(args=args[1]):
                warnings, w = self.build(args)
                self.assertEqual(warnings, [])

    @unittest.skipUnless(edge(), "needs Microsoft Edge")
    def test_dark_wireframe_texts_pass_aa(self):
        import check_contrast
        _, w = self.build(["--brand", DARK, "--mode", "dark"])
        out = w / "wf.html"
        subprocess.run([sys.executable, str(HERE / "gen_wireframe_hf.py"), "--layout",
                        str(w / "design" / "specs" / "layout.json"), "--tokens", str(w / "design" / "tokens.json"),
                        "--theme", str(w / "design" / "themes" / "pbip-polish.json"), "--data", "none", "--out",
                        str(out)], check=True, capture_output=True)
        rows = check_contrast.measure(out.read_text(encoding="utf-8"))
        fails, _ = check_contrast.summary(rows)
        self.assertGreater(len(rows), 100)
        self.assertEqual(fails, [])


@unittest.skipUnless(edge(), "needs Microsoft Edge")
class EdgeReadTests(unittest.TestCase):
    def test_check_contrast_finds_a_failing_text(self):
        import check_contrast
        page = ('<html><body><div class="page on" data-page="P1" style="background:#FFFFFF">'
                '<div data-id="P1-V01" style="color:#BBBBBB">pale</div>'
                '<div data-id="P1-V02" style="color:#1D2733">dark</div></div></body></html>')
        rows = check_contrast.measure(page)
        fails, _ = check_contrast.summary(rows)
        self.assertEqual([r["id"] for r in fails], ["P1-V01"])

    def test_html_reference_palette(self):
        import ref_palette
        r = ref_palette.extract(LAYOUTS / "bento.html")
        self.assertEqual(r["mode"], "light")
        self.assertEqual(r["background"], "#F3F2EE")
        self.assertTrue(any(G.hue_band(c) == "blue" or G.hue_band(c) == "purple" for c in r["brand"]), r["brand"])
        self.assertEqual(r["container"]["radius"], 24)

    def test_image_reference_palette(self):
        import edge_page, ref_palette
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik-ref-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        page = ('<html><body style="margin:0;background:#0E1A2B"><div style="position:absolute;left:60px;top:60px;'
                'width:600px;height:300px;background:#1B2A40"></div><div style="position:absolute;left:100px;'
                'top:120px;width:300px;height:60px;background:#F2B705"></div></body></html>')
        png = edge_page.screenshot(page, tmp / "ref.png", 800, 450)
        r = ref_palette.extract(png)
        self.assertEqual(r["mode"], "dark")
        self.assertTrue(r["brand"] and G.hue_band(r["brand"][0]) == "yellow", r["brand"])
        t = G.run(ref=str(png), base=json.loads((KIT / "design" / "tokens.json").read_text()))
        self.assertEqual(t[3], [])                                          # every check passes

    def test_layout_styles_from_html(self):
        want = {"grid": ("grid", 9), "bento": ("bento", 8), "rail": ("rail", 9), "tabs": ("tabs", 9),
                "dense": ("dense table", 5)}
        for name, (style, n) in want.items():
            with self.subTest(name=name):
                ref = RL.read_html(LAYOUTS / f"{name}.html")
                lay, findings, styles = RL.map_reference(ref)
                self.assertIn(style, styles["P1"])
                self.assertEqual(len(lay["visuals"]), n)
                ids = [v["id"] for v in lay["visuals"]]
                self.assertEqual(ids, [f"P1-V{i:02d}" for i in range(1, n + 1)])
        lay, findings, _ = RL.map_reference(RL.read_html(LAYOUTS / "dense.html"))
        self.assertIn("sparkline in a cell", {f for _, f, _, _ in findings})
        lay, findings, _ = RL.map_reference(RL.read_html(LAYOUTS / "tabs.html"))
        self.assertIn("tabs inside a card", {f for _, f, _, _ in findings})
        types = [v["type"] for v in RL.map_reference(RL.read_html(LAYOUTS / "grid.html"))[0]["visuals"]]
        self.assertEqual(types, ["textbox", "slicer"] + ["cardVisual"] * 4 + ["lineChart", "clusteredBarChart",
                                                                              "tableEx"])


class RefLayoutTests(unittest.TestCase):
    """A boxes file (what the agent writes after looking at an image) to layout.json."""

    REF = {"width": 1440, "height": 810, "pages": [{"name": "Ops", "boxes": [
        {"kind": "rail", "x": 0, "y": 0, "w": 200, "h": 810, "items": 4},
        {"kind": "title", "x": 224, "y": 24, "w": 200, "h": 36, "label": "Operations"},
        {"kind": "kpi", "x": 224, "y": 84, "w": 276, "h": 110, "label": "Open"},
        {"kind": "kpi", "x": 524, "y": 84, "w": 276, "h": 110, "label": "Won"},
        {"kind": "kpi", "x": 824, "y": 84, "w": 276, "h": 110, "label": "Rate"},
        {"kind": "chart", "chart": "column", "x": 224, "y": 218, "w": 744, "h": 568, "label": "By stage",
         "features": ["gradient fill"]},
        {"kind": "table", "x": 992, "y": 218, "w": 424, "h": 568, "rows": 30, "rowHeight": 18,
         "features": ["sparkline in a cell"]}]}]}

    def test_ids_types_and_grid(self):
        lay, findings, styles = RL.map_reference(self.REF)
        v = {x["id"]: x for x in lay["visuals"]}
        self.assertEqual(v["P1-V01"]["type"], "pageNavigator")             # the rail first
        self.assertEqual(v["P1-V01"]["navigator"], {"orientation": "vertical"})
        self.assertEqual(v["P1-V01"]["x"], 0)
        self.assertEqual(v["P1-V02"]["type"], "textbox")
        self.assertEqual(v["P1-V02"]["cols"][1] - v["P1-V02"]["cols"][0], 5)    # titles get room
        self.assertEqual([v[f"P1-V0{i}"]["type"] for i in (3, 4, 5)], ["cardVisual"] * 3)
        self.assertEqual(len({v[f"P1-V0{i}"]["w"] for i in (3, 4, 5)}), 1)      # look-alikes split equally
        self.assertEqual(v["P1-V06"]["type"], "clusteredColumnChart")
        self.assertEqual(v["P1-V06"]["cols"], [3, 8])
        self.assertEqual(v["P1-V06"]["x"], RL.grid_box(3, 8)[0])
        self.assertEqual(v["P1-V07"]["type"], "tableEx")
        self.assertEqual(v["P1-V07"]["props"], {"grid.rowPadding": 2})       # dense
        self.assertEqual(v["P1-V08"]["type"], "shape")                       # the band behind the rail
        self.assertTrue(all(x["y"] % 8 == 0 and x["h"] % 8 == 0 for x in lay["visuals"]))
        self.assertTrue(all(x["build"]["step"] == 1 for x in lay["visuals"]))
        self.assertEqual({(w, f) for w, f, _, _ in findings},
                         {("P1-V06", "gradient fill"), ("P1-V07", "sparkline in a cell")})
        self.assertEqual(styles["P1"], ["rail"])                            # one table among charts isn't "dense"
        self.assertIn("dense", v["P1-V07"]["notes"])

    def test_report_lists_what_cannot_be_reproduced(self):
        lay, findings, styles = RL.map_reference(self.REF)
        md = RL.report_md(lay, findings, styles, ["boxes.json"])
        self.assertIn("## Can't be reproduced in Power BI", md)
        self.assertIn("| P1-V07 | sparkline in a cell | a table column with an SVG measure image", md)

    def test_tall_reference_gets_a_tall_page(self):
        ref = {"width": 1440, "height": 1600, "pages": [{"name": "Long", "boxes": [
            {"kind": "chart", "chart": "line", "x": 24, "y": 1200, "w": 600, "h": 300}]}]}
        lay, findings, _ = RL.map_reference(ref)
        self.assertGreater(lay["pages"]["P1"]["height"], 1080)
        self.assertIn("taller than one page", {f for _, f, _, _ in findings})


if __name__ == "__main__":
    unittest.main()
