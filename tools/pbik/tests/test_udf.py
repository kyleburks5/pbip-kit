"""UDF toolbelt tests (UDF KPI card study, 2026-11-15): the kit library, install, inline, the bind check, udfCard.

    python tools\\pbik\\tests\\test_udf.py

Runs on scratch copies of the Rep 4 fixture and the made-up bind sample; never on a person's model.
"""
import json, os, pathlib, re, shutil, sys, tempfile, unittest
os.environ.setdefault("PBIK_HOME", tempfile.mkdtemp(prefix="pbik_home_"))

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
KIT = HERE.parents[2]
LIB = KIT / "design" / "udf" / "library" / "park-kpi"

import test_pbik as TP  # noqa: E402
from pbikit import build as B, udf as U  # noqa: E402
from pbikit.report import Report  # noqa: E402

CARDS = ["Park.SVG.Card1", "Park.SVG.Card2", "Park.SVG.SVGKPICard", "Park.SVG.SVGKPICardGradient"]
ICONS = ["Park.Icons.SolidIcon", "Park.Icons.GradientIcon"]


def tokens():
    return json.loads(TP.SAMPLE_TOKENS.read_text(encoding="utf-8"))


class LibraryTests(unittest.TestCase):
    """1-2: the 33 kit-copy functions, their fingerprints, and the icons turned off."""

    def setUp(self):
        self.by = U.load(KIT)

    def test_33_functions_fingerprinted_only_icons_off(self):
        self.assertEqual(len(self.by), 33)
        probs = U.check(self.by)
        self.assertEqual(len(probs), 2, probs)
        for n in ICONS:
            self.assertIn("licence", U.disabled_reason(self.by[n]))
        self.assertEqual(sorted(n for n in self.by if U.disabled_reason(self.by[n])), sorted(ICONS))

    def test_originals_and_icons_stay_out_of_the_kit(self):
        self.assertFalse((KIT / "design" / "reviews" / "study-udf-kpi").exists())
        self.assertFalse(list(KIT.glob("design/udf/library/**/icons*.tmdl")))
        self.assertFalse(list(LIB.parent.glob("**/*.svg")))
        for f in LIB.glob("*.tmdl"):
            self.assertNotIn("DAXLIB_Package", f.read_text(encoding="utf-8"), f.name)

    def test_index_entries_have_plain_words(self):
        for n, f in self.by.items():
            for k in ("description", "params", "calls", "requires", "sha256", "status", "file"):
                self.assertIn(k, f, n)
            if f["role"] == "card":
                self.assertTrue(f.get("useWhen") and f.get("avoidWhen") and f.get("size"), n)

    def test_no_card_example_or_card_code_calls_an_icon_function(self):
        for n in CARDS:
            self.assertFalse(set(U.closure(self.by, [n])) & set(ICONS), n)
            self.assertNotIn("Park.Icons", self.by[n].get("example") or "", n)

    def test_list_hides_turned_off_functions(self):
        text = "\n".join(U.lines_list(self.by))
        self.assertIn("Park.SVG.Card2", text)
        self.assertNotIn("SolidIcon", text)
        self.assertIn("SolidIcon", "\n".join(U.lines_list(self.by, all_=True)))
        self.assertIn("brings along", "\n".join(U.lines_show(self.by, "park.svg.svgkpicard")))

    def test_changed_file_is_noticed(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_udf_"))
        try:
            dest = tmp / "design" / "udf" / "library" / "park-kpi"
            shutil.copytree(LIB, dest)
            f = dest / "Park.SVG.Card2.tmdl"
            f.write_text(f.read_text(encoding="utf-8") + "\n// edited\n", encoding="utf-8")
            probs = U.check(U.load(tmp), ["Park.SVG.Card2"])
            self.assertTrue(any("changed" in p for p in probs), probs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_render_fills_every_token_and_refuses_icons(self):
        text = U.render(self.by, ["Park.SVG.SVGKPICard"], tokens())
        self.assertNotIn("{{", text)
        self.assertNotIn("%23", text)
        q = U.render(self.by, ["Park.SVG.Card2"], tokens(), fmt="query")
        self.assertTrue(q.startswith("DEFINE\nFUNCTION Park.SVG.Card2 ="))
        with self.assertRaises(U.UdfError) as e:
            U.render(self.by, ["Park.Icons.SolidIcon"], tokens())
        self.assertIn("turned off", str(e.exception))
        with self.assertRaises(U.UdfError):
            U.render(self.by, ["Park.SVG.Card2"], {"colors": {}})


class InlineTests(unittest.TestCase):
    """3: inline mode expands calls into plain DAX."""

    def setUp(self):
        self.by = U.load(KIT)

    def test_every_card_example_inlines_cleanly(self):
        for n in CARDS + ["Park.SVG.BasicLineChart"]:
            out = U.inline(self.by[n]["example"], self.by, tokens())
            self.assertEqual(U.inline_problems(out, self.by), [], n)
            self.assertNotIn("_CurrentExpr", U.code_only(out), n)

    def test_val_binds_a_var_expr_is_placed_where_used(self):
        out = U.inline('Park.SVG.Card2 ( [Sales], [Sales PY], "Sales", "", "#038D96" )', self.by, tokens())
        self.assertIn("VAR __i1_Font = BLANK()", out)               # VAL: bound once
        self.assertIn("( [Sales] )", out)                          # EXPR: the argument text itself
        self.assertNotRegex(U.code_only(out), r"(?<![\w])_PastExpr\b")
        self.assertIn('"From Last Year"', out)                     # strings untouched

    def test_columns_go_in_without_brackets_and_nested_calls_expand(self):
        out = U.inline(self.by["Park.SVG.SVGKPICard"]["example"], self.by, tokens())
        self.assertIn("'Date'[Month Number]", out)
        self.assertNotIn("( 'Date'[Month Number] )", out)
        self.assertEqual(U.calls_in(out, self.by), [])

    def test_a_fixed_chart_style_inlines_only_its_chart(self):
        ex = self.by["Park.SVG.SVGKPICard"]["example"]
        for style in self.by["Park.SVG.SVGKPICard"]["styles"]:
            out = U.inline(ex.replace('"Bar5"', f'"{style}"'), self.by, tokens())
            self.assertEqual(U.inline_problems(out, self.by), [], style)
            self.assertLessEqual(len(out), U.INLINE_WARN, style)
            self.assertNotIn("unknown chart style", out, style)
        g = self.by["Park.SVG.SVGKPICardGradient"]["example"]
        for style in self.by["Park.SVG.SVGKPICardGradient"]["styles"]:
            self.assertLessEqual(len(U.inline(g.replace('"Bar1"', f'"{style}"'), self.by, tokens())), U.INLINE_WARN)
        lower = U.inline(ex.replace('"Bar5"', '"bar5"'), self.by, tokens())     # DAX compares text ignoring case
        self.assertLessEqual(len(lower), U.INLINE_WARN)
        dynamic = U.inline(ex.replace('"Bar5"', "[Chart Style]"), self.by, tokens())
        self.assertIn("unknown chart style", dynamic)                         # every style kept, ERROR included
        self.assertTrue(U.size_note(dynamic)[1])
        unknown = U.inline(ex.replace('"Bar5"', '"Nope"'), self.by, tokens())
        self.assertIn("unknown chart style", unknown)                         # the function's own error stays

    def test_size_warning_in_the_card_plan(self):
        args = {"_LabelExpr": "Sales", "_CurrentExpr": "[Sales]", "_PastExpr": "[Sales PY]",
                "_DateNumber": "'Date'[Month Number]", "_DateVal": "'Date'[Month]", "_AccentUp": "token:good",
                "_AccentDown": "token:bad", "_NeutralAccent": "token:textMuted", "_MicrochartType": "Line2"}
        said = []
        p = U.card_plan("P1-V03", {"function": "Park.SVG.SVGKPICard", "args": args}, self.by, tokens(), warnings=said)
        self.assertEqual(said, [])
        self.assertEqual(p["chars"], len(p["expression"]))
        old = U.INLINE_WARN
        try:
            U.INLINE_WARN = 1000
            U.card_plan("P1-V03", {"function": "Park.SVG.SVGKPICard", "args": args}, self.by, tokens(),
                        warnings=said)
        finally:
            U.INLINE_WARN = old
        self.assertTrue(said and "characters" in said[0], said)

    def test_toy_function_semantics(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_udf_"))
        try:
            d = tmp / "design" / "udf" / "library" / "toy"
            d.mkdir(parents=True)
            body = ("function 'Toy.Add' =\n\t\t(\n\t\t\t_a : NUMERIC VAL,\n\t\t\t_b : NUMERIC EXPR\n\t\t) =>\n"
                    "\t\tVAR _x = _a + 1\n\t\tRETURN _x * _b  // _a in a comment stays\n")
            (d / "Toy.Add.tmdl").write_text(body, encoding="utf-8")
            (d / "index.json").write_text(json.dumps({"functions": [{
                "name": "Toy.Add", "role": "number", "description": "toy", "file": "Toy.Add.tmdl", "calls": [],
                "requires": [], "status": "enabled", "sha256": U.sha(body),
                "params": [{"name": "_a", "type": "NUMERIC", "mode": "VAL"},
                           {"name": "_b", "type": "NUMERIC", "mode": "EXPR"}]}]}), encoding="utf-8")
            by = U.load(tmp)
            out = U.inline("[M] + Toy.Add ( 2, [Units] ) + Toy.Add ( 3, 4 )", by, {})
            self.assertIn("VAR __i1_a = 2", out)
            self.assertIn("VAR _x__i1 = __i1_a + 1", out)
            self.assertIn("_x__i1 * ( [Units] )", out)
            self.assertIn("VAR _x__i2 = __i2_a + 1", out)
            self.assertNotIn("comment stays", out)                  # generated DAX: comments dropped
            self.assertTrue(out.startswith("[M] + ("))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CardPlanTests(unittest.TestCase):
    """3: the one-step UDF card (layout.json udfCard)."""

    def setUp(self):
        self.by = U.load(KIT)

    def plan(self, **spec):
        return U.card_plan("P1-V03", spec, self.by, tokens())

    def test_icons_are_refused_and_left_out_by_default(self):
        with self.assertRaises(U.UdfError) as e:
            self.plan(function="Park.SVG.Card2", args={"_CurrentExpr": "[Sales]", "_PastExpr": "[Sales PY]",
                                                       "_LabelExpr": "Sales", "_AccentExpr": "token:brand",
                                                       "_IconExpr": "icon:thumb-up-fill"})
        self.assertIn("icons are turned off", str(e.exception))
        p = self.plan(function="Park.SVG.Card2", mode="calc",
                      args={"_CurrentExpr": "[Sales]", "_PastExpr": "[Sales PY]", "_LabelExpr": "Sales",
                            "_AccentExpr": "token:brand"})
        self.assertIn('"Sales", ""', p["call"])                     # no icon: the card's own tile, no icon table
        self.assertIn('"' + tokens()["colors"]["brand"] + '"', p["call"])
        self.assertEqual(p["measures"], ["Sales", "Sales PY"])
        with self.assertRaises(U.UdfError):
            self.plan(function="Park.Icons.SolidIcon")

    def test_style_names_and_columns(self):
        args = {"_LabelExpr": "Sales", "_CurrentExpr": "[Sales]", "_PastExpr": "[Sales PY]",
                "_DateNumber": "'Date'[Month Number]", "_DateVal": "'Date'[Month]", "_AccentUp": "token:good",
                "_AccentDown": "token:bad", "_NeutralAccent": "token:textMuted", "_MicrochartType": "Bar9"}
        with self.assertRaises(U.UdfError) as e:
            self.plan(function="Park.SVG.SVGKPICard", args=args)
        self.assertIn("Bar5", str(e.exception))
        args["_MicrochartType"] = "Bar5"
        with self.assertRaises(U.UdfError) as e:
            self.plan(function="Park.SVG.SVGKPICard", mode="calc", args=args)
        self.assertIn("columns", str(e.exception))
        p = self.plan(function="Park.SVG.SVGKPICard", args=args)
        self.assertEqual(p["mode"], "inline")
        self.assertEqual(U.calls_in(p["expression"], self.by), [])

    def test_layout_expansion_needs_alt_text_and_keeps_the_shape(self):
        lay = {"visuals": [{"id": "P1-V03", "page": "P1", "x": 32, "y": 32, "w": 438, "h": 400,
                            "udfCard": {"function": "Park.SVG.Card2", "mode": "inline",
                                        "args": {"_CurrentExpr": "[Revenue]", "_PastExpr": "[Revenue PY]",
                                                 "_LabelExpr": "Revenue", "_AccentExpr": "token:brand"}}}]}
        _, _, errs = U.expand_layout(lay, self.by, tokens())
        self.assertTrue(any("alt text" in e for e in errs), errs)
        self.assertTrue(any("keep that shape" in e for e in errs), errs)
        lay["visuals"][0].update(h=235, container={"altText": "Revenue this year against last year"})
        vis, measures, errs = U.expand_layout(lay, self.by, tokens())
        self.assertEqual(errs, [])
        self.assertEqual(vis[0]["template"], "cardVisual.svg-kpi-card")
        self.assertEqual(vis[0]["build"]["step"], 2)
        self.assertIn("img P1-V03", measures)


class InstallAndBuildTests(unittest.TestCase):
    """3: install mode, the udfCard build (calc and inline), and the Desktop check."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik_udf_"))
        TP.copy_project(self.tmp, keep_pages=True)
        self.rep = next(self.tmp.glob("*.Report"))
        self.model = next(self.tmp.glob("*.SemanticModel"))
        tpl = self.tmp / "design" / "templates"
        shutil.copytree(KIT / "design" / "templates", tpl)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def layout(self, mode):
        lay = {"measureTable": "_Measures", "pages": {"P9": {"displayName": "UDF cards"}},
               "visuals": [{"id": "P9-V01", "name": "udf-revenue", "page": "P9", "x": 32, "y": 32, "w": 448,
                            "h": 240, "container": {"altText": "Revenue this year and its change from last year"},
                            "udfCard": {"function": "Park.SVG.Card2", "mode": mode,
                                        "args": {"_CurrentExpr": "[Revenue]", "_PastExpr": "[Revenue PY]",
                                                 "_LabelExpr": "Revenue", "_AccentExpr": "token:brand"}}}]}
        f = self.tmp / "design" / "specs" / "layout.json"
        f.write_text(json.dumps(lay, indent=1), encoding="utf-8")
        return f

    def visual(self):
        f = next(self.rep.glob("definition/pages/*/visuals/P9-V01_*/visual.json"))
        return json.loads(f.read_text(encoding="utf-8"))

    def test_inline_card_builds_without_any_function(self):
        lf = self.layout("inline")
        TP.pbik("build", self.rep, lf)
        ext = json.loads((self.rep / "definition" / "reportExtensions.json").read_text(encoding="utf-8"))
        m = next(x for e in ext["entities"] for x in e["measures"] if x["name"] == "img P9-V01")
        self.assertEqual((m["dataType"], m["dataCategory"]), ("Text", "ImageUrl"))
        self.assertNotIn("Park.", U.code_only(m["expression"]))
        d = self.visual()
        self.assertEqual(d["visual"]["visualType"], "cardVisual")
        img = json.dumps(d["visual"]["objects"]["image"])
        self.assertIn("img P9-V01", img)
        self.assertIn("'imageUrl'", img)
        self.assertFalse((self.model / "definition" / "functions.tmdl").exists())
        again = TP.pbik("build", self.rep, lf)
        self.assertIn("No changes", again.stdout)

    def test_calc_mode_needs_the_function_then_writes_a_visual_calculation(self):
        lf = self.layout("calc")
        r = TP.pbik("build", self.rep, lf, ok=(1, 2))
        self.assertIn("inline mode", r.stdout + r.stderr)
        with self.assertRaises(U.UdfError):                                    # their own model: only on request
            U.install(self.tmp, ["Park.SVG.Card2"], str(self.model))
        U.install(self.tmp, ["Park.SVG.Card2"], str(self.model), own_model=True)
        fn = (self.model / "definition" / "functions.tmdl").read_text(encoding="utf-8")
        self.assertIn(f"annotation {U.ANNOTATION} = park-kpi:", fn)
        self.assertNotIn("{{", fn)
        self.assertEqual(U.compatibility_level(self.model), U.MIN_LEVEL)
        self.assertIn("Park.SVG.Card2", U.state(self.tmp)["installed"])
        U.install(self.tmp, ["Park.SVG.Card2"], str(self.model), own_model=True)       # idempotent
        self.assertEqual(fn, (self.model / "definition" / "functions.tmdl").read_text(encoding="utf-8"))
        TP.pbik("build", self.rep, lf)
        q = self.visual()["visual"]["query"]["queryState"]["Data"]["projections"]
        self.assertEqual(q[0]["field"]["NativeVisualCalculation"]["DataType"], "Text")
        self.assertIn("Park.SVG.Card2", q[0]["field"]["NativeVisualCalculation"]["Expression"])
        self.assertEqual([p.get("hidden") for p in q[1:]], [True, True])
        self.assertIn("SelectRef", json.dumps(self.visual()["visual"]["objects"]["image"]))
        self.assertNotIn("sortDefinition", self.visual()["visual"]["query"])

    def test_install_keeps_the_models_own_functions_and_checks_tables(self):
        f = self.model / "definition" / "functions.tmdl"
        f.write_text("function 'Mine.Twice' = (x : NUMERIC) => x * 2\n", encoding="utf-8")
        U.install(self.tmp, ["Park.SVG.Card1"], str(self.model), own_model=True)
        text = f.read_text(encoding="utf-8")
        self.assertIn("Mine.Twice", text)
        self.assertIn("Park.SVG.Card1", text)
        self.assertEqual(set(U.model_functions(self.model)), {"Mine.Twice", "Park.SVG.Card1"})
        for t in (self.model / "definition" / "tables").glob("*.tmdl"):
            if t.read_text(encoding="utf-8-sig").startswith("table Date"):
                t.unlink()
        with self.assertRaises(U.UdfError) as e:
            U.install(self.tmp, ["Park.SVG.BasicLineChart"], str(self.model), own_model=True)
        self.assertIn("'Date'", str(e.exception))

    def test_desktop_check(self):
        _, probs = U.desktop_check(self.tmp, version="2.140.1.0")
        self.assertTrue(probs)
        facts, probs = U.desktop_check(self.tmp, version="2.159.1231.0")
        self.assertEqual(probs, [])
        self.assertIn("verify in Desktop", " ".join(facts))
        facts, _ = U.desktop_check(self.tmp, version="2.155.756.0")
        self.assertIn("verify in Desktop", " ".join(facts))


class BindAndSynthTests(unittest.TestCase):
    """3: the bind check and the synthetic model with UDFs."""

    def setUp(self):
        import test_bind as TB
        self.TB = TB
        self.base = TB.BindBase("setUp")
        self.base.setUp()
        self.root = self.base.root

    def tearDown(self):
        self.base.tearDown()

    def contract(self):
        return json.loads((self.root / "design/specs/contract.json").read_text(encoding="utf-8"))

    def set_functions(self, fns):
        from pbikit import synth as S
        c = self.contract()
        c["functions"] = fns
        c["approval"] = None
        S.write_json(self.root / "design/specs/contract.json", c)
        S.approve(self.root, "Sample Person", ask=self.TB.TS.say("Example Live"), out=lambda *a: None)

    def add_measure(self, expr):
        U.write_measures(Report(self.base.rep), {"img card": expr}, "_Measures")

    def test_call_missing_live_is_an_error_that_offers_inline(self):
        self.add_measure('Park.SVG.Card2 ( [Total Units], [Total Units], "Units", "", "#123456" )')
        r = self.base.check()
        msg = [e for e in r.errors if "Park.SVG.Card2" in e]
        self.assertTrue(msg and "inline it" in msg[0], r.errors)

    def test_call_present_live_with_the_kits_mark_passes(self):
        by = U.load(KIT)
        self.set_functions({"Park.SVG.Card2": {"kit": "park-kpi:" + by["Park.SVG.Card2"]["sha256"]}})
        self.add_measure('Park.SVG.Card2 ( [Total Units], [Total Units], "Units", "", "#123456" )')
        self.assertFalse([e for e in self.base.check().errors if "Park." in e])
        self.set_functions({"Park.SVG.Card2": {"kit": "park-kpi:0000"}})
        self.assertTrue([e for e in self.base.check().errors if "another version" in e])

    def test_inlined_card_needs_no_function_but_its_tables(self):
        by = U.load(KIT)
        self.add_measure(U.inline('Park.SVG.Card2 ( [Total Units], [Total Units], "Units", "", "#123456" )',
                                  by, tokens()))
        self.assertFalse([e for e in self.base.check().errors if "Park." in e or "function" in e])
        self.add_measure(U.inline(by["Park.SVG.BasicLineChart"]["example"].replace("[Sales]", "[Total Units]"),
                                  by, tokens()))
        self.assertTrue([e for e in self.base.check().errors if "'Date'" in e])

    def test_contract_records_functions_and_the_synthetic_model_keeps_installs(self):
        from pbikit import synthgen as G
        folder = U.synthetic_folder(self.root)
        self.assertIsNotNone(folder)
        U.install(self.root, ["Park.SVG.Card2"])                    # the synthetic model: always allowed
        self.assertIn("Park.SVG.Card2", U.model_functions(folder))
        notes = []
        G.generate(self.root, "Example Synthetic", notes=notes)    # regenerated: the install is kept
        self.assertIn("Park.SVG.Card2", U.model_functions(folder))
        self.assertEqual(U.compatibility_level(folder), U.MIN_LEVEL)
        self.assertTrue(any("DAX function" in n for n in notes))
        from pbikit import synth as S
        c = S.build_contract(folder, self.root)
        self.assertIn("park-kpi:", c["functions"]["Park.SVG.Card2"]["kit"])
        self.assertEqual(c["compatibilityLevel"], U.MIN_LEVEL)


if __name__ == "__main__":
    unittest.main(verbosity=1)
