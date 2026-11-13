"""A made-up PBIR report on the synthetic sample model, referencing fields everywhere a report can: visual queries,
sorts, conditional formatting selectors, filters at report, page and visual level, a slicer's stored filter, a
bookmark, a drillthrough page binding, a tooltip page and a report-level measure. No real names or values."""
import json, pathlib

V = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/{}/{}/schema.json"


def col(ent, prop, alias=False):
    return {"Column": {"Expression": {"SourceRef": {"Source" if alias else "Entity": ent}}, "Property": prop}}


def mea(ent, prop, ext=False):
    sr = {"Entity": ent}
    if ext:
        sr["Schema"] = "extension"
    return {"Measure": {"Expression": {"SourceRef": sr}, "Property": prop}}


def proj(field, query_ref, native):
    return {"field": field, "queryRef": query_ref, "nativeQueryRef": native}


def in_filter(alias, ent, prop, values):
    return {"Version": 2, "From": [{"Name": alias, "Entity": ent, "Type": 0}],
            "Where": [{"Condition": {"In": {"Expressions": [col(alias, prop, alias=True)],
                                            "Values": [[{"Literal": {"Value": v}}] for v in values]}}}]}


def visual(name, vtype, x, y, w, h, query, objects=None, filters=None):
    d = {"$schema": V.format("visualContainer", "2.13.0"), "name": name,
         "position": {"x": x, "y": y, "z": 0, "width": w, "height": h},
         "visual": {"visualType": vtype, "query": query, "drillFilterOtherVisuals": True}}
    if objects:
        d["visual"]["objects"] = objects
    if filters:
        d["filterConfig"] = {"filters": filters}
    return d


def write(f, d):
    f = pathlib.Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")


def make_report(root, model_folder, name="Example"):
    rep = pathlib.Path(root) / f"{name}.Report"
    write(rep / "definition.pbir", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                                               "definitionProperties/2.0.0/schema.json", "version": "4.0",
                                    "datasetReference": {"byPath": {"path": f"../{model_folder}"}}})
    d = rep / "definition"
    write(d / "version.json", {"$schema": V.format("versionMetadata", "1.0.0"), "version": "2.0.0"})
    write(d / "report.json", {"$schema": V.format("report", "3.3.0"), "themeCollection": {},
                              "filterConfig": {"filters": [{"name": "rf1", "field": col("Calendar", "Year"),
                                                            "type": "Categorical",
                                                            "filter": in_filter("c", "Calendar", "Year", ["2024L"])}]}})
    write(d / "pages" / "pages.json", {"$schema": V.format("pagesMetadata", "1.1.0"), "pageOrder": ["p1", "p2"],
                                       "activePageName": "p1"})
    write(d / "pages" / "p1" / "page.json", {
        "$schema": V.format("page", "2.1.0"), "name": "p1", "displayName": "Sample", "displayOption": "FitToPage",
        "height": 1080, "width": 1920,
        "filterConfig": {"filters": [{"name": "pf1", "field": col("Area", "Region"), "type": "Categorical",
                                      "filter": in_filter("a", "Area", "Region", ["'Region 1'"])}]}})
    vis = d / "pages" / "p1" / "visuals"
    write(vis / "P1-V01_amount-card" / "visual.json", visual(
        "P1-V01_amount-card", "cardVisual", 32, 32, 444, 160,
        {"queryState": {"Data": {"projections": [proj(mea("_Measures", "Total Amount"), "_Measures.Total Amount",
                                                      "Total Amount")]}}},
        objects={"value": [{"properties": {"fontSize": {"expr": {"Literal": {"Value": "28D"}}}},
                            "selector": {"metadata": "_Measures.Total Amount"}}]}))
    write(vis / "P1-V02_amount-by-month" / "visual.json", visual(
        "P1-V02_amount-by-month", "lineChart", 32, 216, 912, 400,
        {"queryState": {"Category": {"projections": [proj(col("Calendar", "Month"), "Calendar.Month", "Month")]},
                        "Y": {"projections": [
                            proj({"Aggregation": {"Expression": col("Orders", "Amount"), "Function": 0}},
                                 "Sum(Orders.Amount)", "Sum of Amount"),
                            proj(mea("_Measures", "Total Units"), "_Measures.Total Units", "Total Units")]}},
         "sortDefinition": {"sort": [{"field": col("Calendar", "Month"), "direction": "Ascending"}],
                            "isDefaultSort": True}},
        filters=[{"name": "vf1", "field": col("Orders", "Status"), "type": "Categorical",
                  "filter": in_filter("o", "Orders", "Status", ["'Status 1'"])}]))
    write(vis / "P1-V03_option-slicer" / "visual.json", visual(
        "P1-V03_option-slicer", "advancedSlicerVisual", 32, 640, 444, 80,
        {"queryState": {"Values": {"projections": [proj(col("Plan Option", "Option Label"),
                                                        "Plan Option.Option Label", "Option Label")]}}},
        objects={"general": [{"properties": {"filter": {"filter": in_filter("p", "Plan Option", "Option Label",
                                                                            ["'Option Label 1'"])}}}]}))
    write(vis / "P1-V04_ext-card" / "visual.json", visual(
        "P1-V04_ext-card", "cardVisual", 500, 32, 444, 160,
        {"queryState": {"Data": {"projections": [proj(mea("_Measures", "Per Unit", ext=True), "_Measures.Per Unit",
                                                      "Per Unit")]}}}))
    write(d / "pages" / "p2" / "page.json", {
        "$schema": V.format("page", "2.1.0"), "name": "p2", "displayName": "Detail", "displayOption": "FitToPage",
        "height": 1080, "width": 1920, "visibility": "HiddenInViewMode",
        "pageBinding": {"name": "pb2", "type": "Drillthrough", "parameters": [
            {"name": "dp", "boundFilter": "df1", "fieldExpr": col("Area", "Area Name")}]},
        "filterConfig": {"filters": [{"name": "df1", "field": col("Area", "Area Name"), "type": "Categorical",
                                      "howCreated": "Drillthrough"}]}})
    write(d / "pages" / "p2" / "visuals" / "P2-V01_detail" / "visual.json", visual(
        "P2-V01_detail", "tableEx", 32, 32, 900, 600,
        {"queryState": {"Values": {"projections": [proj(col("Area", "Area Name"), "Area.Area Name", "Area Name"),
                                                   proj(mea("_Measures", "Total Amount"), "_Measures.Total Amount",
                                                        "Total Amount")]}}}))
    write(d / "bookmarks" / "bookmarks.json", {"$schema": V.format("bookmarksMetadata", "1.0.0"),
                                               "items": [{"name": "bm1"}]})
    write(d / "bookmarks" / "bm1.bookmark.json", {
        "$schema": V.format("bookmark", "2.1.0"), "name": "bm1", "displayName": "Saved view",
        "explorationState": {"version": "1.3", "activeSection": "p1", "sections": {"p1": {"visualContainers": {
            "P1-V02_amount-by-month": {"filters": {"byExpr": [
                {"name": "vf1", "type": "Categorical", "expression": col("Orders", "Status"),
                 "filter": in_filter("o", "Orders", "Status", ["'Status 2'"])}]}}}}}}})
    write(d / "reportExtensions.json", {"$schema": V.format("reportExtension", "1.0.0"), "name": "extension",
                                        "entities": [{"name": "_Measures", "measures": [
                                            {"name": "Per Unit", "dataType": "Double",
                                             "expression": "DIVIDE ( SUM ( Orders[Amount] ), [Total Units] )"}]}]})
    return rep
