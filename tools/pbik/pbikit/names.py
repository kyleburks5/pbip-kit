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


class CIDict(dict):
    """A dict whose str keys match case-insensitively (as DAX names do) and keep their first spelling."""

    def __init__(self, *a, **kw):
        super().__init__()
        self._k = {}
        self.update(*a, **kw)

    def _real(self, k):
        return self._k.get(key(k), k) if isinstance(k, str) else k

    def __setitem__(self, k, v):
        old = self._real(k)
        if old in self and old != k:
            k = old                                    # keep the first spelling
        super().__setitem__(k, v)
        if isinstance(k, str):
            self._k[key(k)] = k

    def __getitem__(self, k):
        return super().__getitem__(self._real(k))

    def __contains__(self, k):
        return super().__contains__(self._real(k))

    def __delitem__(self, k):
        r = self._real(k)
        super().__delitem__(r)
        if isinstance(r, str):
            self._k.pop(key(r), None)

    def get(self, k, default=None):
        return super().get(self._real(k), default)

    def pop(self, k, *default):
        r = self._real(k)
        if isinstance(r, str):
            self._k.pop(key(r), None)
        return super().pop(r, *default)

    def setdefault(self, k, default=None):
        if k not in self:
            self[k] = default
        return self[k]

    def update(self, *a, **kw):
        for k, v in dict(*a, **kw).items():
            self[k] = v
