"""pbik roundtrip: after a report pbik built is saved once in Desktop, list what Desktop rewrote, by visual ID, as
proposed pbik fixes. Read-only: nothing is changed.

    pbik roundtrip <Report>                         pbik's files = the last commit (HEAD), Desktop's = the working tree
    pbik roundtrip <Report> --rev HEAD~1 --to HEAD  any two revisions (the kit commits after every pbik build)
    pbik roundtrip <Report> --before <folder>       pbik's files from a copy of the report folder
    pbik roundtrip <Report> --out design/reviews/roundtrip.md

What it compares: every definition/*.json file (pages, visuals, bookmarks, report.json, pages.json, extensions).
Object entries are matched by selector, not by position. Each difference is one of:
- added:    Desktop wrote a key pbik didn't          -> write it too (value shown);
- removed:  pbik wrote a key Desktop dropped          -> stop writing it, or write it as Desktop does;
- changed:  Desktop rewrote a value                   -> write Desktop's value;
- format:   same value, other JSON form (32.0 -> 32)  -> write Desktop's form;
- schema:   Desktop moved the file to another $schema version;
- order:    same content, other key or list order     -> usually harmless; listed once per file;
- newline:  Desktop drops the final newline (every file; listed once in the summary, not per file).
Proposals that repeat across visuals are counted at the top, so one pbik fix can be read off for all of them.
"""
import json, pathlib, re, subprocess

from .report import ID_RE, Report, fail

SKIP_DIRS = ("StaticResources",)


# ---------------------------------------------------------------- reading both sides
def _git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip())
    return r.stdout


def side_from_git(rep_path, rev):
    """{relative path under the .Report folder: text} at a git revision."""
    top = pathlib.Path(_git(rep_path, "rev-parse", "--show-toplevel").decode().strip())
    rel = rep_path.resolve().relative_to(top.resolve()).as_posix()
    names = _git(top, "ls-tree", "-r", "--name-only", rev, "--", f"{rel}/definition").decode("utf-8").splitlines()
    out = {}
    for n in names:
        if n.endswith(".json"):
            out[n[len(rel) + 1:]] = _git(top, "show", f"{rev}:{n}").decode("utf-8")
    return out


def side_from_folder(rep_path):
    out = {}
    for f in sorted(pathlib.Path(rep_path).glob("definition/**/*.json")):
        if not any(s in f.parts for s in SKIP_DIRS):
            out[f.relative_to(rep_path).as_posix()] = f.read_text(encoding="utf-8")
    return out


# ---------------------------------------------------------------- JSON diff
def _sel_key(e):
    return json.dumps(e.get("selector"), sort_keys=True) if isinstance(e, dict) else None


def _is_entry_list(x):
    return isinstance(x, list) and x and all(isinstance(e, dict) and "properties" in e for e in x)


def _label(sel_json):
    return "" if sel_json in (None, "null") else f"@{sel_json}"


def diff(a, b, path=""):
    """[(kind, path, pbik value, Desktop value)]: kind added / removed / changed / format / order."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k not in b:
                out.append(("removed", f"{path}.{k}".lstrip("."), a[k], None))
        for k in b:
            if k not in a:
                out.append(("added", f"{path}.{k}".lstrip("."), None, b[k]))
            else:
                out += diff(a[k], b[k], f"{path}.{k}")
        if not out and list(a) != list(b):
            out.append(("order", path.lstrip(".") or "(file)", list(a), list(b)))
        return out
    if _is_entry_list(a) and _is_entry_list(b):
        ka, kb = {_sel_key(e): e for e in a}, {_sel_key(e): e for e in b}
        if len(ka) == len(a) and len(kb) == len(b):              # selectors unique: match by selector
            for k, e in ka.items():
                if k not in kb:
                    out.append(("removed", f"{path}{_label(k)}", e.get("properties"), None))
                else:
                    out += diff(e, kb[k], f"{path}{_label(k)}")
            for k, e in kb.items():
                if k not in ka:
                    out.append(("added", f"{path}{_label(k)}", None, e.get("properties")))
            if not out and list(ka) != list(kb):
                out.append(("order", path.lstrip("."), None, None))
            return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b) or any(x != y for x, y in zip(a, b)):
            if sorted(map(json.dumps, a)) == sorted(map(json.dumps, b)):
                return [("order", path.lstrip("."), None, None)]
            if len(a) == len(b):
                for k, (x, y) in enumerate(zip(a, b)):
                    out += diff(x, y, f"{path}[{k}]")
                return out
            return [("changed", path.lstrip("."), a, b)]
        return [d for k, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{k}]")]
    if a != b:
        return [("changed", path.lstrip("."), a, b)]
    if type(a) is not type(b):                                    # 32.0 == 32 in Python, not in the file
        return [("format", path.lstrip("."), a, b)]
    return []


SCHEMA_RE = re.compile(r"/definition/([A-Za-z]+)/(\d+\.\d+\.\d+)/")


def owner(rel, doc):
    """Visual ID (or file label) a file belongs to."""
    parts = rel.split("/")
    if "visuals" in parts:
        folder = parts[parts.index("visuals") + 1]
        m = ID_RE.match(folder)
        return m.group(1) if m else f"(no ID) {folder}"
    if rel.endswith("page.json"):
        return f"page {doc.get('displayName', parts[-2]) if isinstance(doc, dict) else parts[-2]}"
    return rel.replace("definition/", "")


def _short(v, n=90):
    t = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return t if len(t) <= n else t[:n - 3] + "..."


def proposal(kind, path, a, b):
    """One line: what pbik should change."""
    if kind == "schema":
        return f"$schema {a} -> {b}: write the version Desktop writes"
    if kind == "added":
        return f"Desktop adds {path} = {_short(b)}: write it too"
    if kind == "removed":
        return f"Desktop drops {path} (pbik wrote {_short(a)}): stop writing it"
    if kind == "changed":
        return f"Desktop rewrites {path}: {_short(a, 50)} -> {_short(b, 50)}"
    if kind == "format":
        return f"Desktop writes {path} as {_short(b)} (pbik: {_short(a)}): same value, Desktop's form"
    if kind == "order":
        return f"key or entry order differs in {path or 'the file'} (content the same)"
    return f"{kind} {path}"


def generic(kind, path, a, b):
    """The same fix seen on many visuals: the path without positions and values (for the summary)."""
    p = re.sub(r"\[\d+\]", "[]", path)
    p = re.sub(r"@\{.*?\}(?=\.|$)", "@<selector>", p)
    if kind in ("format",) and p.startswith("position."):
        return "format: position values written as decimals where Desktop writes whole numbers"
    if kind == "schema":
        return f"schema: {a} -> {b}"
    return f"{kind}: {p}"


def compare(before, after):
    """{owner: [(kind, path, pbik, desktop)]}, newline count, files only on one side."""
    found, newline, only = {}, 0, []
    for rel in sorted(set(before) | set(after)):
        if rel not in after:
            only.append(f"Desktop deleted {rel}")
            continue
        if rel not in before:
            only.append(f"Desktop added {rel}")
            continue
        ta, tb = before[rel], after[rel]
        if ta == tb:
            continue
        if ta.endswith("\n") and not tb.endswith("\n"):
            newline += 1
        try:
            a, b = json.loads(ta), json.loads(tb)
        except json.JSONDecodeError as e:
            only.append(f"{rel}: not JSON ({e})")
            continue
        ds = []
        sa, sb = (a.pop("$schema", None), b.pop("$schema", None)) if isinstance(a, dict) and isinstance(b, dict) else (None, None)
        if sa != sb:
            ma, mb = SCHEMA_RE.search(sa or ""), SCHEMA_RE.search(sb or "")
            ds.append(("schema", "$schema", f"{ma.group(1)} {ma.group(2)}" if ma else sa,
                       f"{mb.group(1)} {mb.group(2)}" if mb else sb))
        ds += diff(a, b)
        if ds:
            found.setdefault(owner(rel, b), []).extend(ds)
    return found, newline, only


def report_text(found, newline, only, label):
    lines = [f"# pbik roundtrip: {label}", "",
             "What Desktop rewrote on its first save of files pbik wrote, as proposed pbik fixes. Nothing was changed.",
             ""]
    counts = {}
    for who, ds in found.items():
        for d in ds:
            if d[0] != "order":
                counts.setdefault(generic(*d), set()).add(who)
    lines.append("## Proposed pbik fixes (by how many visuals or files show them)")
    lines.append("")
    if newline:
        lines.append(f"- newline: Desktop drops the final newline ({newline} file(s)). pbik keeps it on purpose: "
                     "it marks files Desktop hasn't saved (`pbik catalog`).")
    for g, whos in sorted(counts.items(), key=lambda x: (-len(x[1]), x[0])):
        ws = sorted(whos)
        lines.append(f"- {g}  ({len(ws)}: {', '.join(ws[:8])}{' ...' if len(ws) > 8 else ''})")
    if not counts and not newline:
        lines.append("- none: Desktop kept everything pbik wrote.")
    lines += ["", "## By visual ID", ""]
    for who in sorted(found, key=lambda w: (not re.match(r"P\d+-V", w), w)):
        lines.append(f"### {who}")
        for d in found[who]:
            lines.append(f"- {d[0]}: {proposal(*d)}")
        lines.append("")
    if only:
        lines += ["## Files on one side only", ""] + [f"- {x}" for x in only] + [""]
    return "\n".join(lines)


def roundtrip(report_path, rev=None, to=None, before=None, out=None):
    rep = Report(report_path)
    try:
        if before:
            b_rep = Report(before)
            left, label_a = side_from_folder(b_rep.path), str(before)
        else:
            left, label_a = side_from_git(rep.path, rev or "HEAD"), rev or "HEAD"
        if to:
            right, label_b = side_from_git(rep.path, to), to
        else:
            right, label_b = side_from_folder(rep.path), "working tree"
    except RuntimeError as e:
        fail(f"git: {e} (pass --before <copy of the report as pbik wrote it> outside a git repository)")
    found, newline, only = compare(left, right)
    text = report_text(found, newline, only, f"{rep.path.name}, pbik = {label_a}, Desktop = {label_b}")
    print(text)
    if out:
        p = pathlib.Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {p}")
    return found
