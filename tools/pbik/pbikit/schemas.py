"""JSON schema checks against the $schema each PBIR file declares, from a local cache.

`pbik schemas fetch <Report>` downloads each declared schema, and the schemas it references, from
https://developer.microsoft.com/json-schemas/ into tools/pbik/schemas/ (git-ignored). Validation never goes online:
a schema missing from the cache is reported as skipped. jsonschema is optional; without it schema checks are skipped.
"""
import json, pathlib, re, urllib.parse, urllib.request

CACHE = pathlib.Path(__file__).resolve().parents[1] / "schemas"
BASE = "https://developer.microsoft.com/json-schemas/"


def cache_path(url):
    if not url.startswith(BASE):
        return None
    rel = urllib.parse.urlparse(url).path[len("/json-schemas/"):]
    return CACHE / rel


def fetch(urls):
    """Download schemas and everything they $ref (same host only). Returns (fetched, failed)."""
    todo, seen, fetched, failed = list(urls), set(), [], []
    while todo:
        url = todo.pop().split("#", 1)[0]
        if url in seen or not url.startswith(BASE):
            continue
        seen.add(url)
        dest = cache_path(url)
        if not dest.exists():
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    data = r.read()
                json.loads(data)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                fetched.append(url)
            except Exception as e:          # network, 404, bad JSON
                failed.append(f"{url}: {e}")
                continue
        text = dest.read_text(encoding="utf-8")
        for ref in set(re.findall(r'"\$ref"\s*:\s*"([^"#][^"]*)"', text)):
            todo.append(urllib.parse.urljoin(url, ref))
    return fetched, failed


class Checker:
    def __init__(self):
        try:
            import jsonschema
        except ImportError:
            self.available, self.reason = False, "jsonschema is not installed (pip install --user jsonschema)"
            return
        self.available, self.reason = True, None
        self.js = jsonschema
        self.validators = {}
        self.missing = set()

    def _load(self, url):
        p = cache_path(url.split("#", 1)[0])
        if p is None or not p.exists():
            raise FileNotFoundError(url)
        return json.loads(p.read_text(encoding="utf-8"))

    def _validator(self, url):
        if url in self.validators:
            return self.validators[url]
        schema = self._load(url)
        js = self.js
        try:
            from referencing import Registry, Resource
            from referencing.jsonschema import DRAFT7

            def retrieve(uri):
                return Resource.from_contents(self._load(uri), default_specification=DRAFT7)
            registry = Registry(retrieve=retrieve)
            cls = js.validators.validator_for(schema, default=js.Draft7Validator)
            v = cls(schema, registry=registry)
        except ImportError:                              # jsonschema < 4.18
            resolver = js.RefResolver(url, schema, handlers={"https": self._load})
            cls = js.validators.validator_for(schema, default=js.Draft7Validator)
            v = cls(schema, resolver=resolver)
        self.validators[url] = v
        return v

    def check(self, doc):
        """-> list of error strings, or None if the schema isn't cached."""
        url = doc.get("$schema") if isinstance(doc, dict) else None
        if not url:
            return []
        try:
            v = self._validator(url)
            errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
        except FileNotFoundError as e:
            self.missing.add(str(e))
            return None
        out = []
        for e in errs[:20]:
            path = "/".join(str(x) for x in e.absolute_path) or "(root)"
            out.append(f"{path}: {e.message[:300]}")
        return out
