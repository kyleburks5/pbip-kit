"""pbik theme apply / resource add: register files under StaticResources/RegisteredResources.

report.json lists them in resourcePackages (package "RegisteredResources", items {name, path, type}); a custom theme
is also set as themeCollection.customTheme {name, reportVersionAtImport, type: "RegisteredResources"}, layered over
the base theme. Registering is idempotent: the same file name is reused, never copied as <name>_<n>.
"""
import pathlib, shutil

from .objects import load
from .report import Report, fail

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}


def _register(rep, src, item_type, name=None):
    src = pathlib.Path(src)
    if not src.exists():
        fail(f"{src} not found")
    name = name or src.name
    dest = rep.path / "StaticResources" / "RegisteredResources" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.read_bytes() != src.read_bytes():
        shutil.copyfile(src, dest)
        rep.changed.append(str(dest.relative_to(rep.path.parent)).replace("\\", "/"))
    rf = rep.defn / "report.json"
    d = load(rf)
    pkgs = d.setdefault("resourcePackages", [])
    pkg = next((p for p in pkgs if p.get("name") == "RegisteredResources"), None)
    if pkg is None:
        pkg = {"name": "RegisteredResources", "type": "RegisteredResources", "items": []}
        pkgs.append(pkg)
    items = pkg.setdefault("items", [])
    it = next((x for x in items if x.get("name") == name), None)
    if it is None:
        items.append({"name": name, "path": name, "type": item_type})
    else:
        it.update({"path": name, "type": item_type})
    return d, rf, name


def apply(report_path, theme_file, quiet=False, project=None):
    rep = Report(report_path)
    rep.project = project
    tf = pathlib.Path(theme_file)
    if tf.suffix.lower() != ".json":
        fail("a theme is a .json file")
    load(tf)                                        # must be valid JSON
    d, rf, name = _register(rep, tf, "CustomTheme")
    tc = d.setdefault("themeCollection", {})
    old = tc.get("customTheme", {}).get("name")
    base = tc.get("baseTheme", {})
    custom = {"name": name, "type": "RegisteredResources"}
    if base.get("reportVersionAtImport"):
        custom["reportVersionAtImport"] = base["reportVersionAtImport"]
    prev = tc.get("customTheme", {})
    if prev.get("name") == name and prev.get("reportVersionAtImport"):
        custom["reportVersionAtImport"] = prev["reportVersionAtImport"]
    tc["customTheme"] = {k: custom[k] for k in ("name", "reportVersionAtImport", "type") if k in custom}
    if old and old != name:                         # unlist the previous custom theme; its file stays on disk
        for p in d.get("resourcePackages", []):
            if p.get("name") == "RegisteredResources":
                p["items"] = [x for x in p.get("items", []) if not (x.get("name") == old and x.get("type") == "CustomTheme")]
        print(f"note: {old} is no longer the custom theme (its file is kept in RegisteredResources)")
    rep.write(rf, d)
    if not quiet:
        print(f"{'applied' if rep.changed else 'already applied'}: {name} as the custom theme of {rep.path.name}")
        for c in rep.changed:
            print(f"  {c}")
    return rep.changed


def register_image(report_path, file, project=None):
    """Register an image for `pbik build` (layout `image`, roadmap gap 3): -> (item name, files changed)."""
    rep = Report(report_path)
    rep.project = project
    p = pathlib.Path(file)
    if p.suffix.lower() not in IMAGE_EXT:
        fail(f"image {file}: not an image ({', '.join(sorted(IMAGE_EXT))})")
    d, rf, item = _register(rep, p, "Image")
    rep.write(rf, d)
    return item, rep.changed


def resource_add(report_path, file, name=None):
    rep = Report(report_path)
    p = pathlib.Path(file)
    if p.suffix.lower() not in IMAGE_EXT:
        fail(f"resource add takes images ({', '.join(sorted(IMAGE_EXT))})")
    if p.suffix.lower() == ".svg":
        print("warning: SVG images are not yet confirmed in Desktop; the tested route is a PNG at 4x (svg_to_png.py)")
    d, rf, item = _register(rep, p, "Image", name)
    rep.write(rf, d)
    print(f"{'registered' if rep.changed else 'already registered'}: {item}  (bind it as ResourcePackageItem "
          f"PackageName RegisteredResources, PackageType 1, ItemName {item!r})")
