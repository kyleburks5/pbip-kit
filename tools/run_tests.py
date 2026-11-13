"""Run every kit test suite, then (with --regression) the golden builds.

    python tools/run_tests.py                 pbik, Patterns builder, wireframe, design (/theme, /plan from a reference), kit (Copilot files, doctor.ps1)
    python tools/run_tests.py --regression    the same, then tools/regression/regress.py

Exit 1 if any suite fails. Run it after every pbik change; run --regression also after every Desktop update
(README "Regression suite").
"""
import argparse, pathlib, subprocess, sys, time

KIT = pathlib.Path(__file__).resolve().parents[1]
SUITES = [("pbik", "tools/pbik/tests/test_pbik.py"), ("synth", "tools/pbik/tests/test_synth.py"),
          ("bind", "tools/pbik/tests/test_bind.py"),
          ("layout", "tools/pbik/tests/test_layout_rules.py"),
          ("patterns", "tools/patterns/test_patterns.py"),
          ("wireframe", "design/scripts/test_wireframe.py"), ("design", "design/scripts/test_design.py"),
          ("kit", "tools/tests/test_kit.py")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--regression", action="store_true")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(errors="replace")    # a failing suite's output may hold characters the console lacks
    runs = [(name, [sys.executable, str(KIT / f)]) for name, f in SUITES]
    if a.regression:
        runs.append(("regression", [sys.executable, str(KIT / "tools" / "regression" / "regress.py")]))
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
