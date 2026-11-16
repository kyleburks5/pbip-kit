"""Rebuild a kit UDF library's index.json from its files (UDF KPI card study, 2026-11-15; the maintainer's tool).

    python design/udf/library/index_udf.py design/udf/library/park-kpi [--originals <folder>]

Keeps the hand-written fields of each entry (role, description, example, useWhen, avoidWhen) and recomputes the
rest from the kit file and the author's original:
- params (name, type, mode), calls, calledBy, style parameters and the tokens they default to;
- sha256: the kit's fingerprint of the kit file (`pbik udf check` fails when a file no longer matches it);
  originalSha256: the author's original. The originals stay in the study project, never in the master kit: with
  --originals <folder> it is recomputed from them, otherwise the recorded value is kept;
- requires: model tables and columns the function reads by name, its own and through what it calls;
- changes: the K-ids (CHANGES.md) found in the file; status: from STATUS below, else "enabled";
- hand-written fields kept as they are: size (a card's drawn width and height), styles (a card's chart style names).
"""
import hashlib, json, pathlib, re, sys

COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
ICON_OFF = ("disabled: the icon pack's licence isn't confirmed (its site wasn't named; the icon names look like "
            "Remix Icon, whose Remix Icon License v1.0 isn't MIT, Apache or CC0). Name the source and its licence "
            "in design/udf/udf-kpi-library-provenance.md to enable")
STATUS = {"Park.Icons.SolidIcon": ICON_OFF, "Park.Icons.GradientIcon": ICON_OFF}
# tables read by name in the function body (not passed in): table -> columns the code names
DIRECT = {
    "Park.Icons.SolidIcon": {"icons": ["Name", "Content"]},
    "Park.Icons.GradientIcon": {"icons": ["Name", "Content"]},
    "Park.SVG.BasicLineChart": {"Date": []},
    "Park.SVG.Micro.DumbbellSolidRoundedColor": {"Date": []},
}
WHY = {"icons": "looks up the icon by name (LOOKUPVALUE icons[Content], icons[Name])",
       "Date": "SUMMARIZE('Date', <order>, <label>): the order and label columns passed in must be in 'Date'"}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(lib, originals=None):
    lib = pathlib.Path(lib)
    orig_dir = pathlib.Path(originals) if originals else None
    old = json.loads((lib / "index.json").read_text(encoding="utf-8"))
    keep = {f["name"]: f for f in old["functions"]}
    files = {p.stem: p.read_text(encoding="utf-8") for p in sorted(lib.glob("*.tmdl"))}
    names = list(files)
    if set(names) != set(keep):
        sys.exit(f"index and files differ: {sorted(set(names) ^ set(keep))}")
    calls = {}
    for n, t in files.items():
        code = COMMENTS.sub("", t.partition("=>")[2])
        calls[n] = sorted(m for m in names if m != n and re.search(re.escape(m) + r"\s*\(", code, re.I))

    def needs(n, seen=None):
        seen = seen or set()
        out = {t: list(c) for t, c in DIRECT.get(n, {}).items()}
        for c in calls[n]:
            if c not in seen:
                seen.add(c)
                for t, cols in needs(c, seen).items():
                    out.setdefault(t, [])
                    out[t] = sorted(set(out[t]) | set(cols))
        return out

    funcs = []
    for n, t in files.items():
        k = keep[n]
        head = COMMENTS.sub("", t.partition("=>")[0])
        params = [{"name": p, "type": ty.upper(), "mode": m.upper()}
                  for p, ty, m in re.findall(r"(\w+)\s*:\s*([A-Za-z]+)\s+([A-Za-z]+)", head)]
        style = {p: tok for p, tok in re.findall(r'IF\( ISBLANK\( (\w+) \), "\{\{([\w.]+)\}\}"', t)}
        orig = (orig_dir / f"{n}.tmdl").read_text(encoding="utf-8") if orig_dir else None
        req = needs(n)
        funcs.append({
            "name": n, "role": k["role"], "description": k["description"], "params": params,
            "styleParams": style, "output": k["output"], "calls": calls[n],
            "calledBy": [m for m in names if n in calls[m]],
            "requires": [{"table": tb, "columns": cols, "why": WHY[tb]} for tb, cols in sorted(req.items())],
            "example": k["example"], "useWhen": k["useWhen"], "avoidWhen": k["avoidWhen"],
            "tokens": sorted(set(re.findall(r"\{\{([\w.]+)\}\}", t))),
            "changes": sorted(set(re.findall(r"K-\d\d", t))
                              | ({"K-01"} if (("DAXLIB_Package" in orig) if orig is not None
                                             else "K-01" in k.get("changes", [])) else set())
                              | ({"K-03"} if "{{" in t and "K-02" not in t else set())),
            "minCompatibilityLevel": 1702, "sourceVersion": k.get("sourceVersion"),
            "sha256": sha(t), "originalSha256": sha(orig) if orig is not None else k.get("originalSha256"),
            "file": f"{n}.tmdl",
            "status": STATUS.get(n, "enabled"),
            **{x: k[x] for x in ("size", "styles") if x in k},
        })
    order = ["card", "chart", "microchart", "icon", "number", "format", "helper"]
    funcs.sort(key=lambda x: (order.index(x["role"]), x["name"]))
    old["functions"] = funcs
    old["_note"] = ("UDF KPI card library, kit copy (study 2026-11-15). Optional toolbelt: used only when the plan or "
                    "the person picks a function. Permission and sources: design/udf/udf-kpi-library-provenance.md. "
                    "Changes from the author's originals: CHANGES.md. Colours and fonts are {{token}} placeholders "
                    "filled by `pbik udf render`; `pbik udf check` checks fingerprints and model tables first.")
    (lib / "index.json").write_text(json.dumps(old, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"indexed {len(funcs)} functions; disabled: {[f['name'] for f in funcs if f['status'] != 'enabled']}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("library")
    ap.add_argument("--originals", help="the author's original .tmdl files (in the study project only)")
    a = ap.parse_args()
    main(a.library, a.originals)
