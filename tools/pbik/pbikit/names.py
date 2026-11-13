"""Name comparison the way DAX does it: table, column and measure names are case-insensitive."""


def key(name):
    return (name or "").casefold()


def find(names, name):
    """The entry of `names` (any iterable of str, or a dict's keys) equal to `name` ignoring case, else None."""
    k = key(name)
    for n in names:
        if key(n) == k:
            return n
    return None


def same(a, b):
    return key(a) == key(b)


def ci_in(name, names):
    return find(names, name) is not None
