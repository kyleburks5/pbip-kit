"""`pbik step start|end <step>`: mark each workflow step, for token tracking (docs/design/phase1-usability.md, 6).

The agent runs `pbik step start brd` before a step and `pbik step end brd` after it. Lines go to .pbik/steps.jsonl
(git-ignored); tools/usage.py joins them with the session's token usage.
"""
import datetime, json, pathlib


def log_file(root):
    return pathlib.Path(root) / ".pbik" / "steps.jsonl"


def mark(root, event, step, outcome=None, now=None, source=None):
    f = log_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    (f.parent / ".gitignore").write_text("*\n", encoding="utf-8")
    rec = {"event": event, "step": step,
           "at": (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(timespec="seconds")}
    if outcome:
        rec["outcome"] = outcome
    if source:
        rec["source"] = source
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def interaction(root, what="reply", now=None, source=None):
    """One interaction: a message from the person or an approval window answer (v1.7, A9). Sources: "hook" (the chat
    app's hook counts every message itself), "window" (the approval window counts its own answer), or none (the agent
    marked it, as in an app without the hook)."""
    return mark(root, "interaction", what, now=now, source=source)


def interactions(root, since=None):
    """Every interaction logged (since a time, e.g. a build's start): [(what, at)]. Each message and each window
    answer counts once (v1.7 live walkthrough fix 17): once the hook counts messages, the agent's own message notes
    aren't counted again; once a window counts its own answer, the agent's "window:" notes aren't either."""
    f = log_file(root)
    recs = []
    for ln in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("event") == "interaction":
            recs.append(r)
    hook = any(r.get("source") == "hook" for r in recs)
    win = any(r.get("source") == "window" for r in recs)
    out = []
    for r in recs:
        is_window = str(r["step"]).startswith("window:")
        if is_window and win and r.get("source") != "window":
            continue
        if not is_window and hook and r.get("source") != "hook":
            continue
        at = datetime.datetime.fromisoformat(r["at"])
        if at.tzinfo is None:
            at = at.replace(tzinfo=datetime.timezone.utc)
        if since is None or at >= since:
            out.append((r["step"], at))
    return out


def windows(root):
    """[(step, start, end, outcome)] from the log; a step still open ends now."""
    f = log_file(root)
    opened, out = {}, []
    for ln in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        r = json.loads(ln)
        at = datetime.datetime.fromisoformat(r["at"])
        if r["event"] == "interaction":
            continue
        if r["event"] == "start":
            opened[r["step"]] = at
        elif r["event"] == "end" and r["step"] in opened:
            out.append((r["step"], opened.pop(r["step"]), at, r.get("outcome")))
    now = datetime.datetime.now(datetime.timezone.utc)
    out += [(s, t, now, "open") for s, t in opened.items()]
    return sorted(out, key=lambda x: x[1])
