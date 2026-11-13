"""Layout rules (batch 3 items 10, 11 and 14) on made-up sample pages.

    python tools\\pbik\\tests\\test_layout_rules.py
"""
import json, pathlib, shutil, struct, sys, tempfile, unittest, zlib

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(KIT / "design" / "scripts"))

import bind_sample  # noqa: E402
NL = chr(10)
from pbikit import kpicards as KC  # noqa: E402


def card(folder, x, y, w, h, z=1000, bg=True):
    d = {"position": {"x": x, "y": y, "z": z, "width": w, "height": h}, "visual": {"visualType": "cardVisual"}}
    if not bg:
        d["visual"]["visualContainerObjects"] = {"background": [{"properties": {"show": {"expr": {"Literal": {
            "Value": "false"}}}}}]}
    return folder, d


def other(folder, vtype, x, y, w, h, z=0):
    return folder, {"position": {"x": x, "y": y, "z": z, "width": w, "height": h}, "visual": {"visualType": vtype}}


def kpi_row(y=32, w=446, gap=24, n=4, h=150):
    return [card(f"P1-V0{k + 1}_kpi-{k}", 32 + k * (w + gap), y, w, h) for k in range(n)]


def png(path, w, h, pixel):
    """A tiny RGB PNG written with the standard library; pixel(x, y) -> (r, g, b)."""
    raw = b"".join(b"\x00" + bytes(c for x in range(w) for c in pixel(x, y)) for y in range(h))
    chunk = lambda t, b: struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)  # noqa
    pathlib.Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                                   + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class KpiCardTests(unittest.TestCase):
    """Item 10: the card is the container; rows equal, spanning the content width, lined up with the row below."""

    def test_a_good_row_passes(self):
        vis = kpi_row() + [other("P1-V05_chart", "lineChart", 32, 206, 1856, 400)]
        self.assertEqual(KC.check_page("Overview", vis, 1920), [])

    def test_row_rules(self):
        row = kpi_row()
        row[3][1]["position"]["width"] = 440                      # right edge 1882, not 1888
        row[2][1]["position"]["x"] += 5
        w = KC.check_page("Overview", row, 1920)
        self.assertTrue(any("differ in size" in x for x in w))
        self.assertTrue(any("gaps differ" in x for x in w))
        self.assertTrue(any("content width" in x for x in w))
        short = kpi_row(w=400) + [other("P1-V05_chart", "lineChart", 32, 206, 1856, 400)]
        w = KC.check_page("Overview", short, 1920)
        self.assertTrue(any("line up with the row below" in x for x in w))

    def test_the_card_is_the_container(self):
        vis = kpi_row() + [other("P1-V09_card-bg", "shape", 28, 28, 454, 158)]
        self.assertTrue(any("sits behind the KPI card" in x for x in KC.check_page("Overview", vis, 1920)))
        exact = kpi_row() + [other("P1-V09_card-bg", "shape", 32.5, 32, 446, 150.5)]
        self.assertEqual(KC.check_page("Overview", exact, 1920), [], "a shape matching within 1px is allowed")
        off = [card("P1-V01_kpi-a", 32, 32, 1856, 150, bg=False)]
        self.assertTrue(any("container background off" in x for x in KC.check_page("Overview", off, 1920)))
        self.assertEqual(KC.check_page("Overview", [card("P1-V01_total", 32, 32, 900, 150, bg=False)], 1920), [],
                         "not a KPI card")

    def test_background_shapes_keep_layer_order(self):
        panel = other("P1-V09_panel", "shape", 16, 16, 1888, 300, z=0)
        vis = kpi_row() + [panel]
        self.assertTrue(any("without keepLayerOrder" in x for x in KC.layer_order("Overview", vis)))
        panel[1]["visual"]["visualContainerObjects"] = {"general": [{"properties": {"keepLayerOrder": {"expr": {
            "Literal": {"Value": "true"}}}}}]}
        self.assertEqual(KC.layer_order("Overview", vis), [])
        lessons = (KIT / "docs/lessons/cards.md").read_text(encoding="utf-8")
        for lid in ("C-07", "C-10", "C-11"):
            self.assertIn(f"## {lid} ", lessons)
        self.assertIn("Open: does card padding work?", (KIT / "design/known-gaps.md").read_text(encoding="utf-8"))

    def test_empty_space_in_a_screenshot(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            white, ink = (255, 255, 255), (30, 40, 50)
            # page 400 wide at scale 1: one card at 0,0 200x100 with text only in its top quarter, one filled
            png(tmp / "p.png", 400, 100, lambda x, y: ink if (x < 200 and 10 <= y <= 25 and 20 <= x <= 150) or
                (x >= 200 and 12 <= y <= 88 and 220 <= x <= 380 and y % 6 < 3) else white)
            flags = KC.empty_space(tmp / "p.png", [("top-heavy", 0, 0, 200, 100), ("filled", 200, 0, 200, 100)], 400)
            self.assertEqual([f[0] for f in flags], ["top-heavy"])
            self.assertEqual(flags[0][2], "height")
            w, h, px = KC.read_png(tmp / "p.png")
            self.assertEqual((w, h, px[15][30]), (400, 100, ink))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_screenshot_check_is_synthetic_or_sample_only(self):
        import card_space
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "M.SemanticModel" / "definition").mkdir(parents=True)
            (tmp / "M.SemanticModel" / "definition" / "model.tmdl").write_text("model Model\n", encoding="utf-8")
            rep = bind_sample.make_report(tmp, "M.SemanticModel")
            png(tmp / "p.png", 4, 4, lambda x, y: (255, 255, 255))
            self.assertEqual(card_space.run(rep, "Sample", tmp / "p.png")[0], 2)
            (tmp / "M.SemanticModel" / "definition" / "model.tmdl").write_text(
                "model Model\n\nannotation PBIK_Synthetic = 1\n", encoding="utf-8")
            self.assertEqual(card_space.run(rep, "Sample", tmp / "p.png")[0], 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_kpi_delta_card_template_follows_the_rule(self):
        t = json.loads((KIT / "design/templates/cardVisual.kpi-delta-card.json").read_text(encoding="utf-8"))
        self.assertTrue(KC.is_kpi("P1-V01_kpi", t, {"template": "cardVisual.kpi-delta-card"}))
        self.assertTrue(KC.own_container(t))
        vco = t["visual"]["visualContainerObjects"]
        for k in ("background", "border", "dropShadow"):
            self.assertEqual(vco[k][0]["properties"]["show"]["expr"]["Literal"]["Value"], "true", k)
        self.assertIn("radius", vco["border"][0]["properties"])
        self.assertIn("calloutSize", t["visual"]["objects"]["layout"][0]["properties"])
        self.assertNotIn("referenceLabel", t["visual"]["objects"], "no field-bound entries in a template")
        idx = json.loads((KIT / "design/templates/index.json").read_text(encoding="utf-8"))
        self.assertIn("cardVisual.kpi-delta-card", idx["templates"])


class PatternChoicesTests(unittest.TestCase):
    """Item 14: audit_ids' Pattern choices check warns for older specs and fails new ones; canvas.height option."""
    LAYOUT = {"pages": {"P1": {"displayName": "Overview"}, "P2": {"displayName": "Detail"}}}
    GOOD = NL.join(["# Spec", "", "## Pattern choices", "", "| Page | Patterns | Style preset | Reason |",
                    "| --- | --- | --- | --- |",
                    "| Overview | range-band, freshness-line | clean | sample months have a usual range |",
                    "| P2 | none | clean | a plain detail table |", "", "## Fallback register", ""])

    def test_section(self):
        import datetime, pattern_choices as PC
        self.assertEqual(PC.check(self.GOOD, self.LAYOUT), ([], []))
        missing = NL.join(["# Spec", "", "## Fallback register", ""])
        issues, warns = PC.check(missing, self.LAYOUT, datetime.date(2026, 10, 1))
        self.assertEqual(issues, [])
        self.assertIn("before the section existed", warns[0])
        issues, warns = PC.check(missing, self.LAYOUT, datetime.date(2026, 11, 20))
        self.assertTrue(issues and not warns)
        self.assertTrue(PC.check(missing, self.LAYOUT, None)[0], "a spec not committed yet is new")
        bad = self.GOOD.replace("range-band", "spiral").replace("| P2 | none | clean |", "| P2 | none | neon |")
        issues = PC.check(bad, self.LAYOUT)[0]
        self.assertTrue(any("unknown pattern" in x for x in issues))
        self.assertTrue(any("style preset 'neon'" in x for x in issues))
        self.assertTrue(any("no row for page P2" in x for x in PC.check(self.GOOD.replace("| P2 |", "| P9 |"),
                                                                         self.LAYOUT)[0]))

    def test_canvas_height(self):
        import ref_layout as RL
        self.assertEqual(RL.canvas_height({"canvas": {"width": 1920}}), 1080)
        self.assertEqual(RL.canvas_height({"canvas": {"height": 1440}}), 1440)


if __name__ == "__main__":
    unittest.main(verbosity=2)
