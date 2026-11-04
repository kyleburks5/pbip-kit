"""Tests for the high-fidelity wireframe (gen_wireframe_hf.py) and its data step (wireframe_data.py).

    python design/scripts/test_wireframe.py

Run on the regression cases' layouts (tools/regression/cases: Rep 4 parity, Rep 5 parity, Rep 8) without Desktop: the
data step runs against a fake DAX runner, so the privacy rules are tested on numbers made up here.
"""
import html.parser, json, pathlib, re, shutil, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "tools" / "pbik"))

import gen_wireframe_hf as G  # noqa: E402
import wireframe_data as W  # noqa: E402
from pbikit import tmdl  # noqa: E402

CASES = KIT / "tools" / "regression" / "cases"
LAYOUTS = {"rep4-parity": ("rep4-parity", "rep4-parity"), "rep5-overview": ("rep5-parity", "rep5-parity-overview"),
           "rep5-mix": ("rep5-parity", "rep5-parity-workforce-mix"), "rep8": ("rep8", "rep8")}
PRIVACY = {"count": "[Group Size]", "minGroup": 5, "identifiers": ["DataTable[EmployeeID]"], "maxRows": 500}


def case(key):
    proj, name = LAYOUTS[key]
    p = CASES / proj / "project"
    lay = json.loads((p / "design" / "specs" / f"{name}.layout.json").read_text(encoding="utf-8"))
    tok = json.loads((p / "design" / "tokens.json").read_text(encoding="utf-8"))
    model = tmdl.load(next(p.glob("*.SemanticModel")))
    theme = next(p.glob("*.Report/StaticResources/RegisteredResources/*.json"), None)
    return lay, tok, model, json.loads(theme.read_text(encoding="utf-8")) if theme else None


class Ids(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "data-id" in d:
            self.ids.append(d["data-id"])


def fake_runner(counts):
    """A DAX runner that returns rows with the given privacy counts for every query (values 10, 20, ...)."""
    def run(dax, port):
        q = next(q for q in run.qs.values() if q["dax"] == dax)
        ng, ns, nv = len(q["groups"]), sum(1 for g in q["groups"] if g["sortBy"]), len(q["values"])
        if not ng:
            return [[counts[0]] + [10.0 * (k + 1) for k in range(nv)]]
        return [[f"M{i}"] * ng + [float(i)] * ns + [n] + [10.0 * (i + 1)] * nv for i, n in enumerate(counts)]
    return run


def edge_dom(test, page):
    """The page as headless Edge draws it (scripts removed), or skip the test without Edge."""
    import re, edge_page
    if not edge_page.available():
        test.skipTest("Edge not installed")
    return re.sub(r"<script.*?</script>", "", edge_page.dom(page), flags=re.S)


class WireframeTests(unittest.TestCase):
    def test_every_layout_renders_every_visual_with_its_tag(self):
        for key in LAYOUTS:
            lay, tok, _, theme = case(key)
            out = G.build_html(lay, tok, theme, None)
            p = Ids()
            p.feed(out)
            want = [v["id"] for v in lay["visuals"] if (v.get("build") or {}).get("method") != "page-background"]
            self.assertEqual(sorted(p.ids), sorted(want), key)
            spec = json.loads(out.split('id="spec">', 1)[1].split("</script>", 1)[0])
            for s in spec["visuals"]:
                self.assertTrue(s["known"], f"{key} {s['id']}: {s['type']} has no renderer")
                self.assertTrue(s["tag"], s["id"])
            tags = {s["type"]: s["tag"] for s in spec["visuals"]}
            if "pivotTable" in tags:
                self.assertEqual(tags["pivotTable"], "Matrix")
            if "cardVisual" in tags:
                self.assertEqual(tags["cardVisual"], "Card (new)")
            if "advancedSlicerVisual" in tags:
                self.assertEqual(tags["advancedSlicerVisual"], "Button slicer")
            self.assertIn("B ID badges", out)
            self.assertIn("'b'", out)
            self.assertIn("'t'", out)

    def test_labels_button_toggles_badges_and_tags_together(self):
        """One on-screen "Labels" button hides or shows every ID badge and visual-type tag at once; B and T still
        toggle each kind on its own, and the button follows them."""
        lay, tok, _, theme = case("rep8")
        out = G.build_html(lay, tok, theme, None)
        bar = out.split('<div id="bar">', 1)[1].split("</div>", 1)[0]
        self.assertRegex(bar, r'<button id="labels"[^>]*>Labels</button>')
        self.assertIn('aria-pressed="true"', bar, "labels start shown")
        js = out.split("labelsBtn.onclick", 1)[1].split("};", 1)[0]
        self.assertIn("classList.toggle('nobadge', hide)", js, "the button hides the ID badges")
        self.assertIn("classList.toggle('notag', hide)", js, "and the visual-type tags, together")
        self.assertIn("if (k === 'b') { document.body.classList.toggle('nobadge'); syncLabels(); }", out)
        self.assertIn("else if (k === 't') { document.body.classList.toggle('notag'); syncLabels(); }", out)
        self.assertIn("body.nobadge .badge, body.notag .tag, body.notag .nodata", out,
                      "the badge and tag classes are the ones the button sets")

    def test_tags_name_the_visual_and_svg_method(self):
        lay, tok, _, theme = case("rep8")
        v = next(x for x in lay["visuals"] if x["type"] == "tableEx")
        v["build"] = {"method": "svg-measure"}
        lay["visuals"].append({"id": "P1-V99", "name": "odd", "page": "P1", "type": "someCustomVisual", "x": 0, "y": 0,
                               "w": 100, "h": 100})
        spec = json.loads(G.build_html(lay, tok, theme, None).split('id="spec">', 1)[1].split("</script>", 1)[0])
        by = {s["id"]: s for s in spec["visuals"]}
        self.assertEqual(by[v["id"]]["tag"], "SVG in Table")
        self.assertFalse(by["P1-V99"]["known"], "unknown types are a styled placeholder")
        self.assertEqual(by["P1-V99"]["tag"], "someCustomVisual")
        line = next(s for s in spec["visuals"] if s["type"] == "lineChart")
        self.assertEqual(line["tag"], "Line chart")

    def test_style_comes_from_layout_tokens_and_theme(self):
        lay, tok, _, theme = case("rep8")
        spec = json.loads(G.build_html(lay, tok, theme, None).split('id="spec">', 1)[1].split("</script>", 1)[0])
        by = {s["id"]: s for s in spec["visuals"]}
        self.assertEqual(by["P1-V01"]["shape"]["fill"], tok["colors"]["primary"])       # style.fill: primary
        self.assertEqual(by["P1-V15"]["box"]["radius"], tok["container"]["radius"])     # container border radius
        self.assertEqual(by["P1-V04"]["nav"]["states"]["selected"]["color"], tok["colors"]["primary"])   # navigator key
        self.assertEqual(spec["dataColors"], theme["dataColors"])
        self.assertEqual(by["P2-V08"]["tag"], "Slicer (dropdown)")

    def test_queries_follow_bindings_and_default_state(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        qs = W.queries(lay, model)
        card = qs["P1-V09"]
        self.assertTrue(card["dax"].startswith("EVALUATE CALCULATETABLE ( ROW ( \"__n\", [Group Size], \"v0\", [Headcount]"))
        self.assertIn("TREATAS ( { 2024 }, 'Date'[Year] )", card["dax"], "the year slicer's default selection")
        self.assertNotIn("{ 2024 }", qs["P1-V05"]["dax"], "a slicer isn't filtered by its own selection")
        self.assertIn("{ 2020, 2021, 2022, 2023, 2024 }", qs["P1-V05"]["dax"], "its own visual filter applies")
        tbl = qs["P2-V18"]
        self.assertIn("SUMMARIZECOLUMNS ( 'DataTable'[Department], 'DataTable'[JobRole]", tbl["dax"])
        self.assertEqual([x["label"] for x in tbl["values"]][:2], ["Headcount", "Hires"])
        line = qs["P1-V15"]
        self.assertIn("'Date'[Month Number]", line["dax"], "sort-by column grouped too")

    def test_no_privacy_config_fetches_nothing(self):
        lay, _, model, _ = case("rep8")
        with self.assertRaises(W.PrivacyError):
            W.queries(lay, model)

    def test_small_groups_hidden_with_secondary_suppression(self):
        q = {"groups": [{"label": "Dept", "sortBy": None}], "values": [{"label": "Headcount", "format": "#,0"}],
             "cat": 0, "leg": None}
        d = W.shape(q, [["A", 40.0, 40.0], ["B", 3.0, 3.0], ["C", 12.0, 12.0], ["D", 8.0, 8.0]], PRIVACY)
        self.assertEqual(d["hidden"], 2, "B (3) hidden, and D (8, the smallest left) so B can't be derived")
        self.assertEqual([r[0] for r in d["rows"]], ["A", "C"])
        d2 = W.shape(q, [["A", 40.0, 40.0], ["B", 3.0, 3.0], ["C", 2.0, 2.0]], PRIVACY)
        self.assertEqual(d2["hidden"], 2)
        self.assertEqual([r[0] for r in d2["rows"]], ["A"])

    def test_fetch_and_check_with_a_fake_runner(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        run = fake_runner([30.0, 2.0, 25.0, 9.0, 40.0])
        run.qs = W.queries(lay, model)
        out = W.fetch(lay, model, 0, runner=run)
        self.assertTrue(any("passed" in x for x in out["privacy"]))
        for vid, d in out["visuals"].items():
            self.assertTrue(all(n >= 5 for n in d["counts"]), vid)
        self.assertEqual(out["visuals"]["P2-V18"]["hidden"], 2)
        html_out = G.build_html(lay, *case("rep8")[1:2], case("rep8")[3], out)
        self.assertIn("groups under 5 hidden", html_out)

    def test_identifier_column_fails_the_save(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        lay["visuals"].append({"id": "P2-V99", "name": "people", "page": "P2", "type": "tableEx", "x": 0, "y": 0,
                               "w": 100, "h": 100, "bindings": {"Values": ["DataTable[EmployeeID]", "[Headcount]"]}})
        run = fake_runner([30.0, 25.0])
        run.qs = W.queries(lay, model)
        with self.assertRaises(W.PrivacyError) as e:
            W.fetch(lay, model, 0, runner=run)
        self.assertIn("P2-V99: groups by DataTable[EmployeeID]", str(e.exception))
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:                                        # through main: exit 1, no file written
            lf = tmp / "design" / "specs" / "layout.json"
            lf.parent.mkdir(parents=True)
            lf.write_text(json.dumps(lay), encoding="utf-8")
            out = tmp / "wf.json"
            from pbikit import slicerfit
            orig, orig_port = W.run, slicerfit.require_port
            W.run = lambda dax, port, script=None: run(dax, port)
            slicerfit.require_port = lambda port=None, *a, **k: 1     # no Desktop here: the port "answers"
            try:
                rc = W.main(["--port", "1", "--layout", str(lf), "--model", str(next((CASES / "rep8" / "project").glob("*.SemanticModel"))),
                             "--out", str(out)])
            finally:
                W.run, slicerfit.require_port = orig, orig_port
            self.assertEqual(rc, 1)
            self.assertFalse(out.exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_row_level_output_fails(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = {**PRIVACY, "maxRows": 3}
        run = fake_runner([30.0, 25.0, 40.0, 50.0])
        run.qs = W.queries(lay, model)
        with self.assertRaises(W.PrivacyError) as e:
            W.fetch(lay, model, 0, runner=run)
        self.assertIn("looks row-level", str(e.exception))

    def test_missing_alt_text_is_listed(self):
        lay, _, _, _ = case("rep8")
        missing = G.missing_alt_text(lay)
        self.assertIn("P1-V15", missing, "Rep 8's line chart has no alt text")
        self.assertNotIn("P1-V05", missing, "slicers don't need it")
        self.assertNotIn("P1-V01", missing, "shapes don't need it")
        for v in lay["visuals"]:
            if v["id"] in missing:
                v.setdefault("container", {})
                if isinstance(v["container"], dict):
                    v["container"]["altText"] = f"What {v['name']} shows"
                else:
                    v["container"] = {"altText": "x"}
        self.assertEqual(G.missing_alt_text(lay), [])

    def test_selected_token_passes_aa_with_white(self):
        from pbikit.a11y import contrast
        tok = json.loads((KIT / "design" / "tokens.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(contrast("#FFFFFF", tok["colors"]["selected"]), 4.5)   # a rep may change teal freely

    def test_define_makes_proposed_measures_known(self):
        """wireframe_data.py --define: measures proposed at /plan, run query-scoped, before they are in the model."""
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        lay["visuals"].append({"id": "P1-V98", "name": "proposed", "page": "P1", "type": "cardVisual", "x": 0, "y": 0,
                               "w": 100, "h": 100, "bindings": {"Data": ["[Proposed KPI]"]}})
        self.assertNotIn("P1-V98", W.queries(lay, model), "an unknown measure is skipped")
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            f = tmp / "proposed.dax"
            f.write_text("// proposed at /plan\nMEASURE '_Measures'[Proposed KPI] = [Headcount] * 2\n", encoding="utf-8")
            W.load_defines(f)
            q = W.queries(lay, model)["P1-V98"]
            self.assertIn("[Proposed KPI]", q["dax"])
            self.assertTrue(W.with_defines(q["dax"]).startswith("DEFINE\nMEASURE '_Measures'[Proposed KPI]"))
            self.assertNotIn("// proposed", W.with_defines(q["dax"]))
        finally:
            W.DEFS.update({"text": "", "names": set()})
            shutil.rmtree(tmp, ignore_errors=True)

    def test_reference_lines_topn_and_point_colours(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        v = next(x for x in lay["visuals"] if x["id"] == "P1-V16")      # turnover by department, company line
        v["filters"] = [{"type": "TopN", "field": "DataTable[Department]", "by": "[Turnover Rate]", "n": 2}]
        v.setdefault("cf", []).append({"type": "measure", "object": "dataPoint", "property": "fill",
                                       "measure": "[Turnover vs Company Colour]", "perPoint": True})
        qs = W.queries(lay, model)
        q = qs["P1-V16"]
        self.assertTrue(q["colour"])
        self.assertIn("__colour", q["dax"])
        self.assertTrue(q["refs"], "the layout's reference line")

        def runner(n_ref):
            def run(dax, port):
                if any(x.get("refDax") == dax for x in qs.values()):
                    return [[n_ref, 0.12]]
                qq = next(x for x in qs.values() if x["dax"] == dax)
                ng, ns, nv = len(qq["groups"]), sum(1 for g in qq["groups"] if g["sortBy"]), len(qq["values"])
                rows = [[f"D{i}"] * ng + [float(i)] * ns + [40.0] + [0.1 * (i + 1)] * nv for i in range(4)]
                if qq.get("colour"):
                    rows = [r + ["#A84545"] for r in rows]
                return rows if ng else [[40.0] + [1.0] * nv]
            return run

        out = W.fetch(lay, model, 0, runner=runner(40.0))["visuals"]["P1-V16"]
        self.assertEqual(len(out["rows"]), 2, "Top N keeps n rows")
        self.assertEqual(out["colours"], ["#A84545", "#A84545"])
        self.assertEqual(out["refLines"][0]["value"], 0.12)
        small = W.fetch(lay, model, 0, runner=runner(3.0))["visuals"]["P1-V16"]
        self.assertIsNone(small["refLines"][0]["value"], "a reference line over fewer than 5 people shows no value")

    def test_topn_by_a_measure_the_visual_does_not_show(self):
        """Rep 10 (P1-V10, P2-V04, P2-V07, P3-V07): the Top N runs in the query, ranked by its own measure."""
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        bar = next(x for x in lay["visuals"] if x["id"] == "P1-V16")     # turnover rate by department
        bar["filters"] = [{"type": "TopN", "field": "DataTable[Department]", "by": "[Headcount]", "n": 2,
                           "direction": "Bottom"}]
        bar["sort"] = {"field": "[Turnover Rate]", "direction": "Descending"}
        mx = next(x for x in lay["visuals"] if x["id"] == "P2-V17")      # department and job role rows
        mx["filters"] = [{"type": "TopN", "field": "DataTable[Department]", "by": "[Hires]", "n": 1}]
        qs = W.queries(lay, model)
        q = qs["P1-V16"]
        self.assertTrue(q["dax"].startswith("DEFINE\nVAR __top0 = SELECTCOLUMNS ( TOPN ( 2, SUMMARIZECOLUMNS ( "
                                            "'DataTable'[Department]"), q["dax"])
        self.assertIn('"__by", [Headcount] ), [__by], ASC )', q["dax"])
        self.assertIn("TREATAS ( __top0, 'DataTable'[Department] )", q["dax"])
        self.assertNotIn('"v1"', q["dax"], "the ranking measure is not returned as a value")
        self.assertNotIn("topN", q, "no cut in Python: the query already keeps the members")
        self.assertEqual(q["order"], {"value": 0, "desc": True}, "the layout's sort orders the kept members")
        m = qs["P2-V17"]
        self.assertIn("TOPN ( 1, ", m["dax"])
        self.assertIn('[Hires] ), [__by], DESC )', m["dax"])
        self.assertNotIn("topN", m, "every row of the kept members stays (department x job role)")
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:                                     # proposed measures go before the VAR in the same DEFINE
            f = tmp / "proposed.dax"
            f.write_text("MEASURE '_Measures'[Rank Key] = [Headcount]\n", encoding="utf-8")
            W.load_defines(f)
            self.assertTrue(W.with_defines(q["dax"]).startswith("DEFINE\nMEASURE '_Measures'[Rank Key] = "
                                                                "[Headcount]\n\nVAR __top0"))
        finally:
            W.DEFS.update({"text": "", "names": set(), "formats": {}})
            shutil.rmtree(tmp, ignore_errors=True)

        others = fake_runner([40.0, 40.0, 40.0])
        others.qs = qs

        def run(dax, port):
            if dax == q["dax"]:                  # the two kept departments, unordered
                return [["Sales", 40.0, 0.1], ["R&D", 40.0, 0.3]]
            return others(dax, port)
        out = W.fetch(lay, model, 0, runner=run)["visuals"]
        self.assertEqual(out["P1-V16"]["rows"], [["R&D", 0.3], ["Sales", 0.1]])
        self.assertEqual(len(out["P2-V17"]["rows"]), 3)

    def test_format_comments_of_proposed_measures(self):
        """Rep 10: `// format [Measure] = ...` lines in proposed-measures.dax give the wireframe its formats."""
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        for i, m in enumerate(("[Growth]", "[Share]", "[Headcount]")):
            lay["visuals"].append({"id": f"P1-V9{i}", "name": "kpi", "page": "P1", "type": "cardVisual", "x": 0,
                                   "y": 0, "w": 100, "h": 100, "bindings": {"Data": [m]}})
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            f = tmp / "proposed.dax"
            f.write_text('// format [Growth] = 0"×"\n// format \'_Measures\'[Share] = 0%\n'
                         "// format [Headcount] = #,0.0\n"
                         "MEASURE '_Measures'[Growth] = 64\nMEASURE '_Measures'[Share] = 0.45\n", encoding="utf-8")
            W.load_defines(f)
            self.assertEqual(W.DEFS["formats"], {"Growth": '0"×"', "Share": "0%", "Headcount": "#,0.0"})
            qs = W.queries(lay, model)
            self.assertEqual(qs["P1-V90"]["values"][0]["format"], '0"×"')
            self.assertEqual(qs["P1-V91"]["values"][0]["format"], "0%")
            self.assertEqual(qs["P1-V92"]["values"][0]["format"], "#,0.0", "a model measure's proposed format wins")
            self.assertNotIn("format", W.with_defines(qs["P1-V90"]["dax"]))
        finally:
            W.DEFS.update({"text": "", "names": set(), "formats": {}})
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(W.known_measure(model, "Growth"), (False, None), "no format without the measure")

    def card_dom(self, props, value, fmt):
        """The drawn text of one new card holding `value` (format `fmt`), via headless Edge."""
        lay, tok, _, theme = case("rep8")
        lay["visuals"] = [{"id": "P1-V01", "name": "card", "page": "P1", "type": "cardVisual", "x": 0, "y": 0,
                           "w": 300, "h": 120, "bindings": {"Data": ["[Headcount]"]}, "props": props}]
        data = {"privacy": ["privacy check passed"], "visuals": {"P1-V01": {
            "groups": [], "values": ["Headcount"], "formats": [fmt], "cat": None, "leg": None, "rows": [[value]],
            "counts": [40], "hidden": 0, "total": 1}}}
        return edge_dom(self, G.build_html(lay, tok, theme, data))

    def test_image_cards_draw_no_value(self):
        """Rep 10 sparkline and parity cards: value.show off -> the value is not drawn; labelPrecision sets decimals."""
        props = {"value.show@default": False, "label.show@default": False, "image.show@default": True}
        lay, tok, _, theme = case("rep8")
        lay["visuals"] = [{"id": "P1-V01", "name": "spark", "page": "P1", "type": "cardVisual", "x": 0, "y": 0,
                           "w": 300, "h": 44, "bindings": {"Data": ["[Headcount]"]}, "props": props,
                           "cf": [{"type": "image", "measure": "[img Spark]"}]}]
        self.assertFalse(G.spec_for(G.Resolver(tok, theme), lay["visuals"][0], lay, {})["card"]["value"])
        self.assertNotIn("4,321", self.card_dom(props, 4321.0, "#,0"))
        self.assertIn("4,321", self.card_dom({}, 4321.0, "#,0"))
        self.assertIn(">45%<", self.card_dom({"value.labelPrecision@default": 0}, 0.4503, "0.0%"))
        self.assertIn(">64×<", self.card_dom({}, 63.517, '0"×"'))

    def test_images_drawn_from_their_files(self):
        """Rep 10 hero tiles: image visuals and page / container backgrounds drawn from their files, embedded once."""
        lay, tok, _, theme = case("rep8")
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "design" / "assets" / "png").mkdir(parents=True)
            (tmp / "design" / "images").mkdir(parents=True)
            png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS"
                   b"\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00"
                   b"\x00IEND\xaeB`\x82")
            (tmp / "design" / "assets" / "png" / "hero-p1.png").write_bytes(png)
            (tmp / "design" / "images" / "wall.svg").write_text(
                "<svg xmlns='http://www.w3.org/2000/svg' width='4' height='4'><rect width='4' height='4'/></svg>",
                encoding="utf-8")
            reg = lambda name: {"raw": {"expr": {"ResourcePackageItem": {   # noqa: E731
                "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": name}}}}
            lay["_root"] = str(tmp)
            lay["pages"] = {"P1": {"displayName": "One", "background": "background"}}
            lay["visuals"] = [
                {"id": "P1-V01", "name": "hero-bg", "page": "P1", "type": "image", "x": 40, "y": 40, "w": 400,
                 "h": 300, "props": {"general.imageUrl": reg("hero-p1.png")}},           # found by ItemName
                {"id": "P1-V02", "name": "hero", "page": "P1", "type": "textbox", "x": 60, "y": 60, "w": 300,
                 "h": 80, "z": 3, "text": [{"runs": [{"text": "64×", "color": "#FFFFFF"}]}]},
                {"id": "P1-V03", "name": "wall", "page": "P1", "type": "image", "image": "design/images/wall.png",
                 "build": {"method": "page-background"}},                            # same stem, .svg on disk
                {"id": "P1-V04", "name": "gone", "page": "P1", "type": "image", "x": 500, "y": 40, "w": 100,
                 "h": 100, "resource": "design/assets/png/missing.png"},
                {"id": "P1-V05", "name": "tile", "page": "P1", "type": "shape", "x": 600, "y": 40, "w": 100,
                 "h": 100, "container": {"background": {"image": "design/assets/png/hero-p1.png"}}}]
            out = G.build_html(lay, tok, theme, None)
            spec = json.loads(out.split('id="spec">', 1)[1].split("</script>", 1)[0])
            self.assertEqual(sorted(spec["images"]), ["design/assets/png/hero-p1.png", "design/images/wall.svg"])
            self.assertTrue(spec["images"]["design/assets/png/hero-p1.png"].startswith("data:image/png;base64,"))
            self.assertEqual(out.count("data:image/png;base64,"), 1, "each file embedded once")
            self.assertEqual(spec["pages"][0]["walls"][0]["src"], "design/images/wall.svg")
            self.assertEqual(G.MISSING_IMAGES, ["design/assets/png/missing.png"])
            dom = edge_dom(self, out)
            self.assertEqual(dom.count("url(&quot;data:image/png;base64,"), 2)       # the image and the tile
            self.assertIn('<div class="wall" style="position: absolute; left: 0px; top: 0px; width: 1920px', dom)
            self.assertIn("url(&quot;data:image/svg+xml;base64,", dom)
            self.assertIn("not found: design/assets/png/missing.png", dom)
            self.assertNotIn("render error", dom)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_identifier_names(self):
        for c in ("EmployeeID", "Employee ID", "CustomerKey", "Email", "Birth Date", "Address"):
            self.assertTrue(W.looks_like_identifier(c), c)
        for c in ("Paid", "Valid", "Month Number", "Department", "JobRole", "Gender"):
            self.assertFalse(W.looks_like_identifier(c), c)

    def test_renderer_refuses_unchecked_data(self):
        lay, tok, _, theme = case("rep4-parity")
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "lay.json").write_text(json.dumps(lay), encoding="utf-8")
            (tmp / "tok.json").write_text(json.dumps(tok), encoding="utf-8")
            (tmp / "data.json").write_text(json.dumps({"visuals": {}}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                G.main(["--layout", str(tmp / "lay.json"), "--tokens", str(tmp / "tok.json"), "--data",
                        str(tmp / "data.json"), "--out", str(tmp / "wf.html")])
            self.assertFalse((tmp / "wf.html").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)



class PatternTests(unittest.TestCase):
    """docs/patterns/: one renderer per pattern, and the Deneb (Vega-Lite) renderer, on the gallery layout."""
    GALLERY = KIT / "docs" / "patterns" / "gallery-layout.json"

    def gallery(self, vega="offline"):
        lay = json.loads(self.GALLERY.read_text(encoding="utf-8"))
        tok = json.loads((KIT / "design" / "tokens.json").read_text(encoding="utf-8"))
        out = G.build_html(lay, tok, None, None, vega=vega)
        return out, json.loads(out.split('id="spec">', 1)[1].split("</script>", 1)[0])

    def test_every_pattern_has_a_renderer_and_a_page(self):
        out, spec = self.gallery()
        for name in G.PATTERNS:
            self.assertIn(f"P['{name}'] = ", out, name)
            self.assertTrue((KIT / "docs" / "patterns" / f"{name}.md").exists(), name)
        self.assertEqual({s["pattern"] for s in spec["visuals"]}, G.PATTERNS)
        self.assertIn("pattern: ${esc(s.pattern)}", out)

    def test_unknown_pattern_falls_back_to_the_type(self):
        lay = {"pages": {"P1": {}}, "visuals": [{"id": "P1-V01", "page": "P1", "type": "lineChart", "pattern": "nope"}]}
        s = json.loads(G.build_html(lay, {}, None, None).split('id="spec">', 1)[1].split("</script>", 1)[0])
        self.assertIsNone(s["visuals"][0]["pattern"])

    def test_deneb_spec_inline_or_from_a_file(self):
        _, spec = self.gallery()
        dn = [s for s in spec["visuals"] if s["type"] == "deneb"]
        self.assertEqual(len(dn), 3)                       # range, partial (layered), brush (one layer + interval)
        self.assertTrue(all(s["tag"] == "Deneb" and (s["deneb"]["spec"].get("layer") or s["deneb"]["spec"].get("mark"))
                            for s in dn))
        self.assertTrue(any(p.get("select", {}).get("type") == "interval" for s in dn for p in s["deneb"]["spec"].get("params", [])))
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "p1-v01.vl.json").write_text('{"mark": "bar"}', encoding="utf-8")
            lay = {"_root": str(tmp), "pages": {"P1": {}}, "visuals": [
                {"id": "P1-V01", "page": "P1", "type": "deneb", "deneb": {"spec": "p1-v01.vl.json"}},
                {"id": "P1-V02", "page": "P1", "type": "deneb", "deneb": {"spec": "missing.json"}}]}
            s = json.loads(G.build_html(lay, {}, None, None).split('id="spec">', 1)[1].split("</script>", 1)[0])
            self.assertEqual(s["visuals"][0]["deneb"]["spec"], {"mark": "bar"})
            self.assertIn("not found", s["visuals"][1]["deneb"]["spec"]["_error"])
        finally:
            shutil.rmtree(tmp)

    def test_w4_vega_lite_by_default_subset_offline(self):
        """W4 (Rep 10 P1-V09): Vega-Lite itself by default (online), the subset renderer when it didn't load, and
        vega "offline" loads nothing."""
        lay = json.loads(self.GALLERY.read_text(encoding="utf-8"))
        tok = json.loads((KIT / "design" / "tokens.json").read_text(encoding="utf-8"))
        out = G.build_html(lay, tok, None, None)
        for u in G.VEGA_CDN:
            self.assertIn(f'<script src="{u}"></script>', out)
            self.assertRegex(u, r"@\d+\.\d+\.\d+/")             # pinned exact versions
        self.assertEqual(json.loads(out.split('id="spec">', 1)[1].split("</script>", 1)[0])["vega"], "cdn")
        self.assertIn("if (S.vega === 'cdn' && window.vegaEmbed)", out)
        self.assertIn("offline: drawn by the Vega-Lite subset renderer", out)
        sub, spec = self.gallery("offline")
        self.assertNotIn("cdn.jsdelivr.net/npm/vega", sub.split("<script>", 1)[0])
        self.assertEqual(spec["vega"], "offline")
        self.assertEqual(self.gallery("subset")[1]["vega"], "offline", "the older name still works")

    def test_vega_project_setting(self):
        """layout.json `vega`: "cdn" (default) or "offline"; --vega overrides it; anything else stops."""
        lay = json.loads(self.GALLERY.read_text(encoding="utf-8"))
        spec = lambda out: json.loads(out.split('id="spec">', 1)[1].split("</script>", 1)[0])["vega"]   # noqa: E731
        self.assertEqual(spec(G.build_html(lay, {}, None, None)), "cdn")
        lay["vega"] = "offline"
        out = G.build_html(lay, {}, None, None)
        self.assertEqual(spec(out), "offline")
        self.assertNotIn("cdn.jsdelivr.net/npm/vega", out.split("<script>", 1)[0])
        self.assertEqual(spec(G.build_html(lay, {}, None, None, vega="cdn")), "cdn", "--vega wins")
        lay["vega"] = "online"
        with self.assertRaises(SystemExit):
            G.build_html(lay, {}, None, None)

    def test_w4_subset_renderer_runs_calculate_filter_and_conditions(self):
        """W4: offline, `transform` calculate and filter and conditional colours apply (text drawn once, not on
        every point)."""
        spec = {"transform": [{"calculate": "datum['Nations'] < 100 && datum['Year'] >= 1948", "as": "Exception"}],
                "encoding": {"x": {"field": "Year", "type": "ordinal"}},
                "layer": [{"mark": {"type": "point", "filled": True},
                           "encoding": {"y": {"field": "Nations", "type": "quantitative"},
                                        "color": {"condition": {"test": "datum['Exception']", "value": "#E0533D"},
                                                  "value": "#0F172A"}}},
                          {"transform": [{"filter": "datum['Exception'] && datum['Year'] == 1976"}],
                           "mark": {"type": "text"}, "encoding": {"y": {"field": "Nations", "type": "quantitative"},
                                                                  "text": {"value": "1976 boycott"}}}]}
        lay = {"pages": {"P1": {}}, "visuals": [{"id": "P1-V01", "page": "P1", "type": "deneb", "x": 0, "y": 0, "w": 600,
                                                 "h": 300, "bindings": {"dataset": ["Games[Year]", "[Nations]"]},
                                                 "deneb": {"spec": spec}}]}
        data = {"privacy": ["privacy check passed"], "visuals": {"P1-V01": {
            "groups": ["Year"], "values": ["Nations"], "formats": ["#,0"], "cat": 0, "leg": None,
            "rows": [[1936.0, 49.0], [1972.0, 121.0], [1976.0, 92.0], [1980.0, 80.0]], "counts": [9] * 4,
            "hidden": 0, "total": 4}}}
        dom = edge_dom(self, G.build_html(lay, {}, None, data, vega="offline"))
        self.assertEqual(dom.count(">1976 boycott<"), 1)
        self.assertEqual(dom.count('fill="#E0533D"'), 2, "1976 and 1980; 1936 is before 1948")
        self.assertEqual(dom.count('fill="#0F172A"'), 2)
        self.assertNotIn("not drawn", dom)

    def test_gallery_renders_without_errors_in_edge(self):
        out, _ = self.gallery()
        dom = edge_dom(self, out)                          # the drawn page only
        self.assertIn('data-id="P2-V02"', dom)
        self.assertNotIn("render error", dom)
        self.assertNotIn("no wireframe renderer", dom)
        self.assertGreater(dom.count("<circle"), 40)          # dots, dumbbells, hollow points drawn


def page_of(visuals, data):
    """A one-page layout (Rep 8's tokens and theme) holding `visuals`, and a checked data file holding `data`."""
    lay, tok, _, theme = case("rep8")
    lay["pages"] = {"P1": {"displayName": "One"}}
    lay["visuals"] = visuals
    full = {}
    for vid, d in data.items():
        full[vid] = {"cat": 0 if d.get("groups") else None, "leg": None, "counts": [9] * len(d["rows"]), "hidden": 0,
                     "total": len(d["rows"]), **d}
    return G.build_html(lay, tok, theme, {"privacy": ["privacy check passed"], "visuals": full})


def svg_of(dom, vid):
    """The markup of one visual (its element up to the next visual)."""
    i = dom.index(f'data-id="{vid}"')
    j = dom.find('data-id="P', i + 10)
    return dom[i:j if j > 0 else None]


class DesktopMatchTests(unittest.TestCase):
    """The wireframe drawing limits W1-W9 (Rep 10 design/known-gaps.md): each drawn as Desktop draws it."""

    def test_w1_matrix_with_columns_is_a_grid_with_cell_colours_and_dashes(self):
        """W1 (Rep 10 P2-V04): rows x columns in the columns' sort order, rows by their total, each cell's colours
        from its cf measures, an en dash where there is no value, the hidden-groups note only with the labels."""
        v = {"id": "P1-V01", "name": "m", "page": "P1", "type": "pivotTable", "x": 0, "y": 0, "w": 600, "h": 300,
             "bindings": {"Rows": [{"field": "NOC[NOC]", "displayName": "Nation"}], "Columns": ["Games[Decade Label]"],
                          "Values": [{"field": "[Medals Cell]", "displayName": "Medals"}]},
             "sort": {"field": "[Medals Cell]", "direction": "Descending"},
             "columnWidths": {"NOC[NOC]": 96, "[Medals Cell]": 74},
             "props": {"columnHeaders.alignment": "Center", "grid.gridHorizontalWeight": 4, "grid.gridVertical": True,
                       "grid.gridVerticalWeight": 4, "grid.rowPadding": 11}}
        d = {"groups": ["Nation", "Decade Label"], "values": ["Medals"], "formats": ["#,0;–;0"], "leg": 1,
             "rows": [["FRA", "1890s", 11.0], ["FRA", "1900s", -1.0], ["USA", "1890s", 19.0], ["USA", "1900s", 330.0]],
             "backs": ["#E9C46A", "#F3F5F9", "#D4AF37", "#D4AF37"], "fonts": ["#111111", "#8A96A3", "#111111", "#111111"],
             "levels": [["FRA", "GBR", "USA"], ["1890s", "1900s", "1910s"]], "hidden": 2}
        out = page_of([v], {"P1-V01": d})
        self.assertIn("body.notag .hiddenrows", out, "the note goes with the labels, so it never covers a visual")
        m = svg_of(edge_dom(self, out), "P1-V01")
        self.assertEqual(m.count("<tr>"), 4, "a header and one row per nation, not one row per nation and decade")
        self.assertEqual(re.findall(r">(1890s|1900s|1910s)</th>", m), ["1890s", "1900s", "1910s"])
        self.assertEqual(re.findall(r">(USA|FRA|GBR)</th>", m), ["USA", "FRA", "GBR"], "rows by their total, then data order")
        self.assertIn("background:#D4AF37\">330<", m.replace(" ", ""))
        self.assertIn("border-spacing:4px 4px", m)
        self.assertEqual(m.count(">–<"), 6, "FRA 1900s (no team: the format's dash), GBR's 3 hidden cells, 1910s")
        self.assertIn("<col style=\"width:92px\">", m, "Desktop's 96px column includes the 4px gap")

    def test_w1_data_keeps_cell_colours_and_column_order(self):
        q = {"groups": [{"label": "Nation", "sortBy": None}, {"label": "Decade", "sortBy": "'Games'[Decade]"}],
             "values": [{"label": "Medals", "format": "#,0"}], "cat": 0, "leg": 1, "extras": ["back", "font"]}
        raw = [["USA", "2000s", 2000.0, 40.0, 300.0, "#D4AF37", "#111111"],
               ["USA", "1990s", 1990.0, 40.0, 200.0, "#C0C0C0", "#111111"],
               ["GBR", "1990s", 1990.0, 3.0, 9.0, "#F3F5F9", "#111111"],
               ["GBR", "2000s", 2000.0, 2.0, 4.0, "#F3F5F9", "#111111"]]
        out = W.shape(q, raw, {"minGroup": 5})
        self.assertEqual(out["levels"][1], ["1990s", "2000s"], "the decade's sort-by column, not the text")
        self.assertEqual(out["levels"][0], ["GBR", "USA"], "a nation with every cell hidden keeps its row")
        self.assertEqual(out["backs"], ["#C0C0C0", "#D4AF37"])
        self.assertEqual(out["rows"], [["USA", "1990s", 200.0], ["USA", "2000s", 300.0]])

    def test_w2_rank_lines_over_negative_values_with_end_labels(self):
        """W2 (Rep 10 P2-V07): ranks stored as -rank draw inside the plot, rank 1 on top, the label measure at both
        ends (left of the first point, right of the last), no minus signs on the axis."""
        v = {"id": "P1-V01", "name": "slope", "page": "P1", "type": "lineChart", "pattern": "direct-labels",
             "x": 0, "y": 0, "w": 600, "h": 360,
             "bindings": {"Category": ["Games[Decade Label]"], "Series": [{"field": "NOC[NOC]", "displayName": "Nation"}],
                          "Y": [{"field": "[Rank Plot]", "displayName": "Rank"}]},
             "props": {"labels.show": True, "categoryAxis.axisType": "Categorical"}}
        rows = [["1980s", "JPN", -16.0], ["1980s", "USA", -2.0], ["1980s", "CHN", -9.0],
                ["2010s", "JPN", -6.0], ["2010s", "CHN", -2.0], ["2010s", "USA", -1.0]]
        d = {"groups": ["Decade Label", "Nation"], "values": ["Rank"], "formats": ["0;0;0"], "leg": 1, "rows": rows,
             "labels": {"Rank": ["JPN 16th", "USA 2nd", "CHN 9th", "6th JPN", "2nd CHN", "1st USA"]}}
        m = svg_of(edge_dom(self, page_of([v], {"P1-V01": d})), "P1-V01")
        lines = re.findall(r'<polyline points="([^"]+)"', m)
        self.assertEqual(len(lines), 3)
        ys = {n: [float(p.split(",")[1]) for p in pts.split()] for n, pts in zip(("JPN", "USA", "CHN"), lines)}
        self.assertTrue(all(0 < y < 360 for v_ in ys.values() for y in v_), ys)
        self.assertLess(ys["USA"][1], ys["JPN"][0], "rank 1 above rank 16")
        self.assertRegex(m, r'text-anchor="end"[^>]*>JPN 16th<')
        self.assertRegex(m, r'text-anchor="start"[^>]*>6th JPN<')
        self.assertNotRegex(m, r">[−-]\d", "the format's negative section has no sign")

    def test_w3_image_cards_and_table_images_draw_the_svg_measure(self):
        """W3 (Rep 10 P1-V16, P1-V24): the SVG the image measure returned is drawn as Power BI reads it (a raw % in
        DaxLib.SVG output: no %-decoding, so raw # colours draw)."""
        svg = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100%' height='100%' "
               "viewBox='0 0 10 10'><rect fill='#2F5BEA' width='10' height='10'/></svg>")
        card = {"id": "P1-V01", "name": "spark", "page": "P1", "type": "cardVisual", "x": 0, "y": 0, "w": 300, "h": 44,
                "bindings": {"Data": ["[Athletes Latest]"]}, "cf": [{"type": "image", "measure": "[img Spark]"}],
                "props": {"value.show@default": False, "label.show@default": False}}
        table = {"id": "P1-V02", "name": "t", "page": "P1", "type": "tableEx", "x": 0, "y": 60, "w": 300, "h": 100,
                 "bindings": {"Values": ["NOC[NOC]", "[img Bar]"]}}
        dom = edge_dom(self, page_of([card, table], {
            "P1-V01": {"groups": [], "values": ["Athletes Latest"], "formats": ["#,0"], "rows": [[11179.0]], "images": [svg]},
            "P1-V02": {"groups": ["NOC"], "values": ["img Bar"], "formats": [None], "rows": [["USA", svg]]}}))
        c, t = svg_of(dom, "P1-V01"), svg_of(dom, "P1-V02")
        self.assertIn('<img alt="" src="data:image/svg+xml;charset=utf-8,%3Csvg', c)
        self.assertIn("%232F5BEA", c)
        self.assertNotIn("image from data", c)
        self.assertNotIn("11,179", c)
        self.assertIn("%232F5BEA", t)

    def test_w3_image_measures_are_evaluated_from_report_extensions(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        lay["visuals"] = [{"id": "P1-V01", "page": "P1", "type": "cardVisual", "bindings": {"Data": ["[1_Headcount]"]},
                           "cf": [{"type": "image", "measure": "[img Spark]"}]}]
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            rd = tmp / "X.Report" / "definition"
            rd.mkdir(parents=True)
            (rd / "reportExtensions.json").write_text(json.dumps({"entities": [{"name": "_Measures", "measures": [
                {"name": "img Spark", "expression": "DaxLib.SVG.Viz.Area ( 'Date'[Year], [1_Headcount] )",
                 "dataType": "Text", "dataCategory": "ImageUrl"}]}]}), encoding="utf-8")
            W.load_extensions(tmp)
            q = W.queries(lay, model)["P1-V01"]
            self.assertTrue(q["dax"].startswith("DEFINE\nMEASURE '_Measures'[img Spark] = DaxLib.SVG.Viz.Area"))
            self.assertIn("UNICHAR ( 10 )", q["dax"], "the SVG text on one line")
            out = W.fetch(lay, model, 0, runner=lambda dax, port: [[40.0, 12.0, "data:image/svg+xml;utf8,<svg/>"]])
            self.assertEqual(out["visuals"]["P1-V01"]["images"], ["data:image/svg+xml;utf8,<svg/>"])
            self.assertEqual(out["visuals"]["P1-V01"]["rows"], [[12.0]])
        finally:
            W.EXT.clear()
            shutil.rmtree(tmp, ignore_errors=True)

    def test_w5_card_alignment_fonts_and_several_fields(self):
        """W5 (Rep 10 P1-V05, P1-V13, P1-V14): layout.alignment, the label's size and font, the value's font, and
        every field of a multi-field card."""
        v = {"id": "P1-V01", "name": "glass", "page": "P1", "type": "cardVisual", "x": 0, "y": 0, "w": 668, "h": 140,
             "bindings": {"Data": [{"field": "[Games Held]", "displayName": "Games"}, {"field": "[Athletes]", "displayName": "athletes"},
                                   {"field": "[Nations]", "displayName": "nations"}]},
             "props": {"layout.alignment@none": "top", "layout.columnCount@none": 3, "label.fontSize@default": 11,
                       "label.fontFamily@default": "Segoe UI Semibold", "label.position@default": "aboveValue",
                       "value.fontFamily@default": "'Segoe UI Bold', wf_segoe-ui_bold, helvetica, arial, sans-serif",
                       "value.horizontalAlignment@default": "left"}}
        regular = {**v, "id": "P1-V02", "y": 200, "bindings": {"Data": ["[Hero Insight]"]},
                   "props": {"value.fontFamily@default": "Segoe UI"}}
        dom = edge_dom(self, page_of([v, regular], {
            "P1-V01": {"groups": [], "values": ["Games", "athletes", "nations"], "formats": ["#,0"] * 3, "rows": [[28.0, 116175.0, 229.0]]},
            "P1-V02": {"groups": [], "values": ["Hero Insight"], "formats": [None], "rows": [["The Games grew"]]}}))
        m, r = svg_of(dom, "P1-V01"), svg_of(dom, "P1-V02")
        self.assertIn("justify-content: flex-start", m)
        self.assertIn("grid-template-columns:repeat(3,", m)
        for x in (">28<", ">116,175<", ">229<", ">athletes<", ">nations<"):
            self.assertIn(x, m)
        self.assertIn("font-weight:600;font-size:14.7px", m, "the label: 11pt Segoe UI Semibold")
        self.assertIn("font-family:'Segoe UI';font-weight:700", m, "the value: Segoe UI Bold from the CSS list")
        self.assertLess(m.index(">Games<"), m.index(">28<"), "label above the value")
        self.assertIn("font-family:'Segoe UI';font-weight:400", r, "value.fontFamily Segoe UI: regular, not semibold")

    def test_w6_totals_label_measures_axis_range_and_fonts(self):
        """W6 (Rep 10 P1-V10, P2-V08, P3-V05, P3-V07): totals.show, a label measure per series (labels.show off for
        one series), an axis end from a measure, bold category labels, the legend on top."""
        v = {"id": "P1-V01", "name": "c", "page": "P1", "type": "columnChart", "x": 0, "y": 0, "w": 500, "h": 300,
             "bindings": {"Category": ["Games[Decade]"], "Y": [{"field": "[Women]", "displayName": "Women"},
                                                             {"field": "[Men]", "displayName": "Men"}]},
             "props": {"totals.show": True, "labels.show": True, "labels.show@[Men]": False,
                       "categoryAxis.fontFamily": "'Segoe UI Bold', wf_segoe-ui_bold", "legend.position": "Top"}}
        d = {"groups": ["Decade"], "values": ["Women", "Men"], "formats": ["#,0", "#,0"],
             "rows": [["1990s", 40.0, 60.0], ["2000s", 45.0, 55.0]], "labels": {"Women": ["40%", "45%"]},
             "axis": {"end": 200}}
        m = svg_of(edge_dom(self, page_of([v], {"P1-V01": d})), "P1-V01")
        self.assertIn(">40%<", m)
        self.assertIn(">45%<", m)
        self.assertNotIn(">60<", m, "labels.show off for Men")
        self.assertEqual(len(re.findall(r'font-weight="600"[^>]*>100<', m)), 2, "a total over each column")
        self.assertIn(">200<", m)
        self.assertNotRegex(m, r">2[2-9]0<|>300<", "no tick above the axis end")
        self.assertRegex(m, r'font-weight="700"[^>]*>1990s<')
        self.assertRegex(m, r'<text x="[\d.]+" y="12"[^>]*>Women<', "legend on top")

    def test_w6_label_and_axis_measures_in_the_query(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        sel = '{"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "_Measures.1_Headcount"}'
        lay["visuals"] = [{"id": "P1-V01", "page": "P1", "type": "clusteredColumnChart",
                           "bindings": {"Category": ["DataTable[Department]"], "Y": [{"field": "[1_Headcount]", "displayName": "HC"}]},
                           "cf": [{"type": "measure", "object": "labels", "property": "dynamicLabelValue",
                                   "measure": "[1_Headcount LY]", "target": "[1_Headcount]", "perPoint": True},
                                  {"type": "measure", "object": "valueAxis", "property": "end", "measure": "[1_Headcount LY]"}],
                           "props": {f"labels.dynamicLabelValue@{sel}": {"raw": {"expr": {"Measure": {
                               "Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": "2_Hires LY"}}}}}}]
        q = W.queries(lay, model)["P1-V01"]
        self.assertEqual(q["extras"], ["label:HC", "label:HC"])
        self.assertIn('"__x1", IF ( NOT ISBLANK ( [Group Size] ), [2_Hires LY] )', q["dax"])
        self.assertEqual(q["rowItems"], [["axis", "end"]])

        def run(dax, port):
            if dax == q["refDax"]:
                return [[40.0, 250.0]]
            return [["Sales", 40.0, 120.0, "120 now", "3 hires"], ["R&D", 40.0, 80.0, None, None]]
        out = W.fetch(lay, model, 0, runner=run)["visuals"]["P1-V01"]
        self.assertEqual(out["axis"], {"end": 250.0})
        self.assertEqual(out["labels"], {"HC": [None, "3 hires"]}, "one set per series (the later one wins), rows sorted")

    def test_w7_round_ticks_and_reference_line_labels(self):
        """W7 (Rep 10 P2-V08): ticks on round steps with a negative minimum; a reference line with dataLabel off
        draws no label."""
        v = {"id": "P1-V01", "name": "c", "page": "P1", "type": "clusteredColumnChart", "x": 0, "y": 0, "w": 500,
             "h": 300, "bindings": {"Category": ["Games[Year]"], "Y": [{"field": "[Host Boost]", "displayName": "Boost"}]},
             "referenceLines": [{"axis": "value", "value": 0, "label": "", "dataLabel": False},
                                {"axis": "value", "value": 50, "label": "Half", "labelText": "Name"}]}
        d = {"groups": ["Year"], "values": ["Boost"], "formats": ["+0.0;-0.0;0.0"],
             "rows": [[1904.0, 65.3], [1976.0, -0.6], [1980.0, 13.0]],
             "refLines": [{"axis": "value", "label": "", "value": 0}, {"axis": "value", "label": "Half", "value": 50}]}
        m = svg_of(edge_dom(self, page_of([v], {"P1-V01": d})), "P1-V01")
        ticks = re.findall(r'text-anchor="end"[^>]*>([^<]+)<', m)
        self.assertEqual(ticks, ["-20", "0", "+20", "+40", "+60", "+80", "Half"], "ticks (decimals of the step, as "
                         "Desktop draws them), then the label")
        self.assertNotIn("0.00", m)
        self.assertIn(">Half<", m)

    def test_w8_combo_line_on_its_secondary_axis(self):
        """W8 (Rep 10 P3-V06): the line is scaled to secEnd (a measure), not to its own maximum."""
        v = {"id": "P1-V01", "name": "c", "page": "P1", "type": "lineStackedColumnComboChart", "x": 0, "y": 0,
             "w": 500, "h": 300, "bindings": {"Category": ["Games[Year]"], "Y": [{"field": "[Events]", "displayName": "Events"}],
                                              "Y2": [{"field": "[Sports]", "displayName": "Sports"}]},
             "props": {"valueAxis.secShow": False}}
        d = {"groups": ["Year"], "values": ["Events", "Sports"], "formats": ["#,0", "#,0"],
             "rows": [[2008.0, 100.0, 50.0], [2012.0, 300.0, 50.0]], "axis": {"secEnd": 100}}
        m = svg_of(edge_dom(self, page_of([v], {"P1-V01": d})), "P1-V01")
        grid_ys = sorted({float(y) for y in re.findall(r'<line x1="[\d.]+" x2="[\d.]+" y1="([\d.]+)" y2="\1"', m)})
        self.assertEqual(len(grid_ys), 4, grid_ys)                # 0, 100, 200, 300 on the column axis
        line_y = {float(p.split(",")[1]) for p in re.search(r'<polyline points="([^"]+)"', m).group(1).split()}
        self.assertEqual(len(line_y), 1)
        self.assertAlmostEqual(line_y.pop(), (grid_ys[1] + grid_ys[2]) / 2, delta=1, msg="50 of 100: half way up")

    def test_w9_button_slicer_outline_off(self):
        """W9 (Rep 10 P1-V03): outline.show false draws no item borders; the default keeps them."""
        base = {"page": "P1", "type": "advancedSlicerVisual", "x": 0, "y": 0, "w": 240, "h": 52,
                "bindings": {"Values": ["Games[Season]"]}, "items": ["Summer", "Winter"],
                "selection": {"field": "Games[Season]", "values": ["Summer"]}}
        off = {**base, "id": "P1-V01", "props": {"outline.show@default": False, "fillCustom.fillColor@default": "#F1F4F8"}}
        on = {**base, "id": "P1-V02", "y": 100}
        dom = edge_dom(self, page_of([off, on], {}))
        a, b = svg_of(dom, "P1-V01"), svg_of(dom, "P1-V02")
        self.assertEqual(len(re.findall(r'data-item="[^"]+"', a)), 2)
        self.assertNotIn("solid", a)
        self.assertIn("1px solid", b)


class KitV12Tests(unittest.TestCase):
    """Kit v1.2: Desktop's {"id": "default"} selector, theme colours as Desktop saves them, HTML Content, the no-data
    banner and visual measure filters."""

    def test_default_selector_and_theme_data_colours(self):
        R = G.Resolver({"colors": {"card": "#FFFFFF", "text": "#111111"}}, {"dataColors": ["#336699", "#993366"],
                                                                         "background": "#FAFAFA", "foreground": "#222222"})
        raw = lambda cid, pct=0: {"raw": {"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": cid, "Percent": pct}}}}}}
        v = {"props": {'text.fontColor@{"id":"default"}': raw(2), 'fill.show@{"id": "default"}': False,
                       "outline.lineColor@default": "#123456"}}
        self.assertEqual(G.prop(v, "text.fontColor"), {"theme": 2, "percent": 0.0})
        self.assertIs(G.prop(v, "fill.show"), False, '{"id": "default"} with spaces too')
        self.assertEqual(G.prop(v, "outline.lineColor"), "#123456")
        self.assertIsNone(G.prop({"props": {'fill.show@{"metadata": "T.M"}': False}}, "fill.show"),
                          "a per-field selector isn't the visual-wide value")
        self.assertEqual(R.colour(G.prop(v, "text.fontColor")), "#336699", "ColorId 2 = dataColors[0]")
        self.assertEqual(R.colour(raw(0)), "#FAFAFA", "ColorId 0 = background")
        self.assertEqual(R.colour(raw(1)), "#222222", "ColorId 1 = foreground")
        self.assertEqual(R.colour(raw(3, -0.5)), G.shade("#993366", -0.5), "Percent darkens")
        self.assertIsNone(G.selector_key('{"id":"default"}'))

    def test_html_content_tag_frame_and_placeholder(self):
        hc = "htmlContent443BE3AD55E043BF878BED274D3A6855"
        v = {"id": "P1-V01", "name": "h", "page": "P1", "type": hc, "x": 0, "y": 0, "w": 400, "h": 200,
             "bindings": {"content": ["[Status HTML]"]}, "build": {"method": "custom-visual", "step": 4}}
        out = page_of([v], {"P1-V01": {"groups": [], "values": ["Status HTML"], "formats": [None],
                                       "rows": [["<b>On track</b><script>alert(1)</script>"]]}})
        spec = json.loads(out.split('id="spec">', 1)[1].split("</script>", 1)[0])
        s = spec["visuals"][0]
        self.assertEqual((s["tag"], s["render"], s["known"]), ("HTML Content", "htmlContent", True))
        self.assertIn("sandbox", out.split("R.htmlContent", 1)[1][:1200])
        self.assertIn("default-src 'none'", out)
        self.assertNotIn('id="nodata-banner"', out, "with data: no banner")
        lay, tok, _, theme = case("rep8")
        no_data = G.build_html(dict(lay, pages={"P1": {"displayName": "One"}}, visuals=[v]), tok, theme, None)
        self.assertIn("No data – placeholder values", no_data)
        dom = edge_dom(self, out)
        frame = svg_of(dom, "P1-V01")
        self.assertIn("<iframe", frame)
        self.assertIn('sandbox=""', frame)
        dom2 = edge_dom(self, no_data)
        self.assertIn("HTML Content", svg_of(dom2, "P1-V01"))
        self.assertNotIn("<iframe", svg_of(dom2, "P1-V01"), "no data: a labelled box")
        self.assertIn('id="nodata-banner"', dom2)

    def test_html_content_measures_one_line_in_the_query(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        lay["visuals"] = [{"id": "P1-V01", "name": "h", "page": "P1", "type": "htmlContent443BE3AD55E043BF878BED274D3A6855",
                           "x": 0, "y": 0, "w": 400, "h": 200, "bindings": {"content": ["[Headcount]"]}}]
        q = W.queries(lay, model)["P1-V01"]
        self.assertIn("SUBSTITUTE ( SUBSTITUTE ( [Headcount]", q["dax"])

    def test_visual_measure_filters_in_the_query(self):
        lay, _, model, _ = case("rep8")
        lay["privacy"] = PRIVACY
        lay["visuals"] = [{"id": "P1-V01", "name": "t", "page": "P1", "type": "tableEx", "x": 0, "y": 0, "w": 400,
                           "h": 200, "bindings": {"Values": ["DataTable[Department]", "[Headcount]"]},
                           "filters": [{"field": "[Headcount]", "op": ">", "value": 10}]},
                          {"id": "P1-V02", "name": "c", "page": "P1", "type": "cardVisual", "x": 0, "y": 300, "w": 200,
                           "h": 100, "bindings": {"Data": ["[Headcount]"]},
                           "filters": [{"field": "[Headcount]", "op": "<=", "value": 5}]}]
        qs = W.queries(lay, model)
        self.assertIn("EVALUATE FILTER ( SUMMARIZECOLUMNS ( 'DataTable'[Department]", qs["P1-V01"]["dax"])
        self.assertIn("( [Headcount] ) > 10 )", qs["P1-V01"]["dax"])
        self.assertIn("FILTER ( ROW ( ", qs["P1-V02"]["dax"])
        self.assertIn("( [Headcount] ) <= 5", qs["P1-V02"]["dax"])

    def test_require_port_skips_stale_port_files(self):
        from pbikit import slicerfit as SF
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            import os, time
            for k, port in enumerate((50001, 50002)):     # 50002 is newer but its Desktop closed
                d = tmp / "AnalysisServicesWorkspaces" / f"ws{k}" / "Data"
                d.mkdir(parents=True)
                (d / "msmdsrv.port.txt").write_bytes(str(port).encode("utf-16-le"))
                os.utime(d / "msmdsrv.port.txt", (time.time() + k, time.time() + k))
            live = lambda p: p == 50001
            self.assertEqual(SF.discover_port([tmp], answers=live), 50001)
            self.assertIsNone(SF.discover_port([tmp], answers=lambda p: False))
            self.assertEqual(SF.require_port(None, [tmp], answers=live, running=lambda: True), 50001)
            self.assertEqual(SF.require_port("50001", [tmp], answers=live, running=lambda: True), 50001)
            for args in ((None, lambda: False), ("50002", lambda: True), ("auto", lambda: None)):
                with self.assertRaises(RuntimeError) as cm:
                    SF.require_port(args[0], [tmp], answers=lambda p: False, running=args[1])
                self.assertIn("Open the report in Desktop first", str(cm.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ps = (KIT / ".claude" / "scripts" / "run-dax.ps1").read_text(encoding="utf-8")
        self.assertIn("[Parameter(Mandatory)][int]$Port", ps, "no hard-coded default port")


class FidelityTests(unittest.TestCase):
    """fidelity_check.py: the wireframe against the report pbik built from the same layout, and the comparison."""

    def test_edge_page_returns_the_drawn_dom(self):
        import edge_page
        if not edge_page.available():
            self.skipTest("Edge not installed")
        dom = edge_page.dom("<html><body><div id=x></div><script>document.getElementById('x').textContent = "
                            "location.hash</script></body></html>", hash_="#page=2")
        self.assertIn('<div id="x">#page=2</div>', dom)

    def test_wireframe_matches_the_report_built_from_its_layout(self):
        """Rep 8: positions, types and literal texts agree with what pbik build writes (text boxes with TEXT_FIT)."""
        import edge_page, fidelity_check as F
        if not edge_page.available():
            self.skipTest("Edge not installed")
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            proj = tmp / "rep8"
            shutil.copytree(CASES / "rep8" / "project", proj)
            (tmp / "empty").mkdir()
            lay = proj / "design" / "specs" / "rep8.layout.json"
            import subprocess
            r = subprocess.run([sys.executable, str(KIT / "tools" / "pbik" / "pbik.py"), "build", str(proj / "HR Overview.Report"),
                                str(lay), "--tokens", str(proj / "design" / "tokens.json"), "--templates", str(tmp / "empty")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            layout, tok, _, theme = case("rep8")
            wf = F.wireframe_visuals(G.build_html(layout, tok, theme, None))
            rp = F.report_visuals(proj / "HR Overview.Report")
            for key, p in layout["pages"].items():
                diffs, _ = F.compare([v for v in wf if v["page"] == key], rp[p["displayName"]])
                self.assertEqual(diffs, [], key)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_compare_lists_position_type_text_and_missing_visuals(self):
        import fidelity_check as F
        wf = [{"id": "P1-V01", "type": "textbox", "main": "Olympic Games", "measure": False, "x": 40, "y": 30, "w": 200,
               "h": 40, "hidden": False},
              {"id": "P1-V02", "type": "deneb", "main": "Nations", "measure": False, "x": 0, "y": 100, "w": 300, "h": 200,
               "hidden": False},
              {"id": "P1-V03", "type": "lineChart", "main": "Title", "measure": False, "x": 0, "y": 400, "w": 300,
               "h": 200, "hidden": False},
              {"id": "P1-V04", "type": "cardVisual", "main": "1,234", "measure": False, "x": 0, "y": 700, "w": 100,
               "h": 50, "hidden": False},
              {"id": "P1-V05", "type": "shape", "main": "", "measure": False, "x": 0, "y": 0, "w": 9, "h": 9, "hidden": False}]
        rp = [{"id": "P1-V01", "type": "textbox", "text": "Olympic  Games", "x": 40, "y": 24, "w": 200, "h": 52, "hidden": False},
              {"id": "P1-V02", "type": "deneb7E15AEF80B9E4D4F8E12924291ECE89A", "title": "Nations", "x": 0, "y": 100,
               "w": 300, "h": 200, "hidden": False},
              {"id": "P1-V03", "type": "areaChart", "title": "Other", "x": 10, "y": 400, "w": 300, "h": 200, "hidden": False},
              {"id": "P1-V04", "type": "cardVisual", "x": 0, "y": 700, "w": 100, "h": 50, "hidden": False, "valueShow": True},
              {"id": "P1-V06", "type": "image", "x": 0, "y": 0, "w": 9, "h": 9, "hidden": False}]
        diffs, notes = F.compare(wf, rp, {"P1-V04": {"values": ["1,235"]}})
        self.assertEqual(diffs, [("P1-V03", "type", "lineChart", "areaChart"), ("P1-V03", "position", "x 0", "x 10"),
                                 ("P1-V03", "main text", "Title", "Other"), ("P1-V04", "main text", "1,234", "1,235"),
                                 ("P1-V05", "missing in the report", "shape", ""),
                                 ("P1-V06", "missing in the wireframe", "", "image")])
        self.assertEqual(F.compare(wf[3:4], rp[3:4])[1], [("P1-V04", "card value needs --port")])
        self.assertEqual(F.precision("0.0%", 0), "0%")


if __name__ == "__main__":
    unittest.main(verbosity=2)
