"""`pbik step start|end <step>`: mark each workflow step, for token tracking (docs/design/phase1-usability.md, 6).

The agent runs `pbik step start brd` before a step and `pbik step end brd` after it. Lines go to .pbik/steps.jsonl
(git-ignored); tools/usage.py joins them with the session's token usage.
"""
import datetime, json, pathlib


def log_file(root):
    return pathlib.Path(root) / ".pbik" / "steps.jsonl"


def mark(root, event, step, outcome=None, now=None):
    f = log_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    (f.parent / ".gitignore").write_text("*\n", encoding="utf-8")
    rec = {"event": event, "step": step,
           "at": (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(timespec="seconds")}
    if outcome:
        rec["outcome"] = outcome
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def windows(root):
    """[(step, start, end, outcome)] from the log; a step still open ends now."""
    f = log_file(root)
    opened, out = {}, []
    for ln in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        r = json.loads(ln)
        at = datetime.datetime.fromisoformat(r["at"])
        if r["event"] == "start":
            opened[r["step"]] = at
        elif r["event"] == "end" and r["step"] in opened:
            out.append((r["step"], opened.pop(r["step"]), at, r.get("outcome")))
    now = datetime.datetime.now(datetime.timezone.utc)
    out += [(s, t, now, "open") for s, t in opened.items()]
    return sorted(out, key=lambda x: x[1])
