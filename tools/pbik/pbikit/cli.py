"""pbik command line. `pbik <command> --help` for each command's options."""
import argparse, pathlib, sys

from . import __version__


def versions_default():
    return pathlib.Path("design") / "specs" / "project.json"


def main(argv=None):
    """`pbik --report json <command> ...` prints a machine summary (pbikit/summary.py) for the agent."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    argv = _enter_project(argv)
    if argv is None:
        return 2
    if argv[:2] == ["--report", "json"] or argv[:1] == ["--report=json"]:
        rest = argv[2:] if argv[0] == "--report" else argv[1:]
        from . import summary
        words = [a for a in rest if not a.startswith("-")][:2]
        code, text = summary.run_json(" ".join(words), lambda: _main(rest))
        print(text)
        return code
    return _main(argv)


def find_project(name, start=None):
    """A project by name: a folder, or projects/<name> in the current folder, above it, or in the kit."""
    p = pathlib.Path(name)
    if p.is_dir():
        return p.resolve()
    here = pathlib.Path(start or ".").resolve()
    kit = pathlib.Path(__file__).resolve().parents[3]
    for base in [here, *here.parents, kit]:
        cand = base / "projects" / name
        if cand.is_dir():
            return cand
    return None


def _enter_project(argv):
    """`pbik --in <project> ...` (anywhere before the command): run in that project's folder (v1.7, A7)."""
    import os
    for i, a in enumerate(argv):
        if a == "--in" or a.startswith("--in="):
            name = a.split("=", 1)[1] if "=" in a else (argv[i + 1] if i + 1 < len(argv) else "")
            rest = argv[:i] + argv[i + (1 if "=" in a else 2):]
            folder = find_project(name)
            if not folder:
                print(f"pbik: there is no project called {name!r}", file=sys.stderr)
                return None
            os.chdir(folder)
            return rest
        if not a.startswith("-") and a not in ("json",):
            break                                          # --in only before the command
    return argv


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="pbik", description="pbip-kit's PBIR / TMDL tool (Python standard library).")
    ap.add_argument("--version", action="version", version=f"pbik {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("templates", help="visual templates").add_subparsers(dest="sub", required=True)
    h = t.add_parser("harvest", help="copy the visuals on the 'Patterns' page into design/templates/")
    h.add_argument("report")
    h.add_argument("--out", default="design/templates")
    h.add_argument("--page", default="Patterns")

    b = sub.add_parser("build", help="create or update pages and visuals from layout.json")
    b.add_argument("report")
    b.add_argument("layout")
    b.add_argument("--prune", action="store_true", help="remove ID'd visuals that are no longer in layout.json")
    b.add_argument("--reset", action="store_true", help="rebuild every visual from its template")
    b.add_argument("--map", help="ID map file (default: visual-map.json next to layout.json)")
    b.add_argument("--tokens", help="tokens.json (default: design/tokens.json)")
    b.add_argument("--templates", help="templates folder (default: design/templates)")
    b.add_argument("--no-custom-visuals", action="store_true",
                   help="build each Deneb visual's native or SVG `fallback` instead (same ID and folder; "
                        "project.json customVisuals false does the same)")
    b.add_argument("--project", help="project.json (default: next to layout.json): targetDesktop caps $schema versions")
    b.add_argument("--strict", action="store_true",
                   help="a property, setting or value outside Microsoft's cached schema is an error (default: warning)")

    m = sub.add_parser("measure", help="report extension measures").add_subparsers(dest="sub", required=True)
    me = m.add_parser("ext", help="reportExtensions.json measures").add_subparsers(dest="op", required=True)
    a = me.add_parser("add", help="add or update an extension measure")
    a.add_argument("report")
    a.add_argument("name")
    a.add_argument("--expression", required=True)
    a.add_argument("--data-category", help="e.g. ImageUrl (for SVG measures)")
    a.add_argument("--data-type", help="Text (default), Double, Integer, Decimal, Boolean, DateTime")
    a.add_argument("--table", help="home table (default: _Measures)")
    a.add_argument("--format-string")
    a.add_argument("--description")
    ls_ = me.add_parser("list")
    ls_.add_argument("report")
    rm = me.add_parser("remove")
    rm.add_argument("report")
    rm.add_argument("name")

    th = sub.add_parser("theme", help="themes").add_subparsers(dest="sub", required=True)
    ta = th.add_parser("apply", help="register a theme JSON and set it as the custom theme")
    ta.add_argument("report")
    ta.add_argument("theme")

    rs = sub.add_parser("resource", help="registered resources").add_subparsers(dest="sub", required=True)
    ra = rs.add_parser("add", help="register an image once under RegisteredResources")
    ra.add_argument("report")
    ra.add_argument("file")
    ra.add_argument("--name")
    ra.add_argument("--type", default="Image", choices=["Image", "ShapeMap"],
                    help="Image (default) or ShapeMap (a TopoJSON map for the shape map visual; unverified in Desktop)")

    v = sub.add_parser("validate", help="schema checks and kit rules")
    v.add_argument("report")
    v.add_argument("--layout", help="also check visual IDs against this layout.json")
    v.add_argument("--port", help="Desktop model port (or 'auto') for button slicer item counts")
    v.add_argument("--catalog", help="settings catalog file (default: project.json `catalog`, else home)")
    v.add_argument("--no-catalog", action="store_true", help="skip the settings catalog check")
    v.add_argument("--no-a11y", action="store_true", help="skip the accessibility checks")
    v.add_argument("--project", help="project.json (default: <project>/design/specs/project.json): target and catalog")
    v.add_argument("--strict", action="store_true",
                   help="properties pbik wrote that aren't in Microsoft's cached schema are errors (default: warnings)")

    ca = sub.add_parser("catalog", help="settings Desktop saved").add_subparsers(dest="sub", required=True)
    cr = ca.add_parser("refresh", help="scan Desktop-saved files and merge them into the catalog")
    cr.add_argument("folders", nargs="+", help="project or *.Report folders")
    cr.add_argument("--catalog", help="catalog file (default: --name, else tools/pbik/catalogs/home.json)")
    cr.add_argument("--name", help="named catalog, e.g. home (default) or work (tools/pbik/catalogs/<name>.json)")
    cr.add_argument("--desktop", help="the Desktop version that saved the files (default: detected)")
    cr.add_argument("--all", action="store_true", help="also files Desktop didn't save (with a final newline)")
    cs = ca.add_parser("show", help="print the catalog")
    cs.add_argument("--catalog")
    cs.add_argument("--name", help="named catalog")
    ca.add_parser("list", help="the catalogs, their size and the Desktop version each came from")
    cs.add_argument("--type", help="visual type, or container / page")
    cs.add_argument("--object")

    rt = sub.add_parser("roundtrip", help="what Desktop rewrote on save, as proposed pbik fixes (read-only)")
    rt.add_argument("report")
    rt.add_argument("--rev", help="pbik's files at this git revision (default HEAD)")
    rt.add_argument("--to", help="Desktop's files at this git revision (default: the working tree)")
    rt.add_argument("--before", help="pbik's files from a copy of the report folder instead of git")
    rt.add_argument("--out", help="also write the list to this .md file")
    rt.add_argument("--name-new", action="store_true",
                    help="give visuals Desktop added (no ID) their proposed ID, folder name and alt text (writes)")
    rt.add_argument("--layout", help="layout.json, for retired IDs (default design/specs/layout.json)")

    cp = sub.add_parser("copy", help="copy between reports").add_subparsers(dest="sub", required=True)
    cpp = cp.add_parser("page", help="copy a page (visual IDs renumbered, filter and binding names made unique)")
    cpp.add_argument("source")
    cpp.add_argument("page", help="page name (id) or display name in the source report")
    cpp.add_argument("target")
    cpp.add_argument("--key", required=True, help="the layout page key the copy gets (P<n>): visual IDs move to it")
    cpp.add_argument("--as", dest="as_name", help="display name in the target (default: the same)")
    cpp.add_argument("--bookmarks", action="store_true", help="also copy the bookmarks that belong to that page alone")

    va = sub.add_parser("values", help="model values written into the report files, for a privacy review (read-only)")
    va.add_argument("report")
    va.add_argument("--out", help="also write the list to this .md file")

    i = sub.add_parser("info", help="pages and visuals by ID")
    i.add_argument("report")
    i.add_argument("--json", action="store_true")

    mo = sub.add_parser("model", help="semantic model").add_subparsers(dest="sub", required=True)
    mc = mo.add_parser("check", help="TMDL checks: descriptions, format strings, references, relationships")
    mc.add_argument("model")
    mc.add_argument("--folder", help="only measures in this display folder (e.g. Model)")
    mi = mo.add_parser("intake", help="the model drop folder: delete data files, detect the format, write the contract")
    mi.add_argument("--root", default=".")
    mi.add_argument("--folder", help="drop folder (default design/reference/model)")
    mi.add_argument("--open", action="store_true", help="make the drop folder and open it for the user (reads nothing)")
    mpk = mo.add_parser("packs", help="model packs in the project's pack folders (project.json packFolders)")
    mpk.add_argument("--root", default=".")
    mpk.add_argument("--add-folder", help="remember a pack folder for every project (your own settings, not a file "
                                          "in any repository)")
    mpk.add_argument("--team", action="store_true", help="with --add-folder: it is the team folder")
    mrp = mo.add_parser("rules", help="rules a person made that the kit's rule library could learn")
    mrp.add_argument("--root", default=".")
    mr = mo.add_parser("register", help="save the approved contract, synthetic model and bind map as a model pack")
    mr.add_argument("project")
    mr.add_argument("--to", required=True, help="the packs folder (outside the kit and any git repository)")
    mr.add_argument("--allow-repo", action="store_true",
                    help="allow a git repository that isn't the kit's or the project's (the .gitignore still keeps it out)")
    md = mo.add_parser("drift", help="what changed between a pack and a new TMDL (resolutions pre-filled)")
    md.add_argument("pack")
    md.add_argument("tmdl")
    mp = mo.add_parser("approve", help="person-only: approve the drift, regenerate affected tables, bump the version")
    mp.add_argument("pack")
    mp.add_argument("--by", required=True)

    sc = sub.add_parser("schemas", help="schema cache").add_subparsers(dest="sub", required=True)
    sf = sc.add_parser("fetch", help="download the $schema files a report declares into tools/pbik/schemas/")
    sf.add_argument("report")
    sf.add_argument("--project", help="project.json: also fetch the target Desktop's schema versions")
    sl = sc.add_parser("lower", help="lower every file's $schema to the target Desktop's (project.json), e.g. to open "
                                     "the Patterns report in an older Desktop")
    sl.add_argument("report")
    sl.add_argument("--project", help="project.json (default: <project>/design/specs/project.json)")
    su = sc.add_parser("support", help="PBIR schema versions by Desktop release (tools/pbik/schema-support.json)")
    su.add_argument("--refresh", action="store_true", help="re-read Microsoft's CHANGELOGs and Desktop archive (online)")

    pj = sub.add_parser("project", help="design/specs/project.json: target Desktop and catalog")
    pjs = pj.add_subparsers(dest="sub", required=True)
    ps_ = pjs.add_parser("show", help="target Desktop, its release month, pinned schema versions, catalog")
    ps_.add_argument("--project", default=str(versions_default()))
    pr = pjs.add_parser("record", help="write this machine's Desktop version into project.json (/model)")
    pr.add_argument("--project", default=str(versions_default()))
    pr.add_argument("--version", help="Desktop version (default: detected from the installed Desktop)")
    pc = pjs.add_parser("check", help="installed Desktop against targetDesktop: exit 5 if Desktop is newer "
                                      "(run /update first), 3 if its version can't be found (/build runs it first)")
    pc.add_argument("--project", default=str(versions_default()))
    pc.add_argument("--version", help="Desktop version (default: detected from the installed Desktop)")

    pst = pjs.add_parser("setup", help="first run in a fresh copy of the kit: make this folder the project (Model and "
                                       "Reference folders, data class, status, its own git)")
    pst.add_argument("--root", default=".")
    pst.add_argument("--name", help="the project's name (default: the folder's name)")
    pst.add_argument("--class", dest="cls", default="restricted", choices=["public", "internal", "restricted"])
    pms = pjs.add_parser("master", help="(the maintainer) mark this folder as the master kit, so it is never set up")
    pms.add_argument("--here", action="store_true", required=True)
    pms.add_argument("--root", default=".")
    pin = pjs.add_parser("init", help="a new report project beside the kit: kit copy, git, data class")
    pin.add_argument("name")
    pin.add_argument("--parent", help="folder to create it in (default: beside the kit)")
    pin.add_argument("--class", dest="cls", default="restricted", choices=["public", "internal", "restricted"])
    pin.add_argument("--from-pack", dest="init_pack", help="start from this model pack, at the plan step")
    pnw = pjs.add_parser("new", help="start a project at the plan step from a model pack")
    pnw.add_argument("folder", nargs="?", default=".")
    pnw.add_argument("--from-pack", required=True, help="the pack folder (<packs>/<model>)")
    pcl = pjs.add_parser("class", help="data class: public, internal (default) or restricted (synthetic model only)")
    pcl.add_argument("value", nargs="?", choices=["public", "internal", "restricted"])
    pcl.add_argument("--root", default=".", help="project folder (default: the current folder)")
    pcl.add_argument("--guard", choices=["dax", "screenshot"], help="exit 2 with the reason when this may not run")

    sy = sub.add_parser("synth", help="synthetic model: contract, approval, slice, generate, verify")
    sys_ = sy.add_subparsers(dest="sub", required=True)
    syc = sys_.add_parser("contract", help="contract.json from a TMDL folder or a createOrReplace script")
    syc.add_argument("source")
    syc.add_argument("--root", default=".")
    syc.add_argument("--out")
    syc.add_argument("--no-library", action="store_true", help="don't apply the kit's rule library")
    syr = sys_.add_parser("resolve", help="resolve a flag (or --every flag of a kind) and record the rule")
    syr.add_argument("flag", help="flag ID (F3), or a kind with --every")
    syr.add_argument("resolution")
    syr.add_argument("--why")
    syr.add_argument("--every", action="store_true")
    syr.add_argument("--root", default=".")
    sya = sys_.add_parser("approve", help="person-only: approve the contract and its resolutions")
    sya.add_argument("--by", required=True)
    sya.add_argument("--root", default=".")
    sysl = sys_.add_parser("slice", help="generate.json slice: the fields layout.json and planned measures need")
    sysl.add_argument("layout")
    sysl.add_argument("--root", default=".")
    syg = sys_.add_parser("generate", help="write <name>.SemanticModel (inline DATATABLEs) from the approved contract")
    syg.add_argument("name")
    syg.add_argument("--root", default=".")
    syv = sys_.add_parser("verify", help="the synthetic model against the contract slice")
    syv.add_argument("model")
    syv.add_argument("--root", default=".")

    bi = sub.add_parser("bind", help="synthetic model <-> published model (docs/design/synth-to-live.md)")
    bis = bi.add_subparsers(dest="sub", required=True)
    bic = bis.add_parser("check", help="every field the report uses exists in the contract (through bind-map.json)")
    bic.add_argument("report")
    bic.add_argument("--root", help="project folder (default: the report's)")
    bip = bis.add_parser("prepare", help="planned measures -> report-level measures, values checked")
    bip.add_argument("report")
    bip.add_argument("--root")
    bip.add_argument("--port", help="Desktop port (or auto) of the open synthetic model, to compare values")
    bil = bis.add_parser("live", help="person-only: rewrite references per the map and connect to the published model")
    bil.add_argument("report")
    bil.add_argument("--by", required=True)
    bil.add_argument("--workspace")
    bil.add_argument("--model")
    bil.add_argument("--id", help="semantic model ID, or a link with /datasets/<id>/, /semanticmodels/<id>/, "
                                  "/modeling/<id>/")
    bil.add_argument("--from", dest="from_", help="a Desktop-saved report connected to the model (safest)")
    bil.add_argument("--root")
    bim = bis.add_parser("map", help="design/specs/bind-map.json: synthetic -> live names").add_subparsers(
        dest="op", required=True)
    bmd = bim.add_parser("draft", help="match names the contract lacks to similar contract names")
    bmd.add_argument("report")
    bmd.add_argument("--root")
    bma = bim.add_parser("approve", help="person-only: rerun the check through the map and approve it")
    bma.add_argument("report")
    bma.add_argument("--by", required=True)
    bma.add_argument("--root")
    bpk = bis.add_parser("picker", help="Desktop as the model picker: make and open the folder, or --scan for the pick")
    bpk.add_argument("--root", default=".")
    bpk.add_argument("--open", action="store_true", help="open the folder in File Explorer")
    bpk.add_argument("--scan", action="store_true", help="say which published model the newest pick connects to")
    blo = bis.add_parser("local", help="back to the synthetic model (refuses while Desktop is open)")
    blo.add_argument("report")
    blo.add_argument("--root")
    blo.add_argument("--restore-backup", action="store_true",
                     help="put the whole pre-live backup back (typed 'restore'; changes made while live are lost)")

    sa = sub.add_parser("start", help="the start of a build: what the person gave, and the starter layouts")
    sas = sa.add_subparsers(dest="sub", required=True)
    sad = sas.add_parser("detect", help="what is in the inputs folder, and the path the kit takes")
    sad.add_argument("--root", default=".")
    sai = sas.add_parser("inputs", help="make the Reference folder (never opens File Explorer)")
    sai.add_argument("--root", default=".")
    sac = sas.add_parser("check", help="at the start of every build: what the Model and Reference folders hold, and "
                                       "what is missing, one line each")
    sac.add_argument("--root", default=".")
    sast = sas.add_parser("starters", help="the starter layouts, filled with the model's names")
    sast.add_argument("--root", default=".")
    sast.add_argument("--kpi", action="append", default=[], help="a measure for the next KPI slot (up to 4)")
    sast.add_argument("--date", help="the date field, e.g. Calendar[Date]")
    sast.add_argument("--category", help="the category field, e.g. Region[Name]")
    sast.add_argument("--title")
    pl = sub.add_parser("plan", help="the plan as a picture: drawn pages and a short list")
    pls = pl.add_subparsers(dest="sub", required=True)
    pls_ = pls.add_parser("show", help="draw the plan (design/plan/) and write the short list")
    pls_.add_argument("--root", default=".")
    pls_.add_argument("--layout")
    pls_.add_argument("--purpose", action="append", default=[], help="P1=what the page helps people decide")
    pls_.add_argument("--assume", action="append", default=[], help="an assumption shown in the list")
    plp = pls.add_parser("picture", help="draw any layout (a starter, a draft) as one picture per page")
    plp.add_argument("layout")
    plp.add_argument("--out", required=True)
    plc = pls.add_parser("check", help="before the build: exit 1 if the plan changed after the person's OK")
    plc.add_argument("--root", default=".")
    plc.add_argument("--layout")
    plo = pls.add_parser("open", help="open the plan pictures (or any pictures) beside the chat")
    plo.add_argument("files", nargs="*", help="pictures (default: the plan's page pictures)")
    plo.add_argument("--root", default=".")
    pla = pls.add_parser("approve", help="the person said OK in the chat: record the plan")
    pla.add_argument("--root", default=".")
    pla.add_argument("--layout")
    la = sub.add_parser("layout", help="draft layouts from other sources").add_subparsers(dest="sub", required=True)
    lfr = la.add_parser("from-report", help="an existing report (.Report folder) as a draft layout.json")
    lfr.add_argument("report")
    lfr.add_argument("--out", default="design/specs/layout.reference.json")

    sc_ = sub.add_parser("score", help="the polish score (10 items; target 7 before showing colleagues)")
    sc_.add_argument("report", nargs="?")
    sc_.add_argument("--layout", default="design/specs/layout.json")
    sc_.add_argument("--root", default=".")
    sc_.add_argument("--item", action="append", default=[],
                     help="the agent's own checks: 1=pass (matches the approved picture), 3=pass (KPI cards filled), "
                          "7=pass (interactions working)")
    sc_.add_argument("--final", action="store_true", help="the build's final score: record it in the build history")
    sc_.add_argument("--hand-minutes", type=float, help="the person's hand-polish minutes (wrap-up)")
    md_ = sub.add_parser("mode", help="the build option: guided or quick (no value: the default and why)")
    md_.add_argument("value", nargs="?", choices=["guided", "quick"])
    md_.add_argument("--root", default=".")
    md_.add_argument("--report-type")

    sts = sub.add_parser("status", help="where the project is, in one plain line (design/status.json)")
    sts.add_argument("--root", default=".")
    sts.add_argument("--done", help="mark this stage done (start, model, page purpose, plan, theme, build, checks, "
                                    "polish, result, live, wrap-up)")
    sts.add_argument("--mode", choices=["guided", "quick"])
    sts.add_argument("--path", dest="path_taken", help="the start path (from wireframe, from picture, from report, "
                                                        "starter layouts)")
    sts.add_argument("--report-type")
    sts.add_argument("--pack")
    sts.add_argument("--class", dest="data_class", choices=["public", "internal", "restricted"])
    sts.add_argument("--plan-hash")
    sts.add_argument("--score", type=int)
    sts.add_argument("--json", action="store_true", help="the whole status file")
    sop = sub.add_parser("open", help="open the project folder in File Explorer")
    sop.add_argument("--root", default=".")

    stp = sub.add_parser("step", help="mark a workflow step for token tracking (tools/usage.py)")
    stp.add_argument("event", choices=["start", "end", "note"])
    stp.add_argument("step")
    stp.add_argument("--outcome")
    stp.add_argument("--interaction", action="store_true", help="with note: one reply from the person or one "
                                                                 "approval window (the step names which)")
    stp.add_argument("--root", default=".")
    ga = sub.add_parser("gate", help="person-only steps: an approval window with a typed code (the agent opens it)")
    gas = ga.add_subparsers(dest="sub", required=True)
    gp = gas.add_parser("prepare", help="the agent: write the plain summary of what the person approves")
    gp.add_argument("gate", choices=["synth-approve", "map-approve", "model-approve", "bind-live", "bind-local",
                                     "class-lower", "pack-register"])
    gp.add_argument("--root", default=".")
    gp.add_argument("--report")
    gp.add_argument("--pack")
    gp.add_argument("--from", dest="from_")
    gp.add_argument("--workspace")
    gp.add_argument("--model")
    gp.add_argument("--id", dest="mid")
    gp.add_argument("--to-class", choices=["public", "internal", "restricted"])
    gp.add_argument("--to", help="the team pack folder (pack-register)")
    gr = gas.add_parser("run", help="show the approval window and wait; apply on Yes with the typed code")
    gr.add_argument("gate")
    gr.add_argument("--root", default=".")
    go = gas.add_parser("open", help="the agent: open the approval window in its own process, return at once")
    go.add_argument("gate")
    go.add_argument("--root", default=".")
    gw = gas.add_parser("wait", help="the agent: wait for the person's answer in the approval window")
    gw.add_argument("gate")
    gw.add_argument("--root", default=".")
    gw.add_argument("--minutes", type=float, default=30)
    gt = gas.add_parser("tasks", help="write .vscode/tasks.json (one task per gate)")
    gt.add_argument("--root", default=".")

    dk = sub.add_parser("desktop", help="Power BI Desktop through .claude/scripts/pbi-bridge.ps1")
    dk.add_argument("--bridge", help="path to pbi-bridge.ps1 (default: found above the current folder)")
    ds = dk.add_subparsers(dest="sub", required=True)
    st = ds.add_parser("state")
    st.add_argument("--fail-if-dirty", action="store_true", help="exit 4 when Desktop has unsaved changes")
    rl = ds.add_parser("reload", help="reload the report (not the model); refuses while unsaved")
    rl.add_argument("--force", action="store_true")
    rl.add_argument("--report", help="the report folder (default: the project's one)")
    dcl = ds.add_parser("close", help="close Desktop without saving, only when its only unsaved changes are its own "
                                      "reload marks (else it says why and leaves it open)")
    dcl.add_argument("--report")
    dcl.add_argument("--root", default=".")
    dop = ds.add_parser("open", help="open the project's report in Power BI Desktop")
    dop.add_argument("--root", default=".")
    dop.add_argument("--no-wait", action="store_true", help="return at once instead of waiting until Desktop answers")
    sh = ds.add_parser("screenshot")
    sh.add_argument("--page", required=True, help="page name (id), or display name with --report")
    sh.add_argument("--out", required=True)
    sh.add_argument("--report")
    sh.add_argument("--region", help="x,y,w,h in page units, e.g. 0,0,1920,1080")
    sh.add_argument("--scale", type=int, default=1)

    args = ap.parse_args(argv)
    c = args.cmd
    if c == "templates":
        from .templates import harvest
        harvest(args.report, args.out, args.page)
    elif c == "build":
        from .build import build
        build(args.report, args.layout, prune=args.prune, reset=args.reset, map_path=args.map,
              tokens_path=args.tokens, templates=args.templates, no_custom_visuals=args.no_custom_visuals,
              project=args.project, strict=args.strict)
        from . import desktop as D_
        from .newreport import report_folder
        D_.mark_built(".", args.report if pathlib.Path(args.report, "definition").is_dir() else report_folder(args.report))                   # the agent's own change, for desktop close (D1)
    elif c == "measure":
        from . import extensions as X
        if args.op == "add":
            X.add(args.report, args.name, args.expression, args.data_category, args.data_type, args.table,
                  args.format_string, args.description)
        elif args.op == "list":
            X.list_(args.report)
        else:
            X.remove(args.report, args.name)
    elif c == "theme":
        from .theme import apply
        apply(args.report, args.theme)
    elif c == "resource":
        from .theme import resource_add
        resource_add(args.report, args.file, args.name, args.type)
    elif c == "validate":
        from .validate import validate
        return 1 if validate(args.report, args.layout, port=args.port, catalog=args.catalog,
                             use_catalog=not args.no_catalog, use_a11y=not args.no_a11y,
                             project=args.project, strict_schema=args.strict).errors else 0
    elif c == "catalog":
        from . import catalog as CAT
        if args.sub == "refresh":
            CAT.refresh(args.folders, args.catalog, args.all, args.name, args.desktop)
        elif args.sub == "list":
            CAT.list_catalogs()
        else:
            CAT.show(CAT.catalog_path(args.name, args.catalog), args.type, args.object)
    elif c == "roundtrip":
        from .roundtrip import roundtrip
        roundtrip(args.report, args.rev, args.to, args.before, args.out, args.name_new, args.layout)
    elif c == "copy":
        from .copy import copy_page
        copy_page(args.source, args.page, args.target, args.key, args.as_name, args.bookmarks)
    elif c == "values":
        from .values import values
        values(args.report, args.out)
    elif c == "info":
        from .info import info
        info(args.report, args.json)
    elif c == "model" and args.sub == "packs":
        from . import packs as PK
        if args.add_folder:
            PK.add_pack_folder(args.add_folder, args.team)
            print(f"I'll look for model packs in that {'team ' if args.team else ''}folder in every project.")
        found = PK.list_packs(args.root)
        for name, v, cls, folder, team in found:
            print(f"{name}: version {v}, data class {cls}{' (team folder)' if team else ''}")
        if not found:
            print("no model packs in the pack folders")
    elif c == "model" and args.sub == "rules":
        from . import rules as R
        from .synth import read_json, specs
        props = R.write_proposals(args.root, R.propose(read_json(specs(args.root) / "contract.json") or {}))
        print(f"{len(props)} rule(s) proposed for the library")
    elif c == "model" and args.sub == "intake":
        from . import intake as IN, synth as S3
        if args.open:
            IN.open_drop(args.root)
            print("Put a copy of your semantic model export in the Model folder of this project (never your only "
                  "file), then say done.")
            return 0
        try:
            IN.intake(args.root, args.folder)
        except (IN.IntakeError, S3.ContractError) as e:
            print(f"pbik: {e}", file=sys.stderr)
            return 2
    elif c == "model" and args.sub in ("register", "drift", "approve"):
        from . import dataclass_ as DC, packs as PK, synth as S
        try:
            if args.sub == "register":
                PK.register(args.project, args.to, pathlib.Path(__file__).resolve().parents[3],
                            allow_repo=args.allow_repo)
            elif args.sub == "drift":
                PK.drift(args.pack, args.tmdl)
            else:
                PK.approve(args.pack, args.by)
        except (PK.PackError, S.ContractError, DC.Refused) as e:
            print(f"pbik: {e}", file=sys.stderr)
            return 2
    elif c == "model":
        from .modelcheck import check
        return 1 if check(args.model, args.folder) else 0
    elif c == "project":
        from . import versions as V
        if args.sub == "setup":
            from . import projectsetup as PS
            try:
                PS.setup(args.root, args.name, args.cls)
            except PS.SetupError as e:
                print(f"pbik: {e}", file=sys.stderr)
                return 2
            return 0
        if args.sub == "master":
            from . import projectsetup as PS
            PS.mark_master(args.root)
            print("This folder is marked as the master kit: status says so, and it is never set up as a project.")
            return 0
        if args.sub == "init":
            from . import projectinit as PI, packs as PK
            try:
                PI.init(args.name, args.parent, args.cls, args.init_pack)
            except (PI.InitError, PK.PackError) as e:
                print(f"pbik: {e}", file=sys.stderr)
                return 2
            return 0
        if args.sub == "new":
            from . import packs as PK
            try:
                PK.project_new(args.folder, args.from_pack)
            except PK.PackError as e:
                print(f"pbik: {e}", file=sys.stderr)
                return 2
            return 0
        if args.sub == "class":
            from . import dataclass_ as DC
            if args.guard:
                why = DC.guard(args.root, args.guard)
                print(why or "ok")
                return 2 if why else 0
            if args.value:
                try:
                    old = DC.set_class(args.root, args.value)
                except DC.Refused as e:
                    print(f"pbik: {e}", file=sys.stderr)
                    return 2
                print(f"data class: {old} -> {args.value}")
            else:
                print(f"data class: {DC.data_class(args.root)}")
            return 0
        if args.sub == "show":
            V.show(args.project)
        elif args.sub == "check":
            return V.check(args.project, args.version)
        else:
            V.record(args.project, args.version)
    elif c == "schemas" and args.sub == "lower":
        from . import versions as V
        return V.lower(args.report, args.project)
    elif c == "schemas" and args.sub == "support":
        from . import versions as V
        if args.refresh:
            return 1 if V.refresh()[1] else 0
        V.show_support()
    elif c == "schemas":
        from . import schemas, versions as V
        from .objects import load
        from .report import Report, SCHEMA
        rep = Report(args.report)
        rep.project = args.project
        urls = set()
        for kind in V.KINDS:                      # the target's own versions, so validate can check what pbik writes
            cap = rep.target.cap(kind)
            if cap:
                urls.add(SCHEMA.format(kind, cap))
        for f in list(rep.defn.rglob("*.json")) + [rep.path / "definition.pbir"]:
            if f.exists():
                try:
                    u = load(f).get("$schema")
                except Exception:
                    u = None
                if u:
                    urls.add(u)
        fetched, failed = schemas.fetch(sorted(urls))
        print(f"{len(urls)} declared schema(s); downloaded {len(fetched)} file(s) into {schemas.CACHE}")
        for x in failed:
            print(f"failed: {x}")
        return 1 if failed else 0
    elif c == "synth":
        return synth_cmd(args)
    elif c == "bind":
        return bind_cmd(args)
    elif c == "start":
        from . import start as SR, status as ST
        if args.sub == "detect":
            d = SR.detect(args.root)
            for ln in SR.say(d):
                print(ln)
            ST.update(args.root, done=None, path=d["path"], **({"reportType": d["reportType"]}
                                                               if d["reportType"] else {}))
        elif args.sub == "inputs":
            SR.open_inputs(args.root)
            print("Put a copy of your wireframe, screenshots, requirements or an existing report in the Reference "
                  "folder of this project, then say done.")
        elif args.sub == "check":
            for ln in SR.check(args.root):
                print(ln)
        else:
            fs = SR.write_starters(args.root, args.kpi, args.date, args.category, args.title)
            print(f"{len(fs)} starter layouts: " + ", ".join(SR.STARTER_NAMES.get(f.name.split('.')[0], f.stem)
                                                              for f in fs) + ".")
            print("next: I'll show them as pictures; pick one and change it in plain words")
    elif c == "plan":
        from . import plan as PL
        try:
            if args.sub == "show":
                purposes = dict(x.split("=", 1) for x in args.purpose if "=" in x)
                notes = []
                pngs, text, h = PL.show(args.root, args.layout, purposes, args.assume, notes=notes)
                print(text.rstrip())
                print(f"drew {len(pngs)} page picture(s)")
                for n in notes:
                    print(n)
                print("next: I'll show you the picture; say OK, or what to change")
            elif args.sub == "picture":
                notes = []
                pngs = PL.picture(args.layout, args.out, notes=notes)
                print(f"drew {len(pngs)} page picture(s)")
                for n in notes:
                    print(n)
            elif args.sub == "check":
                if PL.changed_since_approval(args.root, args.layout):
                    ch = PL.changes_since_approval(args.root, args.layout)
                    print("What you approved changed after your OK: " + "; ".join(ch) + ".")
                    print("next: I'll show you the plan picture again before building")
                    return 1
                print("The plan is the one you approved (my own fixes and polish since then don't change it).")
            elif args.sub == "open":
                files = args.files or sorted((pathlib.Path(args.root) / PL.PLAN_DIR).glob("page-*.png"))
                if not files:
                    print("pbik: there are no pictures to open yet", file=sys.stderr)
                    return 2
                how = PL.open_beside(files)
                print(f"Opened {len(files)} picture(s) " + ("beside the chat." if how == "vscode" else
                                                             "in the picture viewer."))
            else:
                PL.approve(args.root, args.layout)
                from . import status as ST
                nxt = ST.read(args.root).get("next")
                print("Plan approved.")
                print(f"next: {ST.PLAIN.get(nxt, nxt)}")
        except PL.PlanError as e:
            print(f"pbik: {e}", file=sys.stderr)
            return 2
    elif c == "layout":
        from . import fromreport as FR
        from .synth import write_json
        try:
            layout, findings, left_out = FR.from_report(args.report)
        except FR.FromReportError as e:
            print(f"pbik: {e}", file=sys.stderr)
            return 2
        write_json(pathlib.Path(args.out), layout)
        print(f"read the report: {len(layout['pages'])} page(s), {len(layout['visuals'])} visual(s)"
              + (f"; left out {len(left_out)}: " + "; ".join(left_out) if left_out else ""))
        for vid, feat, native, _ in findings:
            print(f"note {vid}: {feat}: {native}")
        print("next: I'll turn it into a plan and show it to you as a picture")
    elif c == "score":
        from . import score as SC, status as ST, history as HI, steps as STP
        if args.hand_minutes is not None and not args.report:
            HI.set_hand_minutes(args.hand_minutes)
            print(f"Thanks: {args.hand_minutes:g} minute(s) of hand polish recorded.")
            return 0
        report = args.report or next((str(x) for x in pathlib.Path(args.root).glob("*.Report")), None)
        lf = pathlib.Path(args.root) / args.layout
        if not report or not lf.exists():
            print("pbik: there is no built report or layout to score yet", file=sys.stderr)
            return 2
        import json as _j
        res = SC.compute(report, _j.loads(lf.read_text(encoding="utf-8")), SC.parse_items(args.item))
        st = ST.read(args.root)
        SC.write_review(args.root, res, st.get("mode"))
        for ln in SC.say(res):
            print(ln)
        t_ = SC.total(res)
        ST.update(args.root, score=t_)
        if args.final:
            mins = round(sum((e - s).total_seconds() for _, s, e, _ in STP.windows(args.root)) / 60, 1)
            HI.record(st.get("mode", "guided"), st.get("reportType") or st.get("path"), t_,
                      len(STP.interactions(args.root)), mins, args.hand_minutes)
    elif c == "mode":
        from . import status as ST, history as HI
        st = ST.read(args.root)
        if args.value:
            ST.update(args.root, mode=args.value)
            print(f"Build option: {ST.MODE_WORDS[args.value]}.")
        else:
            rt = args.report_type or st.get("reportType") or st.get("path")
            team = HI.team_default(args.root)
            m, why = HI.default_mode(rt, team)
            print(f"Default build option: {ST.MODE_WORDS[m]} ({why}).")
            if st.get("mode"):
                print(f"next: no question: you chose {ST.MODE_WORDS[st['mode']]} for this project")
            elif HI.read() or team in HI.MODES:
                print(f"next: no question: the plan list says {ST.MODE_WORDS[m]} ({why}); the person can change it "
                      "there")
            else:
                print("next: ask once, with the other questions: guided build or quick build (no earlier build "
                      "on this computer)")
            tip = HI.suggestion(rt)
            if tip:
                print(tip)
    elif c == "status":
        from . import status as ST
        fields = dict(mode=args.mode, path=args.path_taken, reportType=args.report_type, pack=args.pack,
                      dataClass=args.data_class, planHash=args.plan_hash, score=args.score)
        if args.done or any(v is not None for v in fields.values()):
            try:
                ST.update(args.root, done=args.done, **fields)
            except ValueError as e:
                print(f"pbik: {e}", file=sys.stderr)
                return 2
        if args.json:
            import json as _j
            print(_j.dumps(ST.read(args.root), indent=1, ensure_ascii=False))
        else:
            ST.show(args.root)
    elif c == "open":
        import os
        folder = pathlib.Path(args.root).resolve()
        if hasattr(os, "startfile"):
            os.startfile(str(folder))                     # noqa: S606  File Explorer on Windows
        print(f"Opened your project {folder.name} in File Explorer.")
    elif c == "step":
        from . import steps as STP
        if args.event == "note":
            if not args.interaction:
                print("pbik: step note needs --interaction", file=sys.stderr)
                return 2
            STP.interaction(args.root, args.step)
            print(f"interactions so far: {len(STP.interactions(args.root))}")
        else:
            STP.mark(args.root, args.event, args.step, args.outcome)
            print(f"step {args.step}: {args.event}")
    elif c == "gate":
        from . import gates as GT, synth as S2, dataclass_ as DC2
        try:
            if args.sub == "prepare":
                d = GT.prepare(args.gate, args.root, args.report, args.pack, args.from_, args.workspace, args.model,
                               args.mid, args.to_class, args.to)
                print(d["summary"])
                print(f"next: I'll open the approval window ({d['task']}): check it, then click Yes or No")
            elif args.sub == "run":
                GT.run(args.gate, args.root)
            elif args.sub == "open":
                d = GT.open_window(args.gate, args.root)
                print(f"The approval window ({d['task']}) is open in front of your other windows: check it, then "
                      "click Yes or No" + (" (screen control is on, so it also asks for the code in its picture)."
                                           if GT.needs_code() else "."))
                print("next: I'll wait for your answer")
            elif args.sub == "wait":
                r = GT.wait(args.gate, args.root, timeout=args.minutes * 60)
                said = {"approved": f"Approved by {r.get('by')}.", "declined": "Not approved: nothing changed.",
                        "not answered": "No answer in the approval window yet."}
                print(said.get(r["result"], r["result"]) + (f" ({r['why']})" if r.get("why", "no") != "no" else ""))
                return 0 if r["result"] == "approved" else 1
            else:
                from .synth import write_json
                write_json(pathlib.Path(args.root) / ".vscode" / "tasks.json", GT.tasks_json())
                print("wrote .vscode/tasks.json")
        except (GT.GateError, S2.ContractError, DC2.Refused) as e:
            print(f"pbik: {e}", file=sys.stderr)
            return 2
    elif c == "desktop":
        from . import desktop as D
        if args.sub == "state":
            D.state(args.bridge, args.fail_if_dirty)
        elif args.sub == "reload":
            D.reload(args.bridge, args.force, report=args.report)
        elif args.sub == "close":
            why = D.close(args.root, args.report, args.bridge)
            if why:
                print(f"I left Desktop open: {why}. Please close it yourself without saving (File > Close, then "
                      "Don't save) and tell me.")
                return 4
            print("Closed Desktop without saving (it held only its own reload marks).")
            print("next: I'll open the report again")
        elif args.sub == "open":
            import os
            pbip = next(pathlib.Path(args.root).glob("*.pbip"), None)
            if not pbip:
                print("pbik: there is no report in this project yet", file=sys.stderr)
                return 2
            if hasattr(os, "startfile"):
                os.startfile(str(pbip.resolve()))                 # noqa: S606
            import time as _t
            D.opening_file(args.root).parent.mkdir(parents=True, exist_ok=True)
            D.opening_file(args.root).write_text(str(_t.time()), encoding="utf-8")
            print("Opening the report in Power BI Desktop.")
            if not args.no_wait:
                if D.wait_ready(args.bridge):
                    print("Power BI Desktop has the report open.")
                else:
                    print("Power BI Desktop is still opening the report. I'll check again in a moment.")
                    return D.NOT_READY
        else:
            D.screenshot(args.page, args.out, args.report, args.region, args.scale, args.bridge)
    return 0


def bind_cmd(args):
    from . import bind as BD, dataclass_ as DC, synth as S
    try:
        if args.sub == "picker":
            from . import picker as PKR
            if args.scan:
                try:
                    ws, model, mid, _ = PKR.picked(args.root)
                except PKR.PickError as e:
                    print(f"pbik: {e}", file=sys.stderr)
                    return 2
                print(f"picked: model {model!r} in workspace {ws!r}")
                print("Next (the person): Command Palette > Tasks: Run Task > Connect to the live model "
                      "(after the agent runs gate prepare bind-live --from picked)")
            else:
                PKR.prepare(args.root, args.open)
                print("the picker folder is ready: in Power BI Desktop, File > New, Get data > Power BI semantic "
                      "models, pick the model, then save as a Power BI project (.pbip) in that folder and close")
            return 0
        if args.sub == "check":
            r = BD.check(args.report, args.root)
            for x in r.notes:
                print(f"note            {x}")
            for x in r.stale:
                print(f"stale reference {x}")
            for x in r.errors:
                print(f"error           {x}")
            print(f"{len(r.errors)} error(s), {len(r.stale)} stale reference(s), {len(r.notes)} note(s)")
            return 0 if r.ok() else 1
        if args.sub == "prepare":
            query = None
            if args.port:
                query = BD.port_query(args.report, args.port)
            BD.prepare(args.report, args.root, query)
            return 0
        if args.sub == "live":
            BD.live(args.report, args.by, args.workspace, args.model, args.id, args.from_, args.root)
            return 0
        if args.sub == "local":
            BD.local(args.report, args.root, restore_backup=args.restore_backup)
            return 0
        if args.op == "draft":
            m = BD.map_draft(args.report, args.root)
            print(f"bind-map.json drafted: {len(m['tables'])} table(s), {len(m['fields'])} field(s), "
                  f"{len(m['unmatched'])} unmatched. Review it; a person runs `pbik bind map approve --by <name>`")
            return 1 if m["unmatched"] else 0
        BD.map_approve(args.report, args.by, args.root)
        print("bind-map.json approved.")
        return 0
    except (BD.BindError, S.ContractError, DC.Refused) as e:
        print(f"pbik: {e}", file=sys.stderr)
        return 2


def synth_cmd(args):
    from . import dataclass_ as DC, synth as S
    try:
        if args.sub == "contract":
            c, out = S.contract(args.source, args.root, args.out, library=not args.no_library)
            print(f"{out}: {len(c['tables'])} table(s), {len(c['relationships'])} relationship(s), "
                  f"{len(c['flags'])} flag(s)")
            for f in c["flags"]:
                print(f"  {f['id']} {f['kind']:10} {f.get('table') or '(model)'}: {f['detail']}"
                      + (f" -> {f['resolution']} (rule {f.get('rule')})" if f.get("resolution") else ""))
            return 0
        if args.sub == "resolve":
            for f in S.resolve(args.root, args.flag, args.resolution, args.why, args.every):
                print(f"{f['id']} -> {f['resolution']}")
            print("Approval cleared: a person runs `pbik synth approve --by <name>`")
            return 0
        if args.sub == "approve":
            S.approve(args.root, args.by)
            print("Contract approved.")
            return 0
        from . import synthgen as G
        if args.sub == "slice":
            g, missing = S.slice_(args.root, args.layout)
            print(f"generate.json slice: {len(g['slice'])} table(s), "
                  f"{sum(len(e['columns']) for e in g['slice'].values())} column(s), "
                  f"{sum(len(e['measures']) for e in g['slice'].values())} measure(s)")
            for x in missing:
                print(f"  not in the contract or plannedMeasures: {x}")
            return 1 if missing else 0
        if args.sub == "generate":
            said = []
            print(f"wrote {G.generate(args.root, args.name, notes=said)}")
            for x in said:
                print(x)
            return 0
        errs, notes = G.verify(args.root, args.model)
        for x in notes:
            print(f"note  {x}")
        for x in errs:
            print(f"error {x}")
        print(f"{len(errs)} error(s), {len(notes)} note(s)")
        return 1 if errs else 0
    except (S.ContractError, DC.Refused) as e:
        print(f"pbik: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
