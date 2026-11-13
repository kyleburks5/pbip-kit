# Brushed range selection

`pattern: "brushed-range"`

**Question it answers:** what happens in the period I pick, and how does it compare with the rest?

- **Use when:** a long series (2+ years of days or weeks) whose readers explore sub-periods they pick.
- **Avoid when:** the period choice is always a month, quarter or year (a button slicer is quicker and keyboard-friendly).

## When to use
- A long time series (2+ years of days or weeks) where readers explore sub-periods: an incident, a campaign, a
  season. The selection filters the rest of the page.

## Design
- An overview strip (60-90px high) with the whole series, the selected range highlighted (`tealTint` behind it), and
  the detail visuals below responding to it.
- Show the selected range in words near the headline numbers ("1 Mar - 14 Apr 2026") with a text measure, so the state
  is clear without looking at the strip.

## Build (visual-method ladder)
| Step | How | Draws | Status |
| --- | --- | --- | --- |
| 1 native (pick this) | Slicer `slicerMode: "between"` on `'Date'[Date]` (a range slider) directly above an overview line chart; detail visuals filtered by it | range picked with a slider handle, page filtered | `slicer.data` in the catalog (`data.mode` from the theme, `slicerMode` writes it) |
| 1 native, chart only | Zoom slider on the line chart's x axis | zooms that chart only, filters nothing else | *harvest*; not a page filter, so it rarely answers the question |
| 3 Deneb | Single-layer overview chart with an interval selection (`params: [{"name": "brush", "select": {"type": "interval", "encodings": ["x"]}}]`) | drag directly on the chart; the brush cross-filters the page | **Confirmed in Desktop (v0.4, Rep 10 scratch, 2026-10-24):** with Deneb's "Expose cross-filtering values for dataset rows" on (Deneb editor, Project setup, Cross-filtering; off by default), dragging filtered a card and a bar chart on the page. Not tested with it off, and the Desktop-saved file holds no property for it (only `developer.version` and `vega.version` were added), so pbik can't set it. Keyboard users still need the native slider: keep it as the documented fallback (`fallback`) |

Deneb example (the gallery's P2-V03, and P5-V01 in the v0.4 scratch test), with the between slicer as its fallback:

```json
{"id": "P1-V04", "name": "overview-brush", "page": "P1", "type": "deneb", "pattern": "brushed-range",
 "bindings": {"dataset": ["Games[Year]", "[Athletes]"]},
 "deneb": {"spec": {"data": {"name": "dataset"},
   "params": [{"name": "brush", "select": {"type": "interval", "encodings": ["x"]}}],
   "mark": {"type": "line", "point": true, "color": {"expr": "pbiColor(0)"}},
   "encoding": {"x": {"field": "Year", "type": "quantitative", "scale": {"zero": false}, "axis": {"format": "d"}},
                "y": {"field": "Athletes", "type": "quantitative"}}}},
 "fallback": {"type": "slicer", "slicerMode": "between", "bindings": {"Values": ["Games[Year]"]},
              "container": {"title": "Pick a year range"},
              "build": {"method": "native", "step": 1, "reason": "Between slicer filters the page"}},
 "container": {"title": "Drag across the chart to pick years", "altText": "Athletes per Games; drag to select years"},
 "build": {"method": "deneb", "step": 3, "nativeTried": "Between slicer", "reason": "Brush on the chart"}}
```

After `pbik build`, open the visual in the Deneb editor, check "Expose cross-filtering values for dataset rows" is on,
drag once to confirm the page filters, and save. pbik writes no property for it: the save showed none.

The native slider is keyboard accessible; a brush drawn with a mouse is not. When step 3 is chosen, keep the slider
(smaller) as the accessible path and name it in the spec.

## Measures (sketch)
```dax
Selected range label =
VAR _a = MIN ( 'Date'[Date] ) VAR _b = MAX ( 'Date'[Date] )
RETURN FORMAT ( _a, "d mmm yyyy" ) & " - " & FORMAT ( _b, "d mmm yyyy" )
```

## layout.json example
```json
[{"id": "P1-V03", "name": "date-range", "page": "P1", "type": "slicer", "pattern": "brushed-range",
  "x": 32, "y": 120, "w": 1856, "h": 76, "z": 1, "slicerMode": "between",
  "bindings": {"Values": ["'Date'[Date]"]}, "build": {"method": "native", "step": 1,
  "reason": "Between slicer filters the page and is keyboard accessible"}},
 {"id": "P1-V04", "name": "overview", "page": "P1", "type": "lineChart", "pattern": "brushed-range",
  "x": 32, "y": 196, "w": 1856, "h": 88, "z": 1,
  "bindings": {"Category": ["'Date'[Date]"], "Y": ["[Value]"]},
  "props": {"categoryAxis.show": false, "valueAxis.show": false, "legend.show": false},
  "container": {"title": false, "altText": "Daily value over the whole period; the slider above picks the range"},
  "build": {"method": "native", "step": 1, "reason": "Overview strip for the slider"}}]
```
Give the overview chart an interaction of `NoFilter` from the slider (page `interactions`) if it should keep showing
the whole period while the details follow the selection.

## Wireframe
A slider with two handles over the overview strip, the selected span shaded `tealTint`; the overview line drawn
across. A Deneb overview draws its spec with the brush region shaded.

## Audit
Key values in the default range and in a narrow range (one week), the empty case (a range with no rows), and the
range label text.
