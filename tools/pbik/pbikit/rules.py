"""Flag grouping and plain-language explanations (docs/PLAIN-WORDS.md); the rule library comes in stage (d)."""
from . import synth as S

PLAIN = {"enter-data": "a small table someone typed into the model",
         "m-code": "a table loaded by a query",
         "connection": "a link to a data source; it isn't copied",
         "rls": "a row-level security role; it isn't copied",
         "entity": "a table about accounts, members or other people or organisations"}


def plain(f):
    return f"{f.get('table') or 'the model'}: {PLAIN.get(f['kind'], f['kind'])}"


def groups(c):
    """{"rules": resolved by a rule, "keep": option tables to keep, "you": still need a person} of a contract."""
    out = {"rules": [], "keep": [], "you": []}
    for f in c["flags"]:
        if not f.get("resolution"):
            out["you"].append(f)
        elif f["resolution"] == S.KEEP_ROWS:
            out["keep"].append(f)
        else:
            out["rules"].append(f)
    return out
