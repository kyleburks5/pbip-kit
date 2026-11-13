"""Kit tests outside pbik: Copilot files (tools/copilot/sync.py), the go/no-go check (tools/doctor.ps1), the
vendored DAX Lib packages (design/udf/vendored.py) and the lessons' format and budgets (tools/lessons.py).

    python tools\\tests\\test_kit.py
"""
import contextlib, io, json, pathlib, re, shutil, subprocess, sys, tempfile, unittest
from unittest import mock

KIT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools" / "copilot"))
sys.path.insert(0, str(KIT / "tools"))
sys.path.insert(0, str(KIT / "design" / "scripts"))
sys.path.insert(0, str(KIT / "tools" / "pbik"))
sys.path.insert(0, str(KIT / "design" / "udf"))

import ambition, ladder  # noqa: E402
import lessons  # noqa: E402
import svg_to_png  # noqa: E402
import sync  # noqa: E402


class LadderTests(unittest.TestCase):
    def v(self, **b):
        return {"id": "P1-V01", "build": b}

    def test_native_with_step_and_reason_passes(self):
        self.assertEqual(ladder.issues(self.v(method="native", step=1, reason="line chart")), [])

    def test_missing_step_and_reason(self):
        out = " | ".join(ladder.issues(self.v(method="svg-measure")))
        self.assertIn("no build.step (svg-measure is step 2", out)
        self.assertIn("no build.reason", out)

    def test_step_must_match_the_method(self):
        self.assertIn("doesn't match deneb", " ".join(ladder.issues(self.v(method="deneb", step=2, reason="x"))))

    def test_custom_visual_needs_an_it_check(self):
        out = ladder.issues(self.v(method="custom-visual", step=4, reason="x"))
        self.assertTrue(any("itCheck" in x for x in out))
        self.assertEqual(ladder.issues(self.v(method="html-measure", step=4, reason="x", itCheck="IT, 2026-10-24")), [])

    def test_unknown_method(self):
        self.assertIn("not on the ladder", ladder.issues(self.v(method="python", step=1, reason="x"))[0])


class AmbitionTests(unittest.TestCase):
    def test_headline_needs_a_comparison(self):
        card = {"id": "P1-V03", "type": "cardVisual", "bindings": {"Data": ["[Sales]"]}}
        self.assertEqual(len(ambition.headline_issues([card])), 1)
        self.assertEqual(ambition.headline_issues([{**card, "comparison": "P1-V06"}]), [])
        self.assertEqual(ambition.headline_issues([{**card, "referenceLabels": {"labels": [{"value": "[Sales PY]"}]}}]), [])
        self.assertEqual(ambition.headline_issues([{**card, "pattern": "freshness-line"}]), [])
        self.assertEqual(ambition.headline_issues([{"id": "P1-V04", "type": "kpi",
                                                   "bindings": {"Indicator": ["[Sales]"], "Goal": ["[Target]"]}}]), [])

    def test_spec_section(self):
        self.assertIn('no "Design ambition"', ambition.spec_issues("# Spec\n## Fallback register\n")[0])
        ok = ("## Design ambition\n| Key number | Baseline | Normal | Exceptions | Partial or stale | Patterns |\n"
              "## Build order\n")
        self.assertEqual(ambition.spec_issues(ok), [])
        self.assertIn("partial", ambition.spec_issues("## Design ambition\nbaseline, normal, exceptions\n## X\n")[0])


class PatternPageTests(unittest.TestCase):
    """Batch 3 item 13: every pattern page has Use when / Avoid when lines; /plan (and Copilot /kit-plan) lists the
    patterns and style preset chosen per page, with a reason each."""

    def test_use_and_avoid_lines(self):
        for f in sorted((KIT / "docs" / "patterns").glob("*.md")):
            if f.name == "README.md":
                continue
            text = f.read_text(encoding="utf-8")
            self.assertIn("- **Use when:** ", text, f.name)
            self.assertIn("- **Avoid when:** ", text, f.name)

    def test_plan_asks_for_pattern_choices(self):
        for f in (KIT / ".claude" / "commands" / "plan.md", KIT / ".github" / "prompts" / "kit-plan.prompt.md"):
            text = f.read_text(encoding="utf-8")
            self.assertIn("Pattern choices", text, f.name)
            self.assertIn("Style preset", text, f.name)


class BudgetTests(unittest.TestCase):
    """The lean learning system (docs/lessons/README.md, tools/lessons.py): lesson format and indexes, budgets
    (CLAUDE.md 150 lines, a lesson file 120, a pattern entry 80: a warning at the budget, a failure 25% over), no
    duplicate rules and no PROJECT-ONLY lesson in the kit."""

    def test_kit_passes_the_lesson_check(self):
        warns, errs = lessons.check()
        for w in warns:
            print(f"\n  budget warning: {w}", end="")
        self.assertEqual(errs, [], "fix the lessons (python tools/lessons.py check)")

    def test_claude_md_within_its_budget(self):
        n = len((KIT / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(n, lessons.BUDGETS["CLAUDE.md"] * lessons.OVER,
                             f"CLAUDE.md has {n} lines: place lessons per docs/lessons/README.md")

    def test_warn_at_budget_fail_25_percent_over(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "docs" / "lessons").mkdir(parents=True)
            (tmp / "docs" / "patterns").mkdir(parents=True)
            (tmp / "CLAUDE.md").write_text("x\n" * 150, encoding="utf-8")                  # at budget: warn
            (tmp / "docs" / "lessons" / "build.md").write_text("x\n" * 140, encoding="utf-8")   # over, < 25%: warn
            (tmp / "docs" / "patterns" / "p.md").write_text("x\n" * 101, encoding="utf-8")   # 80 x 1.25 = 100: fail
            (tmp / "docs" / "patterns" / "q.md").write_text("x\n" * 100, encoding="utf-8")   # exactly 25%: warn
            with mock.patch.object(lessons, "ROOT", tmp), mock.patch.object(lessons, "LESSONS", tmp / "docs" / "lessons"):
                warns, errs = lessons.budget_findings()
            self.assertEqual(len(warns), 3, warns)
            self.assertEqual(len(errs), 1, errs)
            self.assertIn("docs/patterns/p.md: 101 lines", errs[0])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_format_duplicates_and_project_only(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            f = tmp / "slicers.md"
            f.write_text("# S\n\n## Index\n\n## S-01 One\n- **Rule:** Keep it short.\n- **Why:** w\n"
                         "- **Enforced by:** not enforced (read)\n- **Source:** Rep 1\n\n"
                         "## S-02 Two\n- **Rule:** keep it, short!\n- **Why:** w\n- **Source:** Rep 2 PROJECT-ONLY\n\n"
                         "## X-03 Three\n- **Rule:** r\n- **Why:** w\n- **Enforced by:** t\n- **Source:** s\n"
                         "stray text\n## Notes\n", encoding="utf-8")
            les, probs = lessons.parse(f)
            self.assertEqual([x["id"] for x in les], ["S-01", "S-02", "X-03"])
            self.assertTrue(any("S-02 has no **Enforced by:**" in p_ for p_ in probs), probs)
            self.assertTrue(any("X-03 should start with S-" in p_ for p_ in probs), probs)
            self.assertTrue(any("text outside its four fields" in p_ for p_ in probs), probs)
            self.assertTrue(any("'Notes'" in p_ for p_ in probs), probs)
            self.assertEqual(lessons.duplicates(les), ["S-02 repeats the rule of S-01"])
            self.assertEqual(len(lessons.project_only(les)), 1)
            self.assertFalse(lessons.enforced(les[0]))
            self.assertTrue(lessons.enforced(les[2]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_every_lesson_file_has_an_index_and_the_readme_lists_every_lesson(self):
        readme = (KIT / "docs" / "lessons" / "README.md").read_text(encoding="utf-8")
        for f in lessons.lesson_files():
            text = f.read_text(encoding="utf-8")
            self.assertLess(text.index("## Index"), text.index("\n## ", text.index("## Index") + 3), f.name)
            for x in lessons.parse(f)[0]:
                self.assertIn(f"| {x['id']} |", text.split("<!-- /lessons:index -->")[0], f"{f.name} index: {x['id']}")
                self.assertIn(f"| {x['id']} |", readme, f"README: {x['id']}")

    def test_tidy_suggested_after_three_reports(self):
        with mock.patch.object(lessons, "reports_since_tidy", return_value=("pre-tidy-2026-11-01", 3)), \
                mock.patch.object(lessons, "budgets", return_value=[]):
            self.assertIn("3 reports wrapped up since the last tidy (pre-tidy-2026-11-01)", lessons.tidy_due()[0])
        with mock.patch.object(lessons, "reports_since_tidy", return_value=(None, 2)), \
                mock.patch.object(lessons, "budgets", return_value=[("lesson file", KIT / "x.md", 109, 120)]):
            self.assertEqual(lessons.tidy_due(), ["x.md at 109 of 120 lines"], "within 10% of a budget")

    def test_changelog_rows_older_than(self):
        import datetime
        rows = lessons.changelog_rows(30, today=datetime.date(2026, 11, 20))
        self.assertTrue(rows and all(r.startswith("| 2026-10-") for r in rows))


class CopilotTests(unittest.TestCase):
    def test_in_step_with_the_claude_files(self):
        self.assertEqual(sync.main(["--check"]), 0, "run python tools/copilot/sync.py")

    def test_a_prompt_per_command(self):
        cmds = sorted(p.stem for p in (KIT / ".claude" / "commands").glob("*.md"))
        prompts = sorted(p.name[:-len(".prompt.md")] for p in (KIT / ".github" / "prompts").glob("*.prompt.md"))
        self.assertEqual(["kit-" + c for c in cmds], prompts, "kit- keeps clear of Copilot's /plan, /fix, /review")
        for c in cmds:
            t = (KIT / ".github" / "prompts" / f"kit-{c}.prompt.md").read_text(encoding="utf-8")
            self.assertTrue(t.startswith(f"---\nname: kit-{c}\nagent: agent\ndescription: "), c)
            head = t.split("\n---\n", 1)[0]
            self.assertRegex(head, r'\nargument-hint: "[^"]+"', c)
            self.assertNotIn("\nmode:", head, c)
            self.assertNotIn("$ARGUMENTS", t, c)
            self.assertNotIn("${input:", t, c)   # VS Code doesn't fill prompt-body variables (1.143.1)
            src = (KIT / ".claude" / "commands" / f"{c}.md").read_text(encoding="utf-8")
            if "$ARGUMENTS" in src:
                self.assertIn(f"the text after /kit-{c} in my message", t, c)

    def test_instructions_mirror_claude_md_and_rules(self):
        t = (KIT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        self.assertIn((KIT / "CLAUDE.md").read_text(encoding="utf-8").replace("\r\n", "\n").strip()[:400], t)
        for f in (KIT / ".claude" / "rules").glob("*.md"):
            self.assertIn(f"# Rules: {f.stem}", t)

    def test_check_finds_drift(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            for rel in (".claude/commands", ".claude/rules"):
                shutil.copytree(KIT / rel, tmp / rel)
            shutil.copy(KIT / "CLAUDE.md", tmp / "CLAUDE.md")
            old = sync.ROOT
            sync.ROOT = tmp
            try:
                self.assertEqual(sync.main([]), 0)
                self.assertEqual(sync.main(["--check"]), 0)
                (tmp / ".claude" / "commands" / "build.md").write_text("Changed: $ARGUMENTS\n", encoding="utf-8")
                self.assertEqual(sync.main(["--check"]), 1, "an edited command makes its prompt stale")
                sync.main([])
                self.assertIn("Changed: the text after /kit-build in my message", (tmp / ".github" / "prompts" / "kit-build.prompt.md").read_text(encoding="utf-8"))
            finally:
                sync.ROOT = old
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SvgToPngTests(unittest.TestCase):
    """Edge 156 returns before it writes the screenshot (2026-10-23): render() waits for a complete PNG."""
    PNG = svg_to_png.PNG_SIGNATURE + bytes(13) + b"IEND" + bytes(4)

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_waits_for_a_png_written_late(self):
        import threading, time
        f = self.tmp / "late.png"

        def write():
            time.sleep(0.3)
            f.write_bytes(self.PNG[:10])          # a partial file first
            time.sleep(0.3)
            f.write_bytes(self.PNG)
        threading.Thread(target=write).start()
        t0 = time.monotonic()
        self.assertEqual(svg_to_png.wait_for_png(f, timeout=5, poll=0.05), f)
        self.assertGreaterEqual(time.monotonic() - t0, 0.5, "not before the file is complete")

    def test_incomplete_png_times_out(self):
        f = self.tmp / "partial.png"
        f.write_bytes(self.PNG[:-8])
        self.assertFalse(svg_to_png.png_complete(f))
        with self.assertRaises(SystemExit) as e:
            svg_to_png.wait_for_png(f, timeout=0.3, poll=0.05)
        self.assertIn("EDGE_WAIT", str(e.exception))
        self.assertFalse(svg_to_png.png_complete(self.tmp / "missing.png"))

    @unittest.skipUnless(pathlib.Path(svg_to_png.EDGE).exists(), "Edge not installed")
    def test_real_render_returns_a_complete_png(self):
        out = self.tmp / "icon.png"
        out.write_bytes(self.PNG)                 # an older file must not count as this render
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="#037C84"/></svg>'
        svg_to_png.render(svg, out, scale=4)
        self.assertTrue(svg_to_png.png_complete(out))
        self.assertNotEqual(out.read_bytes(), self.PNG)


class EdgePageTests(unittest.TestCase):
    """stop_edge() stops the processes of the browser EDGE names, so Chrome works as the headless browser."""

    def stopped(self, exe):
        import edge_page
        seen = []
        saved = edge_page.EDGE, edge_page.subprocess.run
        edge_page.EDGE, edge_page.subprocess.run = exe, lambda a, **k: seen.append(a[-1])
        try:
            edge_page.stop_edge("C:/tmp/profile")
        finally:
            edge_page.EDGE, edge_page.subprocess.run = saved
        return seen[0] if seen else ""

    @unittest.skipUnless(sys.platform == "win32", "stop_edge runs on Windows only")
    def test_stops_the_browser_edge_names(self):
        self.assertIn("Name='msedge.exe'", self.stopped(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"))
        chrome = self.stopped(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        self.assertIn("Name='chrome.exe'", chrome)
        self.assertIn("*C:/tmp/profile*", chrome)


class VersionsTests(unittest.TestCase):
    """VERSIONS.md releases (semantic versioning, Desktop tested on), one pbik version everywhere, and the update docs
    naming only pbik commands that exist."""

    def releases(self):
        text = (KIT / "VERSIONS.md").read_text(encoding="utf-8")
        self.assertIn("## Releases", text)
        sec = text.split("## Releases", 1)[1].split("\n## ", 1)[0]
        rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in sec.splitlines()
                if ln.startswith("| v")]
        self.assertTrue(rows)
        return text, rows

    def test_releases_table(self):
        _, rows = self.releases()
        seen = []
        for rel, date, kind, pbik, desktop, note in rows:
            self.assertRegex(rel, r"^v\d+\.\d+(\.\d+)?$")
            self.assertIn(kind, ("patch", "minor", "major"), rel)
            self.assertRegex(pbik, r"^\d+\.\d+\.\d+$", rel)
            self.assertTrue(re.search(r"\d+\.\d+\.\d+\.\d+|not Desktop-tested", desktop), f"{rel}: {desktop}")
            v = tuple(int(x) for x in rel[1:].split("."))
            self.assertTrue(not seen or v > seen[-1], f"{rel} out of order")
            seen.append(v)

    def test_kind_matches_the_version_step(self):
        _, rows = self.releases()
        prev = None
        for rel, _, kind, *_ in rows:
            v = (tuple(int(x) for x in rel[1:].split(".")) + (0,))[:3]
            if prev:
                step = "major" if v[0] > prev[0] else "minor" if v[1] > prev[1] else "patch"
                self.assertEqual(kind, step, rel)
            prev = v

    def test_one_pbik_version(self):
        from pbikit import __version__
        text, rows = self.releases()
        self.assertIn(f"| pbik (the kit's own PBIR/TMDL tool, tools/pbik) | {__version__} |", text)
        self.assertEqual(rows[-1][3], __version__, "the newest release carries the current pbik")
        self.assertTrue((KIT / "tools" / "pbik" / "README.md").read_text(encoding="utf-8").startswith(f"# pbik {__version__}\n"))
        self.assertIn(f"version = {__version__}\n", (KIT / "tools" / "pbik" / "setup.cfg").read_text(encoding="utf-8"))

    def test_update_docs_name_real_pbik_commands(self):
        from pbikit.cli import main
        docs = ["docs/UPDATE-ROUTINE.md", ".claude/commands/update.md", ".claude/commands/model.md",
                "tools/pbik/README.md"]
        found = set()
        for d in docs:
            text = (KIT / d).read_text(encoding="utf-8")
            for cmd, sub in re.findall(r"pbik(?:\.py)? (schemas|project|catalog|templates) ([a-z]+)", text):
                found.add((cmd, sub))
        self.assertIn(("project", "record"), found)
        for cmd, sub in sorted(found):
            with self.assertRaises(SystemExit) as e, contextlib.redirect_stdout(io.StringIO()):
                main([cmd, sub, "--help"])
            self.assertEqual(e.exception.code, 0, f"pbik {cmd} {sub}")

    def test_update_command_follows_the_routine(self):
        cmd = (KIT / ".claude" / "commands" / "update.md").read_text(encoding="utf-8")
        self.assertIn("docs/UPDATE-ROUTINE.md", cmd)
        for step in ("project record", "--regression", "/smoke", "build_patterns.py", "templates harvest",
                     "catalog refresh --name"):
            self.assertIn(step, cmd)
        self.assertIn("/update", (KIT / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_kit_project_json(self):
        from pbikit import versions as V
        d = json.loads((KIT / "design" / "specs" / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(set(d) - {"targetDesktop", "catalog", "desktop", "customVisuals"}, set())
        V.Target(d["targetDesktop"])            # resolves (raises on a bad target)
        from pbikit import catalog as CAT
        self.assertEqual(d.get("catalog"), "home")
        self.assertTrue(CAT.catalog_path(d.get("catalog")).exists(), d.get("catalog"))
        self.assertEqual(CAT.catalog_path(), CAT.catalog_path("home"), "no name: home")
        self.assertFalse((KIT / "tools" / "pbik" / "catalog.json").exists(), "moved to catalogs/home.json")


@unittest.skipUnless(sys.platform == "win32", "doctor.ps1 is for Windows")
class DoctorTests(unittest.TestCase):
    def test_parses(self):
        ps = ("$e = $null; [System.Management.Automation.Language.Parser]::ParseFile('" + str(KIT / "tools" / "doctor.ps1")
              + "', [ref]$null, [ref]$e) | Out-Null; $e.Count")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "0", r.stdout + r.stderr)

    def doctor(self, env=None):
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(KIT / "tools" / "doctor.ps1"), "-Offline"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300, env=env)
        return r

    def check_next_lines(self, out):
        """Every WARN names its fallback and every FAIL what to ask IT, on the line under it."""
        lines = out.splitlines()
        for i, ln in enumerate(lines):
            if ln.startswith("WARN "):
                self.assertTrue(lines[i + 1].startswith("      fallback: "), ln)
            if ln.startswith("FAIL "):
                self.assertTrue(lines[i + 1].startswith("      ask IT: "), ln)

    def test_runs_every_check_offline(self):
        r = self.doctor()
        out = r.stdout
        for item in ("Python", "pip", "jsonschema", "pbik", "Execution policy", "Node.js", "Modeling MCP",
                     "DAX Lib", "Power BI Desktop", "Compatibility level 1702", "Desktop Bridge", "Deneb", "Git",
                     "Proxy", "Kit folder", "Copilot files"):
            self.assertRegex(out, rf"(?m)^(PASS|WARN|FAIL)\s+{re.escape(item)}(\s|$)", item)
        self.assertNotIn("index access", out, "-Offline skips the network checks")
        self.assertNotIn("npm registry access", out)
        self.assertNotIn("is not recognized", out + r.stderr)
        self.assertNotIn("Process=Bypass, ", out.split("Execution policy", 1)[1].split("(", 1)[0],
                         "the policy shown ignores doctor's own -ExecutionPolicy Bypass")
        self.check_next_lines(out)
        self.assertRegex(out, r"(?m)^(GO: |GO with fallbacks: |NO-GO: )")
        self.assertEqual(r.returncode, 1 if re.search(r"(?m)^FAIL ", out) else 0)

    def test_without_node_and_git(self):
        import os
        keep = [os.path.dirname(sys.executable), os.path.join(os.environ["SystemRoot"], "System32"),
                os.path.join(os.environ["SystemRoot"], "System32", "WindowsPowerShell", "v1.0")]
        env = {**os.environ, "PATH": os.pathsep.join(keep)}
        r = self.doctor(env)
        self.assertRegex(r.stdout, r"(?m)^WARN\s+Node\.js\s+node is not on PATH")
        self.assertRegex(r.stdout, r"(?m)^FAIL\s+Git\s+git is not on PATH\r?\n      ask IT: Git for Windows")
        self.check_next_lines(r.stdout)
        self.assertIn("NO-GO", r.stdout)
        self.assertEqual(r.returncode, 1)


class VendoredUdfTests(unittest.TestCase):
    """The vendored DAX Lib copy (npm blocked): every listed package, unchanged, with its licence."""

    def test_check_passes(self):
        import vendored
        self.assertEqual(vendored.check(json.loads((KIT / "design" / "udf" / "packages.json").read_text(encoding="utf-8"))), [])

    def test_definitions_match_daxlib_mcp(self):
        import vendored
        f = vendored.folder("DataTides.ColourContrast", "0.1.0") / "functions.tmdl"
        fns = vendored.parse(f.read_text(encoding="utf-8"))
        self.assertEqual([x["name"] for x in fns][0], "DataTides.ColourContrast.HexLuminance")
        for x in fns:
            self.assertEqual(sorted(x), ["annotations", "description", "expression", "name"])
            self.assertEqual(x["annotations"], [{"key": "DAXLIB_PackageId", "value": "DataTides.ColourContrast"},
                                                {"key": "DAXLIB_PackageVersion", "value": "0.1.0"}])
            self.assertNotIn("annotation", x["expression"])
            self.assertFalse(x["expression"].startswith(("\t", " ")))

    def test_a_changed_file_fails(self):
        import vendored
        pk = json.loads((KIT / "design" / "udf" / "packages.json").read_text(encoding="utf-8"))
        pk["packages"][0]["vendored"]["sha256"] = "0" * 64
        self.assertIn("differs", " ".join(vendored.check(pk)))

if __name__ == "__main__":
    unittest.main(verbosity=2)
