"""A clean, empty report folder for a new project (walkthrough fix 1, v1.7).

`pbik build` calls `ensure()` when the report folder it is given doesn't exist yet: it writes `<Name>.Report` with no
pages, linked to `<Name>.SemanticModel` beside it, and `<Name>.pbip`, from the files in tools/pbik/skeleton/ (the
base theme Desktop writes) and the shapes Desktop saved in the kit's fixtures. Nothing is copied from an old report:
no pages, visuals, custom theme, bookmarks or resources. An existing folder is never touched.
"""
import json, pathlib, uuid

SKELETON = pathlib.Path(__file__).resolve().parents[1] / "skeleton"
BASE_THEME = "Fluent2-CY26SU09"
AT_IMPORT = {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}
SCHEMAS = "https://developer.microsoft.com/json-schemas/fabric/"


def report_folder(path):
    """'Orders Overview', 'Orders Overview.pbip' or 'Orders Overview.Report' -> the .Report folder path."""
    p = pathlib.Path(path)
    if p.suffix.lower() == ".pbip":
        return p.with_suffix(".Report")
    if p.name.endswith(".Report"):
        return p
    return p.with_name(p.name + ".Report")


def _write(f, doc):
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def create(folder, model=None):
    """Write an empty report at `folder` (a .Report path that doesn't exist). Returns the files written."""
    folder = pathlib.Path(folder)
    if folder.exists():
        raise FileExistsError(f"{folder.name} already exists")
    name = folder.name[:-len(".Report")]
    model = model or f"{name}.SemanticModel"
    defn = folder / "definition"
    files = {
        folder / ".platform": {
            "$schema": SCHEMAS + "gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Report", "displayName": name},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"pbik-report/{name}"))}},
        folder / "definition.pbir": {
            "$schema": SCHEMAS + "item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0", "datasetReference": {"byPath": {"path": f"../{model}"}}},
        defn / "version.json": {
            "$schema": SCHEMAS + "item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
        defn / "report.json": {
            "$schema": SCHEMAS + "item/report/definition/report/3.3.0/schema.json",
            "themeCollection": {"baseTheme": {"name": BASE_THEME, "reportVersionAtImport": dict(AT_IMPORT),
                                              "type": "SharedResources"}},
            "objects": {"section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}],
                        "outspacePane": [{"properties": {"expanded": {"expr": {"Literal": {"Value": "false"}}}}}]},
            "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                                  "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json",
                                             "type": "BaseTheme"}]}],
            "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                         "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                         "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}},
        defn / "pages" / "pages.json": {
            "$schema": SCHEMAS + "item/report/definition/pagesMetadata/1.1.0/schema.json", "pageOrder": []},
    }
    written = []
    for f, doc in files.items():
        _write(f, doc)
        written.append(f)
    theme = folder / "StaticResources" / "SharedResources" / "BaseThemes" / f"{BASE_THEME}.json"
    theme.parent.mkdir(parents=True, exist_ok=True)
    theme.write_bytes((SKELETON / f"{BASE_THEME}.json").read_bytes())
    written.append(theme)
    pbip = folder.with_suffix(".pbip")
    if not pbip.exists():
        _write(pbip, {"$schema": SCHEMAS + "pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
                      "artifacts": [{"report": {"path": folder.name}}], "settings": {"enableAutoRecovery": True}})
        written.append(pbip)
    return written


def ensure(path, quiet=False):
    """The report folder for `path`, made empty and clean if it doesn't exist. Returns (folder, made)."""
    p = pathlib.Path(path)
    if (p / "definition").is_dir():
        return p, False
    folder = report_folder(p)
    if (folder / "definition").is_dir():
        return folder, False
    if folder.exists():                   # a folder without definition/: not ours to fill
        return folder, False
    create(folder)
    if not quiet:
        print(f"made a new, empty report: {folder.name} (no pages yet; linked to {folder.name[:-7]}.SemanticModel)")
    return folder, True
