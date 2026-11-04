"""The kit's lessons: format, indexes, budgets, duplicates and housekeeping (docs/lessons/README.md).

    python tools/lessons.py check            format, indexes, budgets, duplicates, no PROJECT-ONLY lesson (tests run it)
    python tools/lessons.py index            rewrite each lesson file's Index and the README's list of lessons
    python tools/lessons.py status           budgets, and reports wrapped up since the last /tidy (/wrapup ends with it)
    python tools/lessons.py similar          pairs of lessons that share most of their words (duplicates or contradictions?)
    python tools/lessons.py stale            lessons naming files that don't exist, and kit scripts nothing mentions
    python tools/lessons.py changelog [--days N]   VERSIONS.md changelog rows older than N days (default 30)
    python tools/lessons.py find WORD ...    lessons whose text holds every word (look before adding a new one)

A lesson in docs/lessons/<topic>.md is a `## <ID> <name>` section with four fields, one bullet each:
    - **Rule:** what to do, in one or two sentences.
    - **Why:** what went wrong without it.
    - **Enforced by:** the check, test, token or template that enforces it, or "not enforced (<when it is read>)".
    - **Source:** the rep, smoke or check it came from (Rep 9; /smoke 2026-10-18).
IDs are the file's prefix and a number (B-01), never reused: a retired lesson moves to docs/lessons/_retired.md.
Each file starts with an `## Index` table (ID | Lesson | Enforced by), written by `index`; reference material
(tables, worked examples) goes under `## Reference` after the lessons.
Budgets: CLAUDE.md 150 lines, a lesson file 120, a pattern entry (docs/patterns/<name>.md) 80. At the budget: a
warning; more than 25% over: an error. Two lessons with the same rule are an error.
Lessons marked PROJECT-ONLY belong to a report project, never to the kit (the master): `check` fails on one here.
"""
import argparse, datetime, itertools, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LESSONS = ROOT / "docs" / "lessons"
README = LESSONS / "README.md"
RETIRED = LESSONS / "_retired.md"
PREFIX = {"build": "B", "cards": "C", "slicers": "S", "charts": "CH", "dax": "D", "accessibility": "A",
          "audit-modes": "AM"}
FIELDS = ("Rule", "Why", "Enforced by", "Source")
BUDGETS = {"CLAUDE.md": 150, "lesson file": 120, "pattern entry": 80}
OVER = 1.25                                            # an error past budget x 1.25
HEAD_RE = re.compile(r"^## ([A-Z]{1,2}-\d{2}) (.+)$")
FIELD_RE = re.compile(r"^- \*\*(Rule|Why|Enforced by|Source):\*\* ?(.*)$")
INDEX_START, INDEX_END = "<!-- lessons:index -->", "<!-- /lessons:index -->"
ALL_START, ALL_END = "<!-- lessons:all -->", "<!-- /lessons:all -->"
NOT_ENFORCED = "not enforced"


def lesson_files():
    return [LESSONS / f"{name}.md" for name in PREFIX if (LESSONS / f"{name}.md").exists()]


def read(f):
    return f.read_text(encoding="utf-8").replace("\r\n", "\n")


def parse(f):
    """[{id, name, Rule, Why, Enforced by, Source, file, line}] and format problems of one lesson file."""
    lines, out, probs, cur = read(f).split("\n"), [], [], None
    prefix = PREFIX.get(f.stem)
    for k, ln in enumerate(lines, 1):
        if ln.startswith("## "):
            cur = None
            m = HEAD_RE.match(ln)
            if m:
                cur = {"id": m.group(1), "name": m.group(2).strip(), "file": f.name, "line": k}
                out.append(cur)
                if prefix and not m.group(1).startswith(prefix + "-"):
                    probs.append(f"{f.name}:{k}: {m.group(1)} should start with {prefix}-")
            elif ln.strip() not in ("## Index", "## Reference"):
                probs.append(f"{f.name}:{k}: section {ln[3:]!r} is not '## <ID> <name>', '## Index' or '## Reference'")
            continue
        if cur is None:
            continue
        m = FIELD_RE.match(ln)
        if m:
            cur[m.group(1)] = m.group(2).strip()
            cur["_last"] = m.group(1)
        elif ln.startswith("  ") and cur.get("_last"):          # a field continued on the next line
            cur[cur["_last"]] += " " + ln.strip()
        elif ln.strip():
            probs.append(f"{f.name}:{k}: {cur['id']}: text outside its four fields: {ln.strip()[:60]!r}")
    for les in out:
        les.pop("_last", None)
        for fld in FIELDS:
            if not les.get(fld):
                probs.append(f"{f.name}:{les['line']}: {les['id']} has no **{fld}:**")
    ids = [x["id"] for x in out]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        probs.append(f"{f.name}: {dup} used twice")
    return out, probs


def all_lessons():
    les, probs = [], []
    for f in lesson_files():
        a, b = parse(f)
        les += a
        probs += b
    return les, probs


def enforced(les):
    e = les.get("Enforced by", "")
    return bool(e) and not e.lower().startswith(NOT_ENFORCED)


def short(les, n=80):
    return les["name"] if len(les["name"]) <= n else les["name"][:n - 1] + "…"


def index_table(lessons):
    rows = ["| ID | Lesson | Enforced by |", "| --- | --- | --- |"]
    for x in lessons:
        e = x.get("Enforced by", "") if enforced(x) else "–"
        rows.append(f"| {x['id']} | {short(x).replace('|', '/')} | {e.replace('|', '/')} |")
    return "\n".join(rows)


def readme_list():
    rows = ["| ID | Lesson | File | Enforced |", "| --- | --- | --- | --- |"]
    for f in lesson_files():
        for x in parse(f)[0]:
            rows.append(f"| {x['id']} | {short(x).replace('|', '/')} | [{f.name}]({f.name}) | "
                        f"{'yes' if enforced(x) else '–'} |")
    return "\n".join(rows)


def put_block(text, start, end, body):
    if start not in text or end not in text:
        return None
    a, b = text.index(start) + len(start), text.index(end)
    return text[:a] + "\n" + body + "\n" + text[b:]


def write_indexes(dry=False):
    """Rewrite the Index of each lesson file and the README list. Returns the files that changed (or would)."""
    changed = []
    for f in lesson_files() + [README]:
        text = read(f)
        if f == README:
            new = put_block(text, ALL_START, ALL_END, readme_list())
        else:
            new = put_block(text, INDEX_START, INDEX_END, index_table(parse(f)[0]))
        if new is not None and new != text:
            changed.append(f)
            if not dry:
                f.write_text(new, encoding="utf-8")
    return changed


def words(s):
    return set(re.findall(r"[a-z0-9]+", s.lower())) - {"the", "a", "an", "and", "or", "of", "to", "in", "on", "it",
                                                       "is", "its", "for", "with", "by", "be", "as", "at", "this"}


def norm(s):
    return " ".join(re.findall(r"[a-z0-9]+", s.lower()))


def duplicates(lessons):
    seen, out = {}, []
    for x in lessons:
        key = norm(x.get("Rule", ""))
        if key and key in seen:
            out.append(f"{x['id']} repeats the rule of {seen[key]}")
        seen.setdefault(key, x["id"])
    return out


def similar(lessons, threshold=0.5):
    out = []
    for a, b in itertools.combinations(lessons, 2):
        wa, wb = words(a.get("Rule", "")), words(b.get("Rule", ""))
        if wa and wb and len(wa & wb) / len(wa | wb) >= threshold:
            out.append((a["id"], b["id"], round(len(wa & wb) / len(wa | wb), 2)))
    return out


def budgets():
    """[(what, file, lines, budget)] for CLAUDE.md, every lesson file and every pattern entry."""
    out = [("CLAUDE.md", ROOT / "CLAUDE.md", BUDGETS["CLAUDE.md"])]
    out += [("lesson file", f, BUDGETS["lesson file"]) for f in lesson_files()]
    out += [("pattern entry", f, BUDGETS["pattern entry"]) for f in sorted((ROOT / "docs" / "patterns").glob("*.md"))
            if f.name != "README.md"]
    return [(what, f, len(read(f).rstrip("\n").split("\n")), b) for what, f, b in out]


def budget_findings():
    warns, errs = [], []
    for what, f, n, b in budgets():
        rel = f.relative_to(ROOT).as_posix()
        if n > b * OVER:
            errs.append(f"{rel}: {n} lines, over 25% past its {what} budget of {b}: run /tidy")
        elif n >= b:
            warns.append(f"{rel}: {n} lines, at or past its {what} budget of {b}")
    return warns, errs


def project_only(lessons):
    return [f"{x['id']} is marked PROJECT-ONLY: it belongs to the report project, not the kit"
            for x in lessons if "PROJECT-ONLY" in " ".join(str(v) for v in x.values())]


def check():
    lessons, probs = all_lessons()
    errs = list(probs) + duplicates(lessons) + project_only(lessons)
    stale_idx = write_indexes(dry=True)
    errs += [f"{f.relative_to(ROOT).as_posix()}: index out of date: run python tools/lessons.py index" for f in stale_idx]
    warns, berrs = budget_findings()
    return warns, errs + berrs


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def reports_since_tidy():
    """(last pre-tidy tag or None, wrap-up commits since it)."""
    tags = sorted(git("tag", "--list", "pre-tidy-*").split())
    last = tags[-1] if tags else None
    log = git("log", "--format=%s", f"{last}..HEAD" if last else "HEAD")
    return last, sum(1 for s in log.splitlines() if s.lower().startswith("wrapup:"))


def tidy_due():
    """Reasons to suggest /tidy (Copilot /kit-tidy): a budget within 10% of its limit, or 3+ reports since the last."""
    why = []
    for what, f, n, b in budgets():
        if n >= b * 0.9:
            why.append(f"{f.relative_to(ROOT).as_posix()} at {n} of {b} lines")
    last, n = reports_since_tidy()
    if n >= 3:
        why.append(f"{n} reports wrapped up since {'the last tidy (' + last + ')' if last else 'the kit began'}")
    return why


REP_OUTPUTS = ("design/specs/", "design/reviews/", "design/wireframes/", "design/reference/brd.md")   # made per rep
PATH_RE = re.compile(r"\b((?:design|docs|tools|\.claude|examples)/[\w./-]+\.(?:py|md|json|ps1|html))\b")


def stale():
    """(lessons naming kit files that don't exist, kit scripts no command, doc, rule, test or script mentions)."""
    lessons, _ = all_lessons()
    gone = []
    for x in lessons:
        for p in PATH_RE.findall(" ".join(x.get(k, "") for k in FIELDS)):
            if not p.startswith(REP_OUTPUTS) and not (ROOT / p.rstrip(".")).exists():
                gone.append(f"{x['id']} ({x['file']}) names {p}, which doesn't exist")
    texts = []
    for pat in ("*.md", ".claude/**/*.md", "docs/**/*.md", "design/**/*.md", "tools/**/*.md", "tools/**/*.py",
                "design/**/*.py", "tools/**/*.ps1", ".claude/**/*.ps1", ".github/**/*.md"):
        texts += [read(f) for f in ROOT.glob(pat) if "archive" not in f.parts and "_archive" not in f.parts]
    blob = "\n".join(texts)
    unused = []
    for f in sorted(list((ROOT / "design" / "scripts").glob("*.py")) + list((ROOT / "tools").glob("*/*.py"))):
        if f.name.startswith("test_") or f.name == "__init__.py" or "pbik" in f.parts:
            continue
        if blob.count(f.stem) <= 1:                     # only its own docstring names it
            unused.append(f.relative_to(ROOT).as_posix())
    return gone, unused


def changelog_rows(days=30, today=None):
    today = today or datetime.date.today()
    out = []
    for ln in read(ROOT / "VERSIONS.md").split("\n"):
        m = re.match(r"\| (\d{4}-\d{2}-\d{2}) \|", ln)
        if m and (today - datetime.date.fromisoformat(m.group(1))).days > days:
            out.append(ln[:140])
    return out


def main(argv=None):
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("check", "index", "status", "similar", "stale"):
        sub.add_parser(c)
    cl = sub.add_parser("changelog")
    cl.add_argument("--days", type=int, default=30)
    fd = sub.add_parser("find")
    fd.add_argument("words", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        warns, errs = check()
        for w in warns:
            print(f"warning: {w}")
        for e in errs:
            print(f"error: {e}")
        n = len(all_lessons()[0])
        print(f"{n} lessons; {len(errs)} error(s), {len(warns)} warning(s)")
        return 1 if errs else 0
    if a.cmd == "index":
        for f in write_indexes():
            print(f"wrote {f.relative_to(ROOT).as_posix()}")
        return 0
    if a.cmd == "status":
        for what, f, n, b in budgets():
            flag = "OVER" if n > b * OVER else "at budget" if n >= b else ""
            print(f"{n:4} / {b:3}  {f.relative_to(ROOT).as_posix()}  {flag}".rstrip())
        last, n = reports_since_tidy()
        print(f"reports wrapped up since {last or 'the start'}: {n}")
        why = tidy_due()
        print(("Suggest /tidy (Copilot /kit-tidy): " + "; ".join(why)) if why else "No tidy needed yet.")
        return 0
    if a.cmd == "similar":
        for x, y, s in similar(all_lessons()[0]):
            print(f"{x} ~ {y} ({s}): a duplicate to merge, or a contradiction to settle?")
        return 0
    if a.cmd == "stale":
        gone, unused = stale()
        for g in gone:
            print(f"stale lesson: {g}")
        for u in unused:
            print(f"unused file? {u} (nothing else names it)")
        if not gone and not unused:
            print("nothing stale found")
        return 0
    if a.cmd == "changelog":
        rows = changelog_rows(a.days)
        print("\n".join(rows) if rows else f"no changelog rows older than {a.days} days")
        return 0
    if a.cmd == "find":
        ws = [w.lower() for w in a.words]
        for x in all_lessons()[0]:
            text = " ".join([x["name"]] + [x.get(k, "") for k in FIELDS]).lower()
            if all(w in text for w in ws):
                print(f"{x['id']} ({x['file']}): {x['name']}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
