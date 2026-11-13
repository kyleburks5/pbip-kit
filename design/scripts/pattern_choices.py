"""The spec's "Pattern choices" section (batch 3 items 13-14), checked by audit_ids.py.

/plan writes one row per page: `| Page | Patterns | Style preset | Reason |`. Every page in layout.json (by key or
display name) needs a row with its patterns (docs/patterns/ names, or "none"), a style preset (design/themes/presets/)
and a reason. A spec without the section is a warning when it was created before the section existed (SINCE, from
git's first commit of the file), and an issue when it is newer, or not committed yet.
"""
import datetime, pathlib, re, subprocess

SINCE = datetime.date(2026, 11, 13)
ROOT = pathlib.Path(__file__).resolve().parents[2]
HEAD = re.compile(r"^#+\s*pattern choices[^\n]*\n(.*?)(?=^#+ |\Z)", re.I | re.M | re.S)


def known_patterns(root=ROOT):
    return {f.stem for f in (root / "docs" / "patterns").glob("*.md") if f.name != "README.md"}


def known_presets(root=ROOT):
    return {f.stem for f in (root / "design" / "themes" / "presets").glob("*.json")}


def created(spec, root=ROOT):
    """The date git first committed the spec, or None (not in git, or not committed yet)."""
    try:
        r = subprocess.run(["git", "log", "--diff-filter=A", "--follow", "--format=%as", "--", str(spec)], cwd=root,
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    days = [x for x in r.stdout.split() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)]
    return datetime.date.fromisoformat(days[-1]) if days else None


def rows(section):
    out = []
    for ln in section.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if ln.strip().startswith("|") and len(cells) >= 4 and not set(cells[0]) <= set("-: ") \
                and cells[0].lower() != "page":
            out.append(cells)
    return out


def check(text, layout, created_on=None, root=ROOT):
    """(issues, warnings) for the Pattern choices section of a spec."""
    m = HEAD.search(text or "")
    if not m:
        msg = "spec: no 'Pattern choices' section (one row per page: patterns, style preset, reason)"
        if created_on and created_on < SINCE:
            return [], [msg + f": the spec is from {created_on}, before the section existed; add it at the next /plan"]
        return [msg], []
    issues = []
    pats, presets = known_patterns(root), known_presets(root)
    found = rows(m.group(1))
    for key, page in (layout.get("pages") or {}).items():
        names = {key.lower(), str(page.get("displayName", "")).lower()}
        row = next((r for r in found if r[0].lower() in names), None)
        if not row:
            issues.append(f"spec: Pattern choices has no row for page {key} ({page.get('displayName', '')})")
            continue
        patterns, preset, reason = row[1], row[2], " | ".join(row[3:]).strip()
        used = [p.strip(" `") for p in re.split(r"[,;]", patterns) if p.strip(" `")]
        bad = [p for p in used if p.lower() != "none" and p not in pats]
        if not used:
            issues.append(f"spec: Pattern choices, page {key}: no patterns (write 'none' if it uses none)")
        if bad:
            issues.append(f"spec: Pattern choices, page {key}: unknown pattern(s) {bad} (docs/patterns/)")
        if presets and preset.strip(" `").lower() not in presets:
            issues.append(f"spec: Pattern choices, page {key}: style preset {preset!r} is not one of {sorted(presets)}")
        if not reason:
            issues.append(f"spec: Pattern choices, page {key}: no reason")
    return issues, []
