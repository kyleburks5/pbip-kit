"""Tokens per build step (docs/design/phase1-usability.md, section 6): the baseline for Phase 2.

    python tools/usage.py [--root .] [--transcripts <folder>] [--out design/reviews/usage.md]

Joins the steps the agent marked (`pbik step start|end`, .pbik/steps.jsonl) with Claude Code's session transcripts
(~/.claude/projects/<project folder as a name>/*.jsonl: each assistant message's `usage`, counted once per message
id) by time, and writes one row per step: minutes, input, cache write, cache read and output tokens. GitHub Copilot
doesn't expose usage locally: its column is for the premium-request count from GitHub's usage page, filled in by hand
(verify at work).
"""
import argparse, datetime, json, pathlib, re, sys

KIT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "tools" / "pbik"))

from pbikit import steps as ST  # noqa: E402

FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
TARGETS = {"first setup": (30, 45), "reuse": (0, 10)}


def transcript_folder(root):
    slug = re.sub(r"[:\\/ .]", "-", str(pathlib.Path(root).resolve()))
    return pathlib.Path.home() / ".claude" / "projects" / slug


def usage_records(folder):
    """[(time, {field: n})], one per assistant message id."""
    seen, out = set(), []
    for f in sorted(pathlib.Path(folder).glob("*.jsonl")) if pathlib.Path(folder).is_dir() else []:
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            m = d.get("message") if isinstance(d.get("message"), dict) else None
            if not m or not m.get("usage") or not d.get("timestamp"):
                continue
            mid = m.get("id") or d.get("uuid")
            if mid in seen:
                continue
            seen.add(mid)
            at = datetime.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
            out.append((at, {k: int(m["usage"].get(k) or 0) for k in FIELDS}))
    return out


def per_step(root, folder):
    rows = []
    recs = usage_records(folder)
    for step, start, end, outcome in ST.windows(root):
        tot = {k: 0 for k in FIELDS}
        n = 0
        for at, u in recs:
            if start <= at <= end:
                n += 1
                for k in FIELDS:
                    tot[k] += u[k]
        rows.append({"step": step, "minutes": round((end - start).total_seconds() / 60, 1), "messages": n,
                     "outcome": outcome or "", **tot})
    return rows


def report(rows):
    head = ["# Usage per step", "", "Tokens per workflow step (tools/usage.py; Claude Code transcripts). Copilot: "
            "fill in premium requests from GitHub's usage page (verify at work).", "",
            "| Step | Minutes | Messages | Input | Cache write | Cache read | Output | Copilot requests | Outcome |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    body = [f"| {r['step']} | {r['minutes']} | {r['messages']} | {r['input_tokens']} | "
            f"{r['cache_creation_input_tokens']} | {r['cache_read_input_tokens']} | {r['output_tokens']} |  | "
            f"{r['outcome']} |" for r in rows]
    tot = {k: sum(r[k] for r in rows) for k in ("minutes",) + FIELDS}
    body.append(f"| **total** | {round(tot['minutes'], 1)} |  | {tot['input_tokens']} | "
                f"{tot['cache_creation_input_tokens']} | {tot['cache_read_input_tokens']} | {tot['output_tokens']} |  |  |")
    targets = ["", "## Targets", "", "| Path | Target (minutes) |", "| --- | --- |"]
    targets += [f"| {k} | {a}-{b} |" if a else f"| {k} | about {b} |" for k, (a, b) in TARGETS.items()]
    return "\n".join(head + body + targets) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--transcripts", help="Claude Code transcript folder (default: this project's)")
    ap.add_argument("--out", default="design/reviews/usage.md")
    a = ap.parse_args(argv)
    rows = per_step(a.root, a.transcripts or transcript_folder(a.root))
    out = pathlib.Path(a.root) / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report(rows), encoding="utf-8")
    print(f"{len(rows)} step(s), {sum(r['output_tokens'] for r in rows)} output tokens: wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
