"""Build history and the build option (docs/design/phase1-usability.md, A4).

Every finished build adds one line to a personal file outside every project, %USERPROFILE%\\.pbik\\builds.jsonl
(PBIK_HOME in tests): when, build option, report type, polish score, interactions, minutes, hand-polish minutes,
kit version. No data and no table, measure or project names.

Default option: guided build until a quick build of that report type has reached the target (7/10); after that the
person's last choice, or the team default (team.json `defaultMode` in a team pack folder). If the last 3 quick builds
of a type average below 7, or below the guided builds of that type, the start suggests a guided build.
"""
import datetime, json, os, pathlib

TARGET = 7
MODES = ("guided", "quick")


def history_file():
    return pathlib.Path(os.environ.get("PBIK_HOME") or pathlib.Path.home() / ".pbik") / "builds.jsonl"


def read():
    f = history_file()
    out = []
    for ln in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def record(mode, report_type, score, interactions=None, minutes=None, hand_minutes=None, kit=None):
    from . import __version__
    f = history_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": datetime.datetime.now().isoformat(timespec="seconds"), "mode": mode, "reportType": report_type,
           "score": score, "interactions": interactions, "minutes": minutes, "handMinutes": hand_minutes,
           "kit": kit or __version__}
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def set_hand_minutes(minutes):
    """The person's hand-polish minutes, asked at the wrap-up, on the last build."""
    rows = read()
    if not rows:
        return None
    rows[-1]["handMinutes"] = minutes
    history_file().write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return rows[-1]


def _avg(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 1) if xs else None


def default_mode(report_type, team_default=None, rows=None):
    """(mode, why) for a new build of this report type."""
    rows = read() if rows is None else rows
    quick_ok = any(r.get("mode") == "quick" and r.get("reportType") == report_type and (r.get("score") or 0) >= TARGET
                   for r in rows)
    if not quick_ok:
        return "guided", f"guided build until a quick build of this kind of report reaches {TARGET}/10"
    if rows and rows[-1].get("mode") in MODES:
        return rows[-1]["mode"], "your last choice"
    if team_default in MODES:
        return team_default, "the team default"
    return "guided", "the default"


def suggestion(report_type, rows=None):
    """A plain suggestion to build guided, or None."""
    rows = read() if rows is None else rows
    quick = [r.get("score") for r in rows if r.get("mode") == "quick" and r.get("reportType") == report_type][-3:]
    guided = [r.get("score") for r in rows if r.get("mode") == "guided" and r.get("reportType") == report_type]
    q, g = _avg(quick), _avg(guided)
    if len(quick) < 3 or q is None:
        return None
    if q < TARGET or (g is not None and q < g):
        vs = f"{q} vs {g}" if g is not None else f"{q}, below the {TARGET} target"
        return f"Quick builds of this kind of report have scored lower ({vs}); I suggest a guided build."
    return None


def team_default(root):
    from . import packs as PK
    from .synth import read_json
    for folder, team in PK.pack_folders(root):
        if team:
            m = (read_json(pathlib.Path(folder) / "team.json") or {}).get("defaultMode")
            if m in MODES:
                return m
    return None
