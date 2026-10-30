"""Regression suite: golden builds of the Rep 4 parity, Rep 5 parity (two pages) and Rep 8 layouts.

    python tools/regression/regress.py                 run every case; exit 1 if any output changed
    python tools/regression/regress.py --case rep8     one case
    python tools/regression/regress.py --update        accept the current output as the new golden (after review)
    python tools/regression/regress.py --capture       (re)copy each case's inputs from its source folder

Run it after every pbik change and after every Power BI Desktop update (README "Regression suite").

Each case in cases.json has its inputs copied into tools/regression/cases/<case>/project/ (the layout, tokens, the
semantic model's TMDL definition, and the report shell: definition.pbir, report.json, version.json,
reportExtensions.json and StaticResources, no bookmarks, and only page.json for pages outside the layout, so
navigation targets resolve), so the suite runs without the rep folders.
A run copies the project to a scratch folder, runs `pbik build` from layout.json alone (no templates, as the parity
builds were made), checks that a second build prints "No changes", runs `pbik validate`, and compares every file
pbik wrote (definition/**/*.json and visual-map.json) with cases/<case>/golden.json. A difference is listed per file
and JSON path; nothing in the case folders changes unless --update or --capture is passed.
"""
import argparse, json, pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parents[1]
PBIK = KIT / "tools" / "pbik" / "pbik.py"
sys.path.insert(0, str(KIT / "tools" / "pbik"))

from pbikit.roundtrip import diff  # noqa: E402

SHELL = ("definition.pbir", "definition/report.json", "definition/version.json", "definition/reportExtensions.json")


def load(f):
    return json.loads(pathlib.Path(f).read_text(encoding="utf-8"))


def save(f, d):
    f = pathlib.Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def pbik(*args):
    return subprocess.run([sys.executable, str(PBIK), *map(str, args)], capture_output=True, text=True, encoding="utf-8")


# ---------------------------------------------------------------- capture inputs
def project_dir(case, root=None):
    """cases/<project>/project: cases with the same source share one copy (`project`, default the case name);
    each case's layout is design/specs/<case>.layout.json in it."""
    return (root or HERE / "cases") / case.get("project", case["name"]) / "project"


def capture(case, root=None):
    src = KIT / case["source"]                   # relative to the kit root (an absolute path stays as it is)
    dest = project_dir(case, root)
    if dest.exists() and (dest / "design" / "specs" / f"{case['name']}.layout.json").exists():
        shutil.rmtree(dest)
    if dest.exists():                            # another case of the same project captured it already
        shutil.copy(src / case["layout"], dest / "design" / "specs" / f"{case['name']}.layout.json")
        print(f"{case['name']}: layout copied from {src}")
        return
    rep = next(src.glob("*.Report"))
    mod = next(src.glob("*.SemanticModel"))
    r_dest, m_dest = dest / rep.name, dest / mod.name
    for rel in SHELL:
        if (rep / rel).exists():
            (r_dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(rep / rel, r_dest / rel)
    if (rep / "StaticResources").is_dir():
        shutil.copytree(rep / "StaticResources", r_dest / "StaticResources")
    pages = r_dest / "definition" / "pages"
    pages.mkdir(parents=True)
    meta = load(rep / "definition" / "pages" / "pages.json")
    meta.pop("activePageName", None)
    meta["pageOrder"] = []
    # every source page as a shell (page.json only, no visuals): navigation targets resolve (Rep 4's own pages), and
    # cases sharing a project see the same pages
    for pf in sorted((rep / "definition" / "pages").glob("*/page.json")):
        pd = load(pf)
        if True:
            pd.pop("visualInteractions", None)
            save(pages / pf.parent.name / "page.json", pd)
            meta["pageOrder"].append(pd["name"])
    save(pages / "pages.json", meta)
    shutil.copytree(mod / "definition", m_dest / "definition")
    for x in ("definition.pbism", ".platform"):
        if (mod / x).exists():
            shutil.copy(mod / x, m_dest / x)
    (dest / "design" / "specs").mkdir(parents=True)
    shutil.copy(src / case["layout"], dest / "design" / "specs" / f"{case['name']}.layout.json")
    shutil.copy(src / case.get("tokens", "design/tokens.json"), dest / "design" / "tokens.json")
    print(f"{case['name']}: inputs copied from {src}")


# ---------------------------------------------------------------- run
def outputs(work, rep_name):
    out = {}
    rep = work / rep_name
    for f in sorted(rep.glob("definition/**/*.json")):
        out[f.relative_to(work).as_posix()] = load(f)
    vm = work / "design" / "specs" / "visual-map.json"
    if vm.exists():
        out["design/specs/visual-map.json"] = load(vm)
    return out


def run_case(case, update=False, keep=False, root=None):
    root = root or HERE / "cases"
    proj = project_dir(case, root)
    if not proj.exists():
        return [f"inputs missing: run with --capture first ({proj})"]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"pbik-regress-{case['name']}-"))
    try:
        work = tmp / "p"
        shutil.copytree(proj, work)
        rep_name = next(work.glob("*.Report")).name
        lay = work / "design" / "specs" / "layout.json"
        shutil.copy(work / "design" / "specs" / f"{case['name']}.layout.json", lay)
        for other in (work / "design" / "specs").glob("*.layout.json"):
            other.unlink()
        empty = tmp / "no-templates"
        empty.mkdir()
        args = ["build", work / rep_name, lay, "--tokens", work / "design" / "tokens.json", "--templates", empty]
        problems = []
        first = pbik(*args)
        if first.returncode:
            return [f"pbik build failed ({first.returncode}):\n{first.stdout}{first.stderr}"]
        second = pbik(*args)
        if "No changes" not in second.stdout:
            problems.append(f"second build was not 'No changes':\n{second.stdout}")
        val = pbik("validate", work / rep_name, "--layout", lay, "--no-catalog", "--no-a11y")   # errors only: warning checks evolve
        lines = val.stdout.strip().splitlines()
        summary = (lines or ["?"])[-1]
        uncached = sum(1 for x in lines if x.startswith("warning schemas:") and "not cached" in x)
        if uncached:      # no schema cache on this machine (git-ignored): a setup gap, not a change in pbik's output
            print(f"{case['name']}: schemas not cached, schema checks skipped (pbik schemas fetch)")
            summary = re.sub(r"(\d+) warning\(s\)", lambda m: f"{int(m.group(1)) - uncached} warning(s)", summary)
        got = outputs(work, rep_name)
        got["_validate"] = summary.split(": ", 1)[-1]
        gf = root / case["name"] / "golden.json"
        if update or not gf.exists():
            save(gf, got)
            print(f"{case['name']}: golden written ({len(got) - 1} files; validate {got['_validate']})")
            return problems
        want = load(gf)
        for rel in sorted(set(want) | set(got)):
            if rel not in got:
                problems.append(f"{rel}: no longer written")
            elif rel not in want:
                problems.append(f"{rel}: new file")
            else:
                for kind, path, a, b in diff(want[rel], got[rel]):
                    if kind == "order":
                        continue
                    sa, sb = (json.dumps(x, ensure_ascii=False)[:120] for x in (a, b))
                    problems.append(f"{rel}: {kind} {path}: golden {sa} -> now {sb}")
        return problems
    finally:
        if keep:
            print(f"kept {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="pbik golden builds (Rep 4 parity, Rep 5 parity, Rep 8)")
    ap.add_argument("--case", action="append", help="run only this case (repeatable)")
    ap.add_argument("--update", action="store_true", help="write the current output as the golden")
    ap.add_argument("--capture", action="store_true", help="copy the inputs from each case's source folder")
    ap.add_argument("--keep", action="store_true", help="keep the scratch folders")
    ap.add_argument("--root", help="cases folder (default tools/regression/cases; tests use a copy)")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    root = pathlib.Path(a.root) if a.root else None
    spec = root.parent / "cases.json" if root and (root.parent / "cases.json").exists() else HERE / "cases.json"
    cases = [c for c in load(spec)["cases"] if not a.case or c["name"] in a.case]
    if a.capture:
        for c in cases:
            capture(c, root)
    failed = 0
    for c in cases:
        probs = run_case(c, update=a.update, keep=a.keep, root=root)
        if probs:
            failed += 1
            print(f"FAIL {c['name']}: {len(probs)} difference(s)")
            for p in probs[:60]:
                print(f"  {p}")
            if len(probs) > 60:
                print(f"  ... {len(probs) - 60} more")
        elif not a.update:
            print(f"ok   {c['name']}")
    print(f"\n{len(cases) - failed} of {len(cases)} case(s) unchanged" if not a.update else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
