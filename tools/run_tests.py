"""Run the kit test suites, then (with --regression) the golden builds.

    python tools/run_tests.py                 every suite in the master kit; in a report project (a copy of the kit with
                                              a *.pbip or design/specs/layout.json) only the suites related to the files
                                              changed since the last commit (fast mode)
    python tools/run_tests.py --all           every suite, wherever it runs
    python tools/run_tests.py --changed       fast mode, even in the master kit
    python tools/run_tests.py --regression    every suite, then tools/regression/regress.py

Suites: pbik, synth and bind (synthetic to live), layout (KPI cards, layout fidelity, pattern choices), patterns
(Patterns builder), wireframe, design (/theme, /plan from a reference), kit (Copilot files, doctor.ps1, lessons).
Exit 1 if any suite fails. Run it after every pbik change; run --regression also after every Desktop update
(README "Regression suite").
"""
import argparse, fnmatch, pathlib, subprocess, sys, time

KIT = pathlib.Path(__file__).resolve().parents[1]
SUITES = [("pbik", "tools/pbik/tests/test_pbik.py"), ("synth", "tools/pbik/tests/test_synth.py"),
          ("bind", "tools/pbik/tests/test_bind.py"),
          ("layout", "tools/pbik/tests/test_layout_rules.py"),
          ("patterns", "tools/patterns/test_patterns.py"),
          ("wireframe", "design/scripts/test_wireframe.py"), ("design", "design/scripts/test_design.py"),
          ("kit", "tools/tests/test_kit.py")]
ALL = [n for n, _ in SUITES]
PBIK_CORE = ["pbik", "synth", "bind", "layout"]
# a changed path (glob; the first match wins) -> the suites that test it
RELATED = [("tools/run_tests.py", ALL),
           ("tools/pbik/tests/test_pbik.py", ["pbik"]), ("tools/pbik/tests/test_synth.py", ["synth"]),
           ("tools/pbik/tests/test_bind.py", ["bind"]), ("tools/pbik/tests/bind_sample.py", ["bind", "layout"]),
           ("tools/pbik/tests/test_layout_rules.py", ["layout"]), ("tools/pbik/tests/synth_sample/*", ["synth", "bind"]),
           ("tools/pbik/pbikit/synth*.py", ["synth", "bind"]), ("tools/pbik/pbikit/packs.py", ["synth"]),
           ("tools/pbik/pbikit/bind*.py", ["bind"]), ("tools/pbik/pbikit/filtertypes.py", ["bind", "pbik"]),
           ("tools/pbik/pbikit/dataclass_.py", ["synth", "bind", "layout"]),
           ("tools/pbik/pbikit/kpicards.py", ["layout", "pbik"]), ("tools/pbik/pbikit/namenew.py", ["pbik"]),
           ("tools/pbik/*", PBIK_CORE + ["patterns", "wireframe", "design"]),
           ("tools/patterns/*", ["patterns"]), ("tools/fixtures/*", ["pbik", "patterns"]),
           ("tools/regression/*", []),
           ("design/scripts/pattern_choices.py", ["layout"]), ("design/scripts/card_space.py", ["layout"]),
           ("design/scripts/ref_layout.py", ["design", "layout"]),
           ("design/scripts/*", ["wireframe", "design", "layout"]),
           ("design/templates/*", ["pbik", "patterns", "layout"]),
           ("design/themes/*", ["design", "wireframe", "kit"]),
           ("docs/patterns/*", ["kit", "layout"]),
           ("*", ["kit"])]


def is_project(root=KIT):
    """A report project (a copy of the kit with a report or a layout), not the master kit."""
    return bool(list(root.glob("*.pbip"))) or (root / "design" / "specs" / "layout.json").exists()


def changed_files(root=KIT):
    """Paths changed since the last commit (staged, unstaged, untracked), or None without git."""
    try:
        r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None
    if r.returncode:
        return None
    return [ln[3:].strip().strip('"').split(" -> ")[-1] for ln in r.stdout.splitlines() if ln.strip()]


def related(paths):
    """The suites (in SUITES order) related to the changed paths."""
    want = set()
    for p in paths:
        p = p.replace("\\", "/")
        for pat, suites in RELATED:
            if fnmatch.fnmatch(p, pat):
                want.update(suites)
                break
    return [n for n in ALL if n in want]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--regression", action="store_true", help="every suite, then the golden builds")
    ap.add_argument("--all", action="store_true", help="every suite (the default in the master kit)")
    ap.add_argument("--changed", action="store_true", help="only suites related to changed files (default in a project)")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(errors="replace")    # a failing suite's output may hold characters the console lacks
    names = ALL
    if not (a.all or a.regression) and (a.changed or is_project()):
        files = changed_files()
        if files is None:
            print("fast mode: git not available, running every suite")
        else:
            names = related(files)
            skipped = [n for n in ALL if n not in names]
            print(f"fast mode: {len(files)} changed file(s) -> {', '.join(names) or 'no suites'}"
                  + (f" (skipped {', '.join(skipped)}; --all runs them)" if skipped else ""))
    runs = [(name, [sys.executable, str(KIT / f)]) for name, f in SUITES if name in names]
    if a.regression:
        runs.append(("regression", [sys.executable, str(KIT / "tools" / "regression" / "regress.py")]))
    if not runs:
        print("nothing to run")
        return 0
    failed = []
    for name, cmd in runs:
        t = time.time()
        r = subprocess.run(cmd, cwd=KIT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (r.stdout + r.stderr).strip().splitlines()
        tail = [x for x in out if x.startswith(("Ran ", "OK", "FAILED", "ok ", "FAIL ")) or "case(s) unchanged" in x]
        print(f"{'ok  ' if r.returncode == 0 else 'FAIL'} {name:11} {time.time() - t:5.0f}s  {' | '.join(tail[-3:])}")
        if r.returncode:
            failed.append(name)
            print("\n".join("     " + x for x in out[-40:]))
    print(f"\n{len(runs) - len(failed)} of {len(runs)} suite(s) passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
