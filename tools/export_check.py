"""Clean-export check: run it before every push (README "Before you push").

    python tools/export_check.py              tracked files, unpushed commits and their messages, unpushed tags
    python tools/export_check.py --names "A B" extra names to look for (git user.name and the login are always used)

Looks for personal paths (C:\\Users\\<name>, /Users/<name>, /home/<name>), user names, email addresses, secrets
(keys, tokens, passwords, connection secrets), real data files (csv, xlsx, xls, pbix, abf, parquet, cache) and smoke,
scratch or sample folders. A path or folder that belongs in the kit (a made-up test sample, an address meant to be
public) is listed in tools/export_allow.txt with its reason. Prints a pass/fail table; exit 1 on any finding.
"""
import argparse, fnmatch, getpass, os, pathlib, re, subprocess, sys

KIT = pathlib.Path(__file__).resolve().parents[1]
ALLOW = KIT / "tools" / "export_allow.txt"
DATA_EXT = {".csv", ".xlsx", ".xls", ".pbix", ".abf", ".parquet", ".cache"}
FOLDERS = re.compile(r"(^|/)(pbik-smoke[^/]*|_snapshots|_pbik-built[^/]*|scratch[^/]*|\.pbik|[^/]*sample[^/]*|"
                     r"[^/]*smoke[^/]*)(/|$)", re.I)
PATHS = re.compile(r"(?i)(?:[a-z]:[\\/]+users[\\/]+(?!public\b|default\b|<)[^\\/\s\"'`<>]+|/users/(?!shared\b|<)"
                   r"[^/\s\"'`<>]+/|/home/(?!<)[^/\s\"'`<>]+/)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_OK = re.compile(r"(?i)(noreply@anthropic\.com|@example\.(com|org|net)$|\.invalid$|@users\.noreply\.github\.com$|"
                      r"^git@github\.com$)")
SECRETS = [("AWS key", r"AKIA[0-9A-Z]{16}"), ("GitHub token", r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"),
           ("API key", r"\bsk-[A-Za-z0-9]{20,}"), ("Slack token", r"xox[baprs]-[A-Za-z0-9-]{10,}"),
           ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
           ("password", r"(?i)\b(password|passwd|pwd)\s*[=:]\s*['\"][^'\"\s]{4,}['\"]"),
           ("connection secret", r"(?i)(AccountKey|SharedAccessKey|client_secret|SharedAccessSignature)\s*=\s*[^;\s\"']{8,}")]
CHECKS = ["personal paths", "user names", "emails", "secrets", "data files", "smoke/sample/scratch folders"]


def git(*args):
    r = subprocess.run(["git", *args], cwd=KIT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def allow_list(path=ALLOW):
    """[(check or *, glob)] from export_allow.txt: `<check> | <glob> | <reason>` per line."""
    out = []
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            parts = [x.strip() for x in ln.split("|")]
            if ln.strip() and not ln.lstrip().startswith("#") and len(parts) >= 3 and parts[2]:
                out.append((parts[0], parts[1]))
    return out


def allowed(allow, check, where, text=""):
    return any((c in (check, "*")) and (fnmatch.fnmatch(where, g) or (text and fnmatch.fnmatch(text, g)))
               for c, g in allow)


def name_words(extra=()):
    names = [git("config", "user.name").strip(), getpass.getuser(), os.environ.get("USERNAME", ""), *extra]
    words = set()
    for n in names:
        words |= {w for w in re.split(r"[\s._-]+", n.lower()) if len(w) >= 3}
        if n.strip():
            words.add(n.strip().lower())
    return sorted(words, key=len, reverse=True)


def scan_text(where, text, words, allow, found):
    for m in PATHS.finditer(text):
        if not allowed(allow, "personal paths", where, m.group(0)):
            found["personal paths"].append(f"{where}: {m.group(0)}")
    low = text.lower()
    for w in words:
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low):
            if not allowed(allow, "user names", where, text[m.start():m.end()]):
                found["user names"].append(f"{where}: {text[m.start():m.end()]!r}")
                break
    for m in EMAIL.finditer(text):
        if not EMAIL_OK.search(m.group(0)) and not allowed(allow, "emails", where, m.group(0)):
            found["emails"].append(f"{where}: {m.group(0)}")
    for label, pat in SECRETS:
        for m in re.finditer(pat, text):
            if not allowed(allow, "secrets", where, m.group(0)):
                found["secrets"].append(f"{where}: {label}")


def scan_path(path, allow, found):
    p = path.replace("\\", "/")
    if pathlib.PurePosixPath(p).suffix.lower() in DATA_EXT and not allowed(allow, "data files", p):
        found["data files"].append(p)
    folder = p.rsplit("/", 1)[0] + "/" if "/" in p else ""     # folder names only, not file names (smoke.md)
    if FOLDERS.search(folder) and not allowed(allow, "smoke/sample/scratch folders", p):
        found["smoke/sample/scratch folders"].append(p)


def upstream():
    u = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
    return u or ("origin/main" if git("rev-parse", "--verify", "-q", "origin/main").strip() else None)


def run(extra_names=(), allow_path=ALLOW, out=print):
    allow = allow_list(allow_path)
    words = name_words(extra_names)
    found = {c: [] for c in CHECKS}
    files = [f for f in git("ls-files", "-z").split("\0") if f]
    for f in files:
        scan_path(f, allow, found)
        fp = KIT / f
        try:
            data = fp.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:4096]:
            continue                                     # binary
        scan_text(f, data.decode("utf-8", errors="replace"), words, allow, found)
    up = upstream()
    rng = f"{up}..HEAD" if up else "HEAD"
    for sha in git("rev-list", rng).split():
        msg = git("log", "-1", "--format=%B", sha)
        scan_text(f"commit {sha[:7]} message", msg, words, allow, found)
        for f in git("show", "--name-only", "--format=", sha).split("\n"):
            if f.strip():
                scan_path(f.strip(), allow, found)      # files added then removed in a later commit still ship
    remote_tags = set(re.findall(r"refs/tags/([^\s^]+)", git("ls-remote", "--tags", "origin")))
    for t in git("tag").split():
        if t not in remote_tags:
            scan_text(f"tag {t} message", git("tag", "-l", "--format=%(contents)", t), words, allow, found)
    found = {c: list(dict.fromkeys(v)) for c, v in found.items()}
    out(f"{'check':30} result  findings")
    for c in CHECKS:
        out(f"{c:30} {'PASS' if not found[c] else 'FAIL':6}  {len(found[c])}")
    for c in CHECKS:
        for x in found[c][:50]:
            out(f"  {c}: {x}")
    total = sum(len(v) for v in found.values())
    out(f"\n{len(files)} tracked file(s), commits {rng}: {'clean' if not total else f'{total} finding(s)'}")
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--names", default="", help="extra names (space- or comma-separated) to look for")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(errors="replace")
    found = run([x for x in re.split(r"[,\s]+", a.names) if x])
    return 1 if any(found.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
