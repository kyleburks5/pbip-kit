"""Numbers audit: each key value recomputed from the raw columns vs the model's measure, in every audit state, plus
the numbers drawn inside SVG measures vs the measure they show.

Reads design/specs/audit.json (written by /plan from brd.md; the same file drives audit_svg.py):
    {"mode": "full",                       # full | sampled | aggregate-only (CLAUDE.md "Audit modes"; set by /model)
     "states": {"default": [], "2020": ["'Date'[Year] = 2020"], "empty case": ["..."]},
     "values": [{"key": "Points", "expected": "SUMX ( FILTER ( Shots, Shots[EVENT_TYPE] = \\"Made Shot\\" ), ... )",
                 "model": "[Player Points]", "states": ["default", "empty case"], "tolerance": 0.0005}],
     "svg": [{"measure": "KPI SVG", "value": "[Player Points]", "format": "#,0", "states": ["default"]}]}
  values.expected: plain DAX over raw columns (FILTER / COUNTROWS / SUMX, no model measures).
                   aggregate-only mode: keep each recompute at the grain of the key value (no row export, no per-row
                   loops over the fact table beyond one SUMX); sampled mode: list only the sampled members in states.
  values.states:   default = every state. tolerance: relative (default 0.0005); blanks must match blanks.
  svg:             evaluates the SVG measure and FORMAT ( value, format ); the formatted number must appear in the
                   SVG's visible text (a % in the text is decoded from %25).
Output: a markdown table to stdout (paste into design/reviews/), the run time of each query block, exit 1 on a mismatch.
Usage: python design/scripts/audit_numbers.py --port <port> [--define <defs.dax>]
"""
import argparse, json, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit_svg import ROOT, run_dax, decode, svg_texts   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def calc(expr, flt):
    return f"CALCULATE ( {', '.join([expr] + list(flt))} )"


def num(x):
    try:
        return float(x.replace(",", ""))
    except (AttributeError, ValueError):
        return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--define", help="file of MEASURE definitions to run query-scoped")
    a = ap.parse_args()
    f = ROOT / "design" / "specs" / "audit.json"
    if not f.exists():
        sys.exit("design/specs/audit.json not found: /plan writes it from brd.md.")
    cfg = json.loads(f.read_text(encoding="utf-8"))
    states = cfg.get("states", {"default": []})
    defs = pathlib.Path(a.define).read_text(encoding="utf-8") if a.define else ""
    head = f"DEFINE\n{defs}\n" if defs else ""
    bad = 0
    print(f"Audit mode: {cfg.get('mode', 'full')}" + (" (query-scoped --define)" if defs else ""))

    rows = []
    for v in cfg.get("values", []):
        for st in v.get("states") or list(states):
            label = f"{v['key']} | {st}".replace('"', "'")
            rows.append(f'ROW ( "k", "{label}", "v", {calc(v["expected"], states[st])} & " ¦ " & '
                        f'{calc(v["model"], states[st])} )')
    if rows:
        t0 = time.perf_counter()
        out = run_dax(head + "EVALUATE UNION (\n" + ",\n".join(rows) + "\n)\n", a.port)
        secs = time.perf_counter() - t0
        tol = {v["key"]: v.get("tolerance", 0.0005) for v in cfg.get("values", [])}
        print("\n| value | state | expected (raw) | model | ok |\n| --- | --- | --- | --- | --- |")
        for k, rest in out:
            exp, _, mod = rest.partition(" ¦ ")
            key, state = k.split(" | ", 1)
            e, m = num(exp), num(mod)
            ok = (exp == mod) if e is None or m is None else abs(e - m) <= tol[key] * max(abs(e), 1e-9)
            bad += not ok
            print(f"| {key} | {state} | {exp or '(blank)'} | {mod or '(blank)'} | {'ok' if ok else 'MISMATCH'} |")
        print(f"\n{len(out)} values in {secs:.1f}s")

    rows = []
    for sv in cfg.get("svg", []):
        for st in sv.get("states") or list(states):
            label = f"{sv['measure']} | {st}".replace('"', "'")
            rows.append(f'ROW ( "k", "{label}", "v", FORMAT ( {calc(sv["value"], states[st])}, "{sv["format"]}" ) '
                        f'& " ¦ " & {calc("[" + sv["measure"] + "]", states[st])} )')
    if rows:
        t0 = time.perf_counter()
        out = run_dax(head + "EVALUATE UNION (\n" + ",\n".join(rows) + "\n)\n", a.port)
        secs = time.perf_counter() - t0
        print("\n| SVG measure | state | value (formatted) | numbers in the SVG text | ok |\n| --- | --- | --- | --- | --- |")
        for k, rest in out:
            want, _, uri = rest.partition(" ¦ ")
            name, state = k.split(" | ", 1)
            texts = svg_texts(decode(uri)[1]) if uri else []
            ok = (not want and not texts) or any(want and want in t for t in texts)
            bad += not ok
            print(f"| {name} | {state} | {want or '(blank)'} | {'; '.join(texts) or '(none)'} | "
                  f"{'ok' if ok else 'MISMATCH'} |")
        print(f"\n{len(out)} SVG checks in {secs:.1f}s")
    print(f"\n{bad} mismatches.")
    sys.exit(1 if bad else 0)
