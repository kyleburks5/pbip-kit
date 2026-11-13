"""Generate design/themes/pbip-polish.json (Power BI report theme) from design/tokens.json.

Font sizes come from tokens.fontPt (points); colors and container styling from tokens.colors / tokens.container.
tokens.chart.series (colour names, optional) sets the series order after any region colours.
Region colors (tokens.regionColors, optional) lead dataColors when present: the mains in card order, then the tints,
so visuals can reference them by theme index (see REGION_INDEX). Without them dataColors starts at colors.primary.
Apply with:
    python tools/pbik/pbik.py theme apply "<name>.Report" design/themes/pbip-polish.json
Options: --tokens (default design/tokens.json), --out (default design/themes/pbip-polish.json).
"""
import argparse, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]  # design/scripts/ -> project root
_ap = argparse.ArgumentParser(description="Power BI theme from tokens.json")
_ap.add_argument("--tokens", default=str(ROOT / "design" / "tokens.json"))
_ap.add_argument("--out", default=str(ROOT / "design" / "themes" / "pbip-polish.json"))
ARGS = _ap.parse_args()
T = json.loads(pathlib.Path(ARGS.tokens).read_text(encoding="utf-8"))
C, F, P, K = T["colors"], T["font"], T["fontPt"], T["container"]
REGIONS = {k: v for k, v in T.get("regionColors", {}).items() if not k.startswith("_")}

# dataColors index of each region's main and tint (0-based). A ThemeDataColor reference uses ColorId = index + 2
# (ColorId 0 and 1 are the theme background and foreground; Desktop check 2026-10-18).
REGION_INDEX = {r: {"main": i, "tint": len(REGIONS) + i} for i, r in enumerate(REGIONS)}

FONT = F["family"]
SEMIBOLD = f"{FONT} Semibold"


def solid(hex_):
    return {"solid": {"color": hex_}}


def css_shadow(s):
    """Parse '0 2px 8px rgba(0,0,0,0.12)' into Power BI drop shadow settings."""
    x, y, blur = (float(v.replace("px", "")) for v in s.split("rgba")[0].split()[:3])
    r, g, b, a = (float(v) for v in re.search(r"rgba\(([^)]+)\)", s).group(1).split(","))
    return {
        "show": True,
        "color": solid("#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))),
        "position": "Outer",
        "preset": "Custom",
        "shadowSpread": 0,
        "shadowBlur": blur,
        "shadowDistance": (x ** 2 + y ** 2) ** 0.5,
        "angle": 90,  # straight down (CSS x-offset 0, positive y)
        "transparency": round((1 - a) * 100),
    }


axis = {
    "fontFamily": FONT,
    "fontSize": P["caption"],
    "labelColor": solid(C["textMuted"]),
    "showAxisTitle": False,
    "gridlineColor": solid(C["border"]),
}
legend = {
    "show": True,
    "position": "TopRight",
    "fontFamily": FONT,
    "fontSize": P["caption"],
    "labelColor": solid(C["textMuted"]),
    "showTitle": False,
}
pad = K["padding"]

theme = {
    "name": "pbip-polish",
    "dataColors": [v["main"] for v in REGIONS.values()] + [v["tint"] for v in REGIONS.values()]
                  + ([C[n] for n in T["chart"]["series"]] if "chart" in T  # Rep 3: series order from tokens.chart
                     else [C["primary"], C["textMuted"], C["accent"], C["good"], C["warning"], C["bad"]]),
    "foreground": C["text"],
    "foregroundNeutralSecondary": C["textMuted"],
    "foregroundNeutralTertiary": C["textMuted"],
    "background": C["card"],
    "backgroundLight": C["background"],
    "backgroundNeutral": C["border"],
    "tableAccent": C["primary"],
    "good": C["good"],
    "bad": C["bad"],
    "neutral": C["warning"],
    "textClasses": {
        # Rep 2: the report title is regular weight and near-black, as in the reference.
        "largeTitle": {"fontFace": FONT, "fontSize": P["title"], "color": C["text"]},
        "title": {"fontFace": SEMIBOLD, "fontSize": P["cardTitle"], "color": C["text"]},
        "header": {"fontFace": SEMIBOLD, "fontSize": P["body"], "color": C["text"]},
        "callout": {"fontFace": SEMIBOLD, "fontSize": P["kpi"], "color": C["text"]},
        "label": {"fontFace": FONT, "fontSize": P["body"], "color": C["text"]},
        "smallLabel": {"fontFace": FONT, "fontSize": P["caption"], "color": C["textMuted"]},
        "lightLabel": {"fontFace": FONT, "fontSize": P["body"], "color": C["textMuted"]},
    },
    "visualStyles": {
        # Rep 2: visuals sit inside card shapes, so by default they carry no container styling of their own.
        "*": {"*": {
            "background": [{"show": False}],
            "border": [{"show": False}],
            "dropShadow": [{"show": False}],
            "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}],
            "title": [{"show": False, "fontFamily": SEMIBOLD, "fontSize": P["cardTitle"],
                       "fontColor": solid(C["text"]), "alignment": "left"}],
            # batch 4 item 2: no visual header (the hover icons) on any visual type; validate flags a visual
            # whose own formatting turns it back on
            "visualHeader": [{"show": False}],
        }},
        # Region card backgrounds: white, 1px border, rounded corners, shadow token. The sidebar shape overrides
        # fill/outline/shadow per visual.
        "shape": {"*": {
            "fill": [{"show": True, "fillColor": solid(C["card"]), "transparency": 0}],
            "outline": [{"show": True, "lineColor": solid(C["border"]), "weight": K["borderWidth"], "transparency": 0}],
            "shape": [{"tileShape": "rectangleRoundedByPixel", "rectangleRoundedCurve": K["radius"]}],
            "dropShadow": [css_shadow(K["shadow"])],
        }},
        "page": {"*": {
            "background": [{"color": solid(C["background"]), "transparency": 0}],
            "outspace": [{"color": solid(C["background"]), "transparency": 0}],
        }},
        # Title text box sits directly on the page background (see wireframe header).
        "textbox": {"*": {
            "background": [{"show": False}],
            "border": [{"show": False}],
            "dropShadow": [{"show": False}],
            "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}],
            "title": [{"show": False}],
        }},
        # Rep 2 Year dropdown: no header or title, the selected year in label size.
        "slicer": {"*": {
            "title": [{"show": False}],
            # Rep 2: the Year dropdown is a white box with a 1px border on the page background.
            "background": [{"show": True, "color": solid(C["card"]), "transparency": 0}],
            "border": [{"show": True, "color": solid(C["border"]), "width": K["borderWidth"], "radius": 0}],
            "header": [{"show": False, "fontFamily": FONT, "textSize": P["caption"],
                        "fontColor": solid(C["textMuted"]), "bold": False}],
            "items": [{"fontFamily": FONT, "textSize": P["label"], "fontColor": solid(C["text"])}],
            "data": [{"mode": "Dropdown"}],
        }},
        # KPI cards: muted label above a large value; reference label shows only "vs prior year" + YoY detail.
        # Per-field card objects need the "default" selector ($id) to apply.
        "cardVisual": {"*": {
            "title": [{"show": False}],
            # Deviation from tokens: label + 30pt value + reference label need ~108px; with 20px vertical
            # padding the reference label's descenders clip (verified in Desktop). Keep 20px on the sides.
            # One "padding" key holds both the container padding and the card's internal padding ($id default).
            "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0},
                        {"$id": "default", "paddingSelection": "Custom", "paddingUniform": 0}],
            "divider": [{"$id": "default", "show": False}],
            "outline": [{"$id": "default", "show": False}],
            "cardCalloutArea": [{"$id": "default", "paddingUniform": 0}],
            # Callout (label + value) gets most of the height; the default leaves the label clipped
            # and empty space under the reference label.
            "layout": [{"calloutSize": 75}],
            "spacing": [{"$id": "default", "verticalSpacing": 4}],
            "referenceLabel": [{"$id": "default", "backgroundShow": False, "paddingUniform": 0}],
            "label": [{"$id": "default", "show": True, "position": "aboveValue", "horizontalAlignment": "left",
                       "fontFamily": FONT, "fontSize": P["label"], "fontColor": solid(C["text"])}],
            "value": [{"$id": "default", "horizontalAlignment": "left", "fontFamily": SEMIBOLD, "fontSize": P["kpi"],
                       "fontColor": solid(C["text"]), "labelDisplayUnits": 1}],  # Rep 2: measures carry their own formats
            "referenceLabelLayout": [{"$id": "default", "position": "below", "horizontalAlignment": "left",
                                      "style": "sentence", "customizePadding": True, "outerPadding": 0,
                                      "paddingBeforeDivider": 0, "paddingAfterDivider": 0}],
            # Trend line at body size (Rep 1 review: caption size was too small to read).
            # Rep 2: "PY: 597.4M" in body text, then the pill (detail) beside it.
            "referenceLabelTitle": [{"$id": "default", "show": True, "titleFontFamily": FONT,
                                     "titleFontSize": P["caption"], "titleFontColor": solid(C["text"])}],
            "referenceLabelValue": [{"$id": "default", "show": True, "valueFontFamily": FONT, "valueFontSize": P["caption"],
                                     "valueFontColor": solid(C["text"]), "valueDisplayUnits": 1}],
            # No detailFontColor here: the per-card good/bad/neutral color must not be shadowed by a theme color.
            # Rep 2: caption-size reference line in the 176px callouts; the pill never wraps mid-text.
            "referenceLabelDetail": [{"$id": "default", "show": True, "detailFontFamily": FONT,
                                      "detailFontSize": P["caption"], "textWrap": False}],
        }},
        # Detail table: muted semibold caption headers, body-size values, horizontal rules only, no banding/totals.
        "tableEx": {"*": {
            "columnHeaders": [{"alignment": "Auto",  # text headers left, numeric headers right (match values)
                               "fontFamily": SEMIBOLD, "fontSize": P["caption"], "fontColor": solid(C["textMuted"]),
                               "backColor": solid(C["card"]), "outlineColor": solid(C["border"]),
                               "outlineStyle": 2}],  # 2 = bottom only
            "values": [{"fontFamily": FONT, "fontSize": P["body"], "wordWrap": False, "fontColorPrimary": solid(C["text"]),
                        "fontColorSecondary": solid(C["text"]), "backColorPrimary": solid(C["card"]),
                        "backColorSecondary": solid(C["card"])}],
            "grid": [{"gridHorizontal": True, "gridHorizontalColor": solid(C["border"]), "gridHorizontalWeight": 1,
                      "gridVertical": False, "outlineColor": solid(C["border"]), "rowPadding": 6}],
            "total": [{"totals": False}],
        }},
        "lineChart": {"*": {
            "categoryAxis": [{**axis, "gridlineShow": False}],
            # Rep 2: Auto display units (52M / 12.5M / 60K), no gridlines or legend.
            "valueAxis": [{**axis, "gridlineShow": False}],
            "legend": [{"show": False}],
        }},
        "clusteredBarChart": {"*": {
            "categoryAxis": [{**axis, "fontSize": P["body"], "labelColor": solid(C["text"]), "gridlineShow": False}],
            "valueAxis": [{**axis, "show": False, "gridlineShow": False}],
            "legend": [{"show": False}],
            "labels": [{"show": True, "fontFamily": FONT, "fontSize": P["caption"], "color": solid(C["textMuted"]),
                        "labelDisplayUnits": 1000000, "labelPrecision": 1}],
        }},
    },
}

out = pathlib.Path(ARGS.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(theme, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
