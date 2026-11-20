"""`pbik visual`: kit custom visuals (.pbiviz from the app-visual template) and Deneb specs (docs/design/app-visuals.md).

    pbik visual new <name> [--deneb]          a custom visual from tools/appvisuals/template into visuals/<name>/, or a
                                              Deneb spec from the kit starter into design/deneb/<name>.vl.json
    pbik visual build <name>                  lint + pbiviz package --certification-audit + the kit's bundle checks, in
                                              the kit tools folder (never in the repo); Deneb: the spec checks
    pbik visual test <name> [--scenario f]    the offline harness (tools/appvisuals/harness): screenshots, frames,
                                              checks; never needs Desktop
    pbik visual add <name> --report R [--layout L --id P1-V04 --page P1 --box x,y,w,h --bind Role=Table[Field] ...]
                                              register the package in the report (custom) and add the layout entry
    pbik visual refresh <name>                the visual's kit runtime (src/kit) from the template, nothing else
    pbik visual list [--report R]             visuals in this project, their build and where they are used
    pbik visual remove <name> --report R      unregister a custom visual no page uses any more

How a report stores a private visual is the form Desktop saved (scratch save 2026-11-16, .claude/rules/pbik.md):
CustomVisuals/<guid>/package.json and resources/<guid>.pbiviz.json (the package's own files, re-indented, CRLF) and a
report.json resourcePackages entry {name: <guid>, type: CustomVisual, items: [{name, path: <guid>.pbiviz.json, type:
CustomVisualMetadata}]}.
"""
import base64, hashlib, json, os, pathlib, re, secrets, shutil, subprocess, zipfile

from . import apptools as AT

KIT = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = KIT / "tools" / "appvisuals" / "template"
HARNESS = KIT / "tools" / "appvisuals" / "harness"
DENEB_STARTER = KIT / "tools" / "appvisuals" / "deneb"
STARTERS = KIT / "tools" / "appvisuals" / "starters"
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,60}$")
FONT_FILES = [("Inter", "400", "inter-latin-400-normal.woff2"), ("Inter", "600", "inter-latin-600-normal.woff2")]
# the kit's own bundle checks, on top of pbiviz's certification audit (no network, no dynamic code, nothing external)
BANNED = [("eval", r"\beval\s*\("), ("new Function", r"new\s+Function\s*\("), ("fetch", r"(?<![\w.])fetch\s*\("),
          ("XMLHttpRequest", r"XMLHttpRequest"), ("WebSocket", r"\bWebSocket\b"), ("sendBeacon", r"sendBeacon"),
          ("importScripts", r"importScripts"), ("dynamic import", r"(?<![\w.])import\s*\("),
          ("external font", r"@font-face[^}]*url\(")]
URL = re.compile(r"https?://[^\s\"'`)<>]+")
URL_OK = re.compile(r"^https?://(www\.w3\.org/|example\.invalid/|powerbi\.com/product/schema#)")   # ids, never fetched


class VisualError(Exception):
    pass


def root(project="."):
    return pathlib.Path(project).resolve()


def src_dir(name, project="."):
    return root(project) / "visuals" / name


def spec_file(name, project="."):
    return root(project) / "design" / "deneb" / f"{name}.vl.json"


def kind(name, project="."):
    if (src_dir(name, project) / "pbiviz.json").exists():
        return "custom"
    if spec_file(name, project).exists():
        return "deneb"
    return None


def build_dir(name, project="."):
    h = hashlib.sha1(str(root(project)).lower().encode()).hexdigest()[:8]
    return AT.tools_dir() / "builds" / f"{h}-{name}"


def state(name, project="."):
    f = build_dir(name, project) / "kit-build.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def check_name(name):
    if not NAME.match(name):
        raise VisualError(f"{name!r}: use letters, digits, - and _ (for example P1-V04_dot-chart)")


# ------------------------------------------------------------------------------------------------ new
def starters():
    """The kit's visual starters (tools/appvisuals/starters/<name>): whole visuals built on the template."""
    return sorted(p.name for p in STARTERS.iterdir() if p.is_dir()) if STARTERS.exists() else []


def new(name, deneb=False, display=None, project=".", start=None):
    check_name(name)
    if start and start not in starters():
        raise VisualError(f"no visual starter called {start!r} (starters: {', '.join(starters()) or 'none'})")
    if kind(name, project):
        raise VisualError(f"there is already a visual called {name}")
    if deneb:
        f = spec_file(name, project)
        f.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DENEB_STARTER / "starter.vl.json", f)
        t = json.loads((DENEB_STARTER / "starter.test.json").read_text(encoding="utf-8"))
        t["spec"] = f"{name}.vl.json"
        (f.parent / f"{name}.test.json").write_text(json.dumps(t, indent=2) + "\n", encoding="utf-8")
        print(f"Made the Deneb chart {name} from the kit starter (theme colours, tooltips, cross-filter).")
        return f
    d = src_dir(name, project)
    shutil.copytree(TEMPLATE, d, ignore=shutil.ignore_patterns("node_modules", "dist", ".tmp", "*.pbiviz"))
    camel = re.sub(r"[^A-Za-z0-9]", "", name.title())[:28]
    guid = f"pbik{camel}{secrets.token_hex(3)}"
    pb = json.loads((d / "pbiviz.json").read_text(encoding="utf-8"))
    pb["visual"].update(name=camel[:1].lower() + camel[1:], displayName=display or name.split("_", 1)[-1].replace("-", " ").capitalize(),
                        guid=guid)
    (d / "pbiviz.json").write_text(json.dumps(pb, indent=2) + "\n", encoding="utf-8")
    pk = json.loads((d / "package.json").read_text(encoding="utf-8"))
    pk["name"] = re.sub(r"[^a-z0-9-]", "-", name.lower())
    (d / "package.json").write_text(json.dumps(pk, indent=2) + "\n", encoding="utf-8")
    if start:                          # a starter: its own visual, settings, capabilities and tests over the template
        src = STARTERS / start
        for f in src.rglob("*"):
            if f.is_file() and "golden" not in f.parts:
                dst = d / f.relative_to(src)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
        if (src / "test").exists():    # the template's own scenarios belong to the unit chart
            for t in (TEMPLATE / "test").glob("*.json"):
                if not (src / "test" / t.name).exists():
                    (d / "test" / t.name).unlink(missing_ok=True)
        print(f"Made the custom visual {name} from the kit starter {start} (id {guid}).")
    else:
        print(f"Made the custom visual {name} from the kit's app-visual template (id {guid}).")
    print("note: the author email and support link are the kit's placeholders; an organisation sets its own before IT "
          "review (pbiviz.json author.email, visual.supportUrl)")
    return d


def refresh(name, project=".", check=True):
    """Bring a visual's kit runtime (src/kit) up to the template's; the visual's own files stay as they are. When the
    runtime changed and the visual was built, rebuild it and run its scenarios: an unexpected look change against the
    golden screenshots fails the refresh (the files stay updated, so the diff can be looked at)."""
    if kind(name, project) != "custom":
        raise VisualError(f"{name} isn't a custom visual")
    dst = src_dir(name, project) / "src" / "kit"
    changed = []
    base = TEMPLATE / "src" / "kit"
    for f in sorted(base.rglob("*.ts")):
        if f.name == "fonts.generated.ts":
            continue
        rel = f.relative_to(base)
        t = dst / rel
        if not t.exists() or t.read_bytes() != f.read_bytes():
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            changed.append(rel.as_posix())
    print(f"Updated {name}'s kit runtime: {', '.join(changed) if changed else 'already the same as the template'}.")
    if changed and state(name, project) and check:
        build(name, project)
        bad = test_all(name, project)
        if bad:
            raise VisualError(f"{name} looks different after the update ({', '.join(bad)}): check the .diff.png files; "
                              f"if the new look is right, accept it with `pbik visual test {name} --all --update-golden`")
    return changed


def scenarios(name, project="."):
    """The visual's test scenarios (not the real-time recordings)."""
    if kind(name, project) == "custom":
        fs = sorted((src_dir(name, project) / "test").glob("*.json"))
    else:
        fs = sorted(spec_file(name, project).parent.glob(f"{name}*.test.json"))
    return [f for f in fs if not f.stem.startswith(("recording", "_"))]


def test_all(name, project=".", update_golden=False):
    """Run every scenario; the names of the ones that failed (a check or a golden)."""
    bad = []
    for f in scenarios(name, project):
        if test(name, str(f), project=project, update_golden=update_golden) != 0:
            bad.append(f.stem)
    return bad


# ------------------------------------------------------------------------------------------------ build
def _sync(src, dst):
    """Copy the source into the build folder, keeping the node_modules junction and nothing stale."""
    dst.mkdir(parents=True, exist_ok=True)
    for p in dst.iterdir():
        if p.name in ("node_modules",):
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for p in src.iterdir():
        if p.name in ("node_modules", "dist", ".tmp"):
            continue
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, dst / p.name)


def _junction(dst):
    link = dst / "node_modules"
    if link.exists():
        return
    target = AT.tools_dir() / "node_modules"
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    if r.returncode != 0:
        raise VisualError("couldn't link the shared packages into the build folder: " + (r.stdout + r.stderr).strip())


def _fonts(dst):
    out = ["// Generated by pbik visual build: Inter (SIL Open Font License 1.1, Copyright 2016 The Inter Project",
           "// Authors, https://github.com/rsms/inter), from @fontsource/inter, as base64. Registered from memory.",
           "export const FONTS: Array<{ family: string; weight: string; data: string }> = ["]
    for fam, w, f in FONT_FILES:
        p = AT.tools_dir() / "node_modules" / "@fontsource" / "inter" / "files" / f
        if p.exists():
            out.append(f'    {{ family: "{fam}", weight: "{w}", data: "{base64.b64encode(p.read_bytes()).decode()}" }},')
    out.append("];")
    (dst / "src" / "kit" / "fonts.generated.ts").write_text("\n".join(out) + "\n", encoding="utf-8")


def bundle_checks(js, css):
    """(errors, warnings) for the built bundle: dynamic code, network calls, external fonts, unexpected URLs."""
    errors = [f"the bundle uses {label}" for label, pat in BANNED if re.search(pat, js) or re.search(pat, css)]
    urls = sorted({u for u in URL.findall(js + css) if not URL_OK.match(u)})
    warnings = [f"the bundle names a web address (not fetched, but check it): {u}" for u in urls[:10]]
    return errors, warnings


def _quiet(line):
    return any(x in line for x in ("Certificate verification", "Generating a new certificate", "Create certificate",
                                   "pwsh", "operable program", "DEP0187", "trace-deprecation", "Webpack Bundle Analyzer",
                                   "No bundles were parsed", "Error parsing bundle asset"))


def build(name, project="."):
    k = kind(name, project)
    if k == "deneb":
        return build_deneb(name, project)
    if k != "custom":
        raise VisualError(f"there is no visual called {name} (make one with `pbik visual new {name}`)")
    if AT.summary_line():
        raise VisualError("the app-visual tools aren't ready (`pbik tools install`)")
    src, dst = src_dir(name, project), build_dir(name, project)
    _sync(src, dst)
    _junction(dst)
    _fonts(dst)
    code, out = AT.run("pbiviz", "package", "--certification-audit", cwd=dst, timeout=900)
    lines = [ln for ln in out.splitlines() if ln.strip() and not _quiet(ln)]
    pkgs = sorted((dst / "dist").glob("*.pbiviz"))
    if code != 0 or not pkgs:
        tail = "\n".join(ln for ln in lines if "error" in ln.lower() or "TS" in ln)[-3000:]
        raise VisualError("the visual didn't build:\n" + (tail or "\n".join(lines[-20:])))
    pkg = pkgs[-1]
    with zipfile.ZipFile(pkg) as z:
        res = [n for n in z.namelist() if n.startswith("resources/") and n.endswith(".pbiviz.json")][0]
        meta = json.loads(z.read(res).decode("utf-8"))
    js, css = meta["content"]["js"], meta["content"].get("css", "")
    h = dst / "harness"
    h.mkdir(exist_ok=True)
    (h / "visual.js").write_text(js, encoding="utf-8")
    (h / "visual.css").write_text(css, encoding="utf-8")
    errors, warnings = bundle_checks(js, css)
    audit_ok = "No external requests found" in out
    lint_ok = "Lint check completed" in out
    st = {"name": name, "guid": meta["visual"]["guid"], "version": meta["visual"]["version"],
          "displayName": meta["visual"]["displayName"], "pbiviz": str(pkg), "bytes": pkg.stat().st_size,
          "lint": lint_ok, "certificationAudit": audit_ok, "kitChecks": {"errors": errors, "warnings": warnings},
          "recommended": [ln.split(" - ")[0].replace("warn", "").strip() for ln in lines
                          if ln.strip().startswith("warn") and " - https" in ln]}
    (dst / "kit-build.json").write_text(json.dumps(st, indent=1) + "\n", encoding="utf-8")
    print(f"Built {name}: {pkg.stat().st_size // 1024} KB package, lint {'clean' if lint_ok else 'NOT clean'}, "
          f"certification audit {'no external requests' if audit_ok else 'NOT passed'}.")
    for e in errors:
        print(f"error: {e}")
    for w in warnings:
        print(f"warning: {w}")
    for r in st["recommended"]:
        print(f"note: pbiviz recommends: {r}")
    if errors or not audit_ok or not lint_ok:
        raise VisualError("the build doesn't meet the kit's rules (no network, no dynamic code, lint clean)")
    return st


def build_deneb(name, project="."):
    from . import deneb as DN
    f = spec_file(name, project)
    spec = json.loads(f.read_text(encoding="utf-8"))
    issues = DN.spec_issues(spec)[0]
    tmp = AT.tools_dir() / "builds" / "_spec-check.mjs"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text("import * as vl from 'vega-lite'; import fs from 'node:fs';\n"
                   "const s = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));\n"
                   "s.data = { name: 'dataset', values: [] };\n"
                   "try { vl.compile(s); console.log('RESULT ok'); } catch (e) { console.log('RESULT error: ' + e.message); }\n",
                   encoding="utf-8")
    code, out = AT.run("node", str(tmp), str(f), cwd=AT.tools_dir())
    lines = out.splitlines()
    res = [ln for ln in lines if ln.startswith("RESULT ")]
    if not res or res[-1] != "RESULT ok":
        issues.append(res[-1][7:] if res else "Vega-Lite couldn't compile the spec")
    for ln in lines:
        if ln.startswith("WARN"):
            print(f"warning: {name}: Vega-Lite says: {ln[4:].strip()}")
    if issues:
        for i in issues:
            print(f"error: {name}: {i}")
        raise VisualError(f"the Deneb spec {name} has {len(issues)} problem(s)")
    print(f"Checked the Deneb chart {name}: Vega-Lite {json.loads((AT.PIN / 'package.json').read_text())['devDependencies']['vega-lite']} compiles it, no external data or images.")
    return {"name": name, "kind": "deneb"}


# ------------------------------------------------------------------------------------------------ test
def theme_file(project="."):
    for p in [root(project) / "design" / "themes" / "pbip-polish.json", *sorted((root(project) / "design" / "themes").glob("*.json"))]:
        if p.exists():
            return p
    return None


def test(name, scenario=None, out=None, record=False, project=".", update_golden=False):
    k = kind(name, project)
    if not k:
        raise VisualError(f"there is no visual called {name}")
    if k == "custom":
        sc_path = pathlib.Path(scenario) if scenario else src_dir(name, project) / "test" / "scenario.json"
        st = state(name, project)
        if not st:
            raise VisualError(f"{name} isn't built yet (`pbik visual build {name}`)")
    else:
        sc_path = pathlib.Path(scenario) if scenario else spec_file(name, project).with_name(f"{name}.test.json")
    sc = json.loads(sc_path.read_text(encoding="utf-8"))
    sc["kind"] = k
    if k == "custom":
        h = build_dir(name, project) / "harness"
        sc["bundle"] = {"js": str(h / "visual.js"), "css": str(h / "visual.css"), "guid": st["guid"]}
    else:
        sp = sc.get("spec", f"{name}.vl.json")
        sc["spec"] = str((sc_path.parent / sp).resolve()) if isinstance(sp, str) else sp
    if "theme" not in sc and theme_file(project):
        sc["theme"] = str(theme_file(project))
    elif isinstance(sc.get("theme"), str):
        sc["theme"] = str((sc_path.parent / sc["theme"]).resolve())
    if isinstance((sc.get("data") or {}).get("rowsFile"), str):
        sc["data"]["rowsFile"] = str((sc_path.parent / sc["data"]["rowsFile"]).resolve())
    if record:
        sc["record"] = True
    gold = (src_dir(name, project) / "test" / "golden" if k == "custom"
            else spec_file(name, project).parent / "golden" / name) / sc_path.stem
    sc["goldenDir"] = str(gold)
    sc["updateGolden"] = bool(update_golden)
    out = pathlib.Path(out) if out else root(project) / "_snapshots" / "visuals" / name / sc_path.stem
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / f"_{sc_path.stem}.json"
    tmp.write_text(json.dumps(sc, indent=1), encoding="utf-8")
    e = AT.env()
    e["PBIK_TOOLS_DIR"] = str(AT.tools_dir())
    r = subprocess.run(AT.command("node", str(HARNESS / "run.mjs"), str(tmp), str(out)), env=e, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=1800)
    tmp.unlink(missing_ok=True)
    text = (r.stdout + r.stderr).strip()
    ran = any(ln.startswith(("PASS", "FAIL")) for ln in text.splitlines())
    for ln in text.splitlines():
        if ln.startswith(("PASS", "FAIL")):
            print(f"Harness {ln}")
        elif ln.strip().startswith("failed:"):
            print("error: " + ln.strip()[8:])
    if not ran:                                        # the harness stopped before its report: say why
        print("error: the harness didn't finish: " + " ".join(text.splitlines()[-6:])[:900])
        return 2
    print(f"Screenshots and report.json: {out}")
    return r.returncode


# ------------------------------------------------------------------------------------------------ add / remove / list
def _crlf_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n")


def register(report, name, project="."):
    """Put the built package into the report as Desktop does (CustomVisuals/<guid>/ and resourcePackages)."""
    st = state(name, project)
    if not st:
        raise VisualError(f"{name} isn't built yet (`pbik visual build {name}`)")
    rep = pathlib.Path(report)
    guid = st["guid"]
    with zipfile.ZipFile(st["pbiviz"]) as z:
        pkg = json.loads(z.read("package.json").decode("utf-8"))
        res = [n for n in z.namelist() if n.endswith(".pbiviz.json")][0]
        meta = json.loads(z.read(res).decode("utf-8"))
    cv = rep / "CustomVisuals" / guid
    (cv / "resources").mkdir(parents=True, exist_ok=True)
    changed = []
    for f, obj in ((cv / "package.json", pkg), (cv / "resources" / f"{guid}.pbiviz.json", meta)):
        text = _crlf_json(obj)
        if not f.exists() or f.read_bytes().decode("utf-8") != text:     # as written (CRLF): no rewrite each build
            f.write_text(text, encoding="utf-8", newline="")
            changed.append(f)
    rf = rep / "definition" / "report.json"
    d = json.loads(rf.read_text(encoding="utf-8"))
    pk = d.setdefault("resourcePackages", [])
    entry = {"name": guid, "type": "CustomVisual",
             "items": [{"name": f"{guid}.pbiviz.json", "path": f"{guid}.pbiviz.json", "type": "CustomVisualMetadata"}]}
    if entry not in pk:
        pk[:] = [p for p in pk if p.get("name") != guid] + [entry]
        rf.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        changed.append(rf)
    return guid, changed


def users(report, guid):
    rep = pathlib.Path(report) / "definition" / "pages"
    out = []
    for f in rep.glob("*/visuals/*/visual.json"):
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("visual", {}).get("visualType") == guid:
                out.append(f.parent.name)
        except ValueError:
            pass
    return out


def add(name, report, layout=None, vid=None, page=None, box=None, binds=(), title=None, project="."):
    k = kind(name, project)
    if not k:
        raise VisualError(f"there is no visual called {name}")
    if k == "custom":
        guid, changed = register(report, name, project)
        print(f"Registered {name} in the report ({'changed ' + str(len(changed)) + ' file(s)' if changed else 'already there'}).")
    if not layout:
        return 0
    if not (vid and page and box):
        raise VisualError("to place it, give --id, --page and --box x,y,w,h")
    L = json.loads(pathlib.Path(layout).read_text(encoding="utf-8"))
    x, y, w, h = [float(v) for v in box.split(",")]
    bindings = {}
    for b in binds:
        role, field = b.split("=", 1)
        bindings.setdefault(role.strip(), []).append(field.strip())
    fields = [f for fs in bindings.values() for f in fs]
    entry = {"id": vid, "name": name.split("_", 1)[-1], "page": page, "x": x, "y": y, "w": w, "h": h}
    if k == "custom":
        entry.update(type="custom", custom=name, bindings=bindings)
        method, step = "custom-visual", 4
    else:
        entry.update(type="deneb", bindings={"dataset": fields},
                     deneb={"spec": f"design/deneb/{name}.vl.json", "interactivity": {"crossFilter": True, "tooltips": True, "contextMenu": True}})
        method, step = "deneb", 3
    entry["fallback"] = {"type": "tableEx", "bindings": {"Values": fields},
                         "build": {"method": "native", "step": 1, "reason": "a table of the same fields"},
                         "container": {"title": f"{title or entry['name']} (table)"}}
    entry["container"] = {"title": title or entry["name"].replace("-", " ").capitalize(),
                          "altText": f"{title or entry['name']}: an app visual; the fallback is a table of the same fields"}
    entry["build"] = {"method": method, "step": step, "nativeTried": "to fill in at /plan", "reason": "to fill in at /plan"}
    vis = [v for v in L.get("visuals", []) if v.get("id") != vid]
    vis.append(entry)
    L["visuals"] = vis
    pathlib.Path(layout).write_text(json.dumps(L, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Added {vid} ({name}) to the layout; the next build places it.")
    return 0


def remove(name, report, project="."):
    st = state(name, project)
    if not st:
        raise VisualError(f"{name} has no build here, so its id is unknown")
    guid = st["guid"]
    used = users(report, guid)
    if used:
        raise VisualError(f"{name} is still on the report ({', '.join(used)}): take it out of layout.json and build first")
    cv = pathlib.Path(report) / "CustomVisuals" / guid
    if cv.exists():
        shutil.rmtree(cv)
    rf = pathlib.Path(report) / "definition" / "report.json"
    d = json.loads(rf.read_text(encoding="utf-8"))
    before = len(d.get("resourcePackages", []))
    d["resourcePackages"] = [p for p in d.get("resourcePackages", []) if p.get("name") != guid]
    if len(d["resourcePackages"]) != before:
        rf.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Removed {name} from the report (its source in visuals/{name} stays).")
    return 0


def listing(report=None, project="."):
    rows = []
    for d in sorted((root(project) / "visuals").glob("*/pbiviz.json")):
        n = d.parent.name
        st = state(n, project)
        used = users(report, st["guid"]) if (report and st) else []
        rows.append((n, "custom visual", f"built {st['bytes'] // 1024} KB" if st else "not built", ", ".join(used) or "-"))
    for f in sorted((root(project) / "design" / "deneb").glob("*.vl.json")):
        rows.append((f.name[:-8], "Deneb chart", "spec", "-"))
    if not rows:
        print("There are no app visuals in this project yet.")
    for r in rows:
        print(f"{r[0]}: {r[1]}, {r[2]}, on the report: {r[3]}")
    return 0


# ------------------------------------------------------------------------------------------------ IT handoff pack
def _imports(src):
    names = set()
    for f in pathlib.Path(src).rglob("*.ts"):
        for m in re.finditer(r'from\s+"([^".][^"]*)"', f.read_text(encoding="utf-8")):
            n = m.group(1)
            names.add("/".join(n.split("/")[:2]) if n.startswith("@") else n.split("/")[0])
    return sorted(names)


# what IT may ask about a package's licence, and the way around it
LICENCE_NOTES = {
    "d3-flextree": "d3-flextree is WTFPL (permissive, but some legal teams don't accept it). The visual also bundles "
                   "d3-hierarchy's own tree layout (ISC): Format pane > Tree > Tree layout > Standard (d3.tree) uses "
                   "only ISC code for the layout. If WTFPL isn't accepted, set Standard on every copy of the visual, "
                   "or ask for a build without d3-flextree.",
    "flubber": "flubber (MIT) has had no release since 2018; its dependencies are earcut (ISC), svgpath (MIT) and "
               "svg-path-properties (ISC).",
}


def _licence(pkg):
    f = AT.tools_dir() / "node_modules" / pkg / "package.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d.get("version", ""), d.get("license") or str(d.get("licenses", ""))
    except (OSError, ValueError):
        return "", "?"


def handoff(name, project="."):
    """visuals/<name>/handoff/: what IT needs to review one visual (README.md, icon, screenshots, the package)."""
    if kind(name, project) != "custom":
        raise VisualError(f"{name} isn't a custom visual (Deneb charts are reviewed as the certified Deneb visual)")
    st = state(name, project)
    if not st:
        raise VisualError(f"{name} isn't built yet (`pbik visual build {name}`)")
    src = src_dir(name, project)
    out = src / "handoff"
    if out.exists():
        shutil.rmtree(out)
    (out / "screenshots").mkdir(parents=True)
    pb = json.loads((src / "pbiviz.json").read_text(encoding="utf-8"))
    caps = json.loads((src / "capabilities.json").read_text(encoding="utf-8"))
    shutil.copy2(src / "assets" / "icon.png", out / "icon.png")
    shutil.copy2(st["pbiviz"], out / pathlib.Path(st["pbiviz"]).name)          # git-ignored (*.pbiviz)
    shots = []
    for g in sorted((src / "test" / "golden").rglob("*.png"))[:12]:
        t = out / "screenshots" / f"{g.parent.name}-{g.name}"
        shutil.copy2(g, t)
        shots.append(t.name)
    pkgs = [p for p in _imports(src / "src") if p != "powerbi-visuals-api"]
    v = pb["visual"]
    notes = (src / "CHANGELOG.md").read_text(encoding="utf-8") if (src / "CHANGELOG.md").exists() else \
        f"## {v['version']}\n- First version, made with pbip-kit's app-visual template.\n"
    a = pb.get("author", {})
    lines = [f"# {v['displayName']} ({v['version']})", "", v.get("description", ""), "",
             "| | |", "| --- | --- |",
             f"| Visual id (guid) | `{v['guid']}` |",
             f"| Package | `{pathlib.Path(st['pbiviz']).name}` ({st['bytes'] // 1024} KB) |",
             f"| Visuals API | {pb.get('apiVersion')} |",
             f"| Author / support | {a.get('name')} {a.get('email')} / {v.get('supportUrl')} (placeholders until the organisation sets its own) |",
             "| Privileges asked | " + (", ".join(x.get("name", "") for x in caps.get("privileges", [])) or
                                       "none (no web access, no local storage, no downloads)") + " |",
             "| Network calls | " + ("none: the pbiviz certification audit found no external requests" if st["certificationAudit"]
                                    else "NOT checked") + " |",
             "| Lint (eslint-plugin-powerbi-visuals, recommended) | " + ("clean" if st["lint"] else "NOT clean") + " |",
             "| Kit bundle checks (eval, new Function, fetch, XHR, WebSocket, dynamic import, external fonts) | " +
             ("none found" if not st["kitChecks"]["errors"] else "; ".join(st["kitChecks"]["errors"])) + " |",
             f"| Web addresses named in the bundle (not fetched) | {len(st['kitChecks']['warnings'])} |", "",
             "## Data roles", ""]
    lines += [f"- **{r.get('displayName', r['name'])}** ({r['kind']})" for r in caps.get("dataRoles", [])]
    lines += ["", "## Formatting pane", ""]
    lines += [f"- {o}: {', '.join(p['properties'])}" for o, p in caps.get("objects", {}).items() if o not in ("state", "general")]
    lines += ["", "Saved with the report and in bookmarks: the `state` object (view, drill, camera) and, in filter mode, "
              "the visual's filter.", "", "## Third-party code bundled", "", "| Package | Version | Licence |",
              "| --- | --- | --- |"]
    lines += [f"| {p} | {_licence(p)[0]} | {_licence(p)[1]} |" for p in pkgs]
    for p_, note in LICENCE_NOTES.items():
        if p_ in pkgs:
            lines += ["", note]
    lines += ["", "Template code: MIT, started from Microsoft's Dot Plot visual (NOTICE.md).", "",
              "## Screenshots (the visual's golden harness screenshots)", ""]
    lines += [f"![{x}](screenshots/{x})" for x in shots]
    lines += ["", "## Version notes", "", notes]
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if (src / "NOTICE.md").exists():
        shutil.copy2(src / "NOTICE.md", out / "NOTICE.md")
    print(f"Made the IT handoff pack for {name}: README (checks, licences, roles, settings, notes), icon, "
          f"{len(shots)} screenshot(s) and the package.")
    return out


# ------------------------------------------------------------------------------------------------ pbik build hook
def resolve(visuals, no_custom, project=".", exported=(), log=None):
    """layout `type: "custom"` -> the visual's guid (registered on build), or its fallback with --no-custom-visuals or
    on a page marked `exported` (exported to PDF / PowerPoint or sent by subscription: only certified visuals are
    drawn there, so a kit visual would be blank; Microsoft's FAQ, docs/design/app-visuals.md)."""
    from . import deneb as DN
    out, errors, register_names = [], [], []
    for v in visuals:
        if v.get("type") != "custom":
            out.append(v)
            continue
        name = v.get("custom")
        fb = v.get("fallback")
        if not isinstance(fb, dict) or not fb.get("type"):
            errors.append(f"{v['id']}: a custom visual needs a `fallback` (a native or SVG visual)")
            continue
        st = state(name, project) if name else None
        if v.get("page") in exported and log is not None:
            log.append(f"{v['id']}: page {v.get('page')} is exported / subscribed: built as its fallback "
                       f"({fb['type']}), not the kit visual {name}")
        if no_custom or v.get("page") in exported:
            w = {k: v[k] for k in DN.KEEP if k in v}
            w.update({k: x for k, x in fb.items() if k != "container"})
            if isinstance(fb.get("container"), dict):
                w["container"] = {**{k: x for k, x in (v.get("container") or {}).items() if k not in DN.OWN_TEXT}, **fb["container"]}
            w["_swapFrom"] = st["guid"] if st else None
            out.append(w)
            continue
        if not st:
            errors.append(f"{v['id']}: the custom visual {name!r} isn't built (`pbik visual build {name}`)")
            continue
        register_names.append(name)
        from . import honest as HD                 # small-sample threshold and privacy mode from project.json
        extra = HD.props_for(v, src_dir(name, project), project)
        props = {**(v.get("props") or {}), **extra} if extra else v.get("props")
        w = {**v, "type": st["guid"], "_custom": name, "_swapFrom": fb["type"]}
        if props:
            w["props"] = props
        out.append(w)
    return out, errors, register_names
