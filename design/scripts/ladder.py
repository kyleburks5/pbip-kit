"""Visual-method ladder (CLAUDE.md "Native first"): the step each build.method sits on, and the layout checks for it.

    1 native        native, page-background
    2 SVG           svg-measure (svg), image (a registered PNG drawn from SVG: a fallback, .claude/rules/svg.md)
    3 Deneb         deneb (certified AppSource visual; needs a native or SVG `fallback`, checked by pbik validate)
    4 custom visual custom-visual, html-measure (any other custom visual: uncertified until checked, docs/it-security.md)

/plan picks the lowest step that meets the design and records `build.step` and `build.reason` on every visual.
audit_ids.py calls issues() for each layout visual.
"""

STEPS = {"native": 1, "page-background": 1, "image": 2, "svg-measure": 2, "svg": 2, "deneb": 3,
         "custom-visual": 4, "html-measure": 4, "html": 4}
NAMES = {1: "native", 2: "SVG", 3: "Deneb", 4: "custom visual"}


def step_of(method):
    return STEPS.get(method)


def issues(v):
    """Ladder issues for one layout visual (list of text)."""
    vid, b = v.get("id") or "(no id)", v.get("build") or {}
    method, step = b.get("method"), b.get("step")
    if not method:
        return []                                   # audit_ids reports a missing method itself
    want = step_of(method)
    out = []
    if want is None:
        out.append(f"layout: {vid} build.method {method!r} is not on the ladder ({', '.join(sorted(STEPS))})")
        return out
    if step is None:
        out.append(f"layout: {vid} has no build.step ({method} is step {want}, {NAMES[want]})")
    elif step != want:
        out.append(f"layout: {vid} build.step {step!r} doesn't match {method} (step {want}, {NAMES[want]})")
    if not str(b.get("reason") or "").strip():
        out.append(f"layout: {vid} has no build.reason (why step {want} is the lowest that meets the design)")
    if want == 4 and not str(b.get("itCheck") or "").strip():
        out.append(f"layout: {vid} is a custom visual (step 4) with no build.itCheck: uncertified visuals need a "
                   "separate IT check (docs/it-security.md), recorded here as who and when")
    return out
