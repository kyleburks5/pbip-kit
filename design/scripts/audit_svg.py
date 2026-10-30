"""SVG audit: every SVG image measure must return well-formed SVG, in every filter state the report shows.

Finds the SVG measures in the TMDL on disk (measures with `dataCategory: ImageUrl`), evaluates each one in the
filter states of design/specs/audit.json against the open Desktop model (read-only, .claude/scripts/run-dax.ps1),
decodes the data URI and parses it as XML. A broken SVG renders as an empty image or a broken-image icon, with no error.
Also checks the data URI itself: every % must start a %XX escape. A raw % (text like "24%") makes Power BI skip
decoding, so %23 colours stay encoded and every fill draws black while the text still shows (write it as %25).
The numbers inside the SVG text are checked by audit_numbers.py (it imports svg_texts from here).

design/specs/audit.json (written by /plan; the same file drives audit_numbers.py, which adds "mode", "values", "svg"):
    {"states": {"default": [], "2020": ["'Date'[Year] = 2020"], "empty case": ["'Shots'[PLAYER_NAME] = \\"X\\""]},
     "extra": {"<SVG measure>": [["'Rating'[Order] = 1"], ["'Rating'[Order] = 2"]]}}
  states: label -> CALCULATE filter expressions (boolean filters on columns). Include the empty case (a member with
          rows but nothing to draw) and the first year (no prior year).
  extra:  the row context a visual gives one measure (a table row, a small multiple), added to every state.
Usage: python design/scripts/audit_svg.py --port <port> [--define <defs.dax>]
       --define: a file of `MEASURE 'Table'[Name] = ...` lines run as query-scoped definitions, to test new
       definitions before they go to the TMDL, or the old ones to confirm the check fails before a fix (CLAUDE.md).
"""
import argparse, json, pathlib, re, subprocess, sys, tempfile, urllib.parse
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEP = " ¦ "


def svg_measures():
    """[(table, measure)] for every measure with dataCategory ImageUrl in the TMDL."""
    out = []
    for f in ROOT.glob("*.SemanticModel/definition/tables/*.tmdl"):
        text = f.read_text(encoding="utf-8-sig")
        table = re.search(r"^table\s+(.+?)\s*$", text, re.M).group(1).strip("'")
        blocks = re.split(r"(?m)^\t(?=measure |column |partition |hierarchy |annotation |calculationGroup)", text)
        for blk in blocks:
            m = re.match(r"measure\s+('(?:[^']|'')+'|[^\s=]+)\s*=", blk)
            if m and re.search(r"^\t\tdataCategory:\s*ImageUrl\s*$", blk, re.M):
                out.append((table, m.group(1).strip("'").replace("''", "'")))
    return sorted(out)


def run_dax(query, port):
    q = pathlib.Path(tempfile.gettempdir()) / "pbip_audit.dax"
    q.write_text(query, encoding="utf-8")
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(ROOT / ".claude" / "scripts" / "run-dax.ps1"), "-File", str(q), "-Port", str(port)],
                         capture_output=True, text=True, encoding="utf-8").stdout
    if out.startswith("ERROR"):
        sys.exit(out)
    return [line.split(SEP, 1) for line in out.splitlines() if SEP in line]


def decode(uri):
    """data:image/svg+xml;utf8,<...> -> (raw payload, decoded SVG text)."""
    raw = uri.split(",", 1)[1] if "," in uri else uri
    return raw, urllib.parse.unquote(raw)


def stray_percent(raw):
    return re.findall(r"%(?![0-9A-Fa-f]{2}).{0,6}", raw)


def svg_texts(svg):
    """Visible text in an SVG (every <text>/<tspan>), for the numbers audit."""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return []
    return ["".join(t.itertext()).strip() for t in root.iter() if t.tag.split("}")[-1] == "text"]


def load_states():
    f = ROOT / "design" / "specs" / "audit.json"
    if not f.exists():
        print("note: design/specs/audit.json not found; default filter state only")
        return {"default": []}, {}
    d = json.loads(f.read_text(encoding="utf-8"))
    return d.get("states", {"default": []}), d.get("extra", {})


def queries(measures, states, extra, defs=""):
    rows = []
    for table, name in measures:
        for state, flt in states.items():
            for ctx in extra.get(name, [[]]):
                label = f"{name} | {state}" + (f" | {ctx[0]}" if ctx else "")
                args = ", ".join([f"[{name}]"] + list(flt) + list(ctx))
                rows.append(f'ROW ( "k", "{label.replace(chr(34), chr(39))}", "v", CALCULATE ( {args} ) )')
    return (f"DEFINE\n{defs}\n" if defs else "") + "EVALUATE UNION (\n" + ",\n".join(rows) + "\n)\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--define", help="file of MEASURE definitions to run query-scoped")
    a = ap.parse_args()
    ms = svg_measures()
    if not ms:
        sys.exit("No measures with dataCategory ImageUrl in the TMDL: nothing to audit.")
    states, extra = load_states()
    defs = pathlib.Path(a.define).read_text(encoding="utf-8") if a.define else ""
    bad = ok = blank = 0
    for k, v in run_dax(queries(ms, states, extra, defs), a.port):
        if v == "(blank)":
            blank += 1
            print(f"BLANK  {k}")
            continue
        raw, svg = decode(v)
        stray = stray_percent(raw)
        if stray:
            bad += 1
            print(f"RAW %  {k}: {stray[:3]} (colours draw black; write % as %25)")
            continue
        try:
            ET.fromstring(svg)
            ok += 1
        except ET.ParseError as e:
            bad += 1
            print(f"BROKEN {k}: {e}")
    print(f"{'--define definitions' if a.define else 'Model'}: {len(ms)} SVG measures, {ok} well-formed, {bad} broken, "
          f"{blank} blank (blank = nothing to draw; check the empty case shows something sensible)")
    sys.exit(1 if bad else 0)
