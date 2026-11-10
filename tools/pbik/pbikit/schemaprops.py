"""Is a property in Microsoft's PBIR schema? A standard-library walk of the cached schemas (no jsonschema needed).

Used by `pbik build` (layout `props`, `container:` props, the `report` key, page `filterPane` / `filterCards`) and by
`pbik validate` (the properties pbik owns). A miss is a warning; `--strict` makes it an error.

Provenance (roadmap batch 1, item b, 2026-11-10): Microsoft's json-schemas (MIT), the versions pbik caches in
tools/pbik/schemas/ (`pbik schemas fetch`). What the schemas list, read on 2026-11-10:
- visualContainer 2.13.0 -> visualConfiguration 2.8.0: `visualContainerObjects` lists every object and its
  properties (#VisualContainerFormattingObjects, each with additionalProperties false), so container props are checked
  exactly.
- A visual's `objects` is #DataViewObjectDefinitions in formattingObjectDefinitions 1.5.0: any object name, any
  property, for every visual type. The schemas carry no per-visual-type property list, so for `objects` this check
  can only say "open"; the settings catalog (Desktop-saved files, `pbik validate`) is what checks those per type.
- A version Microsoft hasn't published (visualContainer 2.14.0, which Desktop writes and the kit's templates carry, is
  a 404) is checked against the newest older version in the cache, and a miss there is only a warning (NEAREST).
- page 2.1.0 #PageFormattingObjects and report 3.3.0 #ReportFormattingObjects / #ExplorationSettings list their
  objects, properties and (settings) enum values.
"""
import json, re

from . import schemas

OK, UNKNOWN, OPEN, UNCACHED = "ok", "unknown", "open", "uncached"
NEAREST = "unknown-nearest"     # a miss against an older cached version (the declared one isn't published): never an
                                # error, since the newer schema may have added the property


class Walker:
    """Follow a path of property names through a cached schema, resolving $ref across cached files."""

    def __init__(self):
        self.docs = {}

    def _doc(self, url):
        if url not in self.docs:
            p = schemas.cache_path(url)
            self.docs[url] = json.loads(p.read_text(encoding="utf-8")) if p is not None and p.exists() else None
        return self.docs[url]

    def _deref(self, url, node):
        seen = 0
        while isinstance(node, dict) and "$ref" in node and seen < 20:
            ref = node["$ref"]
            base, _, frag = ref.partition("#")
            if base:
                import urllib.parse
                url = urllib.parse.urljoin(url, base)
            doc = self._doc(url)
            if doc is None:
                raise FileNotFoundError(url)
            node = doc
            for part in [x for x in frag.split("/") if x]:
                node = node[part]
            seen += 1
        return url, node

    def walk(self, url, path):
        """-> (status, node, url): OK with the schema node, UNKNOWN (additionalProperties false), OPEN (anything
        allowed from here on), UNCACHED."""
        doc = self._doc(url)
        if doc is None:
            return UNCACHED, None, url
        node = doc
        try:
            for seg in path:
                url, node = self._deref(url, node)
                if "items" in node and "properties" not in node:        # an object's entry list
                    url, node = self._deref(url, node["items"])
                props = node.get("properties") or {}
                if seg in props:
                    node = props[seg]
                    continue
                ap = node.get("additionalProperties", True)
                if ap is False:
                    return UNKNOWN, node, url
                if isinstance(ap, dict) and ap:
                    node = ap
                    continue
                return OPEN, None, url
            url, node = self._deref(url, node)
        except FileNotFoundError as e:
            return UNCACHED, str(e), url
        return OK, node, url


def enum_values(node):
    """The const values of an anyOf / enum node, with whether each is marked Deprecated in its description."""
    out = {}
    for alt in (node or {}).get("anyOf", []) + [{"const": v} for v in (node or {}).get("enum", [])]:
        if "const" in alt:
            out[alt["const"]] = "deprecated" in (alt.get("description") or "").lower()
    return out


_W = Walker()


def _short(url):
    parts = (url or "").split("/definition/")[-1].split("/")
    return f"{parts[0]} {parts[1]}" if len(parts) > 2 else url


VER_RE = re.compile(r"(.*/definition/[A-Za-z]+/)(\d+)\.(\d+)\.(\d+)(/.*)$")


def nearest_cached(url):
    """The newest cached version of the same kind older than url's, or None."""
    m = VER_RE.match(url or "")
    p = schemas.cache_path(url) if m else None
    if p is None:
        return None
    want = tuple(int(x) for x in m.group(2, 3, 4))
    kind_dir = p.parent.parent
    best = None
    for d in kind_dir.glob("*.*.*") if kind_dir.is_dir() else []:
        try:
            v = tuple(int(x) for x in d.name.split("."))
        except ValueError:
            continue
        if v < want and (d / p.name).exists() and (best is None or v > best):
            best = v
    return f"{m.group(1)}{'.'.join(map(str, best))}{m.group(5)}" if best else None


def check(url, path, label, value=None):
    """-> (status, message or None). url: the file's $schema (visualContainer / page / report)."""
    st, node, where = _W.walk(url, path)
    if st == UNCACHED:
        near = nearest_cached(url)
        if near:
            st2, msg = check(near, path, label, value)
            if st2 == UNKNOWN:
                return NEAREST, (f"{msg} (checked against {_short(near)}: {_short(url)} isn't published, "
                                 "so this stays a warning)")
            return st2, msg
    if st == UNKNOWN:
        return st, f"{label} is not in Microsoft's {_short(where)} schema"
    if st == UNCACHED:
        return st, None
    if st == OK and value is not None:
        vals = enum_values(node)
        if vals and value not in vals:
            return UNKNOWN, f"{label} = {value!r} is not one of the schema's values ({', '.join(map(str, vals))})"
    return st, None


def visual_prop(container_url, where, obj, prop=None):
    """where: 'objects' or 'visualContainerObjects'."""
    path = ["visual", where, obj] + (["properties", prop] if prop else [])
    label = ("container:" if where == "visualContainerObjects" else "") + (f"{obj}.{prop}" if prop else obj)
    return check(container_url, path, label)


def page_prop(page_url, obj, prop=None):
    return check(page_url, ["objects", obj] + (["properties", prop] if prop else []),
                 f"page {obj}.{prop}" if prop else f"page {obj}")


def report_prop(report_url, obj, prop):
    return check(report_url, ["objects", obj, "properties", prop], f"report {obj}.{prop}")


def report_setting(report_url, key, value=None):
    return check(report_url, ["settings", key], f"report setting {key}",
                 value if isinstance(value, str) else None)


def property_order(url, path):
    """The property names at this path in the schema's order (Desktop writes report settings in it), or None."""
    st, node, _ = _W.walk(url, path)
    if st == UNCACHED:
        near = nearest_cached(url)
        if near:
            st, node, _ = _W.walk(near, path)
    return list((node or {}).get("properties") or {}) if st == OK else None


def deprecated(url, path):
    """Values the schema marks Deprecated at this path (e.g. page displayOption), or None when not cached."""
    st, node, _ = _W.walk(url, path)
    if st != OK:
        return None
    return {v for v, dep in enum_values(node).items() if dep}


def tree_issues(url, path, node, label=""):
    """Every key in a JSON fragment pbik writes that Microsoft's cached schema doesn't allow there: [(status, message)].
    url: the file's $schema; path: where the fragment sits (e.g. ["annotations"]). Closed objects are checked key by
    key and recursed into; open or uncached parts pass. A version Microsoft hasn't published is checked against the
    newest older cached one (NEAREST, a warning only). Used for the roadmap batch 2 features (pbikit/unverified.py)."""
    status = UNKNOWN
    if _W._doc(url) is None:
        near = nearest_cached(url)
        if near is None:
            return []
        url, status = near, NEAREST
    return _tree(url, list(path), node, label, status)


def _tree(url, path, node, label, status):
    out = []
    if isinstance(node, list):
        for x in node:
            out += _tree(url, path, x, label, status)
        return out
    if not isinstance(node, dict):
        return out
    for k, v in node.items():
        st, _, where = _W.walk(url, path + [k])
        if st == UNKNOWN:
            out.append((status, f"{label}{'.'.join(map(str, path + [k]))} is not in Microsoft's {_short(where)} schema"))
        elif st == OK:
            out += _tree(url, path + [k], v, label, status)
    return out
