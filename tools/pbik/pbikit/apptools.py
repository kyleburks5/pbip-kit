"""`pbik tools`: the app-visual toolchain (docs/design/app-visuals.md), installed without admin rights into the kit
tools folder outside the repo (%USERPROFILE%\\.pbik-tools, or the PBIK_TOOLS folder), pinned by tools/appvisuals/.

    pbik tools check            every item: installed / missing / wrong version, with the one-line fix
    pbik tools install [--only node,npm,sources,deneb,playwright]
    pbik tools run <tool> ...   run pbiviz / eslint / tsc / node / npm / playwright with the kit's Node

Downloads are checked against the sha256 in lock.json (Node's from nodejs.org's SHASUMS256.txt); an empty sha256 is
filled on the first download (`--record`) and checked from then on. Nothing is written into the repo except the lock
files, and only with `--record`.
"""
import hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, urllib.request, zipfile

KIT = pathlib.Path(__file__).resolve().parents[3]
PIN = KIT / "tools" / "appvisuals"
ITEMS = ["node", "npm", "sources", "deneb", "playwright"]


def lock():
    return json.loads((PIN / "lock.json").read_text(encoding="utf-8"))


def tools_dir():
    # Not %LOCALAPPDATA%: apps installed from the Store (the Claude app among them) see a private redirected copy of
    # AppData\Local, so tools installed there from the chat are invisible to Desktop and a normal terminal (v1.11).
    base = os.environ.get("PBIK_TOOLS") or os.path.join(os.path.expanduser("~"), ".pbik-tools")
    p = pathlib.Path(base)
    if KIT in [p, *p.parents]:
        raise SystemExit("pbik: the tools folder must be outside the kit folder (nothing installed goes in the repo)")
    return p


def node_home():
    v = lock()["node"]["version"]
    return tools_dir() / f"node-v{v}-win-x64"


def node_exe():
    return node_home() / "node.exe"


def env():
    e = dict(os.environ)
    e["PATH"] = str(node_home()) + os.pathsep + str(tools_dir() / "node_modules" / ".bin") + os.pathsep + e.get("PATH", "")
    e["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir())
    e["NPM_CONFIG_UPDATE_NOTIFIER"] = "false"
    e["NPM_CONFIG_FUND"] = "false"
    return e


BINS = {"pbiviz": "powerbi-visuals-tools/bin/pbiviz.js", "eslint": "eslint/bin/eslint.js",
        "tsc": "typescript/bin/tsc", "playwright": "playwright/cli.js"}


def command(tool, *args):
    """argv for a kit tool run with the kit's Node (no PATH lookups, no .cmd shims)."""
    node = str(node_exe())
    if tool == "node":
        return [node, *args]
    if tool == "npm":
        return [node, str(node_home() / "node_modules" / "npm" / "bin" / "npm-cli.js"), *args]
    if tool in BINS:
        return [node, str(tools_dir() / "node_modules" / BINS[tool]), *args]
    raise SystemExit(f"pbik: no kit tool called {tool!r} (node, npm, {', '.join(BINS)})")


def run(tool, *args, cwd=None, capture=True, timeout=900):
    r = subprocess.run(command(tool, *args), cwd=cwd or tools_dir(), env=env(), capture_output=capture, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


# ------------------------------------------------------------------------------------------------ downloads
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, name):
    d = tools_dir() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    out = d / name
    if not out.exists():
        tmp = out.with_suffix(out.suffix + ".part")
        req = urllib.request.Request(url, headers={"User-Agent": "pbik-tools"})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.replace(out)
    return out


def verified(path, want, label, record, setter):
    got = sha256(path)
    if want and got != want:
        path.unlink()
        raise SystemExit(f"pbik: {label}: the download's checksum doesn't match the pinned one; removed it, nothing "
                         "installed")
    if not want:
        if not record:
            raise SystemExit(f"pbik: {label}: no pinned checksum yet (the maintainer pins it with --record)")
        setter(got)
    return got


def save_lock(data):
    (PIN / "lock.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def extract(zpath, dest, strip_top=True):
    """Unzip into dest (replaced), dropping the single top folder GitHub and nodejs.org put in their zips."""
    tmp = pathlib.Path(tempfile.mkdtemp(dir=tools_dir()))
    try:
        with zipfile.ZipFile(zpath) as z:
            for m in z.infolist():
                target = (tmp / m.filename).resolve()
                if tmp.resolve() not in target.parents and target != tmp.resolve():
                    raise SystemExit(f"pbik: {zpath.name} has a path outside its folder; not extracted")
            z.extractall(tmp)
        kids = list(tmp.iterdir())
        src = kids[0] if strip_top and len(kids) == 1 and kids[0].is_dir() else tmp
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(src), str(dest))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ install
def install_node(L, record):
    n = L["node"]
    if node_exe().exists() and run("node", "--version")[1].strip() == "v" + n["version"]:
        return f"Node.js {n['version']}: already installed"
    z = download(n["url"], pathlib.Path(n["url"]).name)
    verified(z, n["sha256"], "Node.js", record, lambda s: n.__setitem__("sha256", s))
    extract(z, node_home())
    return f"Node.js {n['version']}: installed (checksum matches nodejs.org)"


def install_npm(L, record):
    t = tools_dir()
    shutil.copy2(PIN / "package.json", t / "package.json")
    have_lock = (PIN / "package-lock.json").exists()
    if have_lock and not record:
        shutil.copy2(PIN / "package-lock.json", t / "package-lock.json")
        code, out = run("npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund", timeout=1800)
    elif record:                                  # the maintainer changed package.json: update the lock from it
        if have_lock:
            shutil.copy2(PIN / "package-lock.json", t / "package-lock.json")
        code, out = run("npm", "install", "--ignore-scripts", "--no-audit", "--no-fund", "--save-exact",
                        timeout=1800)
        if code == 0:
            shutil.copy2(t / "package-lock.json", PIN / "package-lock.json")
    else:
        raise SystemExit("pbik: tools/appvisuals/package-lock.json is missing (the maintainer makes it with --record)")
    if code != 0:
        raise SystemExit("pbik: the npm install failed:\n" + out[-2000:])
    return "npm packages: installed from the lockfile" if have_lock and not record else "npm packages: installed, lockfile recorded"


def install_sources(L, record):
    done = []
    for key, s in L["sources"].items():
        dest = tools_dir() / "sources" / f"{key}-{s['commit'][:7]}"
        if (dest / "LICENSE").exists():
            done.append(f"{key}: already there")
            continue
        url = f"https://codeload.github.com/{s['repo']}/zip/{s['commit']}"
        z = download(url, f"{key}-{s['commit'][:7]}.zip")
        verified(z, s["sha256"], key, record, lambda v, s=s: s.__setitem__("sha256", v))
        dest.parent.mkdir(parents=True, exist_ok=True)
        extract(z, dest)
        lic = (dest / "LICENSE").read_text(encoding="utf-8", errors="replace") if (dest / "LICENSE").exists() else ""
        if "MIT License" not in lic:
            shutil.rmtree(dest)
            raise SystemExit(f"pbik: {key}: no MIT licence in the download; removed it")
        done.append(f"{key}: installed (MIT)")
    return "Microsoft visuals: " + ", ".join(done)


def install_deneb(L, record):
    d = L["deneb"]
    z = download(d["url"], pathlib.Path(d["url"]).name)
    verified(z, d["sha256"], "Deneb", record, lambda s: d.__setitem__("sha256", s))
    dest = tools_dir() / "deneb"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(z, dest / z.name)
    return f"Deneb {d['version']}: downloaded (checksum checked)"


def install_playwright(L, record):
    if chromium_path():
        return f"Playwright Chromium {L['playwright']['chromium']}: reused (already installed)"
    code, out = run("playwright", "install", "chromium", timeout=1800)
    if code != 0:
        raise SystemExit("pbik: the Chromium download failed:\n" + out[-1500:])
    return f"Playwright Chromium {L['playwright']['chromium']}: installed"


def install(only=None, record=False):
    L = lock()
    tools_dir().mkdir(parents=True, exist_ok=True)
    steps = {"node": install_node, "npm": install_npm, "sources": install_sources, "deneb": install_deneb,
             "playwright": install_playwright}
    for k in (only or ITEMS):
        if k not in steps:
            raise SystemExit(f"pbik: no install step called {k!r} ({', '.join(ITEMS)})")
        if k != "node" and not node_exe().exists():
            print(install_node(L, record))
        print(steps[k](L, record))
        if record:
            save_lock(L)
    return 0


# ------------------------------------------------------------------------------------------------ check
def _chromium_in(base):
    rev = lock()["playwright"]["chromium"]
    for sub in ("chrome-win64", "chrome-win"):
        exe = pathlib.Path(base) / f"chromium-{rev}" / sub / "chrome.exe"
        if exe.exists():
            return exe
    return None


def browsers_dir():
    """Playwright's browsers: reuse the shared folder when it already has the pinned Chromium, else the tools folder."""
    shared = pathlib.Path(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
    return shared if _chromium_in(shared) and not _chromium_in(tools_dir() / "ms-playwright") else         tools_dir() / "ms-playwright"


def chromium_path():
    return _chromium_in(browsers_dir())


def size(p):
    p = pathlib.Path(p)
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def mb(n):
    return f"{n / 1048576:.0f} MB" if n >= 1048576 else f"{n / 1024:.0f} KB"


def pkg_version(name):
    f = tools_dir() / "node_modules" / name / "package.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return None


def wanted(name):
    return json.loads((PIN / "package.json").read_text(encoding="utf-8"))["devDependencies"][name]


def rows(probe=True):
    """One row per checklist item: item, purpose, want, have, licence, where, size, works, status, fix. probe=False
    skips running the tools and the folder sizes (fast, for `pbik status`)."""
    L = lock()
    t = tools_dir()
    out = []
    deep = probe
    sz_ = size if deep else (lambda p: 0)

    def add(item, purpose, want, have, lic, where, sz, works, fix):
        status = "installed" if have and have == want and works else ("missing" if not have else "wrong version"
                                                                         if have != want else "not working")
        out.append(dict(item=item, purpose=purpose, want=want, have=have or "", licence=lic, where=str(where),
                        size=mb(sz) if sz else "", works=works, status=status, fix="" if status == "installed" else fix))

    nv = L["node"]["version"]
    have = None
    if node_exe().exists():
        code, o = run("node", "--version") if probe else (0, nv)
        have = o.strip().lstrip("v") if code == 0 else "?"
    add("Node.js LTS (portable zip)", "runs the visual build tools", nv, have, "MIT", node_home(), sz_(node_home()),
        have == nv, "pbik tools install --only node")
    npm_ok = node_exe().exists() and (t / "node_modules").exists()

    def npm_item(item, purpose, pkgs, lic, test=None):
        hv = [pkg_version(p) for p in pkgs]
        have_s = "/".join(v or "-" for v in hv) if any(hv) else None
        want_s = "/".join(wanted(p) for p in pkgs)
        works = False
        if npm_ok and all(hv):
            works = True if (test is None or not deep) else test()
        add(item, purpose, want_s, have_s, lic, t / "node_modules" / pkgs[0],
            sum(sz_(t / "node_modules" / p) for p in pkgs), works, "pbik tools install --only npm")

    def ok(tool, *a, expect=""):
        try:
            code, o = run(tool, *a, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return code == 0 and expect in o

    npm_item("powerbi-visuals-tools (pbiviz)", "builds .pbiviz custom visuals", ["powerbi-visuals-tools"], "MIT",
             lambda: ok("pbiviz", "--version", expect=wanted("powerbi-visuals-tools")))
    npm_item("TypeScript, visuals API, eslint + Power BI lint plugin", "code and certification-style checks",
             ["typescript", "powerbi-visuals-api", "eslint", "eslint-plugin-powerbi-visuals", "typescript-eslint"],
             "Apache-2.0 / MIT", lambda: ok("tsc", "--version", expect="5.9") and ok("eslint", "--version"))
    npm_item("D3", "animation, physics (d3-force) and drawing", ["d3"], "ISC",
             lambda: ok("node", "-e", "const d=require('d3');process.exit(d.forceSimulation&&d.transition?0:1)"))
    npm_item("Power BI visuals utils", "formatting pane, tooltips, colours, data view",
             ["powerbi-visuals-utils-formattingmodel", "powerbi-visuals-utils-tooltiputils",
              "powerbi-visuals-utils-colorutils", "powerbi-visuals-utils-dataviewutils"], "MIT")
    npm_item("Vega / Vega-Lite (harness)", "renders Deneb specs offline (Deneb 2.0.1.0's own versions)",
             ["vega", "vega-lite", "vega-embed"], "BSD-3-Clause",
             lambda: ok("node", "--input-type=module", "-e",
                        "import * as vl from 'vega-lite';import * as vg from 'vega';"
                        "const s=vl.compile({data:{values:[{a:1}]},mark:'bar',encoding:{x:{field:'a'}}}).spec;"
                        "new vg.View(vg.parse(s),{renderer:'none'}).runAsync().then(()=>console.log('ok'))",
                        expect="ok"))
    npm_item("Bundled assets: Inter font, world/US maps", "fonts and GeoJSON inside visuals (no network)",
             ["@fontsource/inter", "world-atlas", "us-atlas", "topojson-client"], "OFL-1.1 / ISC")
    npm_item("Shape morph and tree layouts (flubber, d3-flextree)", "morph shapes; tidy trees and org charts",
             ["flubber", "d3-flextree"], "MIT / WTFPL")
    npm_item("Three.js", "3D scenes (WebGL), orbit camera, picking", ["three", "@types/three"], "MIT",
             lambda: ok("node", "--input-type=module", "-e", "import * as T from 'three';console.log(T.REVISION)", expect="187"))

    for key, s in L["sources"].items():
        d = t / "sources" / f"{key}-{s['commit'][:7]}"
        lic = (d / "LICENSE").read_text(encoding="utf-8", errors="replace") if (d / "LICENSE").exists() else ""
        add(f"Microsoft visual: {s['repo'].split('/')[1]}", s["use"], s["commit"][:7],
            s["commit"][:7] if d.exists() else None, "MIT", d, sz_(d), "MIT License" in lic,
            "pbik tools install --only sources")

    dn = L["deneb"]
    f = t / "deneb" / pathlib.Path(dn["url"]).name
    good = f.exists() and (not deep or not dn["sha256"] or sha256(f) == dn["sha256"])
    add("Deneb .pbiviz", "Vega-Lite route (offline copy)", dn["version"], dn["version"] if f.exists() else None, "MIT",
        f, sz_(f), good, "pbik tools install --only deneb")

    pv = pkg_version("playwright")
    cp = chromium_path()
    add("Playwright + Chromium", "harness screenshots and recordings", f"{wanted('playwright')} / chromium "
        f"{L['playwright']['chromium']}", f"{pv} / chromium {L['playwright']['chromium']}" if pv and cp else
        (f"{pv} / no chromium" if pv else None), "Apache-2.0", cp.parent if cp else env()["PLAYWRIGHT_BROWSERS_PATH"],
        sz_(cp.parent) if cp else 0, bool(pv and cp), "pbik tools install --only npm,playwright")
    return out


def check(as_json=False):
    r = rows()
    if as_json:
        print(json.dumps(r, indent=1))
    else:
        for x in r:
            if x["status"] in ("installed", "recorded"):
                print(f"{x['item']}: {x['status']} ({x['have'] or x['want']})")
            else:
                print(f"warning: {x['item']}: {x['status']}; fix: `{x['fix']}`")
        bad = [x for x in r if x["status"] not in ("installed", "recorded")]
        print(f"App-visual tools: {len(r) - len(bad)} of {len(r)} ready" + ("" if not bad else
              f", {len(bad)} to install"))
    return 0 if all(x["status"] in ("installed", "recorded") for x in r) else 1


def summary_line():
    """For `pbik status`: one plain line, or None when every item is ready."""
    try:
        bad = [x["item"] for x in rows(probe=False) if x["status"] not in ("installed", "recorded")]
    except (OSError, SystemExit, ValueError):
        return "The app-visual tools can't be checked here."
    return None if not bad else f"App-visual tools not ready: {', '.join(bad)} (I can install them)."
