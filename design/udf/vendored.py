"""DAX Lib packages from the vendored copy (design/udf/vendor/), for a laptop where npm or npx is blocked.

    python design/udf/vendored.py --check                       every package in packages.json is vendored, unchanged
    python design/udf/vendored.py DaxLib.SVG --out fn.json      the package's functions as modeling MCP definitions

The --out file is the `definitions` list for the modeling MCP `function_operations` Create (name, expression,
description, annotations DAXLIB_PackageId / DAXLIB_PackageVersion, as daxlib-mcp writes them), so /model approved
installs the same functions without daxlib-mcp. Each vendored package keeps its LICENSE, manifest and README
(vendor/NOTICE.md); --check compares the functions.tmdl SHA-256 with packages.json `vendored`.
"""
import argparse, hashlib, json, pathlib, re, sys

UDF = pathlib.Path(__file__).resolve().parent
VENDOR = UDF / "vendor"
HEAD = re.compile(r"^function\s+'?([^'=]+?)'?\s*=\s*$", re.I)
ANNOT = re.compile(r"^\s*annotation\s+(\S+)\s*=\s*(.*?)\s*$")


def folder(pkg_id, version):
    return VENDOR / pkg_id / version


def parse(text):
    """[{name, expression, description, annotations}] from a DAX Lib lib/functions.tmdl."""
    out, doc, cur = [], [], None
    for line in text.replace("\r\n", "\n").split("\n"):
        h = HEAD.match(line)
        if h:
            cur = {"name": h.group(1).strip(), "lines": [], "description": "\n".join(doc), "annotations": []}
            out.append(cur)
            doc = []
            continue
        if line.startswith("///"):
            doc.append(line[3:].strip())
            cur = None
            continue
        a = ANNOT.match(line)
        if a and cur is not None:
            cur["annotations"].append({"key": a.group(1), "value": a.group(2)})
            continue
        if cur is not None and not cur["annotations"]:
            cur["lines"].append(line)
    for f in out:
        lines = f.pop("lines")
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        pad = min((len(x) - len(x.lstrip("\t ")) for x in lines if x.strip()), default=0)
        f["expression"] = "\n".join(x[pad:] for x in lines)
        if not f["description"]:
            del f["description"]
    return out


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check(pk):
    issues = []
    for p in pk.get("packages", []):
        v = p.get("vendored")
        d = folder(p["id"], p["version"])
        if not v:
            issues.append(f"{p['id']} {p['version']}: no `vendored` entry in packages.json")
            continue
        for f in ("functions.tmdl", "manifest.daxlib", "LICENSE"):
            if not (d / f).exists():
                issues.append(f"{p['id']}: {d.relative_to(UDF).as_posix()}/{f} missing")
        if (d / "functions.tmdl").exists():
            if sha(d / "functions.tmdl") != v.get("sha256"):
                issues.append(f"{p['id']}: functions.tmdl differs from packages.json vendored.sha256")
            fns = parse((d / "functions.tmdl").read_text(encoding="utf-8"))
            if len(fns) != v.get("functions"):
                issues.append(f"{p['id']}: {len(fns)} functions, packages.json says {v.get('functions')}")
            bad = [f["name"] for f in fns if not f["name"].startswith(p["id"] + ".")]
            if bad:
                issues.append(f"{p['id']}: functions outside its namespace: {bad[:3]}")
        if (d / "manifest.daxlib").exists():
            m = json.loads((d / "manifest.daxlib").read_text(encoding="utf-8"))
            if (m.get("id"), m.get("version")) != (p["id"], p["version"]):
                issues.append(f"{p['id']}: manifest says {m.get('id')} {m.get('version')}")
        if (d / "LICENSE").exists() and p.get("licence", "") not in (d / "LICENSE").read_text(encoding="utf-8"):
            issues.append(f"{p['id']}: LICENSE doesn't name {p.get('licence')}")
    if "NOTICE.md" not in {x.name for x in VENDOR.glob("*")}:
        issues.append("vendor/NOTICE.md missing")
    return issues


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("package", nargs="?", help="package id from packages.json, e.g. DaxLib.SVG")
    ap.add_argument("--out", help="write the definitions JSON here (default: print a summary)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    pk = json.loads((UDF / "packages.json").read_text(encoding="utf-8"))
    if a.check:
        issues = check(pk)
        for i in issues:
            print(f"error: {i}")
        print(f"{len(pk.get('packages', []))} package(s) vendored" if not issues else f"{len(issues)} issue(s)")
        return 1 if issues else 0
    if not a.package:
        ap.error("name a package, or --check")
    p = next((x for x in pk.get("packages", []) if x["id"].lower() == a.package.lower()), None)
    if not p:
        print(f"error: {a.package} isn't listed in design/udf/packages.json (check its licence and add a row first)")
        return 2
    fns = parse((folder(p["id"], p["version"]) / "functions.tmdl").read_text(encoding="utf-8"))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(fns, indent=1), encoding="utf-8")
        print(f"{p['id']} {p['version']}: {len(fns)} function definitions -> {a.out} "
              "(modeling MCP function_operations Create, useTransaction true)")
    else:
        for f in fns:
            print(f["name"])
        print(f"{p['id']} {p['version']}: {len(fns)} functions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
