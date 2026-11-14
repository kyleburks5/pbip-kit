"""`pbik --report json <command>`: a machine summary the agent turns into plain words (docs/PLAIN-WORDS.md).

{"ok": bool, "command": "synth contract", "exit": 0, "facts": [...], "needs": [{"kind": "error"|"warning"|"gate",
...}], "next": [...]}. Facts are the command's own lines; needs are what someone has to act on: errors, warnings and the
person-only gates (by task name, never a command). The agent never shows the user a path or a command
(docs/design/phase1-usability.md, section 1).
"""
import contextlib, io, json, re

# person-only steps a command may ask for -> the gate and the VS Code task (Command Palette > Tasks: Run Task)
GATES = {
    "synth-approve": ("Approve the model", r"pbik synth approve|synth approve --by"),
    "map-approve": ("Approve the name map", r"bind map approve"),
    "model-approve": ("Approve model changes", r"pbik model approve|model approve <pack>"),
    "bind-live": ("Connect to the live model", r"pbik bind live"),
    "bind-local": ("Back to the synthetic model", r"pbik bind local"),
    "class-lower": ("Loosen the data class", r"lower the data class"),
    "pack-register": ("Share the model pack", r"register to the team folder"),
}
LEVEL = re.compile(r"^\s*(error|warning|note|stale reference|pbik:)\s*", re.I)
# v1.7 walkthrough fix 13: a result never tells the person to run a command, and never passes on a raw error.
CMD = re.compile(r"`(?:pbik|python|powershell|pwsh|git|pip|code|tools[\\/])[^`]*`", re.I)
INSTRUCT = re.compile(r"[,;:]?\s*\(?(?:then\s+)?(?:a person\s+)?(?:run|runs|rerun|pass|use|try)\s+`[^`]+`"
                      r"(?:\s+(?:first|again|with [^.;)]*))?\)?", re.I)
RAW = re.compile(r"^\s*(?:\[raw\] |At (?:[A-Z]:\\|line:)|\+ |\+\s*~|~{4,}|CategoryInfo|FullyQualifiedErrorId|"
                 r"Traceback \(most recent call last\)|File \"[^\"]+\", line \d+|[A-Za-z]+Error: |"
                 r"Exception calling|at System\.)")


def plain_text(text, hints):
    """The text without any instruction to run a command; the commands go to `hints` (for the agent only)."""
    for m in CMD.findall(text):
        hints.append(m.strip("`"))
    t = INSTRUCT.sub("", text)
    t = CMD.sub("the step for it", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ;,:")
    return t or text


def classify(lines):
    facts, needs, nxt = [], [], []
    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            continue
        m = LEVEL.match(s)
        if m:
            kind = m.group(1).lower().rstrip(":")
            kind = "error" if kind in ("pbik", "stale reference") else kind
            text = s[m.end():].strip()
            (needs if kind in ("error", "warning") else facts).append(
                {"kind": kind, "text": text} if kind in ("error", "warning") else text)
        else:
            facts.append(s.strip())
        for gate, (task, pat) in GATES.items():
            if re.search(pat, s, re.I) and not any(n.get("gate") == gate for n in needs if isinstance(n, dict)):
                needs.append({"kind": "gate", "gate": gate, "task": task})
        if s.strip().lower().startswith(("next", "then:")):
            nxt.append(s.strip())
    return facts, needs, nxt


def run_json(command, fn):
    """Run fn() with its output captured; return (exit code, JSON text)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = fn() or 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
            if isinstance(e.code, str) and e.code.strip():       # SystemExit("message"): its text was lost before
                err.write("\npbik: " + e.code.strip() + "\n")
        except Exception as e:                                    # noqa: BLE001  never a traceback, never empty
            code = 1
            err.write(f"\npbik: {type(e).__name__}: {e}\n")
    lines = (out.getvalue() + "\n" + err.getvalue()).splitlines()
    raw = [ln for ln in lines if RAW.match(ln)]
    lines = [ln for ln in lines if not RAW.match(ln)]
    facts, needs, nxt = classify(lines)
    hints = []
    facts = [plain_text(f, hints) if isinstance(f, str) else f for f in facts]
    for n in needs:
        if n.get("text"):
            n["text"] = plain_text(n["text"], hints)
    nxt = [plain_text(x, hints) for x in nxt]
    if raw and not any(isinstance(n, dict) and n.get("kind") == "error" for n in needs):
        needs.append({"kind": "error", "text": "something went wrong inside this step; I'll look at what happened "
                                               "before going on"})
    if code and not facts and not any(isinstance(n, dict) and n.get("kind") == "error" for n in needs):
        needs.append({"kind": "error", "text": f"it stopped without saying why (exit code {code}); I'll look into it "
                                               "before going on"})
    doc = {"ok": code == 0, "command": command, "exit": code, "facts": facts, "needs": needs, "next": nxt}
    if hints or raw:          # for the agent only: never shown to the person
        doc["agent"] = {"commands": list(dict.fromkeys(hints)), "raw": raw[:20]}
    return code, json.dumps(doc, ensure_ascii=False, indent=1)
