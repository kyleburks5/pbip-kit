"""pbik tests on a scratch copy of a saved PBIP (never the original).

    python tools\\pbik\\tests\\test_pbik.py            (source: %PBIK_TEST_SOURCE%, default tools\\fixtures\\rep4)

The source folder is only read: its *.Report and *.SemanticModel (definition only) are copied into a temp folder.
The default is the Rep 4 fixture in the kit (tools/fixtures/README.md), so the tests run on a clean clone; a missing
source fails the run, never skips it.
"""
import contextlib, hashlib, io, json, os, pathlib, shutil, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
PBIK = HERE.parent / "pbik.py"
KIT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
SOURCE = pathlib.Path(os.environ.get("PBIK_TEST_SOURCE", KIT / "tools" / "fixtures" / "rep4"))

from pbikit import build as B, tmdl  # noqa: E402
from pbikit.report import Report  # noqa: E402

SVG = ('"data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 100 10\'>'
       '<rect width=\'100%25\' height=\'10\' fill=\'%23E7F3F5\'/><rect width=\'" & FORMAT ( [Margin %] * 100, "0" ) & '
       '"%25\' height=\'10\' fill=\'%23026E75\'/></svg>"')


def pbik(*args, ok=(0,)):
    r = subprocess.run([sys.executable, str(PBIK), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if r.returncode not in ok:
        raise AssertionError(f"pbik {' '.join(map(str, args))} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def tree_hash(folder):
    h = {}
    for f in sorted(pathlib.Path(folder).rglob("*")):
        if f.is_file():
            h[str(f.relative_to(folder))] = hashlib.sha1(f.read_bytes()).hexdigest()
    return h


def copy_project(dest, keep_pages=True):
    rep = next(SOURCE.glob("*.Report"))
    mod = next(SOURCE.glob("*.SemanticModel"))
    shutil.copytree(rep, dest / rep.name, ignore=shutil.ignore_patterns(".pbi"))
    (dest / mod.name).mkdir()
    for x in ("definition", "definition.pbism", ".platform"):
        src = mod / x
        if src.is_dir():
            shutil.copytree(src, dest / mod.name / x)
        elif src.exists():
            shutil.copy(src, dest / mod.name / x)
    if not keep_pages:
        pages = dest / rep.name / "definition" / "pages"
        for p in pages.iterdir():
            if p.is_dir():
                shutil.rmtree(p)
        meta = json.loads((pages / "pages.json").read_text(encoding="utf-8"))
        meta.pop("activePageName", None)
        meta["pageOrder"] = []
        (pages / "pages.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (dest / "design" / "specs").mkdir(parents=True)
    (dest / "design" / "themes").mkdir()
    shutil.copy(HERE / "sample" / "layout.json", dest / "design" / "specs" / "layout.json")
    shutil.copy(KIT / "design" / "tokens.json", dest / "design" / "tokens.json")
    shutil.copy(KIT / "design" / "themes" / "pbip-polish.json", dest / "design" / "themes" / "pbip-polish.json")
    return dest / rep.name, dest / mod.name


def add_ext(report):
    """The sample's two extension measures: the SVG for the card image, and a bar-only copy of Revenue."""
    pbik("measure", "ext", "add", report, "img Revenue bar", "--expression", SVG, "--data-category", "ImageUrl")
    pbik("measure", "ext", "add", report, "Revenue bar", "--expression", "[Revenue]", "--data-type", "Double",
         "--format-string", "$#,0")


def visual(report, vid):
    return json.loads(next(report.glob(f"definition/pages/*/visuals/{vid}_*/visual.json")).read_text(encoding="utf-8"))


class PbikTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not list(SOURCE.glob("*.Report")):
            raise RuntimeError(f"test source {SOURCE} has no *.Report (set PBIK_TEST_SOURCE, or restore tools/fixtures)")
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pbik-test-"))
        cls.src_before = tree_hash(next(SOURCE.glob("*.Report")))
        # clean project: the source report without its pages, then the sample layout built into it
        cls.proj = cls.tmp / "clean"
        cls.proj.mkdir()
        cls.report, cls.model = copy_project(cls.proj, keep_pages=False)
        cls.layout = cls.proj / "design" / "specs" / "layout.json"
        add_ext(cls.report)
        pbik("theme", "apply", cls.report, cls.proj / "design" / "themes" / "pbip-polish.json")
        cls.first = pbik("build", cls.report, cls.layout)
        cls.after_first = tree_hash(cls.report)
        cls.second = pbik("build", cls.report, cls.layout)
        cls.after_second = tree_hash(cls.report)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- build
    def test_01_first_build_writes(self):
        self.assertIn("file(s) written", self.first.stdout)
        self.assertTrue((self.proj / "design" / "specs" / "visual-map.json").exists())

    def test_02_second_build_changes_nothing(self):
        self.assertIn("No changes", self.second.stdout, self.second.stdout)
        self.assertEqual(self.after_first, self.after_second)

    def test_03_validate_clean(self):
        r = pbik("validate", self.report, "--layout", self.layout)
        self.assertIn("0 error(s)", r.stdout, r.stdout)

    def test_04_folders_and_map(self):
        vm = json.loads((self.proj / "design" / "specs" / "visual-map.json").read_text(encoding="utf-8"))
        lay = json.loads(self.layout.read_text(encoding="utf-8"))
        for v in lay["visuals"]:
            self.assertTrue(vm["visuals"][v["id"]]["folder"].endswith(f"{v['id']}_{v['name']}"))
            self.assertEqual(visual(self.report, v["id"])["name"], f"{v['id']}_{v['name']}")
        self.assertEqual(set(vm["pages"]), {"P1", "P2"})

    def test_05_navigation_by_page_id(self):
        rep = Report(self.report)
        p2 = rep.page_by("pbik stock")[0]
        p1 = rep.page_by("pbik sales")[0]
        link = visual(self.report, "P1-V06")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]
        self.assertEqual(link["navigationSection"]["expr"]["Literal"]["Value"], f"'{p2}'")
        back = visual(self.report, "P2-V02")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]
        self.assertEqual(back["navigationSection"]["expr"]["Literal"]["Value"], f"'{p1}'")
        clear = visual(self.report, "P1-V07")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]
        self.assertEqual(clear["type"]["expr"]["Literal"]["Value"], "'ClearAllSlicers'")

    def test_06_topn_filter_and_reference_line(self):
        d = visual(self.report, "P1-V04")
        f = d["filterConfig"]["filters"][0]
        self.assertEqual(f["type"], "TopN")
        sub = f["filter"]["From"][0]["Expression"]["Subquery"]["Query"]
        self.assertEqual(sub["Top"], 5)
        self.assertEqual(sub["OrderBy"][0]["Direction"], 2)
        self.assertEqual({x["Entity"] for x in sub["From"]}, {"stores", "_Measures"})
        rl = d["visual"]["objects"]["y1AxisReferenceLine"][0]
        self.assertEqual(rl["selector"], {"id": "1"})
        self.assertEqual(rl["properties"]["value"]["expr"]["Literal"]["Value"], "498000D")

    def test_07_conditional_formatting(self):
        bar = visual(self.report, "P1-V04")["visual"]["objects"]["dataPoint"][0]
        cases = bar["properties"]["fill"]["solid"]["color"]["expr"]["Conditional"]["Cases"]
        self.assertEqual([c["Condition"]["Comparison"]["ComparisonKind"] for c in cases], [2, 3])
        t = visual(self.report, "P1-V05")["visual"]["objects"]
        bars = [e for e in t["columnFormatting"] if "dataBars" in e["properties"]]
        self.assertEqual(bars[0]["selector"], {"metadata": "_Measures.Revenue bar"})
        fills = [e for e in t["values"] if "backColor" in e["properties"]]
        self.assertIn("FillRule", fills[0]["properties"]["backColor"]["solid"]["color"]["expr"])
        fonts = [e for e in t["values"] if "fontColor" in e["properties"]]
        self.assertEqual(fonts[0]["selector"]["metadata"], "_Measures.Revenue vs PY %")
        img = visual(self.report, "P1-V03")["visual"]["objects"]["image"][0]["properties"]["imageUrl"]["expr"]
        self.assertEqual(img["Measure"]["Expression"]["SourceRef"], {"Schema": "extension", "Entity": "_Measures"})

    def test_08_typed_literals_selection_interactions(self):
        f = visual(self.report, "P1-V09")["filterConfig"]["filters"][0]
        vals = f["filter"]["Where"][0]["Condition"]["In"]["Values"]
        self.assertEqual(vals[0][0]["Literal"]["Value"], "1L")
        self.assertTrue(f["isHiddenInViewMode"])
        sel = visual(self.report, "P1-V08")["visual"]["objects"]["general"][0]["properties"]["filter"]["filter"]
        self.assertEqual(sel["Where"][0]["Condition"]["In"]["Values"][0][0]["Literal"]["Value"], "'2023'")
        rep = Report(self.report)
        _, pd, _ = rep.page_by("pbik sales")
        self.assertIn({"source": "P1-V08_year", "target": "P1-V04_top-cities", "type": "NoFilter"},
                      pd["visualInteractions"])
        self.assertTrue(pd["filterConfig"]["filters"][0]["name"].startswith("pbik_"))

    def test_09_theme_and_extensions(self):
        rj = json.loads((self.report / "definition" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(rj["themeCollection"]["customTheme"]["name"], "pbip-polish.json")
        self.assertTrue((self.report / "StaticResources" / "RegisteredResources" / "pbip-polish.json").exists())
        r = pbik("theme", "apply", self.report, self.proj / "design" / "themes" / "pbip-polish.json")
        self.assertIn("already applied", r.stdout)
        ext = json.loads((self.report / "definition" / "reportExtensions.json").read_text(encoding="utf-8"))
        m = ext["entities"][0]["measures"][0]
        self.assertEqual((m["name"], m["dataType"], m["dataCategory"]), ("img Revenue bar", "Text", "ImageUrl"))

    def test_10_info(self):
        r = pbik("info", self.report)
        self.assertIn("P1-V04", r.stdout)
        self.assertIn("stores.City", r.stdout)
        j = json.loads(pbik("info", self.report, "--json").stdout)
        self.assertEqual(sorted(v["id"] for p in j for v in p["visuals"]),
                         sorted(v["id"] for v in json.loads(self.layout.read_text(encoding="utf-8"))["visuals"]))

    def test_11_source_untouched(self):
        self.assertEqual(self.src_before, tree_hash(next(SOURCE.glob("*.Report"))))

    # ---------------------------------------------------------------- pbik 0.4 (bookmarks)
    def bookmark_layout(self, name):
        rep, lay, L = self.work(name)
        L["pages"]["P1"]["bookmarks"] = [
            {"name": "open", "displayName": "pbik sales · Filters open", "show": ["P1-V08", "P1-V09"]},
            {"name": "closed", "displayName": "pbik sales · Filters closed", "hide": ["P1-V08", "P1-V09"]},
            {"name": "cleared", "targets": ["P1-V08", "P1-V09"], "data": True, "display": False}]
        L["pages"]["P1"]["bookmarkGroups"] = [{"name": "pane", "displayName": "Filter pane", "bookmarks": ["open", "closed"]}]
        b7 = next(v for v in L["visuals"] if v["id"] == "P1-V07")
        b7["action"] = {"type": "Bookmark", "bookmark": "closed"}
        lay.write_text(json.dumps(L), encoding="utf-8")
        return rep, lay, L

    def test_90_bookmarks_written_like_desktop(self):
        from pbikit.bookmarks import bookmark_id, group_id
        rep, lay, L = self.bookmark_layout("bm")
        pbik("build", rep, lay)
        bdir = rep / "definition" / "bookmarks"
        page = Report(rep).page_by("pbik sales")[0]
        op = json.loads((bdir / f"{bookmark_id('P1', 'open')}.bookmark.json").read_text(encoding="utf-8"))
        self.assertEqual(op["options"], {"applyOnlyToTargetVisuals": True,
                                         "targetVisualNames": ["P1-V08_year", "P1-V09_category"],
                                         "suppressActiveSection": True, "suppressData": True})
        self.assertEqual(op["explorationState"]["activeSection"], page)
        cl = json.loads((bdir / f"{bookmark_id('P1', 'closed')}.bookmark.json").read_text(encoding="utf-8"))
        vc = cl["explorationState"]["sections"][page]["visualContainers"]
        self.assertEqual(vc["P1-V08_year"]["singleVisual"],
                         {"visualType": "advancedSlicerVisual", "objects": {}, "display": {"mode": "hidden"}})
        cr = json.loads((bdir / f"{bookmark_id('P1', 'cleared')}.bookmark.json").read_text(encoding="utf-8"))
        self.assertTrue(cr["options"]["suppressDisplay"])
        self.assertNotIn("suppressData", cr["options"])
        meta = json.loads((bdir / "bookmarks.json").read_text(encoding="utf-8"))
        self.assertIn({"name": group_id("pane"), "displayName": "Filter pane",
                       "children": [bookmark_id("P1", "open"), bookmark_id("P1", "closed")]}, meta["items"])
        self.assertIn({"name": bookmark_id("P1", "cleared")}, meta["items"])
        self.assertNotIn({"name": bookmark_id("P1", "open")}, meta["items"], "a grouped bookmark isn't also standalone")
        link = visual(rep, "P1-V07")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]
        self.assertEqual(link["bookmark"]["expr"]["Literal"]["Value"], f"'{bookmark_id('P1', 'closed')}'")
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lay).stdout)

    def test_91_desktop_bookmarks_never_touched(self):
        rep, lay, L = self.bookmark_layout("bm-desktop")
        bdir = rep / "definition" / "bookmarks"
        bdir.mkdir(parents=True)
        page = Report(rep).page_by("pbik sales")
        mine = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/2.1.0/schema.json",
                "displayName": "made in Desktop", "name": "desktop0000000000001", "options": {"suppressData": True},
                "explorationState": {"version": "1.0", "activeSection": "x", "sections": {}}}
        (bdir / "desktop0000000000001.bookmark.json").write_text(json.dumps(mine, indent=2), encoding="utf-8")
        (bdir / "bookmarks.json").write_text(json.dumps({"items": [{"name": "desktop0000000000001"}]}), encoding="utf-8")
        before = (bdir / "desktop0000000000001.bookmark.json").read_bytes()
        pbik("build", rep, lay)
        pbik("build", rep, lay, "--prune")
        self.assertEqual((bdir / "desktop0000000000001.bookmark.json").read_bytes(), before)
        items = json.loads((bdir / "bookmarks.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual(items[0], {"name": "desktop0000000000001"}, "Desktop's item stays first")
        self.assertIsNotNone(page)

    def test_92_bookmarks_pruned_like_visuals(self):
        from pbikit.bookmarks import bookmark_id
        rep, lay, L = self.bookmark_layout("bm-prune")
        pbik("build", rep, lay)
        L["pages"]["P1"]["bookmarks"] = [b for b in L["pages"]["P1"]["bookmarks"] if b["name"] != "cleared"]
        lay.write_text(json.dumps(L), encoding="utf-8")
        f = rep / "definition" / "bookmarks" / f"{bookmark_id('P1', 'cleared')}.bookmark.json"
        self.assertIn("kept; --prune removes it", pbik("build", rep, lay).stdout)
        self.assertTrue(f.exists())
        pbik("build", rep, lay, "--prune")
        self.assertFalse(f.exists())
        meta = json.loads((rep / "definition" / "bookmarks" / "bookmarks.json").read_text(encoding="utf-8"))
        self.assertNotIn({"name": bookmark_id("P1", "cleared")}, meta["items"])
        self.assertIn("No changes", pbik("build", rep, lay, "--prune").stdout)

    def test_93_bookmark_layout_errors(self):
        rep, lay, L = self.bookmark_layout("bm-err")
        L["pages"]["P1"]["bookmarks"][0]["show"].append("P2-V01")
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("which is on page P2", pbik("build", rep, lay, ok=(1,)).stdout)
        L["pages"]["P1"]["bookmarks"][0]["show"].remove("P2-V01")
        next(v for v in L["visuals"] if v["id"] == "P1-V07")["action"]["bookmark"] = "nope"
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("bookmark 'nope' is not a bookmark on page P1", pbik("build", rep, lay, ok=(1,)).stdout)

    def test_94_validate_bookmark_rules(self):
        from pbikit.bookmarks import bookmark_id
        rep, lay, L = self.bookmark_layout("bm-val")
        L["pages"]["P2"]["bookmarks"] = [{"name": "p2-hide", "hide": ["P2-V01"]}]
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        bdir = rep / "definition" / "bookmarks"
        # a bookmark that lists a visual from another page, and one that isn't on any page
        f = bdir / f"{bookmark_id('P1', 'open')}.bookmark.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        sec = d["explorationState"]["activeSection"]
        d["explorationState"]["sections"][sec]["visualContainers"]["P2-V01_title"] = {"singleVisual": {"visualType": "textbox", "objects": {}}}
        d["explorationState"]["sections"][sec]["visualContainers"]["P1-V99_ghost"] = {"singleVisual": {"visualType": "textbox", "objects": {}}}
        f.write_text(json.dumps(d), encoding="utf-8")
        # a button on P1 that applies P2's bookmark, and one that points to nothing
        for vid, target in (("P1-V07", bookmark_id("P2", "p2-hide")), ("P1-V06", "missing00000000000000")):
            vf = next(rep.glob(f"definition/pages/*/visuals/{vid}_*/visual.json"))
            vd = json.loads(vf.read_text(encoding="utf-8"))
            vd["visual"]["visualContainerObjects"]["visualLink"] = [{"properties": {
                "show": {"expr": {"Literal": {"Value": "true"}}}, "type": {"expr": {"Literal": {"Value": "'Bookmark'"}}},
                "bookmark": {"expr": {"Literal": {"Value": f"'{target}'"}}}}}]
            vf.write_text(json.dumps(vd), encoding="utf-8")
        out = pbik("validate", rep, ok=(1,)).stdout
        for needle in ("would hide or show P2-V01_title, which is on page 'pbik stock'",
                       "lists P1-V99_ghost, which is not a visual on its page",
                       "which hides or shows visuals on page 'pbik stock', not on this page",
                       "button applies bookmark 'missing00000000000000', which doesn't exist"):
            self.assertIn(needle, out, out)

    def test_95_reset_bookmark_on_a_clear_button(self):
        """A data bookmark that resets the page's own slicers (Rep 5 "Filters cleared"), applied by a Clear button:
        data only, the slicers as targets with nothing saved, no hidden flags, and validate clean."""
        from pbikit.bookmarks import bookmark_id
        rep, lay, L = self.bookmark_layout("bm-reset")
        next(v for v in L["visuals"] if v["id"] == "P1-V07")["action"] = {"type": "Bookmark", "bookmark": "cleared"}
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        bid = bookmark_id("P1", "cleared")
        d = json.loads((rep / "definition" / "bookmarks" / f"{bid}.bookmark.json").read_text(encoding="utf-8"))
        self.assertEqual(list(d["options"]), ["applyOnlyToTargetVisuals", "targetVisualNames", "suppressActiveSection",
                                              "suppressDisplay"], "the option keys Desktop saved for Filters cleared")
        sec = d["explorationState"]["sections"][d["explorationState"]["activeSection"]]["visualContainers"]
        self.assertEqual(sec, {"P1-V08_year": {"singleVisual": {"visualType": "advancedSlicerVisual", "objects": {}}},
                               "P1-V09_category": {"singleVisual": {"visualType": "slicer", "objects": {}}}})
        link = visual(rep, "P1-V07")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]
        self.assertEqual(link["bookmark"]["expr"]["Literal"]["Value"], f"'{bid}'")
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lay).stdout)

    # ---------------------------------------------------------------- pbik 0.3 (Rep 5 parity gaps 1-6)
    def work(self, name):
        w = self.tmp / name
        shutil.copytree(self.proj, w)
        lay = w / "design" / "specs" / "layout.json"
        return w / self.report.name, lay, json.loads(lay.read_text(encoding="utf-8"))

    def test_80_page_navigator_gets_empty_query(self):
        rep, lay, L = self.work("nav")
        L["visuals"].append({"id": "P2-V05", "name": "nav", "page": "P2", "type": "pageNavigator",
                             "x": 32, "y": 660, "w": 400, "h": 40})
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        self.assertEqual(visual(rep, "P2-V05")["visual"]["query"], {"queryState": {}})

    def test_81_empty_selectorless_entry_kept(self):
        rep, lay, L = self.work("empty")
        t_ = next(v for v in L["visuals"] if v["id"] == "P1-V05")
        t_["props"]["columnFormatting@none"] = {}
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        cf = visual(rep, "P1-V05")["visual"]["objects"]["columnFormatting"]
        self.assertIn({"properties": {}}, cf)
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        del t_["props"]["columnFormatting@none"]
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        self.assertNotIn({"properties": {}}, visual(rep, "P1-V05")["visual"]["objects"]["columnFormatting"])

    def test_82_no_empty_query_where_layout_or_template_has_none(self):
        rep, lay, L = self.work("noquery")
        next(v for v in L["visuals"] if v["id"] == "P2-V01")["emptyQuery"] = False
        tdir = lay.parent.parent / "templates"
        tdir.mkdir()
        (tdir / "shape.json").write_text(json.dumps({"visual": {"visualType": "shape"}}), encoding="utf-8")
        (tdir / "textbox.json").write_text(json.dumps({"visual": {"visualType": "textbox", "query": {"queryState": {}}}}),
                                           encoding="utf-8")
        L["visuals"].append({"id": "P2-V06", "name": "plain", "page": "P2", "type": "shape", "x": 500, "y": 660, "w": 100, "h": 40})
        L["visuals"].append({"id": "P2-V07", "name": "note", "page": "P2", "type": "textbox", "x": 700, "y": 660,
                             "w": 200, "h": 40, "text": "note"})
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        self.assertNotIn("query", visual(rep, "P2-V01")["visual"], "layout emptyQuery false removes it")
        self.assertNotIn("query", visual(rep, "P2-V06")["visual"], "template without a query")
        self.assertEqual(visual(rep, "P2-V07")["visual"]["query"], {"queryState": {}}, "template with an empty query")
        self.assertIn("No changes", pbik("build", rep, lay).stdout)

    def test_83_svg_percent_reader_on_rep5_measure_text(self):
        """The % hits in Rep 5's [DeltaPY% SVG] are real; comments, doubled quotes and /* */ inside strings are read
        right (trimmed from the measure text in pbip-rep5)."""
        from pbikit.validate import svg_issues
        expr = (
            '//ΔPY% = (AC - PY) / PY (relative difference)\n'
            'VAR _FontWeight =\n    --\'normal\' font for sales persons, \'bold\' for total row\n    "normal"\n'
            'VAR _Width =\n    --bar width - text for SVG\n    FORMAT ( _WidthValue, "0.0%" )\n'
            'VAR _SVG =\n    --rectangle for DeltaPY%% (green or red)\n'
            '    "data:image/svg+xml;utf8," & "<svg xmlns=""http://www.w3.org/2000/svg"">\n    /*" & _Rank & "*/\n'
            '    <line  x1=""50%"" x2=""50%"" y1=""0%"" y2=""100%"" stroke=""" & _ColorGrey & """></line >\n'
            '    <rect y=""35%"" x=""" & _X & """ width=""10"" height=""30%25""></rect>"\n'
            '    & FORMAT ( _Value, "#%" ) & "</text></svg>"\nRETURN _SVG')
        hits = svg_issues("m", expr)
        text = " | ".join(hits)
        self.assertIn('0.0%', text)                                        # FORMAT string inside the SVG measure
        self.assertIn('x1=""50%""'.replace('""', '"'), text.replace('""', '"'))
        self.assertIn('#%', text)
        self.assertNotIn('DeltaPY%%', text, "a -- comment is not SVG text")
        self.assertNotIn('ΔPY%', text, "a // comment is not SVG text")
        self.assertNotIn('30%25', "".join(h for h in hits if '30%25' in h and '30%25"' in h), "%25 is fine")
        self.assertEqual(svg_issues("m", '"data:image/svg+xml;utf8,<svg width=""100%25""/>"'), [])

    def test_84_sync_slicers(self):
        rep, lay, L = self.work("sync")
        y = next(v for v in L["visuals"] if v["id"] == "P1-V08")
        y["sync"] = {"group": "sync-year"}
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        self.assertEqual(visual(rep, "P1-V08")["visual"]["syncGroup"],
                         {"groupName": "sync-year", "fieldChanges": True, "filterChanges": True})
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        del y["sync"]
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        self.assertNotIn("syncGroup", visual(rep, "P1-V08")["visual"])
        y["type"], y["sync"] = y["type"], "x"
        next(v for v in L["visuals"] if v["id"] == "P1-V04")["sync"] = "g"
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("sync is for slicers", pbik("build", rep, lay, ok=(1,)).stdout)

    def test_85_field_parameter(self):
        rep, lay, L = self.work("fparam")
        L["visuals"].append({"id": "P2-V08", "name": "metric-bars", "page": "P2", "type": "clusteredBarChart",
                             "x": 32, "y": 640, "w": 600, "h": 400,
                             "bindings": {"Category": ["stores[City]"], "Y": [{"fieldParameter": "Metric[Metric]"}]}})
        L["visuals"].append({"id": "P2-V09", "name": "metric-one", "page": "P2", "type": "tableEx",
                             "x": 656, "y": 640, "w": 600, "h": 400,
                             "bindings": {"Values": ["stores[City]",
                                                     {"fieldParameter": "Metric[Metric]", "project": "selected", "selected": "Profit"}]}})
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        y = visual(rep, "P2-V08")["visual"]["query"]["queryState"]["Y"]
        self.assertEqual([p["queryRef"] for p in y["projections"]],
                         ["_Measures.Revenue", "_Measures.Profit", "_Measures.Units Sold"])
        self.assertTrue(y["projections"][0]["active"])
        self.assertEqual(y["fieldParameters"], [{"parameterExpr": {"Column": {"Expression": {"SourceRef": {"Entity": "Metric"}},
                                                                              "Property": "Metric"}}, "index": 0, "length": 3}])
        v = visual(rep, "P2-V09")["visual"]["query"]["queryState"]["Values"]
        self.assertEqual([(p["queryRef"], p.get("displayName")) for p in v["projections"]],
                         [("stores.City", None), ("_Measures.Profit", "Profit")])
        self.assertEqual((v["fieldParameters"][0]["index"], v["fieldParameters"][0]["length"]), (1, 1))
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lay).stdout)

    # ---------------------------------------------------------------- Deneb (v0.4, format from the Patterns page save)
    DENEB_SPEC = {"data": {"name": "dataset"}, "mark": {"type": "bar", "color": {"expr": "pbiColor(0)"}},
                  "encoding": {"y": {"field": "City", "type": "nominal", "sort": "-x"},
                               "x": {"field": "Revenue", "type": "quantitative"}}}

    def deneb_visual(self, **extra):
        v = {"id": "P2-V10", "name": "deneb-bars", "page": "P2", "type": "deneb", "x": 32, "y": 640, "w": 600, "h": 300,
             "bindings": {"dataset": ["stores[City]", "[Revenue]"]}, "deneb": {"spec": self.DENEB_SPEC},
             "fallback": {"type": "clusteredBarChart", "bindings": {"Category": ["stores[City]"], "Y": ["[Revenue]"]},
                          "container": {"title": "Revenue by city (bars)"},
                          "build": {"method": "native", "step": 1, "reason": "bars"}},
             "container": {"title": "Revenue by city (Deneb)", "altText": "Revenue by city"},
             "build": {"method": "deneb", "step": 3, "nativeTried": "bar chart", "reason": "test"}}
        v.update(extra)
        return v

    def test_86_deneb_written_like_desktop(self):
        from pbikit import deneb as DN
        rep, lay, L = self.work("deneb")
        L["visuals"].append(self.deneb_visual())
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        d = visual(rep, "P2-V10")["visual"]
        self.assertEqual(d["visualType"], DN.TYPE)
        self.assertEqual([p["queryRef"] for p in d["query"]["queryState"]["dataset"]["projections"]],
                         ["stores.City", "_Measures.Revenue"])
        txt = d["objects"]["vega"][0]["properties"]["jsonSpec"]["expr"]["Literal"]["Value"]
        self.assertIn(chr(13) + chr(10), txt)       # CRLF inside the spec, as Desktop saved it
        self.assertEqual(json.loads(txt[1:-1]), self.DENEB_SPEC)
        sm = d["objects"]["stateManagement"][0]["properties"]
        self.assertEqual(sorted(sm), ["consolidateFieldParameters", "denebMetaVersion", "supportFieldConfiguration",
                                      "viewportHeight", "viewportWidth"])
        self.assertEqual(sm["viewportWidth"]["expr"]["Literal"]["Value"], "600D")
        cfg = json.loads(sm["supportFieldConfiguration"]["expr"]["Literal"]["Value"][1:-1])
        self.assertEqual((cfg["City"]["format"], cfg["Revenue"]["format"]), (False, True))
        rj = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(rj["publicCustomVisuals"], [DN.TYPE])
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        out = pbik("validate", rep, "--layout", lay).stdout
        self.assertIn("0 error(s)", out, out)
        self.assertNotIn("Deneb spec", out)
        # --no-custom-visuals: the fallback in the same folder, and back
        r = pbik("build", rep, lay, "--no-custom-visuals")
        self.assertIn("Deneb visual / fallback", r.stdout)
        fb = visual(rep, "P2-V10")["visual"]
        self.assertEqual(fb["visualType"], "clusteredBarChart")
        self.assertNotIn("vega", fb.get("objects", {}))
        title = fb["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"]
        self.assertEqual(title, "'Revenue by city (bars)'")
        self.assertEqual(len(list(rep.glob("definition/pages/*/visuals/P2-V10_*"))), 1)
        self.assertIn("No changes", pbik("build", rep, lay, "--no-custom-visuals").stdout)
        vm = json.loads((lay.parent / "visual-map.json").read_text(encoding="utf-8"))["visuals"]["P2-V10"]
        self.assertEqual((vm["type"], vm["built"]), ("deneb", "fallback"))
        pbik("build", rep, lay)
        self.assertEqual(visual(rep, "P2-V10")["visual"]["visualType"], DN.TYPE)

    def test_86b_project_blocks_custom_visuals(self):
        from pbikit import deneb as DN
        rep, lay, L = self.work("deneb-blocked")
        L["visuals"].append(self.deneb_visual())
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        proj = lay.parent / "project.json"
        proj.write_text(json.dumps({"targetDesktop": "latest", "catalog": "home", "customVisuals": False}),
                        encoding="utf-8")
        self.assertIn("customVisuals is false", pbik("validate", rep, "--layout", lay).stdout)
        r = pbik("build", rep, lay)
        self.assertIn("customVisuals false: building each Deneb visual's fallback", r.stdout)
        self.assertEqual(visual(rep, "P2-V10")["visual"]["visualType"], "clusteredBarChart")
        self.assertNotIn("customVisuals is false", pbik("validate", rep, "--layout", lay).stdout)
        self.assertIn("customVisuals  false", pbik("project", "show", "--project", proj).stdout)
        proj.write_text(json.dumps({"targetDesktop": "latest", "catalog": "home"}), encoding="utf-8")
        pbik("build", rep, lay)
        self.assertEqual(visual(rep, "P2-V10")["visual"]["visualType"], DN.TYPE)

    def test_87_deneb_layout_errors(self):
        rep, lay, L = self.work("deneb-bad")
        v = self.deneb_visual()
        del v["fallback"]
        L["visuals"].append(v)
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("needs a `fallback`", pbik("build", rep, lay, ok=(1,)).stdout)
        v.update(self.deneb_visual(deneb={"spec": {"data": {"url": "https://example.com/x.csv"}, "mark": "bar"}}))
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("a url loads data", pbik("build", rep, lay, ok=(1,)).stdout)
        v.update(self.deneb_visual())
        del v["fallback"]["container"]
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("the fallback needs its own container title", pbik("build", rep, lay, ok=(1,)).stdout)
        v.update(self.deneb_visual(deneb={"spec": "design/deneb/missing.vl.json"}))
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("not found", pbik("build", rep, lay, ok=(1,)).stdout)

    def test_89_extension_measure_chain_is_an_error(self):
        rep, lay, L = self.work("ext-chain")
        pbik("measure", "ext", "add", rep, "p Base", "--expression", "[Revenue] * 2", "--data-type", "Double")
        self.assertNotIn("references extension", pbik("validate", rep).stdout)
        pbik("measure", "ext", "add", rep, "p Chained", "--expression", "[p Base] + 1", "--data-type", "Double")
        out = pbik("validate", rep, ok=(1,)).stdout
        self.assertIn("p Chained] references extension measure(s) ['p Base']", out)

    def test_88_validate_deneb_rules(self):
        rep, lay, L = self.work("deneb-val")
        L["visuals"].append(self.deneb_visual())
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", rep, lay)
        f = next(rep.glob("definition/pages/*/visuals/P2-V10_*/visual.json"))
        d = json.loads(f.read_text(encoding="utf-8"))
        props = d["visual"]["objects"]["vega"][0]["properties"]
        props["jsonSpec"]["expr"]["Literal"]["Value"] = "'{\"mark\": \"bar\", '"
        f.write_text(json.dumps(d), encoding="utf-8")
        self.assertIn("Deneb spec is not valid JSON", pbik("validate", rep, ok=(1,)).stdout)
        props["jsonSpec"]["expr"]["Literal"]["Value"] = ("'" + json.dumps({"data": {"name": "dataset"}, "mark": "bar",
            "encoding": {"y": {"field": "Nation", "type": "nominal"}}}) + "'")
        f.write_text(json.dumps(d), encoding="utf-8")
        out = pbik("validate", rep).stdout
        self.assertIn("field(s) ['Nation'] that aren't in the dataset", out)       # the Patterns save had this
        rj = rep / "definition" / "report.json"
        r = json.loads(rj.read_text(encoding="utf-8"))
        r.pop("publicCustomVisuals")
        rj.write_text(json.dumps(r), encoding="utf-8")
        self.assertIn("publicCustomVisuals doesn't list", pbik("validate", rep, ok=(1,)).stdout)
        del next(x for x in L["visuals"] if x["id"] == "P2-V10")["fallback"]
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("Deneb visual without a `fallback`", pbik("validate", rep, "--layout", lay, ok=(1,)).stdout)

    # ---------------------------------------------------------------- pbik 0.2 (parity gaps 1, 2, 3, 4, 7, 8)
    def test_70_whole_number_literals(self):
        from pbikit.objects import n
        self.assertEqual(n(0.0)["expr"]["Literal"]["Value"], "0D")
        self.assertEqual(n(1.5)["expr"]["Literal"]["Value"], "1.5D")
        _, pd, _ = Report(self.report).page_by("pbik stock")
        tr = pd["objects"]["background"][0]["properties"]["transparency"]["expr"]["Literal"]["Value"]
        self.assertEqual(tr, "0D")

    def test_71_native_query_ref_keeps_field_name(self):
        from pbikit.objects import measure, native_ref
        p = visual(self.report, "P1-V05")["visual"]["query"]["queryState"]["Values"]["projections"]
        bar = next(x for x in p if x["queryRef"] == "_Measures.Revenue bar")
        self.assertEqual((bar["displayName"], bar["nativeQueryRef"]), (" ", "Revenue bar"))
        self.assertEqual(native_ref(measure("Sales (Current Year)", "_Measures")), "Sales (Current Year)")

    def test_72_empty_query_on_shapes_text_and_buttons(self):
        for vid in ("P1-V01", "P1-V02", "P1-V06", "P1-V07", "P2-V02"):
            self.assertEqual(visual(self.report, vid)["visual"]["query"], {"queryState": {}}, vid)

    def test_73_default_sort(self):
        self.assertTrue(visual(self.report, "P2-V03")["visual"]["query"]["sortDefinition"]["isDefaultSort"])
        self.assertNotIn("isDefaultSort", visual(self.report, "P1-V04")["visual"]["query"]["sortDefinition"])

    def test_74_raw_json_selector_in_props(self):
        work = self.tmp / "rawsel"
        shutil.copytree(self.proj, work)
        lay = work / "design" / "specs" / "layout.json"
        L = json.loads(lay.read_text(encoding="utf-8"))
        card = next(v for v in L["visuals"] if v["id"] == "P1-V03")
        sel = {"data": [{"dataViewWildcard": {"matchingOption": 0}}], "id": "field-x@1", "metadata": "_Measures.Revenue"}
        card["props"]["referenceLabelDetail.detailFontSize@" + json.dumps(sel)] = 9
        lay.write_text(json.dumps(L), encoding="utf-8")
        pbik("build", work / self.report.name, lay)
        o = visual(work / self.report.name, "P1-V03")["visual"]["objects"]
        hit = [e for e in o["referenceLabelDetail"] if e.get("selector") == sel]
        self.assertEqual(hit[0]["properties"]["detailFontSize"]["expr"]["Literal"]["Value"], "9D")
        self.assertIn("No changes", pbik("build", work / self.report.name, lay).stdout)
        card["props"] = {"value.fontSize@{bad json": 9}
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("is not valid JSON", pbik("build", work / self.report.name, lay, ok=(1,)).stdout)

    def test_75_reference_labels(self):
        from pbikit.objects import stable_id
        o = visual(self.report, "P1-V03")["visual"]["objects"]
        rid = stable_id("P1-V03", "_Measures.Revenue", "label 1")
        base = {"metadata": "_Measures.Revenue", "id": rid}
        data = {**base, "data": [{"dataViewWildcard": {"matchingOption": 0}}]}
        lab = o["referenceLabel"][0]
        self.assertEqual(lab["selector"], {**data, "order": 0})
        self.assertEqual(lab["properties"]["value"]["expr"]["Measure"]["Property"], "KPI Revenue PY text")
        title = o["referenceLabelTitle"][0]
        self.assertEqual((title["selector"], title["properties"]), (base, {"show": {"expr": {"Literal": {"Value": "false"}}}}))
        val = o["referenceLabelValue"][0]["properties"]
        self.assertEqual(val["valueFontSize"]["expr"]["Literal"]["Value"], "10D")
        det = o["referenceLabelDetail"][0]
        self.assertEqual(det["selector"], data)
        self.assertNotIn("detailFontSize", det["properties"], "no detailSize in the layout: left to the theme")
        self.assertEqual(det["properties"]["detailFontColor"]["solid"]["color"]["expr"]["Measure"]["Property"],
                         "KPI Revenue delta font")
        self.assertEqual(det["properties"]["detailBackgroundColor"]["solid"]["color"]["expr"]["Measure"]["Property"],
                         "KPI Revenue delta background")
        self.assertFalse([e for k in ("referenceLabelValue", "referenceLabelDetail") for e in o[k]
                          if e.get("selector") == {"metadata": "_Measures.Revenue"}], "no metadata-only entries")

    # ---------------------------------------------------------------- Desktop test round 1 (2026-10-17)
    def test_60_button_text_on_default_selector(self):
        """Desktop keeps button text on {id: default} and `show` selector-less (85 of 85 saved buttons)."""
        for vid, label in (("P1-V06", "'Stock page'"), ("P1-V07", "'Reset filters'")):
            text = visual(self.report, vid)["visual"]["objects"]["text"]
            show = [e for e in text if "show" in e["properties"]]
            self.assertNotIn("selector", show[0])
            rest = [e for e in text if "text" in e["properties"]][0]
            self.assertEqual(rest["selector"], {"id": "default"})
            self.assertEqual(rest["properties"]["text"]["expr"]["Literal"]["Value"], label)
            self.assertIn("fontColor", rest["properties"])

    def test_61_size_tokens_resolve_to_numbers(self):
        """A token name for a size is resolved from tokens.fontPt; validate flags a size written as text."""
        val = visual(self.report, "P1-V03")["visual"]["objects"]["value"][0]
        self.assertEqual(val["selector"], {"id": "default"})
        self.assertEqual(val["properties"]["fontSize"]["expr"]["Literal"]["Value"], "27D")
        work = self.tmp / "sizes"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        f = next(rep.glob("definition/pages/*/visuals/P1-V03_*/visual.json"))
        d = json.loads(f.read_text(encoding="utf-8"))
        d["visual"]["objects"]["value"][0]["properties"]["fontSize"] = {"expr": {"Literal": {"Value": "'kpi'"}}}
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        self.assertIn("value.fontSize is text ('kpi')", pbik("validate", rep, ok=(1,)).stdout)

    def test_62_bar_chart_cf_and_value_axis_line(self):
        """Bar fx is per data point (data wildcard, no column metadata); the value-axis line of a bar chart is y1."""
        d = visual(self.report, "P1-V04")["visual"]["objects"]
        self.assertEqual(d["dataPoint"][0]["selector"], {"data": [{"dataViewWildcard": {"matchingOption": 1}}]})
        self.assertNotIn("xAxisReferenceLine", d)
        work = self.tmp / "axis"
        shutil.copytree(self.proj, work)
        lay = work / "design" / "specs" / "layout.json"
        L = json.loads(lay.read_text(encoding="utf-8"))
        next(v for v in L["visuals"] if v["id"] == "P1-V04")["referenceLines"][0]["axis"] = "x"
        lay.write_text(json.dumps(L), encoding="utf-8")
        r = pbik("build", work / self.report.name, lay, ok=(1,))
        self.assertIn('use axis "value"', r.stdout)

    def test_63_table_widths_bars_and_container(self):
        o = visual(self.report, "P1-V05")["visual"]
        widths = {e["selector"]["metadata"]: e["properties"]["value"]["expr"]["Literal"]["Value"]
                  for e in o["objects"]["columnWidth"]}
        self.assertEqual(widths["stores.Store"], "360D")
        self.assertEqual(widths["_Measures.Revenue bar"], "300D")
        bars = [e for e in o["objects"]["columnFormatting"] if "dataBars" in e["properties"]][0]
        self.assertEqual(bars["properties"]["dataBars"]["hideText"]["expr"]["Literal"]["Value"], "true")
        roles = [pr["queryRef"] for pr in o["query"]["queryState"]["Values"]["projections"]]
        self.assertEqual(roles[1:3], ["_Measures.Revenue bar", "_Measures.Revenue"])
        vco = o["visualContainerObjects"]
        self.assertEqual(vco["background"][0]["properties"]["show"]["expr"]["Literal"]["Value"], "true")
        self.assertEqual(vco["border"][0]["properties"]["show"]["expr"]["Literal"]["Value"], "true")

    def test_64_classic_slicer_list_mode(self):
        """The theme sets slicers to Dropdown; slicerMode list writes objects.data.mode 'Basic' on the visual."""
        o = visual(self.report, "P1-V09")["visual"]["objects"]
        self.assertEqual(o["data"][0]["properties"]["mode"]["expr"]["Literal"]["Value"], "'Basic'")

    def test_66_query_matches_desktop_save(self):
        """As Desktop saves: the first Category (and classic slicer) field is active; no isDefaultSort: false."""
        for vid, role in (("P1-V04", "Category"), ("P2-V03", "Category"), ("P1-V09", "Values")):
            q = visual(self.report, vid)["visual"]["query"]
            self.assertTrue(q["queryState"][role]["projections"][0].get("active"), vid)
            self.assertIsNot(q.get("sortDefinition", {}).get("isDefaultSort"), False)
        q = visual(self.report, "P1-V05")["visual"]["query"]
        self.assertNotIn("active", q["queryState"]["Values"]["projections"][0])

    def test_65_stale_selectorless_props_are_released(self):
        """Rebuilding over round-1 output leaves no selector-less copy of the button text."""
        work = self.tmp / "round1"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        f = next(rep.glob("definition/pages/*/visuals/P1-V06_*/visual.json"))
        d = json.loads(f.read_text(encoding="utf-8"))
        d["visual"]["objects"]["text"].insert(0, {"properties": {"text": {"expr": {"Literal": {"Value": "'old'"}}}}})
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        vm = work / "design" / "specs" / "visual-map.json"
        m = json.loads(vm.read_text(encoding="utf-8"))
        m["owned"]["P1-V06"].append(["objects", "text", None, "text"])
        vm.write_text(json.dumps(m), encoding="utf-8")
        pbik("build", rep, work / "design" / "specs" / "layout.json")
        text = visual(rep, "P1-V06")["visual"]["objects"]["text"]
        self.assertFalse([e for e in text if "selector" not in e and "text" in e["properties"]])

    # ---------------------------------------------------------------- rules on a damaged copy
    def test_20_validate_catches_rule_breaks(self):
        work = self.tmp / "rules"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lay = work / "design" / "specs" / "layout.json"
        pbik("measure", "ext", "add", rep, "img Bad", "--expression",
             '"data:image/svg+xml;utf8,<svg><text>24%</text></svg>"', "--data-category", "ImageUrl")
        d = visual(rep, "P1-V06")
        d["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]["navigationSection"] = \
            {"expr": {"Literal": {"Value": "'pbik stock'"}}}
        d["position"]["x"] = 1800
        f = next(rep.glob("definition/pages/*/visuals/P1-V06_*/visual.json"))
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        d = visual(rep, "P1-V09")
        d["filterConfig"]["filters"][0]["filter"]["Where"][0]["Condition"]["In"]["Values"][0][0]["Literal"]["Value"] = "'1'"
        d["visual"]["query"]["queryState"]["Values"]["projections"][0]["field"]["Column"]["Property"] = "Nope"
        f = next(rep.glob("definition/pages/*/visuals/P1-V09_*/visual.json"))
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        src = next(rep.glob("definition/pages/*/visuals/P1-V07_*"))
        shutil.copytree(src, src.with_name("P1-V07_reset-copy"))
        r = pbik("validate", rep, "--layout", lay, ok=(1,))
        out = r.stdout
        for needle in ("raw '%' in SVG text", "not a page name", "off the page", "has text values",
                       "not in the model's TMDL", "duplicate visual ID"):
            self.assertIn(needle, out, out)

    def test_22_slicer_fit_rules(self):
        """Button slicer fit: no grid, more items than tiles, a label wider than its tile (smoke 2026-10-18)."""
        from pbikit.slicerfit import fit_issues, geometry, lit
        self.assertEqual((lit("8L"), lit("2D"), lit({"expr": {"Literal": {"Value": "11D"}}}), lit("'x'")),
                         (8, 2, 11, None))
        g = {"w": 600, "h": 36, "rows": None, "cols": None, "colGap": 6, "rowGap": 6, "fontPt": 11, "margin": 20}
        self.assertIn("no layout.rowCount", fit_issues(g, 4)[0])
        g.update(rows=1, cols=3)
        self.assertIn("1 scroll out of view", fit_issues(g, ["Downtown", "Commercial", "Residential", "Airport"])[0])
        g.update(cols=4)
        self.assertEqual(fit_issues(g, ["Downtown", "Commercial", "Residential", "Airport"]), [])
        self.assertIn("the text clips", fit_issues(g, ["A very long store location name", "B", "C", "D"])[0])
        self.assertEqual(fit_issues(g, 4), [])                     # a count alone checks only the grid
        d = {"position": {"width": 600, "height": 36}, "visual": {"objects": {
            "layout": [{"properties": {"rowCount": {"expr": {"Literal": {"Value": "1D"}}},
                                       "columnCount": {"expr": {"Literal": {"Value": "4D"}}}}}],
            "padding": [{"selector": {"id": "default"}, "properties": {
                "paddingSelection": {"expr": {"Literal": {"Value": "'Custom'"}}},
                "leftMargin": {"expr": {"Literal": {"Value": "12L"}}},
                "rightMargin": {"expr": {"Literal": {"Value": "8L"}}}}}],
            "value": [{"selector": {"id": "default"}, "properties": {"fontSize": {"expr": {"Literal": {"Value": "11D"}}}}}]}}}
        g = geometry(d)
        self.assertEqual((g["rows"], g["cols"], g["margin"], g["fontPt"]), (1, 4, 20, 11))

    def test_23_validate_slicer_fit_from_layout_hint(self):
        """Without Desktop, validate takes the item count from layout.json `items` and warns (never an error)."""
        work = self.tmp / "slicerfit"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lay = work / "design" / "specs" / "layout.json"
        d = json.loads(lay.read_text(encoding="utf-8"))
        v = next(x for x in d["visuals"] if x["id"] == "P1-V08")
        v["items"] = ["2022", "2023", "2024"]
        lay.write_text(json.dumps(d, indent=2), encoding="utf-8")
        out = pbik("validate", rep, "--layout", lay).stdout
        self.assertIn("P1-V08_year: button slicer: 3 item(s) but no layout.rowCount", out, out)
        self.assertIn("0 error(s)", out, out)
        v["props"].update({"layout.rowCount": {"raw": {"expr": {"Literal": {"Value": "1D"}}}},
                           "layout.columnCount": {"raw": {"expr": {"Literal": {"Value": "2D"}}}}})
        lay.write_text(json.dumps(d, indent=2), encoding="utf-8")
        pbik("build", rep, lay)
        out = pbik("validate", rep, "--layout", lay).stdout
        self.assertIn("3 item(s) in a 1x2 grid: 1 scroll out of view", out, out)
        v["props"]["layout.columnCount"] = {"raw": {"expr": {"Literal": {"Value": "3D"}}}}
        lay.write_text(json.dumps(d, indent=2), encoding="utf-8")
        pbik("build", rep, lay)
        out = pbik("validate", rep, "--layout", lay).stdout
        self.assertNotIn("P1-V08_year: button slicer", out, out)

    def test_24_validate_page_order(self):
        """pages.json: a pageOrder entry with no folder, and a page folder missing from pageOrder, are errors."""
        work = self.tmp / "pageorder"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        f = rep / "definition" / "pages" / "pages.json"
        meta = json.loads(f.read_text(encoding="utf-8"))
        dropped = meta["pageOrder"].pop()
        meta["pageOrder"].append("deadbeef00000000")
        f.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        out = pbik("validate", rep, ok=(1,)).stdout
        self.assertIn("pageOrder lists page deadbeef00000000, which has no page folder", out, out)
        self.assertIn(f"({dropped}) has a folder but is not in pageOrder", out, out)

    def test_25_smoke_remove_cleans_up(self):
        """smoke.py builds _smoke, then --remove drops the folder, its pages.json entry and the smoke spec files."""
        work = self.tmp / "smoke"
        shutil.copytree(self.proj, work)
        (work / "design" / "scripts").mkdir()
        for name in ("smoke.py", "pbik_helpers.py"):
            shutil.copy(KIT / "design" / "scripts" / name, work / "design" / "scripts" / name)
        shutil.copytree(HERE.parent, work / "tools" / "pbik", ignore=shutil.ignore_patterns("__pycache__", "tests"))
        smoke = [sys.executable, str(work / "design" / "scripts" / "smoke.py")]
        r = subprocess.run(smoke + ["--measure", "[Revenue]", "--column", "stores[Location Type]", "--table-columns",
                                    "products[Product_Category],[Revenue]", "--items", "Downtown,Commercial,Residential,Airport"],
                           cwd=work, capture_output=True, text=True, encoding="utf-8")
        self.assertIn("1 x 4 grid", r.stdout, r.stdout + r.stderr)
        rep = work / self.report.name
        smoke_page = Report(rep).page_by("_smoke")
        self.assertIsNotNone(smoke_page)
        r = subprocess.run(smoke + ["--remove"], cwd=work, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        meta = json.loads((rep / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
        self.assertNotIn(smoke_page[0], meta["pageOrder"])
        self.assertNotEqual(meta.get("activePageName"), smoke_page[0])
        self.assertFalse(smoke_page[2].exists())
        for name in ("smoke-layout.json", "smoke-visual-map.json"):
            self.assertFalse((work / "design" / "specs" / name).exists(), name)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", work / "design" / "specs" / "layout.json").stdout)

    def _work(self, name):
        work = self.tmp / name
        shutil.copytree(self.proj, work)
        lay = work / "design" / "specs" / "layout.json"
        return work, work / self.report.name, lay, json.loads(lay.read_text(encoding="utf-8"))

    @staticmethod
    def _save(lay, d):
        lay.write_text(json.dumps(d, indent=2), encoding="utf-8")

    def test_26_theme_colours(self):
        """Theme colours (ThemeDataColor, as Desktop saved them in Rep 7) in props, cf and container keys."""
        work, rep, lay, d = self._work("theme")
        v = {x["id"]: x for x in d["visuals"]}
        v["P1-V03"].setdefault("props", {}).update({"container:dropShadow.color": "theme:0:-0.6",
                                                    "container:subTitle.fontColor": {"theme": 0}})
        v["P1-V03"]["container"] = {"background": {"color": "theme:1", "transparency": 0}}
        v["P1-V05"].setdefault("cf", []).append({"type": "rules", "field": "[Margin %]", "target": "[Margin %]",
                                                 "property": "fontColor", "rules": [{"op": "<", "value": 0, "color": "theme:2"}],
                                                 "else": "#1D2733"})
        self._save(lay, d)
        pbik("build", rep, lay)
        vco = visual(rep, "P1-V03")["visual"]["visualContainerObjects"]
        col = lambda key, prop: next(e["properties"][prop] for e in vco[key] if prop in e["properties"])
        self.assertEqual(col("dropShadow", "color"), {"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": 0, "Percent": -0.6}}}}})
        self.assertEqual(col("subTitle", "fontColor"), {"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": 0, "Percent": 0}}}}})
        self.assertEqual(col("background", "color")["solid"]["color"]["expr"], {"ThemeDataColor": {"ColorId": 1, "Percent": 0}})
        cases = json.dumps(visual(rep, "P1-V05")["visual"]["objects"]["values"])
        self.assertIn('"ThemeDataColor": {"ColorId": 2, "Percent": 0}', cases)
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lay).stdout)
        v["P1-V03"]["props"]["container:dropShadow.color"] = "theme:x"
        self._save(lay, d)
        self.assertIn("theme:<index>", pbik("build", rep, lay, ok=(1,)).stdout)

    def test_27_container_general_and_spacing(self):
        """container altText / keepLayerOrder (general) and spacing, selector-less as Desktop saved them; owned."""
        work, rep, lay, d = self._work("general")
        v = next(x for x in d["visuals"] if x["id"] == "P1-V08")
        v["container"] = {"altText": "Year buttons", "keepLayerOrder": True,
                          "spacing": {"vertical": 10, "belowTitle": 8, "belowSubtitle": 10, "belowTitleArea": 10}}
        self._save(lay, d)
        pbik("build", rep, lay)
        vco = visual(rep, "P1-V08")["visual"]["visualContainerObjects"]
        self.assertEqual(vco["general"], [{"properties": {"keepLayerOrder": {"expr": {"Literal": {"Value": "true"}}},
                                                          "altText": {"expr": {"Literal": {"Value": "'Year buttons'"}}}}}])
        sp = vco["spacing"][0]["properties"]
        self.assertEqual(list(sp), ["customizeSpacing", "verticalSpacing", "spaceBelowTitle", "spaceBelowSubTitle",
                                    "spaceBelowTitleArea"])
        self.assertEqual(sp["spaceBelowTitle"], {"expr": {"Literal": {"Value": "8D"}}})
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        del v["container"]["altText"]
        self._save(lay, d)
        pbik("build", rep, lay)
        gen = visual(rep, "P1-V08")["visual"]["visualContainerObjects"]["general"][0]["properties"]
        self.assertNotIn("altText", gen)
        v["container"]["spacing"] = {"between": 4}
        self._save(lay, d)
        self.assertIn("container.spacing keys ['between']", pbik("build", rep, lay, ok=(1,)).stdout)

    def test_28_visual_groups(self):
        """type "group" with members: a visualGroup folder, members relative to it with parentGroupName (owned),
        nesting, a bookmark that hides a group, validate and audit_layout on page coordinates."""
        work, rep, lay, d = self._work("groups")
        d["visuals"] += [
            {"id": "P1-V20", "name": "kpis", "page": "P1", "type": "group", "displayName": "KPIs",
             "members": ["P1-V03", "P1-V08"], "build": {"method": "native"}},
            {"id": "P1-V21", "name": "all", "page": "P1", "type": "group", "displayName": "All",
             "members": ["P1-V20", "P1-V09"], "build": {"method": "native"}}]
        d["pages"]["P1"]["bookmarks"] = [{"name": "hide-kpis", "displayName": "Hide KPIs", "hide": ["P1-V20"]}]
        self._save(lay, d)
        pbik("build", rep, lay)
        g = visual(rep, "P1-V20")
        self.assertNotIn("visual", g)
        self.assertEqual(g["visualGroup"], {"displayName": "KPIs", "groupMode": "ScaleMode"})
        # KPIs spans P1-V03 (32,172 438x160) and P1-V08 (1418,172 470x44); All adds P1-V09 (1418,240 470x220)
        self.assertEqual({k: g["position"][k] for k in ("x", "y", "width", "height")},
                         {"x": 0, "y": 0, "width": 1856, "height": 160})          # relative to All (32,172)
        self.assertEqual(g["parentGroupName"], "P1-V21_all")
        outer = visual(rep, "P1-V21")
        self.assertEqual({k: outer["position"][k] for k in ("x", "y", "width", "height")},
                         {"x": 32, "y": 172, "width": 1856, "height": 288})
        card = visual(rep, "P1-V03")
        self.assertEqual((card["position"]["x"], card["position"]["y"], card["parentGroupName"]), (0, 0, "P1-V20_kpis"))
        sl = visual(rep, "P1-V08")
        self.assertEqual((sl["position"]["x"], sl["position"]["y"]), (1386, 0))
        bm = next(json.loads(f.read_text(encoding="utf-8")) for f in rep.glob("definition/bookmarks/*.bookmark.json"))
        sec = next(iter(bm["explorationState"]["sections"].values()))
        self.assertEqual(sec["visualContainerGroups"], {"P1-V20_kpis": {"isHidden": True}})
        self.assertIn("P1-V20_kpis", bm["options"]["targetVisualNames"])
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lay).stdout)
        (work / "design" / "scripts").mkdir()
        shutil.copy(KIT / "design" / "scripts" / "audit_layout.py", work / "design" / "scripts" / "audit_layout.py")
        r = subprocess.run([sys.executable, str(work / "design" / "scripts" / "audit_layout.py")], cwd=work,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertNotIn("Traceback", r.stderr, r.stderr)
        self.assertIn("P1-V03_", r.stdout, r.stdout)                  # the audit ran and listed the member
        self.assertNotIn("position (", r.stdout, r.stdout)
        shutil.copy(KIT / "design" / "scripts" / "gen_wireframe.py", work / "design" / "scripts" / "gen_wireframe.py")
        r = subprocess.run([sys.executable, str(work / "design" / "scripts" / "gen_wireframe.py")], cwd=work,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html_ = (work / "design" / "wireframes" / "wireframe.html").read_text(encoding="utf-8")
        self.assertIn('data-id="P1-V21" style="left:32px;top:172px;width:1856px;height:288px', html_)
        # leaving a group drops parentGroupName and the member keeps its page position
        d["visuals"][-2]["members"] = ["P1-V03"]
        self._save(lay, d)
        pbik("build", rep, lay)
        sl = visual(rep, "P1-V08")
        self.assertNotIn("parentGroupName", sl)
        self.assertEqual((sl["position"]["x"], sl["position"]["y"]), (1418, 172))
        # layout errors
        d["visuals"][-2]["members"] = ["P1-V03", "P2-V01"]
        self._save(lay, d)
        self.assertIn("is on page P2", pbik("build", rep, lay, ok=(2,)).stderr)       # layout errors stop the build
        # validate: a parentGroupName with no group
        d2 = visual(rep, "P1-V09")
        d2["parentGroupName"] = "nope"
        next(rep.glob("definition/pages/*/visuals/P1-V09_*/visual.json")).write_text(json.dumps(d2), encoding="utf-8")
        self.assertIn("parentGroupName nope is not a group", pbik("validate", rep, ok=(1,)).stdout)

    def test_29_formatting_from_a_column_aggregation(self):
        """props fx, cf type field and the card image take First/Min(T[C]) (Aggregation Function 3, as Desktop saved
        it in Rep 6 and 7); a bare column is refused."""
        work, rep, lay, d = self._work("aggfmt")
        v = {x["id"]: x for x in d["visuals"]}
        v["P1-V09"].setdefault("props", {})["items.fontColor"] = {"fx": "First(products[Product_Category])"}
        v["P1-V04"].setdefault("cf", []).append({"type": "field", "object": "dataPoint", "property": "fill",
                                                 "field": "Min(stores[City])", "perPoint": True})
        v["P1-V03"].setdefault("cf", []).append({"type": "image", "field": "First(stores[Store])"})
        self._save(lay, d)
        pbik("build", rep, lay)
        agg = lambda tbl, col: {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": tbl}},
                                                                           "Property": col}}, "Function": 3}}
        items = visual(rep, "P1-V09")["visual"]["objects"]["items"]
        self.assertIn({"solid": {"color": {"expr": agg("products", "Product_Category")}}},
                      [e["properties"].get("fontColor") for e in items])
        dp = visual(rep, "P1-V04")["visual"]["objects"]["dataPoint"]
        self.assertIn({"solid": {"color": {"expr": agg("stores", "City")}}}, [e["properties"].get("fill") for e in dp])
        img = next(e for e in visual(rep, "P1-V03")["visual"]["objects"]["image"] if "imageUrl" in e["properties"])
        self.assertEqual(img["properties"]["imageUrl"], {"expr": agg("stores", "Store")})
        self.assertIn("No changes", pbik("build", rep, lay).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lay).stdout)
        v["P1-V04"]["cf"][-1]["field"] = "stores[City]"
        self._save(lay, d)
        self.assertIn("is a column; formatting needs a measure or an aggregation", pbik("build", rep, lay, ok=(1,)).stdout)

    def test_21_prune(self):
        work = self.tmp / "prune"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lay = work / "design" / "specs" / "layout.json"
        d = json.loads(lay.read_text(encoding="utf-8"))
        d["visuals"] = [v for v in d["visuals"] if v["id"] != "P1-V07"]
        d["retired"] = ["P1-V07"]
        lay.write_text(json.dumps(d, indent=2), encoding="utf-8")
        r = pbik("build", rep, lay)
        self.assertIn("kept; --prune removes it", r.stdout)
        self.assertTrue(list(rep.glob("definition/pages/*/visuals/P1-V07_*")))
        pbik("build", rep, lay, "--prune")
        self.assertFalse(list(rep.glob("definition/pages/*/visuals/P1-V07_*")))
        self.assertIn("No changes", pbik("build", rep, lay, "--prune").stdout)

    def test_22_layout_change_is_released(self):
        """A property dropped from layout.json is removed on the next build (ownership in the ID map)."""
        work = self.tmp / "release"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lay = work / "design" / "specs" / "layout.json"
        d = json.loads(lay.read_text(encoding="utf-8"))
        v = next(x for x in d["visuals"] if x["id"] == "P2-V03")
        v.pop("referenceLines")
        v["x"] = 40
        lay.write_text(json.dumps(d, indent=2), encoding="utf-8")
        pbik("build", rep, lay)
        vis = visual(rep, "P2-V03")
        self.assertNotIn("y1AxisReferenceLine", vis["visual"]["objects"])
        self.assertEqual(vis["position"]["x"], 40)

    def test_23_build_leaves_desktop_pages_alone(self):
        work = self.tmp / "keep"
        work.mkdir()
        rep, _ = copy_project(work, keep_pages=True)
        before = {k: v for k, v in tree_hash(rep).items() if "pbik" not in k}
        old_pages = [p.name for p in (rep / "definition" / "pages").iterdir() if p.is_dir()]
        add_ext(rep)
        pbik("build", rep, work / "design" / "specs" / "layout.json")
        after = tree_hash(rep)
        for k, h in before.items():
            if any(f"pages{os.sep}{p}{os.sep}" in k for p in old_pages):
                self.assertEqual(after.get(k), h, k)

    # ---------------------------------------------------------------- templates
    def test_30_templates_harvest_and_use(self):
        work = self.tmp / "tpl"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lay = {"measureTable": "_Measures", "pages": {"P9": {"displayName": "Patterns"}}, "visuals": [
            {"id": "P9-V01", "name": "card", "page": "P9", "type": "cardVisual", "x": 32, "y": 32, "w": 300, "h": 150,
             "bindings": {"Data": ["[Revenue]"]},
             "props": {"accentBar.show@default": True, "accentBar.color@default": "teal"},
             "filters": [{"field": "products[Product_Category]", "values": ["Toys"]}]}]}
        lf = work / "design" / "specs" / "patterns.json"
        lf.write_text(json.dumps(lay), encoding="utf-8")
        pbik("build", rep, lf, "--map", work / "design" / "specs" / "patterns-map.json")
        pbik("templates", "harvest", rep, "--out", work / "design" / "templates")
        t = json.loads((work / "design" / "templates" / "cardVisual.json").read_text(encoding="utf-8"))
        self.assertNotIn("name", t)
        self.assertNotIn("position", t)
        self.assertNotIn("query", t["visual"])
        self.assertIn("accentBar", t["visual"]["objects"])
        self.assertIn("filterConfig", t)
        lay2 = json.loads((work / "design" / "specs" / "layout.json").read_text(encoding="utf-8"))
        lay2["visuals"].append({"id": "P2-V04", "name": "templated", "page": "P2", "type": "cardVisual",
                                "x": 32, "y": 660, "w": 300, "h": 150, "bindings": {"Data": ["[Units Sold]"]}})
        (work / "design" / "specs" / "layout.json").write_text(json.dumps(lay2), encoding="utf-8")
        pbik("build", rep, work / "design" / "specs" / "layout.json")
        d = visual(rep, "P2-V04")
        self.assertIn("accentBar", d["visual"]["objects"])
        got, want = d["filterConfig"]["filters"][0], t["filterConfig"]["filters"][0]
        self.assertTrue(got["name"].startswith("tpl_"), "template filters are renamed tpl_*, so build doesn't clear them")
        self.assertEqual({k: x for k, x in got.items() if k != "name"}, {k: x for k, x in want.items() if k != "name"},
                         "the template's filters reach the new visual (0.2 regression)")
        self.assertEqual(d["visual"]["query"]["queryState"]["Data"]["projections"][0]["queryRef"], "_Measures.Units Sold")

    def test_31_harvest_names_defaults_and_index(self):
        """Every Patterns visual is <type>.<name without ID>; the largest of a type is also <type>.json."""
        work = self.tmp / "tpl31"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lay = {"measureTable": "_Measures", "pages": {"P9": {"displayName": "Patterns"}}, "visuals": [
            {"id": "P9-V01", "name": "small-card", "page": "P9", "type": "cardVisual", "x": 32, "y": 32, "w": 100,
             "h": 40, "bindings": {"Data": ["[Revenue]"]}},
            {"id": "P9-V02", "name": "big-card", "page": "P9", "type": "cardVisual", "x": 32, "y": 100, "w": 300,
             "h": 150, "bindings": {"Data": ["[Revenue]"]}, "props": {"accentBar.show@default": True}}]}
        lf = work / "design" / "specs" / "patterns.json"
        lf.write_text(json.dumps(lay), encoding="utf-8")
        pbik("build", rep, lf, "--map", work / "design" / "specs" / "patterns-map.json")
        out = work / "design" / "templates"
        pbik("templates", "harvest", rep, "--out", out)
        self.assertTrue((out / "cardVisual.small-card.json").exists())
        self.assertTrue((out / "cardVisual.big-card.json").exists())
        default = json.loads((out / "cardVisual.json").read_text(encoding="utf-8"))
        self.assertIn("accentBar", default["visual"]["objects"], "the default is the largest card")
        idx = json.loads((out / "index.json").read_text(encoding="utf-8"))["templates"]
        self.assertEqual(idx["cardVisual"]["sameAs"], "cardVisual.big-card")
        self.assertEqual(idx["cardVisual.small-card"]["source"], "P9-V01_small-card")

    def test_32_kit_templates_work_in_another_model(self):
        """The kit's templates come from Rep 8 (HR); in Rep 4's model (Toy Sales) build drops formatting bound to HR
        fields, warns, and validate stays clean."""
        kit_tpl = KIT / "design" / "templates"
        if not (kit_tpl / "cardVisual.card-reference-labels.json").exists():
            self.fail("kit templates missing from design/templates (pbik templates harvest)")
        work = self.tmp / "tpl32"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lay = json.loads((work / "design" / "specs" / "layout.json").read_text(encoding="utf-8"))
        lay["visuals"] += [
            {"id": "P2-V31", "name": "tpl-card", "page": "P2", "type": "cardVisual", "template": "cardVisual.card-reference-labels",
             "x": 32, "y": 660, "w": 300, "h": 150, "bindings": {"Data": ["[Revenue]"]}},
            {"id": "P2-V32", "name": "tpl-line", "page": "P2", "type": "lineChart", "x": 360, "y": 660, "w": 600,
             "h": 300, "bindings": {"Category": ["Date[Year]"], "Y": ["[Revenue]"]}}]
        (work / "design" / "specs" / "layout.json").write_text(json.dumps(lay), encoding="utf-8")
        r = pbik("build", rep, work / "design" / "specs" / "layout.json", "--templates", kit_tpl)
        self.assertIn("file(s) written", r.stdout)
        text = json.dumps(visual(rep, "P2-V31"))
        self.assertNotIn("Headcount", text)
        self.assertIn("referenceLabelLayout", text, "the template's own formatting stays")
        v = pbik("validate", rep, "--layout", work / "design" / "specs" / "layout.json")
        self.assertIn("0 error(s)", v.stdout, v.stdout)

    def test_32b_templates_carry_formatting_only(self):
        """Smoke 2026-10-19: a default template carried Rep 8's reference labels and table title into a new visual in
        the same HR model. A template now gives formatting only; the layout gives content and field-bound settings."""
        kit_tpl = KIT / "design" / "templates"
        if not (kit_tpl / "tableEx.json").exists():
            self.fail("kit templates missing from design/templates (pbik templates harvest)")
        from pbikit import fieldrefs as FR
        card = json.loads((kit_tpl / "cardVisual.card-reference-labels.json").read_text(encoding="utf-8"))
        table = json.loads((kit_tpl / "tableEx.json").read_text(encoding="utf-8"))
        self.assertIn("referenceLabel", json.dumps(card), "the harvested template still holds Desktop's content")
        FR.formatting_only(card, None, {})
        FR.formatting_only(table, None, {})
        txt = json.dumps(card)
        self.assertNotIn('"Measure"', txt)
        self.assertNotIn('"metadata"', txt)
        self.assertIn("referenceLabelLayout", txt, "layout settings without fields stay")
        self.assertIn("shapeCustomRectangle", txt)
        vco = table["visual"].get("visualContainerObjects", {})
        for key in ("title", "subTitle"):
            for e in vco.get(key, []):
                self.assertNotIn("text", e.get("properties", {}), f"{key} text is content")
        self.assertIn("border", vco, "the container style stays")
        self.assertIn("columnHeaders", table["visual"]["objects"], "table formatting stays")
        btn = {"visual": {"visualType": "actionButton", "visualContainerObjects": {"visualLink": [{"properties": {}}]},
                          "objects": {"text": [{"properties": {"text": {"expr": {"Literal": {"Value": "'Clear'"}}},
                                                                "fontSize": {"expr": {"Literal": {"Value": "11D"}}}},
                                                "selector": {"id": "default"}}]}}}
        FR.formatting_only(btn, None, {})
        self.assertNotIn("visualLink", btn["visual"].get("visualContainerObjects", {}))
        self.assertEqual(list(btn["visual"]["objects"]["text"][0]["properties"]), ["fontSize"])

    def test_32c_template_selected_state_gets_colors_selected(self):
        """Every selected state a template brings takes tokens colors.selected: the button slicer's teal (white text,
        4.0:1) and the navigator's white tile alike. The navigator's dark selected text fails on the new colour: a
        build warning. Layout props still win."""
        kit_tpl = KIT / "design" / "templates"
        if not (kit_tpl / "advancedSlicerVisual.json").exists():
            self.fail("kit templates missing from design/templates (pbik templates harvest)")
        tokens = json.loads((KIT / "design" / "tokens.json").read_text(encoding="utf-8"))
        sel = tokens["colors"]["selected"].upper()

        def edit(lay):
            lay["visuals"] += [
                {"id": "P1-V70", "name": "tpl-buttons", "page": "P1", "type": "advancedSlicerVisual", "x": 32, "y": 900,
                 "w": 600, "h": 36, "bindings": {"Values": ["Date[Year]"]}},
                {"id": "P1-V71", "name": "tpl-nav", "page": "P1", "type": "pageNavigator", "x": 700, "y": 900,
                 "w": 600, "h": 40},
                {"id": "P1-V72", "name": "tpl-buttons-own", "page": "P1", "type": "advancedSlicerVisual", "x": 32,
                 "y": 960, "w": 600, "h": 36, "bindings": {"Values": ["Date[Year]"]},
                 "props": {"fillCustom.fillColor@{\"id\": \"selection:selected\"}": "#000000"}}]
        work, rep, lf = self._item5("sel32c", edit)
        r = pbik("build", rep, lf, "--templates", kit_tpl)
        self.assertIn(f"P1-V70: template selection:selected fill #038D96 -> colors.selected {sel}, text #FFFFFF", r.stdout)
        self.assertIn(f"P1-V71: template selected fill #FFFFFF -> colors.selected {sel}, text #FFFFFF", r.stdout)
        self.assertFalse([x for x in r.stdout.splitlines() if x.startswith(("warning: P1-V70:", "warning: P1-V71:"))],
                         "the text colour is set with the fill, so both pass")

        def state(vid, key, state_id, prop):
            for e in visual(rep, vid)["visual"]["objects"].get(key, []):
                if e.get("selector") == {"id": state_id}:
                    return e["properties"][prop]["solid"]["color"]["expr"]["Literal"]["Value"].strip("'").upper()
        self.assertEqual(state("P1-V70", "fillCustom", "selection:selected", "fillColor"), sel)
        self.assertEqual(state("P1-V70", "outline", "selection:selected", "lineColor"), sel, "the outline follows")
        self.assertEqual(state("P1-V71", "fill", "selected", "fillColor"), sel, "every selected state, for consistency")
        self.assertEqual(state("P1-V70", "value", "selection:selected", "fontColor"), "#FFFFFF")
        self.assertEqual(state("P1-V71", "text", "selected", "fontColor"), "#FFFFFF",
                         "the navigator's dark text became white on the dark selected fill")
        self.assertEqual(state("P1-V72", "fillCustom", "selection:selected", "fillColor"), "#000000",
                         "layout props still win")
        v = pbik("validate", rep, "--layout", lf, "--no-catalog").stdout
        self.assertFalse([x for x in v.splitlines() if "P1-V70" in x and "WCAG" in x], v)
        self.assertIn("No changes", pbik("build", rep, lf, "--templates", kit_tpl).stdout)

    def test_32h_template_colours_follow_a_new_palette(self):
        """tokens theme.recolourTemplates (gen_tokens.py): a template's literal colours map to the tokens by role
        (design/templates/palette.json); without it they stay as drawn."""
        kit_tpl = KIT / "design" / "templates"
        if not (kit_tpl / "pageNavigator.json").exists():
            self.fail("kit templates missing from design/templates (pbik templates harvest)")
        sys.path.insert(0, str(KIT / "design" / "scripts"))
        import gen_tokens
        dark = gen_tokens.run(brand="#0E1A2B,#F2B705,#E4572E", mode="dark",
                              base=json.loads((KIT / "design" / "tokens.json").read_text(encoding="utf-8")))[0]
        c = dark["colors"]

        def edit(lay):
            lay["visuals"].append({"id": "P1-V73", "name": "tpl-nav-dark", "page": "P1", "type": "pageNavigator",
                                   "x": 700, "y": 960, "w": 600, "h": 40})

        def default_text(rep):
            for e in visual(rep, "P1-V73")["visual"]["objects"].get("text", []):
                if e.get("selector") == {"id": "default"} and "fontColor" in e.get("properties", {}):
                    return e["properties"]["fontColor"]["solid"]["color"]["expr"]["Literal"]["Value"].strip("'")
        for recolour, want in ((True, c["onDarkMuted"]), (False, "#B9D9DC")):
            dark["theme"]["recolourTemplates"] = recolour
            work, rep, lf = self._item5(f"recolour32h{recolour}", edit)
            tf = work / "design" / "tokens.json"
            tf.write_text(json.dumps(dark), encoding="utf-8")
            r = pbik("build", rep, lf, "--templates", kit_tpl, "--tokens", tf)
            self.assertEqual(default_text(rep), want, r.stdout)
            self.assertEqual("P1-V73: template colours -> tokens" in r.stdout, recolour)
            self.assertIn("No changes", pbik("build", rep, lf, "--templates", kit_tpl, "--tokens", tf).stdout)

    def test_32d_selected_text_for_light_and_dark_selected_colours(self):
        """The selected state's text: colors.onSelected if set, else white or the dark primary, whichever contrasts
        more; with a light and a dark colors.selected, and layout props on the text winning."""
        from pbikit import a11y
        kit_tpl = KIT / "design" / "templates"
        if not (kit_tpl / "advancedSlicerVisual.json").exists():
            self.fail("kit templates missing from design/templates (pbik templates harvest)")
        dark, light, primary = "#037C84", "#E7F3F5", "#12343B"
        self.assertEqual(a11y.selected_text(dark, None, primary), "#FFFFFF")
        self.assertEqual(a11y.selected_text(light, None, primary), primary)
        self.assertEqual(a11y.selected_text(light, "#000000", primary), "#000000", "colors.onSelected wins")

        def tile(vid):
            ob = visual(rep, vid)["visual"]["objects"]
            get = lambda key, prop: next(e["properties"][prop]["solid"]["color"]["expr"]["Literal"]["Value"].strip("'").upper()  # noqa: E731
                                         for e in ob[key] if e.get("selector") == {"id": "selection:selected"})
            return get("fillCustom", "fillColor"), get("value", "fontColor")

        for name, colour, on, want_text in (("light", light, None, primary), ("dark", dark, None, "#FFFFFF"),
                                            ("on", light, "#000000", "#000000")):
            def edit(lay):
                lay["visuals"] += [
                    {"id": "P1-V73", "name": "sel", "page": "P1", "type": "advancedSlicerVisual", "x": 32, "y": 900,
                     "w": 600, "h": 36, "bindings": {"Values": ["Date[Year]"]}},
                    {"id": "P1-V74", "name": "sel-own-text", "page": "P1", "type": "advancedSlicerVisual", "x": 32,
                     "y": 960, "w": 600, "h": 36, "bindings": {"Values": ["Date[Year]"]},
                     "props": {"value.fontColor@{\"id\": \"selection:selected\"}": "#7A4FA0"}}]
            work, rep, lf = self._item5(f"sel32d-{name}", edit)
            tok = json.loads((work / "design" / "tokens.json").read_text(encoding="utf-8"))
            tok["colors"]["selected"] = colour
            tok["colors"]["primary"] = primary
            if on:
                tok["colors"]["onSelected"] = on
            else:
                tok["colors"].pop("onSelected", None)
            (work / "design" / "tokens.json").write_text(json.dumps(tok), encoding="utf-8")
            r = pbik("build", rep, lf, "--templates", kit_tpl)
            self.assertEqual(tile("P1-V73"), (colour.upper(), want_text.upper()), f"{name}: {r.stdout}")
            self.assertEqual(tile("P1-V74")[1], "#7A4FA0", f"{name}: layout props on the text win")
            self.assertFalse([x for x in r.stdout.splitlines() if x.startswith("warning: P1-V73:")], r.stdout)

    def test_32e_template_reference_line_dropped_whole(self):
        """Rep 9: the clusteredBarChart template (Rep 8) carries a "Company" line bound to [Turnover Rate Company].
        Without that field the line drew at 0 as "Company: 0"; pbik now drops the whole line. A layout line is still
        written, and a template line with a literal value stays."""
        kit_tpl = KIT / "design" / "templates"
        tpl = kit_tpl / "clusteredBarChart.json"
        if not tpl.exists() or "y1AxisReferenceLine" not in tpl.read_text(encoding="utf-8"):
            self.skipTest("no template with a reference line")

        def edit(lay):
            lay["visuals"] += [
                {"id": "P1-V80", "name": "tpl-bars", "page": "P1", "type": "clusteredBarChart", "x": 32, "y": 700,
                 "w": 600, "h": 300, "bindings": {"Category": ["Date[Year]"], "Y": ["[Revenue]"]}},
                {"id": "P1-V81", "name": "tpl-bars-line", "page": "P1", "type": "clusteredBarChart", "x": 700, "y": 700,
                 "w": 600, "h": 300, "bindings": {"Category": ["Date[Year]"], "Y": ["[Revenue]"]},
                 "referenceLines": [{"axis": "value", "value": "[Revenue]", "label": "Target"}]}]
        work, rep, lf = self._item5("ref32e", edit)
        pbik("build", rep, lf, "--templates", kit_tpl)
        self.assertNotIn("y1AxisReferenceLine", visual(rep, "P1-V80")["visual"].get("objects", {}),
                         "the template's field-bound line is gone, not left at 0 with its old label")
        own = visual(rep, "P1-V81")["visual"]["objects"]["y1AxisReferenceLine"]
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]["properties"]["displayName"]["expr"]["Literal"]["Value"], "'Target'")
        self.assertIn("Revenue", json.dumps(own[0]["properties"]["value"]))
        from pbikit import fieldrefs as FR
        lit = {"visual": {"visualType": "lineChart", "objects": {"y1AxisReferenceLine": [
            {"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "value": {"expr": {"Literal": {"Value": "0D"}}}},
             "selector": {"id": "1"}}]}}}
        FR.formatting_only(lit, None, {})
        self.assertIn("y1AxisReferenceLine", lit["visual"]["objects"], "a literal line is formatting and stays")

    def test_32f_tab_order_key(self):
        """Rep 9: a visual numbered after another must come first in tab order. layout `tabOrder` overrides the
        default (visual number x 100); validate's reading-order warning goes."""
        def edit(lay, tab=None):
            lay["visuals"] += [
                {"id": "P1-V90", "name": "first-in-reading", "page": "P1", "type": "textbox", "x": 0, "y": 0, "w": 20,
                 "h": 20, "text": "a", "textFit": False, **({"tabOrder": tab} if tab is not None else {})}]
        work, rep, lf = self._item5("tab32f", edit)
        pbik("build", rep, lf)
        out = pbik("validate", rep, "--layout", lf, "--no-catalog").stdout
        self.assertTrue([x for x in out.splitlines() if "tab order" in x and "P1-V90" in x], out)
        self.assertEqual(visual(rep, "P1-V90")["position"]["tabOrder"], 9000)
        work, rep, lf = self._item5("tab32f2", lambda lay: edit(lay, 50))
        pbik("build", rep, lf)
        self.assertEqual(visual(rep, "P1-V90")["position"]["tabOrder"], 50)
        out = pbik("validate", rep, "--layout", lf, "--no-catalog").stdout
        self.assertFalse([x for x in out.splitlines() if "tab order" in x and "P1-V90" in x], out)
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        work, rep, lf = self._item5("tab32f3", lambda lay: edit(lay, "first"))
        self.assertIn("tabOrder 'first' must be a whole number", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_32g_kpi_card_template_left_padding(self):
        """Rep 9 review item 1: Desktop drew the left-aligned label from the card's edge and clipped its first letter
        ("nteractions"); padding.leftMargin 4 (Custom, on {id: default}) fixed it in Desktop. The KPI card templates
        carry it (a re-harvest must keep it), a card built from the default template gets it, and layout props win."""
        kit_tpl = KIT / "design" / "templates"
        for n in ("cardVisual.json", "cardVisual.card-reference-labels.json", "cardVisual.card-plain.json"):
            f = kit_tpl / n
            if not f.exists():
                self.fail("kit templates missing from design/templates (pbik templates harvest)")
            pad = json.loads(f.read_text(encoding="utf-8"))["visual"]["objects"].get("padding", [])
            e = next((x for x in pad if x.get("selector") == {"id": "default"}), None)
            self.assertIsNotNone(e, f"{n}: no padding on {{id: default}}")
            p = e["properties"]
            self.assertEqual(p["paddingSelection"]["expr"]["Literal"]["Value"], "'Custom'", n)
            self.assertGreaterEqual(float(p["leftMargin"]["expr"]["Literal"]["Value"].rstrip("DL")), 4, n)

        def edit(lay):
            lay["visuals"] += [
                {"id": "P1-V85", "name": "kpi", "page": "P1", "type": "cardVisual", "x": 32, "y": 700, "w": 220,
                 "h": 128, "bindings": {"Data": ["[Revenue]"]}},
                {"id": "P1-V86", "name": "kpi-own", "page": "P1", "type": "cardVisual", "x": 300, "y": 700, "w": 220,
                 "h": 128, "bindings": {"Data": ["[Revenue]"]}, "props": {"padding.leftMargin": 12}}]
        work, rep, lf = self._item5("pad32g", edit)
        pbik("build", rep, lf, "--templates", kit_tpl)

        def left(vid):
            e = next(x for x in visual(rep, vid)["visual"]["objects"]["padding"] if x.get("selector") == {"id": "default"})
            return e["properties"]["leftMargin"]["expr"]["Literal"]["Value"]
        self.assertEqual(left("P1-V85"), "4D")
        self.assertEqual(left("P1-V86"), "12D", "layout props win")
        out = pbik("validate", rep, "--layout", lf).stdout
        self.assertFalse([x for x in out.splitlines() if "catalog" in x and "padding" in x and "P1-V85" in x], out)

    # ---------------------------------------------------------------- settings catalog
    def test_33_catalog_types_selectors_and_desktop_files(self):
        from pbikit import catalog as CAT
        self.assertEqual(CAT.value_type({"expr": {"Literal": {"Value": "true"}}}), "bool")
        self.assertEqual(CAT.value_type({"expr": {"Literal": {"Value": "12D"}}}), "number")
        self.assertEqual(CAT.value_type({"expr": {"Literal": {"Value": "16L"}}}), "int")
        self.assertEqual(CAT.value_type({"expr": {"Literal": {"Value": "'x'"}}}), "text")
        self.assertEqual(CAT.value_type({"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}}), "color:literal")
        self.assertEqual(CAT.value_type({"solid": {"color": {"expr": {"ThemeDataColor": {"ColorId": 2}}}}}), "color:theme")
        self.assertEqual(CAT.selector_shape(None), "none")
        self.assertEqual(CAT.selector_shape({"id": "default"}), "id:default")
        self.assertEqual(CAT.selector_shape({"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                             "metadata": "_Measures.X"}), "data:dataViewWildcard+metadata")
        work = self.tmp / "cat33"
        work.mkdir()
        f1, f2 = work / "desktop.json", work / "pbik.json"
        f1.write_text("{}", encoding="utf-8")
        f2.write_text("{}\n", encoding="utf-8")
        self.assertTrue(CAT.desktop_saved(f1))
        self.assertFalse(CAT.desktop_saved(f2))

    def test_34_catalog_refresh_and_validate_warning(self):
        """A catalog from the Desktop-saved source; pbik-written files (final newline) are skipped; validate warns on a
        property no Desktop file has and stays quiet on one it has."""
        cat = self.tmp / "cat34.json"
        r = pbik("catalog", "refresh", SOURCE, "--catalog", cat)
        self.assertIn("new", r.stdout)
        again = pbik("catalog", "refresh", SOURCE, "--catalog", cat)
        self.assertIn("0 new (unchanged)", again.stdout)
        c = json.loads(cat.read_text(encoding="utf-8"))
        self.assertIn("cardVisual", c["visuals"])
        skipped = pbik("catalog", "refresh", self.report, "--catalog", self.tmp / "cat34b.json")
        self.assertIn("0 setting(s)", skipped.stdout, "pbik's own files aren't Desktop-saved")
        work = self.tmp / "cat34"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lf = work / "design" / "specs" / "layout.json"
        lay = json.loads(lf.read_text(encoding="utf-8"))
        card = next(v for v in lay["visuals"] if v["type"] == "cardVisual")
        card.setdefault("props", {})["madeUpObject.madeUpProperty"] = True
        lf.write_text(json.dumps(lay), encoding="utf-8")
        pbik("build", rep, lf)
        v = pbik("validate", rep, "--layout", lf, "--catalog", cat)
        self.assertIn("madeUpObject", v.stdout)
        self.assertIn(card["id"], [ln for ln in v.stdout.splitlines() if "madeUpObject" in ln][0])
        self.assertIn("0 error(s)", v.stdout, "catalog findings are warnings")
        quiet = pbik("validate", rep, "--layout", lf, "--catalog", cat, "--no-catalog")
        self.assertNotIn("madeUpObject", quiet.stdout)

    # ---------------------------------------------------------------- target Desktop (project.json)
    def _pinned(self, name, target="2.152.882.0", catalog=None):
        work, rep, lf, lay = self._work(name)
        proj = {"targetDesktop": target, **({"catalog": catalog} if catalog else {})}
        (work / "design" / "specs" / "project.json").write_text(json.dumps(proj), encoding="utf-8")
        return work, rep, lf

    @staticmethod
    def _declared(rep, kind):
        import re
        out = set()
        for f in rep.rglob("*.json"):
            m = re.search(rf"/definition/{kind}/(\d+\.\d+\.\d+)/schema\.json", f.read_text(encoding="utf-8")[:400])
            if m:
                out.add(m.group(1))
        return out

    def test_100_pinned_build_writes_the_target_versions(self):
        """Target March 2026 (2.152): every visual and page pbik writes declares what that Desktop supports."""
        work, rep, lf = self._pinned("pin100")
        r = pbik("build", rep, lf)
        self.assertIn("target Desktop 2.152.882.0", r.stdout)
        self.assertEqual(self._declared(rep, "visualContainer"), {"2.7.0"})
        self.assertEqual(self._declared(rep, "pagesMetadata"), {"1.0.0"})
        self.assertEqual(self._declared(rep, "page"), {"2.1.0"})
        self.assertEqual(self._declared(rep, "report"), {"3.2.0"}, "report.json (Desktop's) gets only its $schema lowered")
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        v = pbik("validate", rep, "--layout", lf, "--no-catalog").stdout
        self.assertNotIn("newer than target", v)
        self.assertIn(" 0 error(s)", v)

    def test_101_validate_flags_files_newer_than_the_target(self):
        work, rep, lf = self._pinned("pin101", target="2.143.878.0")          # May 2025
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", ok=(1,)).stdout
        self.assertIn("is newer than target Desktop 2.143.878.0 supports", v)
        self.assertIn("2.0.0, Desktop 2.143.878.0 (2025-05)", v, "visualContainer 2.0.0 was the May 2025 version")
        latest = self._work("pin101b")
        self.assertNotIn("newer than target", pbik("validate", latest[1], "--layout", latest[2], "--no-catalog").stdout)

    def test_105_schemas_lower_for_an_older_desktop(self):
        """The Desktop-saved source (visualContainer 2.9.0 and 2.13.0) lowered for a March 2026 Desktop."""
        work = self.tmp / "pin105"
        rep, _ = copy_project(work)
        (work / "design" / "specs" / "project.json").write_text('{"targetDesktop": "2.152.882.0"}', encoding="utf-8")
        before = self._declared(rep, "visualContainer")
        self.assertIn("2.13.0", before)
        out = pbik("schemas", "lower", rep).stdout
        self.assertIn("file(s) lowered", out)
        self.assertEqual(self._declared(rep, "visualContainer"), {"2.7.0"})
        self.assertNotIn("newer than target", pbik("validate", rep, "--no-catalog", ok=(0, 1)).stdout)
        self.assertIn(" 0 file(s) lowered", pbik("schemas", "lower", rep).stdout)

    def test_102_a_target_newer_than_microsofts_list_is_not_pinned(self):
        """Desktop 2.159 wrote visualContainer 2.14.0 before Microsoft published it: no cap, no error."""
        work, rep, lf = self._pinned("pin102", target="2.999.1.0")
        r = pbik("build", rep, lf)
        self.assertNotIn("target Desktop", r.stdout)
        self.assertIn("2.13.0", self._declared(rep, "visualContainer"))

    def test_103_project_named_catalog(self):
        """project.json `catalog` picks the named catalog validate warns from; --catalog still wins."""
        from pbikit import catalog as CAT, validate as VAL
        saved = CAT.CATALOGS
        CAT.CATALOGS = self.tmp / "catalogs103"
        try:
            CAT.refresh([SOURCE], name="work", desktop="2.152.882.0", today="2026-10-29")
            c = json.loads((CAT.CATALOGS / "work.json").read_text(encoding="utf-8"))
            self.assertEqual(c["desktop"], {"version": "2.152.882.0", "refreshed": "2026-10-29"})
            CAT.refresh([SOURCE], name="work", desktop="2.152.882.0", today="2026-11-01")
            c = json.loads((CAT.CATALOGS / "work.json").read_text(encoding="utf-8"))
            self.assertEqual(c["desktop"]["refreshed"], "2026-10-29", "the date moves only with the version")
            work, rep, lf = self._pinned("pin103", target="latest", catalog="work")
            lay = json.loads(lf.read_text(encoding="utf-8"))
            card = next(v for v in lay["visuals"] if v["type"] == "cardVisual")
            card.setdefault("props", {})["madeUpObject.madeUpProperty"] = True
            self._save(lf, lay)
            pbik("build", rep, lf)
            fd = VAL.validate(rep, str(lf))
            self.assertTrue(any("madeUpObject" in m for m in fd.warnings), fd.warnings)
            missing = self._pinned("pin103b", target="latest", catalog="home")
            fd = VAL.validate(missing[1], str(missing[2]))
            self.assertTrue(any("home.json" in m for m in fd.warnings), "a missing named catalog is reported")
            with self.assertRaises(SystemExit):
                CAT.catalog_path("../work")
        finally:
            CAT.CATALOGS = saved

    def test_104_project_record_and_show(self):
        from pbikit import versions as V
        pj = self.tmp / "pin104" / "project.json"
        V.record(pj, "2.159.883.0", today="2026-10-29")
        d = json.loads(pj.read_text(encoding="utf-8"))
        self.assertEqual(d, {"targetDesktop": "latest", "catalog": "home",
                             "desktop": {"version": "2.159.883.0", "recorded": "2026-10-29"}})
        d["targetDesktop"] = "2.152.882.0"
        pj.write_text(json.dumps(d), encoding="utf-8")
        V.record(pj, "2.160.1.0", today="2026-11-20")
        d = json.loads(pj.read_text(encoding="utf-8"))
        self.assertEqual(d["targetDesktop"], "2.152.882.0", "recording never changes the target")
        out = pbik("project", "show", "--project", pj).stdout
        self.assertIn("visualContainer    2.7.0", out)
        self.assertIn("recorded       Desktop 2.160.1.0", out)

    def test_104b_desktop_version_with_build_suffix(self):
        """MSI and IT-managed installs report '2.155.756.0 (26.06)+<hash>': pbik takes the leading version."""
        from pbikit import versions as V
        self.assertEqual(V.desktop_version("2.155.756.0 (26.06)+3f9c2a1b\r\n"), "2.155.756.0")
        self.assertEqual(V.desktop_version("2.159.883.0"), "2.159.883.0")
        self.assertIsNone(V.desktop_version(""))
        self.assertIsNone(V.desktop_version("Power BI Desktop"))
        pj = self.tmp / "pin104b" / "project.json"
        V.record(pj, "2.155.756.0 (26.06)+3f9c2a1b", today="2026-10-30")
        self.assertEqual(json.loads(pj.read_text(encoding="utf-8"))["desktop"]["version"], "2.155.756.0")

    def test_104c_project_check(self):
        """Desktop newer than targetDesktop: exit 5 (run /update first); equal: pass; older: warn and pass; latest:
        pass; version not found: exit 3."""
        from pbikit import versions as V
        pj = self.tmp / "pin104c" / "project.json"
        pj.parent.mkdir(parents=True)
        pj.write_text(json.dumps({"targetDesktop": "2.155.756.0", "catalog": "work"}), encoding="utf-8")
        newer = pbik("project", "check", "--project", pj, "--version", "2.159.883.0", ok=(5,))
        self.assertIn("run /update first", newer.stderr)
        self.assertIn("matches", pbik("project", "check", "--project", pj, "--version",
                                      "2.155.756.0 (26.06)+3f9c2a1b").stdout)
        self.assertIn("warning: Desktop 2.152.882.0 is older", pbik("project", "check", "--project", pj,
                                                                    "--version", "2.152.882.0").stdout)
        pj.write_text(json.dumps({"targetDesktop": "2.155", "catalog": "work"}), encoding="utf-8")
        self.assertEqual(V.check(pj, "2.155.900.0"), 0, "a target of 2.155 matches every 2.155 build")
        self.assertEqual(V.check(pj, "2.156.1.0"), 5)
        pj.write_text(json.dumps({"targetDesktop": "latest", "catalog": "home"}), encoding="utf-8")
        self.assertEqual(V.check(pj, "2.199.1.0"), 0)
        self.assertEqual(V.check(self.tmp / "pin104c" / "missing.json", "2.199.1.0"), 0, "no project.json: latest")
        saved = V.detect_desktop
        V.detect_desktop = lambda: None
        try:
            self.assertEqual(V.check(pj), 0, "latest passes without a version")
            pj.write_text(json.dumps({"targetDesktop": "2.155.756.0"}), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(V.check(pj), 3)
        finally:
            V.detect_desktop = saved

    # ---------------------------------------------------------------- roundtrip
    def _desktop_rewrite(self, rep):
        """What Desktop did to the Patterns page on save (2026-10-19), applied to one card and one text box."""
        f = next(rep.glob("definition/pages/*/visuals/P1-V01_*/visual.json"))
        d = json.loads(f.read_text(encoding="utf-8"))
        d["$schema"] = d["$schema"].replace("2.13.0", "2.14.0")
        d["position"]["x"] = float(d["position"]["x"])                     # format: pbik side differs in form
        d["visual"]["drillFilterOtherVisuals"] = False                      # changed
        d["visual"]["newDesktopKey"] = True                                 # added
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")             # no final newline, as Desktop
        return f

    def test_35_roundtrip_from_git(self):
        work = self.tmp / "rt35"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "pbik build"]):
            subprocess.run(["git", "-C", str(work), *args], check=True, capture_output=True)
        f = self._desktop_rewrite(rep)
        saved = f.read_text(encoding="utf-8")
        out = work / "design" / "reviews" / "roundtrip.md"
        r = pbik("roundtrip", rep, "--out", out)
        self.assertIn("### P1-V01", r.stdout)
        self.assertIn("schema: visualContainer 2.13.0 -> visualContainer 2.14.0", r.stdout)
        self.assertIn("Desktop adds visual.newDesktopKey = true", r.stdout)
        self.assertIn("Desktop rewrites visual.drillFilterOtherVisuals: true -> false", r.stdout)
        self.assertIn("format: Desktop writes position.x as", r.stdout)
        self.assertIn("newline: Desktop drops the final newline (1 file(s))", r.stdout)
        self.assertTrue(out.exists())
        self.assertEqual(f.read_text(encoding="utf-8"), saved, "roundtrip changes nothing")
        st = subprocess.run(["git", "-C", str(work), "status", "--short"], capture_output=True, text=True).stdout
        lines = [x for x in st.splitlines() if x.strip()]
        self.assertEqual(len(lines), 2, st)                      # the rewritten visual and the new report
        self.assertTrue(any(f.parent.name in x for x in lines) and any("design/reviews/" in x for x in lines), st)

    def test_36_roundtrip_from_a_copy_and_no_changes(self):
        work = self.tmp / "rt36"
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        r = pbik("roundtrip", rep, "--before", self.report)
        self.assertIn("none: Desktop kept everything pbik wrote", r.stdout)
        self._desktop_rewrite(rep)
        r = pbik("roundtrip", rep, "--before", self.report)
        self.assertIn("P1-V01", r.stdout)
        bad = pbik("roundtrip", rep, ok=(2,))                    # not a git repository, no --before
        self.assertIn("--before", bad.stderr)

    # ---------------------------------------------------------------- item 5: Rep 8 build.py as layout keys
    NAV = {"fill": "card", "outline": "onDarkMuted", "radius": "control.radius", "font": "regular", "size": "body",
           "colors": {"default": "onDarkMuted", "hover": "onDark", "selected": "primary"},
           "transparency": {"default": 100, "hover": 85, "selected": 0}}

    def _item5(self, name, edit):
        work = self.tmp / name
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lf = work / "design" / "specs" / "layout.json"
        lay = json.loads(lf.read_text(encoding="utf-8"))
        edit(lay)
        lf.write_text(json.dumps(lay), encoding="utf-8")
        return work, rep, lf

    def test_37_navigator_states_key(self):
        """Rep 8's build.py navigator patch (pbik_helpers.navigator_states) as layout `navigator`."""
        tokens = json.loads((self.proj / "design" / "tokens.json").read_text(encoding="utf-8"))
        tokens.setdefault("control", {}).setdefault("radius", 18)
        tokens["colors"].setdefault("onDarkMuted", "#B9D9DC")
        tokens["colors"].setdefault("onDark", "#FFFFFF")

        def edit(lay):
            lay["visuals"].append({"id": "P1-V40", "name": "nav", "page": "P1", "type": "pageNavigator", "x": 32,
                                   "y": 900, "w": 600, "h": 40, "navigator": self.NAV})
        work, rep, lf = self._item5("nav37", edit)
        (work / "design" / "tokens.json").write_text(json.dumps(tokens), encoding="utf-8")
        pbik("build", rep, lf)
        o = visual(rep, "P1-V40")["visual"]["objects"]
        sel = {json.dumps(e.get("selector")): e["properties"] for e in o["fill"]}
        self.assertEqual(sel["null"], {"show": {"expr": {"Literal": {"Value": "true"}}}}, "show stays selector-less")
        self.assertEqual(sel['{"id": "hover"}']["transparency"]["expr"]["Literal"]["Value"], "85D")
        txt = {json.dumps(e.get("selector")): e["properties"] for e in o["text"]}
        self.assertIn("fontSize", txt['{"id": "default"}'])
        self.assertEqual(o["shape"][0]["properties"]["rectangleRoundedCurve"]["expr"]["Literal"]["Value"], "18L")
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        lay = json.loads(lf.read_text(encoding="utf-8"))           # dropping the key releases what it wrote
        next(v for v in lay["visuals"] if v["id"] == "P1-V40").pop("navigator")
        lf.write_text(json.dumps(lay), encoding="utf-8")
        pbik("build", rep, lf)
        self.assertNotIn("fill", visual(rep, "P1-V40")["visual"].get("objects", {}))

    def test_38_navigator_key_errors(self):
        def edit(lay):
            nav = {k: v for k, v in self.NAV.items()}
            nav["colors"] = {"default": "text"}
            lay["visuals"].append({"id": "P1-V41", "name": "nav", "page": "P1", "type": "pageNavigator", "x": 32,
                                   "y": 900, "w": 600, "h": 40, "navigator": nav})
            lay["visuals"].append({"id": "P1-V42", "name": "notnav", "page": "P1", "type": "textbox", "x": 700,
                                   "y": 900, "w": 200, "h": 40, "text": "x", "navigator": self.NAV})
        work, rep, lf = self._item5("nav38", edit)
        r = pbik("build", rep, lf, ok=(1,))
        self.assertIn("P1-V41: navigator colors and transparency need default, hover, selected", r.stdout)
        self.assertIn("P1-V42: navigator is for pageNavigator", r.stdout)

    def test_39_active_page_and_theme_keys(self):
        def edit(lay):
            lay["pages"]["P2"]["active"] = True
            lay["theme"] = "design/themes/pbip-polish.json"
        work, rep, lf = self._item5("act39", edit)
        r = pbik("build", rep, lf)
        meta = json.loads((rep / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
        vm = json.loads((work / "design" / "specs" / "visual-map.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["activePageName"], vm["pages"]["P2"]["name"])
        rj = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(rj["themeCollection"]["customTheme"]["name"], "pbip-polish.json")
        self.assertIn("No changes", pbik("build", rep, lf).stdout, "theme and active page are idempotent")
        lay = json.loads(lf.read_text(encoding="utf-8"))
        lay["pages"]["P1"]["active"] = True
        lf.write_text(json.dumps(lay), encoding="utf-8")
        self.assertIn("all marked active", pbik("build", rep, lf, ok=(2,)).stderr)
        lay["theme"] = "design/themes/missing.json"
        lay["pages"]["P1"].pop("active")
        lf.write_text(json.dumps(lay), encoding="utf-8")
        self.assertIn("gen_theme.py", pbik("build", rep, lf, ok=(2,)).stderr)

    # ---------------------------------------------------------------- item 6: accessibility
    def test_43_a11y_helpers(self):
        from pbikit import a11y
        self.assertAlmostEqual(a11y.contrast("#FFFFFF", "#000000"), 21.0, places=1)
        self.assertAlmostEqual(a11y.contrast("#FFFFFF", "#038D96"), 4.0, places=1)
        order = a11y.reading_order([("right", 500, 10, 100, 40), ("below", 0, 80, 100, 40), ("left", 0, 0, 100, 60)])
        self.assertEqual(order, ["left", "right", "below"])

    def test_44_a11y_validate_warnings(self):
        def edit(lay):
            lay["visuals"] += [
                {"id": "P1-V50", "name": "pale-small", "page": "P1", "type": "textbox", "x": 1700, "y": 1040, "w": 100,
                 "h": 30, "text": [{"runs": [{"text": "pale", "color": "#DDDDDD", "size": 8}]}], "textFit": False},
                {"id": "P1-V53", "name": "late-top-left", "page": "P1", "type": "textbox", "x": 0, "y": 0, "w": 20,
                 "h": 20, "text": "x", "textFit": False},
                {"id": "P1-V51", "name": "chart-alt", "page": "P1", "type": "lineChart", "x": 32, "y": 900, "w": 300,
                 "h": 150, "bindings": {"Category": ["Date[Year]"], "Y": ["[Revenue]"]},
                 "container": {"altText": "Revenue by year", "background": {"color": "#FFFFFF"}}},
                {"id": "P1-V52", "name": "chart-no-alt", "page": "P1", "type": "lineChart", "x": 360, "y": 900,
                 "w": 300, "h": 150, "bindings": {"Category": ["Date[Year]"], "Y": ["[Revenue]"]}}]
        work, rep, lf = self._item5("a11y44", edit)
        pbik("build", rep, lf)
        out = pbik("validate", rep, "--layout", lf, "--no-catalog").stdout
        lines = [x for x in out.splitlines() if "a11y" in x]
        self.assertTrue(any("P1-V52" in x and "no alt text" in x for x in lines), out)
        self.assertFalse(any("P1-V51" in x and "alt text" in x for x in lines), out)
        self.assertTrue(any("P1-V50" in x and "#DDDDDD" in x and "WCAG AA" in x for x in lines), out)
        self.assertTrue(any("P1-V50" in x and "8pt, below the 10pt minimum" in x for x in lines), out)
        self.assertTrue(any("tab order doesn't follow reading order" in x and "P1-V53" in x for x in lines), out)
        self.assertIn("0 error(s)", out, "accessibility findings are warnings")
        self.assertNotIn("a11y", pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y").stdout)

    def test_45_a11y_state_fill_pairs_with_state_text(self):
        """Selected-state text is checked against the selected-state fill, not the page (button slicers, buttons)."""
        from pbikit import a11y
        d = {"visual": {"visualType": "actionButton", "objects": {
            "fill": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}},
                     {"properties": {"fillColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#12343B'"}}}}},
                                     "transparency": {"expr": {"Literal": {"Value": "0D"}}}}, "selector": {"id": "default"}}],
            "text": [{"properties": {"fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}}},
                      "selector": {"id": "default"}}]}}}
        self.assertEqual(a11y.state_fills(d), {'{"id": "default"}': "#12343B"})
        self.assertEqual([t[1] for t in a11y.texts(d)], ["#FFFFFF"])

    # ---------------------------------------------------------------- item 7: table auto-fit
    def test_46_tablefit_math(self):
        from pbikit import tablefit as TF
        cols = [("a", "Department", "text", None), ("b", "Headcount", "number", None), ("c", "Hires", "number", None),
                ("d", "Fixed", "number", 100)]
        w = TF.widths(cols, 916, 20, 20, 10, 16)
        self.assertEqual(sum(w.values()), 916 - 40 - 16)
        self.assertEqual(w["d"], 100)
        self.assertLessEqual(abs(w["b"] - w["c"]), 2, "numbers share one width (the last column takes the rounding)")
        self.assertGreater(w["a"], w["b"], "text columns get the larger share")
        with self.assertRaises(TF.FitError):
            TF.widths([(k, k, "text", None) for k in "xyz"], 200, 0, 0)

    def test_47_columnwidths_fit_in_build(self):
        def edit(lay):
            lay["visuals"].append({"id": "P1-V60", "name": "fit-table", "page": "P1", "type": "tableEx", "x": 32,
                                   "y": 700, "w": 600, "h": 300, "container": {"padding": 20},
                                   "bindings": {"Values": ["Date[Year]", "[Revenue]", {"field": "[Units Sold]", "displayName": "Units"}]},
                                   "columnWidths": "fit"})
            lay["visuals"].append({"id": "P1-V61", "name": "mixed-table", "page": "P1", "type": "tableEx", "x": 700,
                                   "y": 700, "w": 600, "h": 300,
                                   "bindings": {"Values": ["Date[Year]", "[Revenue]"]},
                                   "columnWidths": {"Date[Year]": 200, "[Revenue]": "fit"}})
        work, rep, lf = self._item5("fit47", edit)
        pbik("build", rep, lf)
        ws = {e["selector"]["metadata"]: e["properties"]["value"]["expr"]["Literal"]["Value"]
              for e in visual(rep, "P1-V60")["visual"]["objects"]["columnWidth"]}
        self.assertEqual(len(ws), 3)
        self.assertEqual(sum(float(x.rstrip("D")) for x in ws.values()), 600 - 40 - 16)
        ws2 = {e["selector"]["metadata"]: float(e["properties"]["value"]["expr"]["Literal"]["Value"].rstrip("D"))
               for e in visual(rep, "P1-V61")["visual"]["objects"]["columnWidth"]}
        self.assertEqual(ws2["Date.Year"], 200)
        self.assertEqual(ws2["_Measures.Revenue"], 600 - 16 - 200)
        self.assertIn("No changes", pbik("build", rep, lf).stdout)

    def test_48_columnwidths_fit_errors(self):
        def edit(lay):
            lay["visuals"].append({"id": "P1-V62", "name": "mx", "page": "P1", "type": "pivotTable", "x": 32, "y": 700,
                                   "w": 600, "h": 300, "bindings": {"Rows": ["Date[Year]"], "Columns": ["Date[Year]"],
                                                                     "Values": ["[Revenue]"]}, "columnWidths": "fit"})
            lay["visuals"].append({"id": "P1-V63", "name": "tiny", "page": "P1", "type": "tableEx", "x": 700, "y": 700,
                                   "w": 120, "h": 300, "bindings": {"Values": ["Date[Year]", "[Revenue]"]},
                                   "columnWidths": "fit"})
            lay["visuals"].append({"id": "P1-V64", "name": "unbound", "page": "P1", "type": "tableEx", "x": 900,
                                   "y": 700, "w": 400, "h": 300, "bindings": {"Values": ["[Revenue]"]},
                                   "columnWidths": {"[Units Sold]": "fit"}})
        work, rep, lf = self._item5("fit48", edit)
        r = pbik("build", rep, lf, ok=(1,))
        self.assertIn("P1-V62: columnWidths fit can't size a matrix with fields on Columns", r.stdout)
        self.assertIn("P1-V63: columnWidths fit needs", r.stdout)
        self.assertIn("P1-V64: columnWidths names fields that aren't bound", r.stdout)

    def test_53_visual_measure_filters(self):
        """A visual filter on a measure (field, op, value) is an Advanced filter with one Comparison; on a page it
        stops the build."""
        def edit(lay):
            lay["visuals"].append({"id": "P1-V65", "name": "mf", "page": "P1", "type": "tableEx", "x": 32, "y": 700,
                                   "w": 600, "h": 300, "bindings": {"Values": ["Date[Year]", "[Revenue]"]},
                                   "filters": [{"field": "[Revenue]", "op": ">", "value": 0},
                                               {"field": "[Units Sold]", "op": "<=", "value": 1.5}]})
        work, rep, lf = self._item5("mf53", edit)
        pbik("build", rep, lf)
        fs = visual(rep, "P1-V65")["filterConfig"]["filters"]
        self.assertEqual([f["type"] for f in fs], ["Advanced", "Advanced"])
        cmps = [f["filter"]["Where"][0]["Condition"]["Comparison"] for f in fs]
        self.assertEqual([c["ComparisonKind"] for c in cmps], [1, 4])
        self.assertEqual([c["Right"]["Literal"]["Value"] for c in cmps], ["0D", "1.5D"])
        self.assertEqual(cmps[0]["Left"]["Measure"]["Property"], "Revenue")
        self.assertEqual(fs[0]["field"]["Measure"]["Property"], "Revenue")
        self.assertIn("No changes", pbik("build", rep, lf).stdout)

        def bad(lay):
            lay["pages"]["P1"]["filters"] = [{"field": "[Revenue]", "op": ">", "value": 0}]
            lay["visuals"].append({"id": "P1-V66", "name": "mf-noop", "page": "P1", "type": "tableEx", "x": 32,
                                   "y": 700, "w": 600, "h": 300, "bindings": {"Values": ["Date[Year]"]},
                                   "filters": [{"field": "[Revenue]", "value": 0}]})
        work, rep, lf = self._item5("mf53b", bad)
        r = pbik("build", rep, lf, ok=(1,))
        self.assertIn("[Revenue] is a measure: Power BI filters on a measure only at visual level", r.stdout)
        self.assertIn("measure filter [Revenue] needs `op`", r.stdout)

    def test_54_html_content_legacy_rendering_and_height(self):
        """Any htmlContent<GUID> type gets compatibility.legacyRendering true; under 43px build and validate warn."""
        hc = "htmlContent443BE3AD55E043BF878BED274D3A6855"

        def edit(lay):
            lay["visuals"].append({"id": "P1-V67", "name": "html", "page": "P1", "type": hc, "x": 32, "y": 700,
                                   "w": 600, "h": 40, "bindings": {"content": ["[Revenue]"]},
                                   "build": {"method": "custom-visual", "step": 4}})
        work, rep, lf = self._item5("hc54", edit)
        r = pbik("build", rep, lf)
        self.assertIn("P1-V67: HTML Content visual is 40px tall, under 43px", r.stdout)
        comp = visual(rep, "P1-V67")["visual"]["objects"]["compatibility"][0]["properties"]
        self.assertEqual(comp["legacyRendering"]["expr"]["Literal"]["Value"], "true")
        rj = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        self.assertIn(hc, rj["publicCustomVisuals"])
        v = pbik("validate", rep, ok=(0, 1))
        self.assertIn("HTML Content visual is 40px tall", v.stdout)
        from pbikit import htmlcontent as HC
        self.assertTrue(HC.is_html_content(hc))
        self.assertFalse(HC.is_html_content("htmlContent"))
        self.assertIsNone(HC.height_issue(43))

    def test_55_lessons_promoted_to_checks(self):
        """Lessons S-01, S-03 and CH-02 as validate warnings (pbikit/validate.py lesson_checks)."""
        from pbikit.validate import lesson_checks
        L = lambda v: {"expr": {"Literal": {"Value": v}}}      # noqa: E731
        btn = {"visual": {"visualType": "advancedSlicerVisual", "objects": {}}}
        self.assertIn("lesson S-01", lesson_checks(btn, 36)[0])
        btn["visual"]["objects"]["padding"] = [{"properties": {"paddingSelection": L("'Custom'"), "topMargin": L("0L"),
                                                               "bottomMargin": L("0L")}, "selector": {"id": "default"}}]
        self.assertEqual(lesson_checks(btn, 36), [])
        self.assertEqual(lesson_checks({"visual": {"visualType": "advancedSlicerVisual"}}, 52), [])
        dd = {"visual": {"visualType": "slicer", "objects": {"data": [{"properties": {"mode": L("'Dropdown'")}}]}}}
        self.assertIn("lesson S-03", lesson_checks(dd, 60)[0])
        self.assertEqual(lesson_checks(dd, 76), [])
        dd["visual"]["objects"]["header"] = [{"properties": {"show": L("false")}}]
        self.assertEqual(lesson_checks(dd, 60), [], "no header: fine")
        ch = {"visual": {"visualType": "lineChart", "query": {"queryState": {"Y": {"projections": [{}, {}]}}},
                         "objects": {"dataPoint": [{"properties": {"fill": {}}}]}}}
        self.assertIn("lesson CH-02", lesson_checks(ch, 300)[0])
        ch["visual"]["objects"]["dataPoint"][0]["selector"] = {"metadata": "_Measures.Revenue"}
        self.assertEqual(lesson_checks(ch, 300), [])

    # ---------------------------------------------------------------- model check
    def test_40_model_check(self):
        r = pbik("model", "check", self.model, ok=(1,))
        self.assertIn("no description", r.stdout)
        r = pbik("model", "check", self.model, "--folder", "Model", ok=(0, 1))
        self.assertIn("measures in display folder 'Model' only", r.stdout)
        work = self.tmp / "model"
        shutil.copytree(self.model, work / "M.SemanticModel")
        defn = work / "M.SemanticModel" / "definition"
        rel = defn / "relationships.tmdl"
        rel.write_text(rel.read_text(encoding="utf-8") + "\nrelationship broken\n\tfromColumn: sales.NoColumn\n"
                       "\ttoColumn: Nowhere.Key\n", encoding="utf-8")
        mt = defn / "tables" / "_Measures.tmdl"
        mt.write_text(mt.read_text(encoding="utf-8") + "\n\t/// Test.\n\tmeasure 'Bad ref' = [Missing Measure] + "
                      "sales[NoCol]\n\t\tformatString: 0\n", encoding="utf-8")
        out = pbik("model", "check", work / "M.SemanticModel", ok=(1,)).stdout
        for needle in ("reference [Missing Measure]", "'sales'[NoCol]", "from column sales[NoColumn]",
                       "to table 'Nowhere'"):
            self.assertIn(needle, out, out)

    def test_42_format_rule_skips_text_and_image_measures(self):
        """Text (dataType string) and ImageUrl measures need no format string; every measure needs a description."""
        defn = self.tmp / "fmt" / "F.SemanticModel" / "definition" / "tables"
        defn.mkdir(parents=True)
        (defn / "_Measures.tmdl").write_text(
            "table _Measures\n\n"
            "\t/// A number.\n\tmeasure 'Has format' = 1\n\t\tformatString: 0\n\n"
            "\t/// A number without a format.\n\tmeasure 'No format' = 1\n\n"
            "\t/// A label.\n\tmeasure 'Text label' = \"x\"\n\t\tdataType: string\n\n"
            "\t/// An SVG image.\n\tmeasure 'Svg image' = \"data:image/svg+xml;utf8,<svg/>\"\n\t\tdataCategory: ImageUrl\n\n"
            "\tmeasure 'Text no description' = \"y\"\n\t\tdataType: string\n\n"
            "\tcolumn Placeholder\n\t\tdataType: string\n", encoding="utf-8")
        out = pbik("model", "check", self.tmp / "fmt" / "F.SemanticModel", ok=(1,)).stdout
        fmt = [ln for ln in out.splitlines() if "no format string" in ln]
        self.assertEqual(len(fmt), 1, out)
        self.assertIn("[No format]", fmt[0])
        desc = [ln for ln in out.splitlines() if "no description" in ln]
        self.assertEqual(len(desc), 1, out)
        self.assertIn("[Text no description]", desc[0])
        self.assertIn("2 error(s)", out)

    def test_44_daxlib_svg_pct23_colour_and_unsafe_names(self):
        """v0.4.1 Desktop check: %23 passed to DaxLib.SVG drew nothing; visuals named with ',', ' ', '#' were skipped."""
        rep, lay, L = self.work("daxlib-names")
        pbik("measure", "ext", "add", rep, "x Line ok", "--expression",
             'DaxLib.SVG.Viz.Line ( stores[City], [Revenue], "#1F5FBF" )', "--data-category", "ImageUrl")
        self.assertNotIn("DaxLib.SVG", pbik("validate", rep, ok=(0, 1)).stdout)
        pbik("measure", "ext", "add", rep, "x Line pct", "--expression",
             'DaxLib.SVG.Viz.Line ( stores[City], [Revenue], "%231F5FBF" )', "--data-category", "ImageUrl")
        self.assertIn("passes a %23 colour to DaxLib.SVG", pbik("validate", rep, ok=(1,)).stdout)
        L["visuals"][0]["name"] = "card-line, raw #"
        lay.write_text(json.dumps(L), encoding="utf-8")
        self.assertIn("must be letters, digits, - or _", pbik("build", rep, lay, ok=(2,)).stderr)

    def test_43_functions_counted_and_unknown_package_calls(self):
        """DAX Lib (v0.4.1): functions.tmdl as Desktop saved DaxLib.SVG 2.0.0; a call to a missing package function."""
        defn = self.tmp / "udf" / "U.SemanticModel" / "definition"
        (defn / "tables").mkdir(parents=True)
        (defn / "functions.tmdl").write_text(
            "/// Wraps content in SVG container\nfunction 'DaxLib.SVG.SVG' =\n\t\t(\n\t\t\twidth : STRING,\n"
            "\t\t\theight : STRING\n\t\t) =>\n\t\t\t\"data:image/svg+xml;utf8,<svg/>\"\n\n", encoding="utf-8")
        (defn / "tables" / "_Measures.tmdl").write_text(
            "table _Measures\n\n"
            "\t/// Uses the package.\n\tmeasure 'Ok' = DaxLib.SVG.SVG ( \"10\", \"10\" )\n\t\tdataCategory: ImageUrl\n\n"
            "\t/// A typo.\n\tmeasure 'Typo' = DaxLib.SVG.Svg2 ( \"10\", \"10\" )\n\t\tdataCategory: ImageUrl\n\n"
            "\t/// A built-in with a dot.\n\tmeasure 'Builtin' = NORM.DIST ( 1, 0, 1, TRUE )\n\t\tformatString: 0.00\n\n"
            "\t/// Text that looks like a call.\n\tmeasure 'Literal' = \"DaxLib.SVG.Nope ( x )\"\n\t\tdataType: string\n",
            encoding="utf-8")
        out = pbik("model", "check", self.tmp / "udf" / "U.SemanticModel", ok=(1,)).stdout
        self.assertIn("1 functions", out)
        self.assertIn("[Typo]: function DaxLib.SVG.Svg2 isn't in the model", out)
        self.assertIn("1 error(s)", out, out)

    def test_49_text_measures_inferred_from_dax(self):
        """Item 8: text measures need no `formatString: @`; the type comes from the DAX (pbikit/daxtype.py)."""
        from pbikit import daxtype as DT
        txt = lambda e, mt=lambda n: False: DT.is_text_expression(e, mt)   # noqa: E731
        self.assertTrue(txt('"LY " & FORMAT ( [Headcount LY], "#,0" )'))
        self.assertTrue(txt('IF ( ISBLANK ( [X] ), "LY –", "LY " & FORMAT ( [X], "#,0" ) )'))
        self.assertTrue(txt('VAR d = [A] - [B] RETURN IF ( d > 0, "#026E75", "#A84545" )'))
        self.assertTrue(txt('SWITCH ( TRUE (), [A] > 0, "up", [A] < 0, "down", BLANK () )'))
        self.assertTrue(txt('VAR n = [C] RETURN "Filters" & IF ( n > 0, " (" & n & ")" )'))
        self.assertTrue(txt("[Label]", lambda n: n == "Label"))
        self.assertTrue(txt("'_Measures'[Label]", lambda n: n == "Label"))
        self.assertTrue(txt('UNICHAR ( 9650 ) -- arrow'))
        self.assertTrue(txt('/* a "comment" */ "x"'))
        self.assertFalse(txt('DIVIDE ( [A], [B] )'))
        self.assertFalse(txt('VAR s = "ignored" RETURN COUNTROWS ( T )'))
        self.assertFalse(txt('CALCULATE ( SUM ( T[Amount] ), T[Kind] = "x" )'))
        self.assertFalse(txt('IF ( [A] = "x", 1, 0 )'))
        defn = self.tmp / "fmt49" / "F.SemanticModel" / "definition" / "tables"
        defn.mkdir(parents=True)
        (defn / "_Measures.tmdl").write_text(
            "table _Measures\n\n"
            "\t/// Concatenation.\n\tmeasure 'LY Text' = \"LY \" & FORMAT ( [Amount], \"#,0\" )\n\n"
            "\t/// Hex colour.\n\tmeasure 'Delta Colour' = VAR d = [Amount] RETURN IF ( d > 0, \"#026E75\", \"#A84545\" )\n\n"
            "\t/// Refers to a text measure.\n\tmeasure 'Label Copy' = [LY Text]\n\n"
            "\t/// Selected text column.\n\tmeasure 'Picked' = SELECTEDVALUE ( T[Name] )\n\n"
            "\t/// A number without a format.\n\tmeasure Amount = SUM ( T[Value] )\n\n", encoding="utf-8")
        (defn / "T.tmdl").write_text("table T\n\n\tcolumn Name\n\t\tdataType: string\n\n\tcolumn Value\n\t\tdataType: int64\n",
                                     encoding="utf-8")
        out = pbik("model", "check", self.tmp / "fmt49" / "F.SemanticModel", ok=(1,)).stdout
        fmt = [ln for ln in out.splitlines() if "no format string" in ln]
        self.assertEqual(len(fmt), 1, out)
        self.assertIn("[Amount]", fmt[0])

    def test_41_dax_references(self):
        m = tmdl.load(self.model)
        self.assertEqual(tmdl.check_references(m, "VAR x = [Revenue] RETURN CALCULATE ( x, 'Date'[Year] = \"2023\" )"), [])
        self.assertEqual(tmdl.check_references(m, "SUMX ( sales, sales[Units] ) // [not a ref]"), [])
        self.assertEqual(tmdl.check_references(m, "[Nope]"), ["[Nope]"])

    # ---------------------------------------------------------------- optional parts
    def test_50_validate_without_jsonschema(self):
        code = ("import sys; sys.modules['jsonschema'] = None; sys.path.insert(0, r'%s'); "
                "from pbikit.cli import main; sys.exit(main(['validate', r'%s']))" % (PBIK.parent, self.report))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("schema checks skipped", r.stdout)

    def test_51_desktop_bridge_missing(self):
        r = pbik("desktop", "--bridge", self.tmp / "no-such-bridge.ps1", "state", ok=(3,))
        self.assertIn("Desktop bridge not available", r.stdout)

    def test_52_cmd_wrapper(self):
        if os.name != "nt":
            self.skipTest("Windows only")
        r = subprocess.run(["cmd", "/c", str(PBIK.with_suffix(".cmd")), "--version"], capture_output=True, text=True)
        from pbikit import __version__
        self.assertIn(f"pbik {__version__}", r.stdout)

    # ---------------------------------------------------------------- roadmap batch 1 (gaps 1, 20, 24; schema props)
    def _batch1(self, name, edit=None):
        work = self.tmp / name
        shutil.copytree(self.proj, work)
        rep = work / self.report.name
        lf = work / "design" / "specs" / "layout.json"
        if edit:
            lay = json.loads(lf.read_text(encoding="utf-8"))
            edit(lay)
            lf.write_text(json.dumps(lay, indent=2), encoding="utf-8")
        return work, rep, lf

    def _relayout(self, lf, edit):
        lay = json.loads(lf.read_text(encoding="utf-8"))
        edit(lay)
        lf.write_text(json.dumps(lay, indent=2), encoding="utf-8")

    def test_110_report_settings_and_filter_pane(self):
        """Gap 1: layout `report` writes report.json in place; dropping a key restores what Desktop had."""
        def edit(lay):
            lay["report"] = {"filterPane": {"expanded": False, "visible": True},
                             "settings": {"exportDataMode": "None", "hideVisualContainerHeader": True}}
        work, rep, lf = self._batch1("b110", edit)
        before = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        r = pbik("build", rep, lf)
        self.assertIn("report.json changed", r.stdout)
        d = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        pane = next(e for e in d["objects"]["outspacePane"] if not e.get("selector"))["properties"]
        self.assertEqual(pane["expanded"], {"expr": {"Literal": {"Value": "false"}}})
        self.assertEqual(pane["visible"], {"expr": {"Literal": {"Value": "true"}}})
        self.assertEqual(d["settings"]["exportDataMode"], "None")
        self.assertIs(d["settings"]["hideVisualContainerHeader"], True)
        for k in ("themeCollection", "resourcePackages"):          # the rest of report.json stays as it was
            self.assertEqual(d[k], before[k])
        self.assertEqual(d["objects"].get("section"), before.get("objects", {}).get("section"))
        m = json.loads((work / "design" / "specs" / "visual-map.json").read_text(encoding="utf-8"))
        self.assertEqual(m["reportOwned"]["settings"]["exportDataMode"], {"was": before["settings"]["exportDataMode"]})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: lay.pop("report"))
        pbik("build", rep, lf)
        d = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(d["settings"], before["settings"])        # Desktop's value back, pbik's own key gone
        self.assertEqual(d.get("objects"), before.get("objects"))
        self.assertNotIn("reportOwned", json.loads((work / "design" / "specs" / "visual-map.json").read_text(encoding="utf-8")))
        self.assertIn("No changes", pbik("build", rep, lf).stdout)

    def test_111_report_key_errors(self):
        work, rep, lf = self._batch1("b111", lambda lay: lay.update(report={"filterPane": {"width": 300}}))
        r = pbik("build", rep, lf, ok=(1,))
        self.assertIn("only expanded and visible are report-level", r.stdout)
        self._relayout(lf, lambda lay: lay.update(report={"filterPane": {"expanded": "no"}}))
        self.assertIn("must be true or false", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_112_page_filter_pane_and_cards(self):
        def edit(lay):
            lay["pages"]["P1"]["filterPane"] = {"backgroundColor": "#FFFFFF", "width": 280, "border": True,
                                                "fontFamily": "regular", "titleSize": "body"}
            lay["pages"]["P1"]["filterCards"] = {"applied": {"backgroundColor": "#F2F2F2", "border": False},
                                                 "available": {"foregroundColor": "#222222"}}
        work, rep, lf = self._batch1("b112", edit)
        pbik("build", rep, lf)
        pg = next(json.loads(f.read_text(encoding="utf-8")) for f in rep.glob("definition/pages/*/page.json")
                  if json.loads(f.read_text(encoding="utf-8"))["displayName"] == "pbik sales")
        op = pg["objects"]["outspacePane"]
        self.assertEqual(len(op), 1)
        self.assertNotIn("selector", op[0])
        self.assertEqual(op[0]["properties"]["width"], {"expr": {"Literal": {"Value": "280D"}}})
        self.assertTrue(op[0]["properties"]["fontFamily"]["expr"]["Literal"]["Value"].startswith("'"))
        self.assertEqual(op[0]["properties"]["titleSize"]["expr"]["Literal"]["Value"][-1], "D")
        cards = {e["selector"]["id"]: e["properties"] for e in pg["objects"]["filterCard"]}
        self.assertEqual(set(cards), {"Applied", "Available"})
        self.assertEqual(cards["Applied"]["border"], {"expr": {"Literal": {"Value": "false"}}})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: (lay["pages"]["P1"].pop("filterPane"), lay["pages"]["P1"].pop("filterCards")))
        pbik("build", rep, lf)
        pg = next(json.loads(f.read_text(encoding="utf-8")) for f in rep.glob("definition/pages/*/page.json")
                  if json.loads(f.read_text(encoding="utf-8"))["displayName"] == "pbik sales")
        self.assertNotIn("outspacePane", pg.get("objects", {}))
        self.assertNotIn("filterCard", pg.get("objects", {}))
        self.assertIn("background", pg["objects"])
        self._relayout(lf, lambda lay: lay["pages"]["P1"].update(filterCards={"pinned": {"border": True}}))
        self.assertIn("must be applied or available", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_113_reset_keeps_desktop_filters(self):
        """Gap 24: an automatic filter Desktop saved (after the pane was opened) survives --reset."""
        work, rep, lf = self._batch1("b113")
        f = next(rep.glob("definition/pages/*/visuals/P1-V04_*/visual.json"))
        d = json.loads(f.read_text(encoding="utf-8"))
        auto = {"name": "a1b2c3d4e5f6a7b8c9d0", "field": {"Column": {"Expression": {"SourceRef": {"Entity": "stores"}},
                                                                   "Property": "City"}},
                "type": "Categorical", "howCreated": "Auto"}
        d.setdefault("filterConfig", {}).setdefault("filters", []).append(auto)
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        pbik("build", rep, lf, "--reset")
        names = [x["name"] for x in visual(rep, "P1-V04")["filterConfig"]["filters"]]
        self.assertIn(auto["name"], names)
        self.assertTrue(any(n_.startswith("pbik_") for n_ in names))        # pbik's Top N filter is still there
        self.assertEqual(len(names), len(set(names)))

    def _stand_in_schemas(self, root):
        """Small hand-written schemas shaped like Microsoft's (closed container title, report pane and settings; open
        visual objects; page displayOption with two values marked Deprecated). Not copies of Microsoft's files."""
        base = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
        cache = root / "fabric" / "item" / "report" / "definition"
        entry = lambda ref: {"type": "array", "items": {"type": "object", "properties": {  # noqa: E731
            "selector": {}, "properties": {"$ref": ref}}}}
        files = {
            "visualContainer/2.13.0/schema.json": {"type": "object", "properties": {
                "visual": {"$ref": base + "visualConfiguration/2.8.0/schema-embedded.json"},
                "annotations": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                           "properties": {"name": {}, "value": {}}}}}},
            "visualConfiguration/2.8.0/schema-embedded.json": {"type": "object", "properties": {
                "objects": {"type": "object", "additionalProperties": {"type": "array"}},
                "visualContainerObjects": {"type": "object", "properties": {"title": entry("#/definitions/Title")}}},
                "definitions": {"Title": {"type": "object", "additionalProperties": False, "properties": {
                    k: {} for k in ("show", "text", "heading", "titleWrap", "fontColor", "background", "alignment",
                                    "fontSize", "bold", "italic", "underline", "fontFamily")}}}},
            "page/2.1.0/schema.json": {"type": "object", "properties": {
                "displayOption": {"type": "string", "anyOf": [
                    {"const": "DeprecatedDynamic", "description": "Deprecated: Use other display options."},
                    {"const": "FitToPage"}, {"const": "FitToWidth"}, {"const": "ActualSize"},
                    {"const": "ActualSizeTopLeft", "description": "Deprecated: Use ActualSize instead."}]},
                "objects": {"type": "object", "properties": {"outspacePane": entry("#/definitions/Pane"),
                                                             "filterCard": entry("#/definitions/Card")}}},
                "definitions": {"Pane": {"type": "object", "additionalProperties": False, "properties": {
                    k: {} for k in ("backgroundColor", "transparency", "foregroundColor", "titleSize", "searchTextSize",
                                    "headerSize", "fontFamily", "border", "borderColor", "checkboxAndApplyColor",
                                    "inputBoxColor", "width")}},
                    "Card": {"type": "object", "additionalProperties": False, "properties": {
                        k: {} for k in ("backgroundColor", "transparency", "border", "borderColor", "foregroundColor",
                                        "textSize", "fontFamily", "inputBoxColor")}}}},
            "report/3.3.0/schema.json": {"type": "object", "properties": {
                "objects": {"type": "object", "additionalProperties": False, "properties": {
                    "outspacePane": entry("#/definitions/Pane"), "section": entry("#/definitions/Section")}},
                "settings": {"type": "object", "additionalProperties": False, "properties": {
                    "exportDataMode": {"type": "string", "anyOf": [{"const": "AllowSummarized"},
                                                                   {"const": "AllowSummarizedAndUnderlying"},
                                                                   {"const": "None"}]},
                    **{k: {"type": "boolean"} for k in (
                        "useStylableVisualContainerHeader", "defaultDrillFilterOtherVisuals", "allowChangeFilterTypes",
                        "useEnhancedTooltips", "useDefaultAggregateDisplayName", "hideVisualContainerHeader")}}}},
                "definitions": {"Pane": {"type": "object", "additionalProperties": False,
                                         "properties": {"expanded": {}, "visible": {}}},
                                "Section": {"type": "object", "additionalProperties": False,
                                            "properties": {"verticalAlignment": {}}}}},
        }
        for rel, doc in files.items():
            p = cache / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(doc), encoding="utf-8")
        return root

    def _pbik_env(self, cache, *args, ok=(0,)):
        env = dict(os.environ, PBIK_SCHEMA_CACHE=str(cache))
        r = subprocess.run([sys.executable, str(PBIK), *map(str, args)], capture_output=True, text=True,
                           encoding="utf-8", env=env)
        if r.returncode not in ok:
            raise AssertionError(f"pbik {' '.join(map(str, args))} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
        return r

    def test_114_schema_props_warn_and_strict(self):
        """Item b: a property outside Microsoft's schema warns; --strict fails (build writes nothing)."""
        cache = self._stand_in_schemas(self.tmp / "b114-schemas")

        def edit(lay):
            v = next(x for x in lay["visuals"] if x["id"] == "P1-V04")
            v.setdefault("props", {})["container:title.notAProp"] = True
            v["props"]["dataPoint.anythingGoes"] = True               # visual objects: open for every type
            lay["report"] = {"settings": {"exportDataMode": "Everything"}}
        work, rep, lf = self._batch1("b114", edit)
        before = tree_hash(rep)
        r = self._pbik_env(cache, "build", rep, lf, "--strict", ok=(1,))
        self.assertIn("container:title.notAProp is not in Microsoft's visualConfiguration 2.8.0 schema (--strict)", r.stdout)
        self.assertIn("exportDataMode = 'Everything' is not one of the schema's values", r.stdout)
        self.assertNotIn("anythingGoes", r.stdout)
        self.assertEqual(tree_hash(rep), before, "a strict failure writes nothing")
        r = self._pbik_env(cache, "build", rep, lf)
        self.assertIn("warning: P1-V04: container:title.notAProp is not in Microsoft's", r.stdout)
        self.assertIn("warning: report: report setting exportDataMode = 'Everything'", r.stdout)
        v = self._pbik_env(cache, "validate", rep, "--layout", lf, "--no-catalog", "--no-a11y", ok=(0, 1))
        self.assertIn("warning P1-V04: container:title.notAProp", v.stdout)
        v = self._pbik_env(cache, "validate", rep, "--layout", lf, "--no-catalog", "--no-a11y", "--strict", ok=(1,))
        self.assertIn("error   P1-V04: container:title.notAProp", v.stdout)
        self.assertIn("error   report.json: report setting exportDataMode", v.stdout)

    def test_114b_settings_in_schema_order(self):
        """Desktop writes report settings in the schema's property order (pbik-smoke-013 save, 2026-11-10)."""
        cache = self._stand_in_schemas(self.tmp / "b114b-schemas")
        work, rep, lf = self._batch1("b114b", lambda lay: lay.update(report={"settings": {
            "hideVisualContainerHeader": True, "exportDataMode": "None"}}))
        self._pbik_env(cache, "build", rep, lf)
        keys = list(json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))["settings"])
        self.assertLess(keys.index("useStylableVisualContainerHeader"), keys.index("useEnhancedTooltips"))
        self.assertEqual(keys[-1], "hideVisualContainerHeader")     # last in the stand-in schema's order
        self.assertIn("No changes", self._pbik_env(cache, "build", rep, lf).stdout)
        from pbikit import fields as F
        self.assertTrue(F.is_automatic({"name": "x", "field": {}, "type": "Categorical"}))
        self.assertTrue(F.is_automatic({"name": "x", "field": {}, "type": "Categorical", "howCreated": "Auto"}))
        self.assertFalse(F.is_automatic({"name": "x", "field": {}, "type": "Categorical", "filter": {}}))
        self.assertFalse(F.is_automatic({"name": "x", "field": {}, "type": "Categorical", "howCreated": "User"}))

    def test_115_schema_walker(self):
        from pbikit import schemaprops as SP, schemas as S
        cache = self._stand_in_schemas(self.tmp / "b115-schemas")
        base = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
        old = S.CACHE
        S.CACHE, SP._W = cache, SP.Walker()
        try:
            vc, pg, rp = (base + "visualContainer/2.13.0/schema.json", base + "page/2.1.0/schema.json",
                          base + "report/3.3.0/schema.json")
            self.assertEqual(SP.visual_prop(vc, "visualContainerObjects", "title", "fontSize")[0], SP.OK)
            self.assertEqual(SP.visual_prop(vc, "visualContainerObjects", "title", "nope")[0], SP.UNKNOWN)
            self.assertEqual(SP.visual_prop(vc, "objects", "dataPoint", "fill")[0], SP.OPEN)
            self.assertEqual(SP.page_prop(pg, "filterCard", "textSize")[0], SP.OK)
            self.assertEqual(SP.page_prop(pg, "filterCard", "width")[0], SP.UNKNOWN)
            self.assertEqual(SP.report_prop(rp, "outspacePane", "expanded")[0], SP.OK)
            self.assertEqual(SP.report_setting(rp, "exportDataMode", "None")[0], SP.OK)
            self.assertEqual(SP.report_setting(rp, "made up", True)[0], SP.UNKNOWN)
            self.assertEqual(SP.deprecated(pg, ["displayOption"]), {"DeprecatedDynamic", "ActualSizeTopLeft"})
            self.assertEqual(SP.visual_prop(base + "notCachedKind/1.0.0/schema.json", "objects", "a", "b")[0],
                             SP.UNCACHED)
            self.assertIsNone(SP.deprecated(base + "page/9.9.9/schema.json", ["displayOption"]))
            vc14 = base + "visualContainer/2.14.0/schema.json"     # Desktop writes it; Microsoft hasn't published it
            st, msg = SP.visual_prop(vc14, "visualContainerObjects", "title", "nope")
            self.assertEqual(st, SP.NEAREST)
            self.assertIn("checked against visualContainer 2.13.0", msg)
            self.assertEqual(SP.visual_prop(vc14, "visualContainerObjects", "title", "text")[0], SP.OK)
        finally:
            S.CACHE, SP._W = old, SP.Walker()

    def test_116_retiring_visuals_and_deprecated_display_option(self):
        """Gap 20: Q&A and Bing Maps visuals, a Q&A button and deprecated page displayOption values warn."""
        work, rep, lf = self._batch1("b116", lambda lay: lay["pages"]["P2"].update(displayOption="ActualSizeTopLeft"))
        r = pbik("build", rep, lf)
        self.assertIn("displayOption ActualSizeTopLeft is deprecated in Microsoft's page schema: use ActualSize", r.stdout)
        for vid, vt in (("P1-V04", "map"), ("P1-V05", "filledMap"), ("P2-V03", "qnaVisual")):
            f = next(rep.glob(f"definition/pages/*/visuals/{vid}_*/visual.json"))
            d = json.loads(f.read_text(encoding="utf-8"))
            d["visual"]["visualType"] = vt
            f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        f = next(rep.glob("definition/pages/*/visuals/P1-V06_*/visual.json"))
        d = json.loads(f.read_text(encoding="utf-8"))
        d["visual"].setdefault("visualContainerObjects", {})["visualLink"] = [
            {"properties": {"show": {"expr": {"Literal": {"Value": "true"}}},
                            "type": {"expr": {"Literal": {"Value": "'Q&A'"}}}}}]
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        v = pbik("validate", rep, "--no-catalog", "--no-a11y", ok=(0, 1)).stdout
        self.assertIn("the Map visual (Bing Maps) is retiring", v)
        self.assertIn("the Filled map visual (Bing Maps) is retiring", v)
        self.assertIn("the Q&A visual is retiring: Q&A goes away in February 2027", v)
        self.assertIn("button action Q&A is retiring", v)
        self.assertIn("displayOption ActualSizeTopLeft is deprecated", v)
        from pbikit import deprecations as DEP
        self.assertIsNone(DEP.visual_issue("azureMap"))
        self.assertIsNone(DEP.visual_issue("qnaVisual", in_build=True))      # validate only (type id unconfirmed)
        self.assertIn("retiring", DEP.visual_issue("filledMap", in_build=True))
        self.assertIsNone(DEP.display_issue("ActualSize", None))
        self.assertIn("FitToPage", DEP.display_issue("DeprecatedDynamic", None))

    def test_117_hidden_pane_with_open_filters(self):
        work, rep, lf = self._batch1("b117", lambda lay: lay.update(report={"filterPane": {"visible": False,
                                                                                         "expanded": False}}))
        r = pbik("build", rep, lf)
        self.assertIn("filterPane.visible false hides the filter pane", r.stdout)
        v = pbik("validate", rep, "--no-catalog", "--no-a11y", ok=(0, 1)).stdout
        self.assertIn("the filter pane is hidden in view mode", v)
        self.assertIn("filter pane collapsed by default", v)

    def test_118_roundtrip_labels_pane_dependent_changes(self):
        """Gap 24: automatic filters and the pane state Desktop saved are labelled pane-dependent, not pbik fixes."""
        work, rep, lf = self._batch1("b118", lambda lay: lay.update(report={"filterPane": {"expanded": False}}))
        pbik("build", rep, lf)
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "build"]):
            subprocess.run(["git", "-C", str(work), *args], check=True, capture_output=True)
        f = next(rep.glob("definition/pages/*/visuals/P1-V04_*/visual.json"))
        d = json.loads(f.read_text(encoding="utf-8"))
        d["filterConfig"]["filters"].append({"name": "auto0001", "type": "Categorical", "howCreated": "Auto",
                                             "field": {"Column": {"Expression": {"SourceRef": {"Entity": "stores"}},
                                                                  "Property": "City"}}})
        d["filterConfig"]["filters"].append({"name": "c208b5f087d7071caa26", "type": "Advanced",   # as Desktop saved
                                             "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}},
                                                                   "Property": "Revenue"}}})          # one (no howCreated)
        d["filterConfig"]["filters"].append({"name": "user0001", "type": "Categorical", "howCreated": "User"})
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        rf = rep / "definition" / "report.json"
        rd = json.loads(rf.read_text(encoding="utf-8"))
        next(e for e in rd["objects"]["outspacePane"] if not e.get("selector"))["properties"]["expanded"] = \
            {"expr": {"Literal": {"Value": "true"}}}
        rf.write_text(json.dumps(rd, indent=2), encoding="utf-8")
        r = pbik("roundtrip", rep).stdout
        self.assertIn("Pane-dependent, not pbik fixes", r)
        self.assertIn("- pane: filterConfig.filters@auto0001 follows the filter pane", r)
        self.assertIn("- pane: filterConfig.filters@c208b5f087d7071caa26 follows the filter pane", r)
        self.assertIn("follows the filter pane", r.split("### report.json", 1)[1])
        self.assertIn("added: Desktop adds filterConfig.filters@user0001", r)       # a real addition stays a proposal
        self.assertNotIn("auto0001  (", r.split("## By visual ID")[0])

    # ---------------------------------------------------------------- roadmap batch 2 (pre-bulk-2026-11-10)
    def test_119_decorative_shapes_and_images(self):
        """Gap 21: a shape without alt text must be marked decorative; decorative visuals leave the tab-order check."""
        work, rep, lf = self._batch1("b119")
        pbik("build", rep, lf)
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", ok=(0, 1)).stdout
        self.assertRegex(v, r"a11y: \d+ shape\(s\) with no alt text and not marked `decorative: true`.*P1-V01_band")
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V01").update(decorative=True))
        pbik("build", rep, lf)
        m = json.loads((work / "design" / "specs" / "visual-map.json").read_text(encoding="utf-8"))
        self.assertTrue(m["visuals"]["P1-V01"]["decorative"])
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", ok=(0, 1)).stdout
        self.assertNotIn("P1-V01_band", "".join(x for x in v.splitlines() if "a11y" in x))   # layers (C-11) may name it
        self.assertEqual(visual(rep, "P1-V01")["position"]["tabOrder"], -9999000)    # Desktop's hidden tab stop
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V01").update(
            container={"altText": "band"}))
        self.assertIn("decorative and altText both set", pbik("build", rep, lf, ok=(2,)).stderr)

    def test_120_learn_accessibility_checklist(self):
        """Gap 22: alt text over 250 characters, text box text missing from its alt text, data visuals without a sort."""
        def edit(lay):
            vs = {x["id"]: x for x in lay["visuals"]}
            vs["P1-V04"].setdefault("container", {})["altText"] = "x" * 260
        work, rep, lf = self._batch1("b120", edit)
        pbik("build", rep, lf)
        f = next(rep.glob("definition/pages/*/visuals/P1-V04_*/visual.json"))
        d = json.loads(f.read_text(encoding="utf-8"))
        d["visual"]["query"].pop("sortDefinition", None)
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", ok=(0, 1)).stdout
        self.assertIn("alt text is 260 characters; Power BI keeps 250", v)
        self.assertIn("P1-V02_title: a11y: text box text isn't in its alt text", v)
        self.assertRegex(v, r"data visual\(s\) without a sort order of their own \([^)]*P1-V04_")
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V02").update(
            container={"altText": "Sales overview"}))
        pbik("build", rep, lf)
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", ok=(0, 1)).stdout
        self.assertNotIn("P1-V02_title: a11y: text box text", v)

    def test_121_annotations(self):
        """Gap 13: annotate stamps pbik.id / pbik.layout / pbik.page; layout annotations are owned; unverified listed."""
        def edit(lay):
            lay["annotate"] = True
            next(x for x in lay["visuals"] if x["id"] == "P1-V04")["annotations"] = {"owner": "sales team"}
            lay["report"] = {"annotations": {"kit": "pbip-kit"}}
        work, rep, lf = self._batch1("b121", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 13)", r.stdout)                # confirmed in Desktop (2026-11-11)
        ann = {a["name"]: a["value"] for a in visual(rep, "P1-V04")["annotations"]}
        self.assertEqual(ann["pbik.id"], "P1-V04")
        self.assertEqual(ann["owner"], "sales team")
        self.assertRegex(ann["pbik.layout"], r"^[0-9a-f]{12}$")
        pg = next(json.loads(f.read_text(encoding="utf-8")) for f in rep.glob("definition/pages/*/page.json")
                  if json.loads(f.read_text(encoding="utf-8"))["displayName"] == "pbik sales")
        self.assertEqual(pg["annotations"], [{"name": "pbik.page", "value": "P1"}])
        rd = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(rd["annotations"], [{"name": "kit", "value": "pbip-kit"}])
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y", ok=(0, 1)).stdout
        self.assertNotIn("roadmap gap 13", v)
        f = next(rep.glob("definition/pages/*/visuals/P1-V05_*/visual.json"))     # a copy keeps the other's ID
        d = json.loads(f.read_text(encoding="utf-8"))
        d["annotations"] = [{"name": "pbik.id", "value": "P1-V04"}, {"name": "x", "value": "1"},
                            {"name": "x", "value": "2"}]
        f.write_text(json.dumps(d, indent=2), encoding="utf-8")
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y", ok=(1,)).stdout
        self.assertIn("annotation pbik.id is P1-V04, but the folder's ID is P1-V05", v)
        self.assertIn("annotation name(s) ['x'] used twice", v)
        def drop(lay):
            lay.pop("annotate"), lay.pop("report")
            next(x for x in lay["visuals"] if x["id"] == "P1-V04").pop("annotations")
        self._relayout(lf, drop)
        pbik("build", rep, lf)
        self.assertNotIn("annotations", visual(rep, "P1-V04"))
        self.assertNotIn("annotations", json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8")))
        cache = self._stand_in_schemas(self.tmp / "b121-schemas")
        from pbikit import schemaprops as SP, schemas as S
        old, S.CACHE, SP._W = S.CACHE, cache, SP.Walker()
        try:
            url = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"
            self.assertEqual(SP.tree_issues(url, ["annotations"], [{"name": "a", "value": "b"}]), [])
            bad = SP.tree_issues(url, ["annotations"], [{"name": "a", "value": "b", "colour": "red"}])
            self.assertEqual(bad[0][0], SP.UNKNOWN)
            self.assertIn("annotations.colour is not in Microsoft's", bad[0][1])
            self.assertEqual(SP.tree_issues(url.replace("2.13.0", "2.14.0"), ["annotations"], [{"z": 1}])[0][0],
                             SP.NEAREST)
        finally:
            S.CACHE, SP._W = old, SP.Walker()

    def test_122_reload_prerequisites(self):
        """Gap 23: the August 2026 Desktop minimum for reloading, and the 260-character path limit."""
        from pbikit import versions as V
        self.assertIn("older than the August 2026 release", V.reload_issue("2.155.756.0 (26.06)+abc"))
        self.assertIn("older than the August 2026 release", V.reload_issue("2.156.951.0"))
        self.assertIsNone(V.reload_issue("2.159.883.0"))
        self.assertIsNone(V.reload_issue(None))
        work = self.tmp / "b122"
        deep = work / ("d" * 40) / ("e" * 40)
        deep.mkdir(parents=True)
        (deep / "x.json").write_text("{}", encoding="utf-8")
        hits = V.long_paths([work], limit=len(str((deep / "x.json").resolve())))
        self.assertEqual(len(hits), 1)
        self.assertEqual(V.long_paths([work], limit=10 ** 4), [])
        pj = work / "project.json"
        pj.write_text(json.dumps({"targetDesktop": "latest"}), encoding="utf-8")
        r = pbik("project", "check", "--project", pj, "--version", "2.155.756.0")
        self.assertIn("reloading external changes needs", r.stdout)

    def test_123_roundtrip_registered_resources(self):
        """Gap 24: roundtrip compares StaticResources/RegisteredResources (theme by key, images by hash)."""
        work, rep, lf = self._batch1("b123")
        before = work / "before"
        shutil.copytree(rep, before / rep.name)
        r = pbik("roundtrip", rep, "--before", before / rep.name).stdout
        self.assertIn("none changed: Desktop kept the theme and images", r)
        res = rep / "StaticResources" / "RegisteredResources"
        theme = next(res.glob("*.json"))
        d = json.loads(theme.read_text(encoding="utf-8"))
        d["name"] = "rewritten by Desktop"
        theme.write_text(json.dumps(d), encoding="utf-8")
        (res / "new-logo.png").write_bytes(b"PNG fake")
        r = pbik("roundtrip", rep, "--before", before / rep.name).stdout
        sec = r.split("## Registered resources", 1)[1]
        self.assertIn(f"- changed: {theme.name}: Desktop rewrites name", sec)
        self.assertIn("- added: Desktop registered new-logo.png", sec)

    def test_124_image_key(self):
        """Gap 3: layout `image` registers the file and binds it as the Patterns page's image did (Desktop-saved)."""
        def edit(lay):
            lay["visuals"].append({"id": "P1-V20", "name": "logo", "page": "P1", "type": "image", "x": 1700, "y": 40,
                                   "w": 64, "h": 64, "z": 2, "image": {"file": "design/images/logo.png",
                                                                       "scaling": "fill"},
                                   "container": {"altText": "Company logo"}})
        work, rep, lf = self._batch1("b124", edit)
        (work / "design" / "images").mkdir()
        (work / "design" / "images" / "logo.png").write_bytes(b"PNG stand-in")
        r = pbik("build", rep, lf)
        self.assertIn("StaticResources/RegisteredResources/logo.png", r.stdout)
        g = visual(rep, "P1-V20")["visual"]["objects"]
        self.assertEqual(g["general"][0]["properties"]["imageUrl"]["expr"]["ResourcePackageItem"],
                         {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": "logo.png"})
        self.assertEqual(g["imageScaling"][0]["properties"]["imageScalingType"], {"expr": {"Literal": {"Value": "'Fill'"}}})
        rd = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        items = next(p_ for p_ in rd["resourcePackages"] if p_["name"] == "RegisteredResources")["items"]
        self.assertIn({"name": "logo.png", "path": "logo.png", "type": "Image"}, items)
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: lay["pages"]["P2"].update(background={"color": "background",
                                                                               "image": "design/images/logo.png",
                                                                               "scaling": "normal"}))
        pbik("build", rep, lf)
        bg = Report(rep).page_by("pbik stock")[1]["objects"]["background"][0]["properties"]
        self.assertEqual(bg["image"]["image"]["url"]["expr"]["ResourcePackageItem"]["ItemName"], "logo.png")
        self.assertEqual(bg["image"]["image"]["scaling"], {"expr": {"Literal": {"Value": "'Normal'"}}})
        self.assertEqual(bg["image"]["image"]["name"], {"expr": {"Literal": {"Value": "'logo.png'"}}})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: lay["visuals"].append(dict(lay["visuals"][-1], id="P1-V21", type="shape")))
        self.assertIn("image is for image visuals", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_125_page_settings_and_lifecycle(self):
        """Gap 12: landing page, page props (schema-checked), and --prune removing a page pbik made."""
        def edit(lay):
            lay["pages"]["P2"]["landing"] = True
            lay["pages"]["P2"]["props"] = {"pageRefresh.show": True, "displayArea.verticalAlignment": "Middle"}
        work, rep, lf = self._batch1("b125", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 12)", r.stdout)                # confirmed in Desktop (2026-11-11)
        meta = json.loads((rep / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
        p2 = Report(rep).page_by("pbik stock")
        self.assertEqual(meta["landingPageName"], p2[0])
        self.assertEqual(p2[1]["objects"]["pageRefresh"], [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}])
        self.assertEqual(p2[1]["objects"]["displayArea"][0]["properties"]["verticalAlignment"],
                         {"expr": {"Literal": {"Value": "'Middle'"}}})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        def drop(lay):
            lay["pages"].pop("P2")
            lay["visuals"] = [v for v in lay["visuals"] if v["page"] != "P2"]
            for v in lay["visuals"]:                                # P1's button to P2 goes too
                if (v.get("action") or {}).get("page") in ("P2", "pbik stock"):
                    v.pop("action")
        self._relayout(lf, drop)
        r = pbik("build", rep, lf)
        self.assertIn("page P2 (pbik stock) is not in layout.json (kept; --prune removes it)", r.stdout)
        self.assertTrue(Report(rep).page_by("pbik stock"))
        r = pbik("build", rep, lf, "--prune")
        self.assertIn("removed page pbik stock", r.stdout)
        self.assertIsNone(Report(rep).page_by("pbik stock"))
        meta = json.loads((rep / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
        self.assertNotIn(p2[0], meta["pageOrder"])
        self.assertNotIn("landingPageName", meta)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y").stdout)
        self._relayout(lf, lambda lay: lay["pages"]["P1"].update(props={"filterCard.textSize": 12}))
        self.assertIn("use the page's filterPane / filterCards keys", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_126_new_resource_support_note(self):
        """Gap 25: registering a new resource prints the support-risk note; re-registering doesn't."""
        work, rep, lf = self._batch1("b126")
        png = work / "pin.png"
        png.write_bytes(b"PNG stand-in")
        self.assertIn("roadmap gap 25", pbik("resource", "add", rep, png).stdout)
        self.assertNotIn("roadmap gap 25", pbik("resource", "add", rep, png).stdout)

    def test_127_more_filter_types(self):
        """Gap 4: Range, Advanced text conditions, RelativeDate, report-level filters, displayName / ordinal / order."""
        def edit(lay):
            lay["pages"]["P1"]["filters"] += [
                {"field": "'Date'[Month No]", "type": "Range", "min": 1, "max": 6, "displayName": "First half",
                 "ordinal": 2},
                {"field": "stores[City]", "type": "Advanced", "join": "or",
                 "conditions": [{"op": "contains", "value": "ville"}, {"op": "isBlank"}], "ordinal": 1},
                {"field": "'Date'[Date]", "type": "RelativeDate", "last": 12, "unit": "months"}]
            lay["pages"]["P1"]["filterOrder"] = "custom"
            lay["report"] = {"filters": [{"field": "products[Product_Category]", "values": ["Toys"], "hidden": True}]}
        work, rep, lf = self._batch1("b127", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 4)", r.stdout)                 # confirmed in Desktop (2026-11-11)
        pg = Report(rep).page_by("pbik sales")[1]
        fs = {f["type"]: f for f in pg["filterConfig"]["filters"]}
        self.assertEqual(pg["filterConfig"]["filterSortOrder"], "Custom")
        rng = next(f for f in pg["filterConfig"]["filters"] if f.get("displayName") == "First half")
        self.assertEqual((rng["type"], rng["ordinal"]), ("Advanced", 2))
        both = rng["filter"]["Where"][0]["Condition"]["And"]
        self.assertEqual((both["Left"]["Comparison"]["ComparisonKind"], both["Left"]["Comparison"]["Right"]),
                         (2, {"Literal": {"Value": "1L"}}))
        self.assertEqual((both["Right"]["Comparison"]["ComparisonKind"], both["Right"]["Comparison"]["Right"]),
                         (4, {"Literal": {"Value": "6L"}}))
        adv = next(f for f in pg["filterConfig"]["filters"] if f["type"] == "Advanced" and "Or" in json.dumps(f["filter"]))
        orc = adv["filter"]["Where"][0]["Condition"]["Or"]
        self.assertEqual(orc["Left"]["Contains"]["Right"], {"Literal": {"Value": "'ville'"}})
        self.assertEqual(orc["Right"]["Comparison"]["Right"], {"Literal": {"Value": "null"}})
        low = fs["RelativeDate"]["filter"]["Where"][0]["Condition"]["Between"]["LowerBound"]["DateSpan"]
        self.assertEqual((low["Expression"]["DateAdd"]["Amount"], low["Expression"]["DateAdd"]["TimeUnit"]), (-12, 2))
        rd = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        rf = [f for f in rd["filterConfig"]["filters"] if f["name"].startswith("pbik_")]
        self.assertEqual(len(rf), 1)
        self.assertTrue(rf[0]["isHiddenInViewMode"])
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y", ok=(0, 1)).stdout
        self.assertIn("0 error(s)", v)
        self.assertNotIn("roadmap gap 4)", v)
        def drop(lay):
            lay.pop("report"), lay["pages"]["P1"].pop("filterOrder")
            lay["pages"]["P1"]["filters"] = lay["pages"]["P1"]["filters"][:1]
        self._relayout(lf, drop)
        pbik("build", rep, lf)
        rd = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        self.assertFalse([f for f in (rd.get("filterConfig") or {}).get("filters", []) if f["name"].startswith("pbik_")])
        self.assertNotIn("filterSortOrder", Report(rep).page_by("pbik sales")[1]["filterConfig"])
        self._relayout(lf, lambda lay: lay.update(report={"filters": [{"field": "[Revenue]", "op": ">", "value": 1}]}))
        self.assertIn("filters on a measure only at visual level", pbik("build", rep, lf, ok=(1,)).stdout)
        self._relayout(lf, lambda lay: lay.update(report={"filters": [{"field": "'Date'[Date]", "type": "RelativeDate",
                                                                      "last": 2, "unit": "fortnights"}]}))
        self.assertIn("relative date unit 'fortnights'", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_128_per_member_formatting(self):
        """Gap 2: members writes one scopeId selector per member, as Desktop saved the Rep 5 donut."""
        def edit(lay):
            next(x for x in lay["visuals"] if x["id"] == "P1-V04")["members"] = {
                "field": "stores[City]", "values": {"Austin": "primary", "Boston": "#5D6B8A"}}
        work, rep, lf = self._batch1("b128", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 2)", r.stdout)                 # dataPoint.fill: Desktop's own form
        dp = visual(rep, "P1-V04")["visual"]["objects"]["dataPoint"]
        sels = {e["selector"]["data"][0]["scopeId"]["Comparison"]["Right"]["Literal"]["Value"]: e for e in dp
                if "scopeId" in json.dumps(e.get("selector"))}
        self.assertEqual(set(sels), {"'Austin'", "'Boston'"})
        left = sels["'Boston'"]["selector"]["data"][0]["scopeId"]["Comparison"]["Left"]
        self.assertEqual(left, {"Column": {"Expression": {"SourceRef": {"Entity": "stores"}}, "Property": "City"}})
        self.assertEqual(sels["'Boston'"]["properties"]["fill"]["solid"]["color"]["expr"]["Literal"]["Value"], "'#5D6B8A'")
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        rep5 = KIT / "tools" / "fixtures" / "rep5" / "HR OVERVIEW.Report"
        saved = json.loads(next(rep5.glob("definition/pages/*/visuals/mix-chart-gender/visual.json")).read_text(
            encoding="utf-8"))["visual"]["objects"]["dataPoint"][1]["selector"]
        self.assertEqual(set(saved["data"][0]["scopeId"]["Comparison"]), set(sels["'Boston'"]["selector"]["data"][0][
            "scopeId"]["Comparison"]), "same shape as Desktop's save")
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V04").update(members=[
            {"field": "stores[City]", "object": "labels", "property": "color", "values": {"Austin": "#000000"}}]))
        r = pbik("build", rep, lf)
        self.assertIn("UNVERIFIED in Desktop (roadmap gap 2)", r.stdout)
        dp = visual(rep, "P1-V04")["visual"]["objects"].get("dataPoint", [])
        self.assertFalse([e for e in dp if "scopeId" in json.dumps(e.get("selector"))], "members owned: removed")
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V04").update(
            members={"field": "[Revenue]", "values": {"a": "#000000"}}))
        self.assertIn("must be a column", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_129_data_bookmarks_save_state(self):
        """Gap 5: a bookmark saves a slicer selection (objects.merge.general.filter) and a sort (orderBy)."""
        def edit(lay):
            lay["pages"]["P1"]["bookmarks"] = [{"name": "toys", "displayName": "Toys only",
                                                "select": {"P1-V09": {"field": "products[Product_Category]",
                                                                      "values": ["Toys"]}},
                                                "sort": {"P1-V04": {"field": "[Revenue]", "direction": "Ascending"}}}]
        work, rep, lf = self._batch1("b129", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 5)", r.stdout)                 # confirmed in Desktop (2026-11-11)
        bd = json.loads(next((rep / "definition" / "bookmarks").glob("*.bookmark.json")).read_text(encoding="utf-8"))
        self.assertNotIn("suppressData", bd["options"])
        sec = next(iter(bd["explorationState"]["sections"].values()))["visualContainers"]
        sl = next(v for k, v in sec.items() if k.startswith("P1-V09"))["singleVisual"]
        flt = sl["objects"]["merge"]["general"][0]["properties"]["filter"]["filter"]
        self.assertEqual(flt["Where"][0]["Condition"]["In"]["Values"], [[{"Literal": {"Value": "'Toys'"}}]])
        ch = next(v for k, v in sec.items() if k.startswith("P1-V04"))["singleVisual"]
        self.assertEqual(ch["orderBy"][0]["Direction"], 1)
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y", ok=(0, 1)).stdout
        self.assertIn("0 error(s)", v)
        self.assertNotIn("roadmap gap 5", v)
        self._relayout(lf, lambda lay: lay["pages"]["P1"]["bookmarks"][0].update(data=False))
        self.assertIn("saves a selection or sort, which needs data", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_130_tooltip_pages(self):
        """Gap 6: a tooltip page (type Tooltip, pageBinding) and a visual pointing at it (visualTooltip section)."""
        def edit(lay):
            lay["pages"]["P3"] = {"displayName": "pbik tip", "width": 320, "height": 240, "tooltip": True,
                                  "hidden": True}
            next(x for x in lay["visuals"] if x["id"] == "P1-V04")["tooltipPage"] = "P3"
        work, rep, lf = self._batch1("b130", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 6)", r.stdout)                 # confirmed in Desktop (2026-11-11)
        name, pg, _ = Report(rep).page_by("pbik tip")
        self.assertEqual(pg["pageBinding"]["parameters"], [])
        self.assertEqual(pg["type"], "Tooltip")
        self.assertEqual(pg["pageBinding"]["type"], "Tooltip")
        vt = visual(rep, "P1-V04")["visual"]["visualContainerObjects"]["visualTooltip"][0]["properties"]
        self.assertEqual(vt["section"], {"expr": {"Literal": {"Value": f"'{name}'"}}})
        self.assertNotIn("type", vt)
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y").stdout)
        pd_file = next(f for f in rep.glob("definition/pages/*/page.json")
                       if json.loads(f.read_text(encoding="utf-8"))["displayName"] == "pbik sales")
        d = json.loads(pd_file.read_text(encoding="utf-8"))
        d["pageBinding"] = dict(pg["pageBinding"])                 # a copied page keeps the binding name
        pd_file.write_text(json.dumps(d, indent=2), encoding="utf-8")
        self.assertIn("must be unique across the report", pbik("validate", rep, "--no-catalog", "--no-a11y", ok=(1,)).stdout)
        d.pop("pageBinding")
        pd_file.write_text(json.dumps(d, indent=2), encoding="utf-8")
        self._relayout(lf, lambda lay: lay["pages"]["P3"].pop("tooltip"))
        self.assertIn("is not a page with `tooltip: true`", pbik("build", rep, lf, ok=(1,)).stdout)
        def drop(lay):
            next(x for x in lay["visuals"] if x["id"] == "P1-V04").pop("tooltipPage")
        self._relayout(lf, drop)
        pbik("build", rep, lf)
        pg = Report(rep).page_by("pbik tip")[1]
        self.assertNotIn("type", pg)
        self.assertNotIn("pageBinding", pg)

    def test_131_drillthrough_pages(self):
        """Gap 7: a drill-through page (type, pageBinding parameters bound to Drillthrough filters) and a button."""
        def edit(lay):
            lay["pages"]["P3"] = {"displayName": "pbik store detail", "drillthrough": {"fields": ["stores[City]"],
                                                                                     "keepFilters": False}}
            next(x for x in lay["visuals"] if x["id"] == "P1-V06")["action"] = {"type": "Drillthrough", "page": "P3"}
        work, rep, lf = self._batch1("b131", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 7)", r.stdout)                 # confirmed in Desktop (2026-11-11)
        name, pg, _ = Report(rep).page_by("pbik store detail")
        self.assertEqual(pg["type"], "Drillthrough")
        pb = pg["pageBinding"]
        self.assertEqual((pb["type"], pb["acceptsFilterContext"]), ("Drillthrough", "None"))
        flt = pg["filterConfig"]["filters"][0]
        self.assertEqual((flt["howCreated"], pb["parameters"][0]["boundFilter"]), ("Drillthrough", flt["name"]))
        self.assertEqual(pb["parameters"][0]["fieldExpr"], flt["field"])
        link = visual(rep, "P1-V06")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]
        self.assertEqual(link["drillthroughSection"], {"expr": {"Literal": {"Value": f"'{name}'"}}})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        v = pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y").stdout
        self.assertIn("0 error(s)", v)
        self.assertIn("drill-through page without a Back button", v)
        self._relayout(lf, lambda lay: lay["pages"]["P3"].update(filters=[{"field": "products[Product_Category]",
                                                                             "values": ["Toys"]}]))
        pbik("build", rep, lf)
        types = sorted(f["howCreated"] for f in Report(rep).page_by("pbik store detail")[1]["filterConfig"]["filters"])
        self.assertEqual(types, ["Drillthrough", "User"], "page filters and drill-through filters live side by side")
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        def drop(lay):
            lay["pages"]["P3"].pop("drillthrough"), lay["pages"]["P3"].pop("filters")
            next(x for x in lay["visuals"] if x["id"] == "P1-V06")["action"] = {"type": "PageNavigation", "page": "P2"}
        self._relayout(lf, drop)
        pbik("build", rep, lf)
        pg = Report(rep).page_by("pbik store detail")[1]
        self.assertFalse({"type", "pageBinding", "filterConfig"} & set(pg))
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V06").update(
            action={"type": "Drillthrough", "page": "P2"}))
        self.assertIn("is not a page with `drillthrough`", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_132_hierarchies_and_expand(self):
        """Gap 8: a hierarchy level as a field (checked against the TMDL, active flags as Desktop saves them); expand is
        an error until Desktop shows its form."""
        def edit(lay):
            lay["visuals"].append({"id": "P2-V10", "name": "by-period", "page": "P2", "type": "pivotTable",
                                   "x": 32, "y": 700, "w": 600, "h": 300, "sort": {"field": "[Revenue]"},
                                   "bindings": {"Rows": [{"hierarchy": "Date[Calendar]", "level": "Year"},
                                                         {"hierarchy": "Date[Calendar]", "level": "Month"}],
                                                "Values": ["[Revenue]"]}})
        work, rep, lf = self._batch1("b132", edit)
        tm = next((work / self.model.name).glob("definition/tables/Date.tmdl"))
        hier = "\n\n\thierarchy Calendar\n\n\t\tlevel Year\n\t\t\tcolumn: Year\n\n\t\tlevel Month\n\t\t\tcolumn: Month\n"
        tm.write_text(tm.read_text(encoding="utf-8").rstrip() + hier, encoding="utf-8")
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 8)", r.stdout)                 # confirmed in Desktop (2026-11-11)
        projs = visual(rep, "P2-V10")["visual"]["query"]["queryState"]["Rows"]["projections"]
        self.assertEqual(projs[0]["field"]["HierarchyLevel"]["Level"], "Year")
        self.assertEqual(projs[0]["field"]["HierarchyLevel"]["Expression"]["Hierarchy"]["Hierarchy"], "Calendar")
        self.assertEqual(projs[0]["queryRef"], "Date.Calendar.Year")
        self.assertEqual([p["active"] for p in projs], [True, False])
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y").stdout)
        self._relayout(lf, lambda lay: lay["visuals"][-1].update(expand="all"))
        self.assertIn("expand isn't supported yet", pbik("build", rep, lf, ok=(1,)).stdout)
        self._relayout(lf, lambda lay: (lay["visuals"][-1].pop("expand"),
                                        lay["visuals"][-1]["bindings"]["Rows"][1].update(level="Week")))
        self.assertIn("no level 'Week'", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_133_group_formatting(self):
        """Gap 27: a group's background, alt text and lock aspect go to visualGroup.objects, owned per property."""
        def edit(lay):
            lay["visuals"].append({"id": "P1-V30", "name": "nav-group", "page": "P1", "type": "group",
                                   "members": ["P1-V06", "P1-V07"], "altText": "Navigation buttons",
                                   "background": {"color": "card", "transparency": 10}, "lockAspect": True})
        work, rep, lf = self._batch1("b133", edit)
        r = pbik("build", rep, lf)
        self.assertIn("UNVERIFIED in Desktop (roadmap gap 27)", r.stdout)
        objs = visual(rep, "P1-V30")["visualGroup"]["objects"]
        self.assertEqual(objs["general"][0]["properties"]["altText"], {"expr": {"Literal": {"Value": "'Navigation buttons'"}}})
        self.assertEqual(objs["lockAspect"][0]["properties"]["show"], {"expr": {"Literal": {"Value": "true"}}})
        self.assertEqual(objs["background"][0]["properties"]["transparency"], {"expr": {"Literal": {"Value": "10D"}}})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: [lay["visuals"][-1].pop(k) for k in ("altText", "background", "lockAspect")])
        pbik("build", rep, lf)
        self.assertNotIn("objects", visual(rep, "P1-V30")["visualGroup"])

    def test_134_service_limits(self):
        """Gap 18: the service limits fire (lowered here, since real reports never reach them)."""
        from pbikit import validate as VA
        rep = Report(self.report)
        fd = VA.Findings()
        VA.check_limits(fd, rep, rep.pages())
        self.assertEqual(fd.errors, [])
        fd = VA.Findings()
        VA.check_limits(fd, rep, rep.pages(), {"pages": 1, "visuals per page": 3, "resource files": 0,
                                               "resource MB": -1, "report files MB": -1})
        text = "\n".join(fd.errors)
        for bit in ("2 pages; a PBIR report holds at most 1", "visuals; at most 3 a page", "registered resource files",
                    "registered resources are", "report definition files are"):
            self.assertIn(bit, text)

    def test_135_values_for_privacy_review(self):
        """Gap 19: pbik values lists filter, slicer and selector literals by field, not formatting literals."""
        work, rep, lf = self._batch1("b135", lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V04").update(
            members={"field": "stores[City]", "values": {"Austin": "#000000"}}))
        pbik("build", rep, lf)
        out = work / "values.md"
        r = pbik("values", rep, "--out", out).stdout
        self.assertIn("page filters, products[Product_Category]: 'Art & Crafts', 'Electronics'", r)
        self.assertIn("selector (dataPoint), stores[City]: 'Austin'", r)
        self.assertNotIn("#000000", r)
        self.assertTrue(out.exists())

    def test_136_no_template_warning(self):
        """Gap 26: a visual type without a template is built bare, with a warning naming the harvest route."""
        work, rep, lf = self._batch1("b136", lambda lay: lay["visuals"].append(
            {"id": "P2-V11", "name": "new-slicer", "page": "P2", "type": "listSlicer", "x": 32, "y": 900, "w": 300,
             "h": 100}))
        (work / "design" / "templates").mkdir()
        r = pbik("build", rep, lf)
        self.assertIn("P2-V11: no template for listSlicer in templates/: built bare", r.stdout)
        self.assertIn("still missing: the list slicer, the input slicer, Azure Maps", r.stdout)
        self.assertEqual(visual(rep, "P2-V11")["visual"]["visualType"], "listSlicer")
        self._relayout(lf, lambda lay: lay["visuals"][-1].update(bindings={"Values": ["stores[City]"]}))
        pbik("build", rep, lf)
        self.assertTrue(visual(rep, "P2-V11")["visual"]["query"]["queryState"]["Values"]["projections"][0]["active"])

    def test_137_more_aggregations(self):
        """Gap 9: Median / StDev / Variance (Function 6-8) and Percentile in the field notation."""
        from pbikit import fields as F
        res = F.Resolver(Report(self.report))
        self.assertEqual(res.field("Median(sales[Units])")["Aggregation"]["Function"], 6)
        self.assertEqual(res.field("StDev(sales[Units])")["Aggregation"]["Function"], 7)
        self.assertEqual(res.field("Variance(sales[Units])")["Aggregation"]["Function"], 8)
        p = res.field("Percentile(sales[Units], 0.9)")
        self.assertEqual(p["Percentile"]["K"], 0.9)
        from pbikit.objects import qref, native_ref
        self.assertEqual(qref(p), "Percentile(sales.Units, 0.9)")
        self.assertEqual(native_ref(p), "Units")
        self.assertEqual(qref(res.field("Median(sales[Units])")), "Median(sales.Units)")
        for bad, why in (("Percentile(sales[Units], 90)", "between 0 and 1"),
                         ("Median(stores[City])", "needs a number column")):
            with self.assertRaises(F.FieldError) as e:
                res.field(bad)
            self.assertIn(why, str(e.exception))
        work, rep, lf = self._batch1("b137", lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V04")[
            "bindings"].update(Y=["Median(sales[Units])"]))
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 9)", r.stdout)                 # confirmed in Desktop (2026-11-11)
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V05")["bindings"].update(
            Values=["stores[Store]", "Avg(sales[Units])", "Median(sales[Units])", "Percentile(sales[Units], 0.9)",
                    "Sum(sales[Units])"]))
        pbik("build", rep, lf)
        refs = [p["nativeQueryRef"] for p in visual(rep, "P1-V05")["visual"]["query"]["queryState"]["Values"]["projections"]]
        self.assertEqual(refs, ["Store", "Units", "Median of Units", "Percentile.Inc(Units, 0.9)", "Sum of Units"])

    def test_138_visual_calcs_and_sparklines(self):
        """Gap 10: a visual calculation and a sparkline column as binding items."""
        def edit(lay):
            vals = next(x for x in lay["visuals"] if x["id"] == "P1-V05")["bindings"]["Values"]
            vals.append({"calc": "Running revenue", "expression": "RUNNINGSUM([Revenue])", "dataType": "Double"})
            vals.append({"sparkline": "[Revenue]", "by": "Date[Year Month]"})
        work, rep, lf = self._batch1("b138", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 10)", r.stdout)                # confirmed in Desktop (2026-11-11)
        projs = visual(rep, "P1-V05")["visual"]["query"]["queryState"]["Values"]["projections"]
        vc = next(p for p in projs if "NativeVisualCalculation" in p["field"])
        self.assertEqual(vc["field"]["NativeVisualCalculation"], {"Language": "dax", "Expression": "RUNNINGSUM([Revenue])",
                                                                  "Name": "Running revenue", "DataType": "Double"})
        sp = next(p for p in projs if "SparklineData" in p["field"])["field"]["SparklineData"]
        self.assertEqual(sp["PointsPerSparkline"], 52)
        refs = [p["nativeQueryRef"] for p in projs]
        self.assertEqual(len(refs), len(set(refs)), "Desktop refuses duplicate native reference names")
        self.assertIn("Revenue by Year Month", refs)
        self.assertEqual(sp["Groupings"][0]["Column"]["Property"], "Year Month")
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self.assertIn("0 error(s)", pbik("validate", rep, "--layout", lf, "--no-catalog", "--no-a11y").stdout)
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V04")["bindings"]["Y"].append(
            {"sparkline": "[Revenue]", "by": "Date[Year Month]"}))
        self.assertIn("sparklines are for tables and matrices", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_139_mobile_layout(self):
        """Gap 11: visual `mobile` writes mobile.json (position only), removed when the key goes."""
        work, rep, lf = self._batch1("b139", lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V03").update(
            mobile={"x": 0, "y": 0, "w": 320, "h": 120}))
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 11)", r.stdout)                # confirmed in Desktop (2026-11-11)
        mf = next(rep.glob("definition/pages/*/visuals/P1-V03_*/mobile.json"))
        md = json.loads(mf.read_text(encoding="utf-8"))
        self.assertIn("visualContainerMobileState/2.8.0", md["$schema"])
        self.assertEqual(md["position"], {"x": 0, "y": 0, "z": 0, "width": 320, "height": 120, "tabOrder": 0})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self.assertNotIn("roadmap gap 11", pbik("validate", rep, "--no-catalog", "--no-a11y").stdout)
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P1-V03").pop("mobile"))
        pbik("build", rep, lf)
        self.assertFalse(mf.exists())

    def test_140_shape_map_resource(self):
        """Gap 14: a TopoJSON registered as a ShapeMap resource; validate errors on a registered file that's missing."""
        work, rep, lf = self._batch1("b140")
        topo = work / "regions.topo.json"
        topo.write_text(json.dumps({"type": "Topology", "objects": {}, "arcs": []}), encoding="utf-8")
        r = pbik("resource", "add", rep, topo, "--type", "ShapeMap").stdout
        self.assertIn("as a ShapeMap resource; bind it with layout `shapeMap`", r)
        rd = json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))
        items = next(p_ for p_ in rd["resourcePackages"] if p_["name"] == "RegisteredResources")["items"]
        self.assertIn({"name": "regions.topo.json", "path": "regions.topo.json", "type": "ShapeMap"}, items)
        (rep / "StaticResources" / "RegisteredResources" / "regions.topo.json").unlink()
        v = pbik("validate", rep, "--no-catalog", "--no-a11y", ok=(1,)).stdout
        self.assertIn("resource 'regions.topo.json' (ShapeMap) has no file", v)
        self.assertIn("a shape map is a TopoJSON file", pbik("resource", "add", rep, work / "x.png", "--type",
                                                             "ShapeMap", ok=(2,)).stderr)
        self._relayout(lf, lambda lay: lay["visuals"].append(
            {"id": "P2-V12", "name": "map", "page": "P2", "type": "shapeMap", "x": 32, "y": 700, "w": 400, "h": 300,
             "bindings": {"Category": ["stores[City]"]}, "shapeMap": {"file": "regions.topo.json"}}))
        pbik("build", rep, lf)
        sh = visual(rep, "P2-V12")["visual"]["objects"]["shape"][0]["properties"]
        self.assertEqual(sh["datasourceType"], {"expr": {"Literal": {"Value": "'file_upload'"}}})
        gj = sh["map"]["geoJson"]
        self.assertEqual(gj["content"]["expr"]["ResourcePackageItem"]["ItemName"], "regions.topo.json")
        self.assertEqual(gj["type"], {"expr": {"Literal": {"Value": "'packaged'"}}})
        self.assertEqual(sh["projectionEnum"], {"expr": {"Literal": {"Value": "'albersUsa'"}}})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)

    def test_141_angle_and_query_options(self):
        """Gap 16: query.options (owned, confirmed in Desktop); angle is an error (Desktop didn't draw the visual)."""
        work, rep, lf = self._batch1("b141", lambda lay: next(x for x in lay["visuals"] if x["id"] == "P2-V03").update(
            queryOptions={"binnedLineSample": True}))
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 16)", r.stdout)
        self.assertEqual(visual(rep, "P2-V03")["visual"]["query"]["options"], {"allowBinnedLineSample": True})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P2-V03").pop("queryOptions"))
        pbik("build", rep, lf)
        self.assertNotIn("options", visual(rep, "P2-V03")["visual"]["query"])
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P2-V03").update(angle=90))
        self.assertIn("angle isn't supported", pbik("build", rep, lf, ok=(1,)).stdout)
        self._relayout(lf, lambda lay: next(x for x in lay["visuals"] if x["id"] == "P2-V03").update(
            queryOptions={"fast": True}, angle=None))
        self.assertIn("queryOptions ['fast']", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_143_copy_page_between_reports(self):
        """Gap 17: copy a page with its bookmark into another report; IDs, filter and binding names follow."""
        def edit(lay):
            lay["pages"]["P2"]["bookmarks"] = [{"name": "trend-only", "hide": ["P2-V01"]}]
            lay["pages"]["P2"]["filters"] = [{"field": "products[Product_Category]", "values": ["Toys"]}]
        work, rep, lf = self._batch1("b143", edit)
        pbik("build", rep, lf)
        dst_proj = self.tmp / "b143-target"
        dst_proj.mkdir()
        dst, _ = copy_project(dst_proj, keep_pages=False)
        r = pbik("copy", "page", rep, "pbik stock", dst, "--key", "P5", "--as", "Stock copy", "--bookmarks").stdout
        self.assertIn("3 visual(s) renumbered to P5", r)
        self.assertIn("copied 1 bookmark(s)", r)
        self.assertIn("P5-V02_back -> ", r)                            # its Back target isn't in the new report
        name, pg, folder = Report(dst).page_by("Stock copy")
        from pbikit.report import stable_name
        self.assertEqual(name, stable_name("page", "P5", "Stock copy"))
        self.assertEqual(sorted(f.name.split("_")[0] for f in (folder / "visuals").iterdir()), ["P5-V01", "P5-V02", "P5-V03"])
        self.assertEqual(visual(dst, "P5-V03")["name"], "P5-V03_trend")
        src_pg = Report(rep).page_by("pbik stock")[1]
        self.assertNotEqual(pg["filterConfig"]["filters"][0]["name"], src_pg["filterConfig"]["filters"][0]["name"])
        self.assertTrue(pg["filterConfig"]["filters"][0]["name"].startswith("pbik_"))
        bd = json.loads(next((dst / "definition" / "bookmarks").glob("*.bookmark.json")).read_text(encoding="utf-8"))
        self.assertEqual(list(bd["explorationState"]["sections"]), [name])
        self.assertEqual(bd["options"]["targetVisualNames"], ["P5-V01_title"])
        self.assertNotIn("bookmark", pbik("validate", dst, "--no-catalog", "--no-a11y", ok=(0, 1)).stdout.split(
            "warning")[0])
        work2, rep2, lf2 = self._batch1("b143b", lambda lay: (lay.update(annotate=True), lay["pages"]["P2"].update(
            bookmarks=[{"name": "b"}]), next(x for x in lay["visuals"] if x["id"] == "P2-V02").update(
            action={"type": "Bookmark", "bookmark": "b"})))
        pbik("build", rep2, lf2)
        pbik("copy", "page", rep2, "pbik stock", rep2, "--key", "P7", "--as", "Copy", "--bookmarks")
        link = visual(rep2, "P7-V02")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]["bookmark"]
        src_link = visual(rep2, "P2-V02")["visual"]["visualContainerObjects"]["visualLink"][0]["properties"]["bookmark"]
        self.assertNotEqual(link, src_link, "the copied button applies the copied bookmark")
        ann = {a["name"]: a["value"] for a in visual(rep2, "P7-V02")["annotations"]}
        self.assertEqual((ann["pbik.id"], ann.get("pbik.layout") is not None), ("P7-V02", True))
        v = pbik("validate", rep2, "--no-catalog", "--no-a11y", ok=(0, 1)).stdout
        self.assertNotIn("but the folder's ID is", v)
        self.assertNotIn("which hides or shows visuals on page", v)
        v = pbik("validate", dst, "--no-catalog", "--no-a11y", ok=(0, 1)).stdout
        self.assertNotIn("duplicate visual ID", v)
        self.assertNotIn("bookmark", v.split("error")[0] if "error   " not in v else "")
        self.assertIn("already has a page", pbik("copy", "page", rep, "pbik stock", dst, "--key", "P5", "--as",
                                                 "Stock copy", ok=(2,)).stderr)

    def test_142_bookmark_display_modes(self):
        """Gap 28: spotlight, elevation and focus (maximize with the accessible data table) in a bookmark."""
        def edit(lay):
            lay["pages"]["P1"]["bookmarks"] = [{"name": "story", "spotlight": ["P1-V04"],
                                                "focus": {"visual": "P1-V05", "table": "accessible"}}]
        work, rep, lf = self._batch1("b142", edit)
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 28)", r.stdout)                # confirmed in Desktop (2026-11-11)
        bd = json.loads(next((rep / "definition" / "bookmarks").glob("*.bookmark.json")).read_text(encoding="utf-8"))
        sec = next(iter(bd["explorationState"]["sections"].values()))["visualContainers"]
        mode = {k.split("_")[0]: v["singleVisual"].get("display") for k, v in sec.items()}
        self.assertEqual(mode["P1-V04"], {"mode": "spotlight"})
        self.assertEqual(mode["P1-V05"], {"mode": "maximize", "maximizedOptions": {"dataTable": "accessible"}})
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        self._relayout(lf, lambda lay: lay["pages"]["P1"]["bookmarks"][0].update(hide=["P1-V04"]))
        self.assertIn("gives ['P1-V04'] two display modes", pbik("build", rep, lf, ok=(1,)).stdout)
        self._relayout(lf, lambda lay: lay["pages"]["P1"]["bookmarks"][0].update(hide=[], elevate=["P1-V03"]))
        self.assertIn("elevate isn't supported", pbik("build", rep, lf, ok=(1,)).stdout)

    def test_144_cross_report_drillthrough(self):
        """Gap 29: crossReport adds referenceScope CrossReport and warns until the report setting is on."""
        work, rep, lf = self._batch1("b144", lambda lay: lay["pages"].update(P3={
            "displayName": "pbik detail", "drillthrough": {"fields": ["stores[City]"], "crossReport": True}}))
        r = pbik("build", rep, lf)
        self.assertNotIn("roadmap gap 29)", r.stdout)                # confirmed in Desktop (2026-11-11)
        self.assertIn("needs the report setting useCrossReportDrillthrough", r.stdout)
        self.assertEqual(Report(rep).page_by("pbik detail")[1]["pageBinding"]["referenceScope"], "CrossReport")
        self._relayout(lf, lambda lay: lay.update(report={"settings": {"useCrossReportDrillthrough": True}}))
        r = pbik("build", rep, lf)
        self.assertNotIn("needs the report setting", r.stdout)
        self.assertIs(json.loads((rep / "definition" / "report.json").read_text(encoding="utf-8"))["settings"][
            "useCrossReportDrillthrough"], True)


    def test_145_layout_fidelity(self):
        """Batch 3 item 11: desktopPosition, inactive bindings, Desktop bookmark groups, naming visuals Desktop added."""
        def edit(lay):
            v4 = next(v for v in lay["visuals"] if v["id"] == "P1-V04")
            v4["desktopPosition"] = {"x": 40.25, "y": 96.5, "z": 7000, "width": 600.75, "height": 300, "tabOrder": 55}
            v4["bindings"]["Category"] = ["stores[City]", {"field": "stores[Store]", "active": False}]
            lay["pages"]["P1"]["bookmarks"] = [{"name": "one", "hide": ["P1-V04"]}, {"name": "two", "show": ["P1-V04"]}]
        work, rep, lf = self._batch1("b145", edit)
        pbik("build", rep, lf)
        f4 = Report(rep).visual_by_id("P1-V04")[0]
        d = json.loads(f4.read_text(encoding="utf-8"))
        self.assertEqual(d["position"], {"x": 40.25, "y": 96.5, "z": 7000, "height": 300, "width": 600.75,
                                         "tabOrder": 55})
        cats = d["visual"]["query"]["queryState"]["Category"]["projections"]
        self.assertEqual([p.get("active") for p in cats], [True, False])
        self.assertIn("No changes", pbik("build", rep, lf).stdout)
        # the author moves bookmark "one" into a group made in Desktop: pbik leaves it alone from then on
        bdir = rep / "definition" / "bookmarks"
        meta = json.loads((bdir / "bookmarks.json").read_text(encoding="utf-8"))
        one = meta["items"][0]["name"]
        meta["items"] = [{"name": "aa11bb22cc33dd44ee55", "displayName": "Author group", "children": [one]}] +             meta["items"][1:]
        (bdir / "bookmarks.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        f1 = bdir / f"{one}.bookmark.json"
        f1.write_text(f1.read_text(encoding="utf-8") + " ", encoding="utf-8")         # the author's own edit
        before = f1.read_bytes()
        self._relayout(lf, lambda lay: lay["pages"]["P1"]["bookmarks"][0].update(hide=["P1-V03"]))
        r = pbik("build", rep, lf)
        self.assertIn("sits in Desktop group 'Author group': left alone", r.stdout)
        self.assertEqual(f1.read_bytes(), before)
        meta = json.loads((bdir / "bookmarks.json").read_text(encoding="utf-8"))
        self.assertEqual([it["name"] for it in meta["items"]].count(one), 0, "not listed twice")
        self.assertEqual(meta["items"][0]["children"], [one])
        # a visual Desktop added (no ID): roundtrip proposes an ID and alt text, --name-new applies them
        src = Report(rep).visual_by_id("P1-V04")[0]
        page = src.parent.parent.parent
        new = page / "visuals" / "a1b2c3d4e5f6a7b8c9d0"
        new.mkdir()
        nd = json.loads(src.read_text(encoding="utf-8"))
        nd["name"] = "a1b2c3d4e5f6a7b8c9d0"
        nd["visual"].pop("visualContainerObjects", None)
        (new / "visual.json").write_text(json.dumps(nd, indent=2), encoding="utf-8")
        r = pbik("roundtrip", rep, "--before", rep, "--layout", lf)
        self.assertIn("Visuals without an ID", r.stdout)
        self.assertIn("Bar chart of Revenue by City, Store", r.stdout)
        self.assertTrue(new.exists(), "read-only without --name-new")
        r = pbik("roundtrip", rep, "--before", rep, "--layout", lf, "--name-new")
        nid = r.stdout.split("| a1b2c3d4e5f6a7b8c9d0 | ")[1].split(" ")[0]
        self.assertFalse(new.exists())
        named = Report(rep).visual_by_id(nid)
        self.assertEqual(len(named), 1)
        self.assertIn("Bar chart of Revenue", named[0].read_text(encoding="utf-8"))
        self.assertNotIn("visual has no ID", pbik("validate", rep, ok=(0, 1)).stdout)


class VersionTests(unittest.TestCase):
    """Target Desktop resolution from Microsoft's published schema CHANGELOGs and Desktop update archive."""
    CHANGELOG = ("# Visual Container Versions\n\n### 2.13.0\n\n<b>Released in: </b> September 2026 <br />\n"
                 "<b>Notes: </b>\n- x\n\n### 2.12.0\n<b>Released in: </b> August 2026 <br />\n"
                 "### 2.7.0\n<b>Released in: </b> March 2026 <br />\n### 1.0.0\n<b>Released in: </b> June 2024 <br />\n")
    ARCHIVE = ('<h2 id="july-2026-update-version-21569510">July 2026 update (version 2.156.951.0)</h2>'
               '<h2 id="may-2026">May 2026 update (version 2.154.1260)</h2>'
               '<h2 id="march-2026">March 2026 update (version 2.152.882.0)</h2>'
               '<h2 id="january-2026-update">January 2026 update</h2>'
               '<h2 id="october-2025">October 2025 update (version 2.148.1226.0)</h2>'
               '<h2 id="july-2025">July 2025 update (2.145.1105.0)</h2><h2>Past updates</h2>')

    def support(self):
        from pbikit import versions as V
        return {"kinds": {"visualContainer": [{"version": v, "released": m}
                                              for v, m in V.parse_changelog(self.CHANGELOG)]},
                "desktop": [{"version": v, "released": m} for v, m in V.parse_desktop_archive(self.ARCHIVE)]}

    def test_parse_microsoft_pages(self):
        from pbikit import versions as V
        self.assertEqual(V.parse_changelog(self.CHANGELOG), [("2.13.0", "2026-09"), ("2.12.0", "2026-08"),
                                                             ("2.7.0", "2026-03"), ("1.0.0", "2024-06")])
        rel = V.parse_desktop_archive(self.ARCHIVE)
        self.assertEqual(rel[0], ("2.156.951.0", "2026-07"))
        self.assertIn(("2.145.1105.0", "2025-07"), rel, "headings without the word 'version'")
        self.assertEqual(len(rel), 5, "January 2026 has no version: skipped")

    def test_target_resolution(self):
        from pbikit import versions as V
        s = self.support()
        self.assertEqual(V.Target("2.152.882.0", s).cap("visualContainer"), "2.7.0")
        self.assertEqual(V.Target("2.156", s).cap("visualContainer"), "2.7.0", "nothing between March and July")
        t = V.Target("2.153.910.0", s)                  # not listed: the release before (March 2026)
        self.assertEqual((t.month, t.cap("visualContainer")), ("2026-03", "2.7.0"))
        self.assertIn("isn't listed", t.note)
        self.assertEqual(V.Target("2.150.1.0", s).month, "2025-10", "an unlisted month takes the earlier release")
        for unpinned in ("latest", "LATEST", "2.159.883.0"):
            self.assertIsNone(V.Target(unpinned, s).cap("visualContainer"), unpinned)
        with self.assertRaises(ValueError):
            V.Target("2.100.1.0", s)
        with self.assertRaises(ValueError):
            V.Target("March 2026", s)
        self.assertIsNone(V.Target("2.152.882.0", {"kinds": {}, "desktop": []}).cap("visualContainer"),
                          "no support data: not pinned")

    def test_capped_url(self):
        from pbikit import versions as V
        t = V.Target("2.145.1105.0", self.support())     # July 2025: no visualContainer between 1.0.0 and 2.7.0
        url = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"
        self.assertEqual(V.capped_url(url, t), url.replace("2.13.0", "1.0.0"))
        self.assertEqual(V.capped_url(url.replace("2.13.0", "1.0.0"), t), url.replace("2.13.0", "1.0.0"))
        page = url.replace("visualContainer/2.13.0", "page/2.1.0")
        self.assertEqual(V.capped_url(page, t), page, "a kind without support data is left alone")
        self.assertEqual(V.capped_url(url, V.Target("latest", self.support())), url)

    def test_refresh_offline(self):
        from pbikit import versions as V
        pages = {V.ARCHIVE: self.ARCHIVE}

        def get(url):
            if url in pages:
                return pages[url]
            if "visualContainer" in url:
                return self.CHANGELOG
            raise OSError("404")
        with tempfile.TemporaryDirectory() as d:
            out, failed = V.refresh(pathlib.Path(d) / "s.json", get=get)
            self.assertEqual([r["version"] for r in out["kinds"]["visualContainer"]], ["1.0.0", "2.7.0", "2.12.0", "2.13.0"])
            self.assertEqual(len(failed), len(V.KINDS) - 1)
            self.assertEqual(out["desktop"][0]["version"], "2.156.951.0")

    def test_kit_support_file_is_current(self):
        """tools/pbik/schema-support.json covers every kind pbik writes, and the versions DEFAULT_VERSIONS uses."""
        from pbikit import versions as V
        from pbikit.report import DEFAULT_VERSIONS
        s = V.load_support()
        for kind, v in DEFAULT_VERSIONS.items():
            self.assertIn(v, [r["version"] for r in s["kinds"].get(kind, [])], kind)
        self.assertTrue(s["desktop"], "pbik schemas support --refresh")


if __name__ == "__main__":
    unittest.main(verbosity=2)
