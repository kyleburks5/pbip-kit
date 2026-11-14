r"""Claude Code UserPromptSubmit hook: every message the person sends in a project counts as one interaction (v1.7 live
walkthrough fix 17), so the interaction counter matches what happened without the agent remembering to mark it.

It appends {"event": "interaction", "step": "message", "source": "hook"} to the project's .pbik/steps.jsonl (the
same log `pbik step note --interaction` writes; pbikit/steps.py counts each message and window answer once). Only in a
project (design/status.json exists): never in the master kit. It never blocks a message and prints nothing.
Copilot has no hooks: there the agent marks each message itself.
"""
import datetime, json, os, pathlib, sys


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        data = {}
    root = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    if not (root / "design" / "status.json").exists():
        return 0
    log = root / ".pbik" / "steps.jsonl"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        (log.parent / ".gitignore").write_text("*\n", encoding="utf-8")
        rec = {"event": "interaction", "step": "message", "source": "hook",
               "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
