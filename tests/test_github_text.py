"""Tests for the GitHub text a reviewer reads: changed_rows.py, lint_github_text.py,
the two templates, and the `issue` / `pr` mode inference in orient.py.

Run from the repo root:

    python3 -m unittest discover -s tests -v

A reviewer reads a pull request from the issue, to the capabilities it moved, to the
code. changed_rows.py gives the middle step as facts from the map at the merge base
and at the head; lint_github_text.py keeps the words around it short and plain.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
SKILL = REPO / "skills" / "promise"
SCRIPTS_DIR = SKILL / "scripts"
CHANGED = SCRIPTS_DIR / "changed_rows.py"
LINT = SCRIPTS_DIR / "lint_github_text.py"
FIX = TESTS_DIR / "fixtures" / "github"
ISSUE_TEMPLATE = SKILL / "templates" / "github" / "ISSUE_TEMPLATE" / "capability.md"
PR_TEMPLATE = SKILL / "templates" / "github" / "pull_request_template.md"

sys.path.insert(0, str(SCRIPTS_DIR))
import orient  # noqa: E402


def run(*args: str, cwd: str = None, stdin: str = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, input=stdin)


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
         "-c", "init.defaultBranch=main", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )
    return done.stdout


def row(rid: str, then: str, verdict: str = "proven", tests=None, story: str = "", doc=None) -> dict:
    return {"id": rid, "story": story or f"story of {rid}", "doc": doc,
            "scenarios": [{"id": "S1", "given": "g", "when": "w", "then": then, "altitude": "response"}],
            "tests": tests or [], "e2eTests": [], "evalTests": [], "siblingTests": [], "verdict": verdict}


DOC = """# Export

Status: {status}

## 0. TLDR

{rule}

## 1. Outcome
"""


class ChangedRows(unittest.TestCase):
    """A two-commit repo: the head adds, changes, removes and touches rows."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        d = self.dir
        (d / ".claude").mkdir()
        (d / ".claude" / "promise.config.json").write_text(json.dumps({
            "version": 1, "docsHome": "docs/designs",
            "map": {"recipe": "docs/map/recipe.md", "find": "python3 docs/map/capability_find.py",
                    "row": "python3 docs/map/capability_find.py --row", "lanes": {"data": "tests[]"},
                    "rowIdPattern": "^C-\\d+$",
                    "issueTracker": {"kind": "github", "repo": "o/r", "template": ".github/x.md"}},
        }), encoding="utf-8")
        (d / "docs" / "map").mkdir(parents=True)
        (d / "docs" / "designs").mkdir(parents=True)
        (d / "src").mkdir()
        (d / "tests").mkdir()
        self.write_map([
            row("C-1", "a report downloads", tests=["tests/export.test.ts::downloads"], doc="docs/designs/export.md"),
            row("C-2", "the old then"),
            row("C-3", "a thing gone"),
            row("C-4", "unchanged", story="The handler (lib/handler.ts:12) answers 200."),
            row("C-5", "quiet"),
        ])
        (d / "tests" / "export.test.ts").write_text("test('downloads')\n", encoding="utf-8")
        (d / "src" / "lib").mkdir()
        (d / "src" / "lib" / "handler.ts").write_text("one\n", encoding="utf-8")
        (d / "src" / "other.ts").write_text("one\n", encoding="utf-8")
        (d / "docs" / "designs" / "export.md").write_text(DOC.format(status="agreed", rule="- A rule."),
                                                           encoding="utf-8")
        git(d, "init", "-q")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "base")
        git(d, "checkout", "-qb", "feat")
        self.write_map([
            row("C-1", "a report downloads", tests=["tests/export.test.ts::downloads"], doc="docs/designs/export.md"),
            row("C-2", "the new then", verdict="under-proven"),
            row("C-4", "unchanged", story="The handler (lib/handler.ts:12) answers 200."),
            row("C-5", "quiet"),
            row("C-6", "a new promise", verdict="not-built"),
        ])
        (d / "tests" / "export.test.ts").write_text("test('downloads')\ntest('more')\n", encoding="utf-8")
        (d / "src" / "lib" / "handler.ts").write_text("two\n", encoding="utf-8")
        (d / "src" / "other.ts").write_text("two\n", encoding="utf-8")
        (d / "docs" / "designs" / "export.md").write_text(DOC.format(status="agreed", rule="- A new rule."),
                                                           encoding="utf-8")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "head")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_map(self, rows) -> None:
        text = json.dumps({"version": 1, "rows": rows}, indent=1)
        (self.dir / "docs" / "map" / "map.json").write_text(text + "\n", encoding="utf-8")

    def report(self, *extra: str) -> dict:
        done = run(CHANGED, "--base", "main", "--head", "feat", "--json", *extra, cwd=str(self.dir))
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_each_row_gets_one_change(self) -> None:
        rows = {r["id"]: r for r in self.report()["rows"]}
        self.assertEqual({k: v["change"] for k, v in rows.items()},
                         {"C-6": "added", "C-2": "changed", "C-3": "removed", "C-1": "touched", "C-4": "touched"})
        self.assertNotIn("C-5", rows, "a row nothing touched is not reported")
        self.assertEqual(rows["C-2"]["verdict"], {"before": "proven", "after": "under-proven"})
        self.assertTrue(rows["C-2"]["verdictMoved"])
        self.assertEqual(rows["C-2"]["scenarios"]["changed"][0]["then"],
                         {"before": "the old then", "after": "the new then"})
        self.assertEqual(rows["C-1"]["testsChanged"], ["tests/export.test.ts"])
        self.assertTrue(rows["C-1"]["docChanged"])
        self.assertEqual(rows["C-4"]["filesNamed"], ["src/lib/handler.ts"])

    def test_docs_and_unhomed_files(self) -> None:
        report = self.report()
        self.assertEqual(report["docs"], [{
            "path": "docs/designs/export.md", "change": "changed", "title": "Export",
            "status": {"before": "agreed", "after": "agreed"}, "section0Changed": True,
            "section6Changed": False,
        }])
        self.assertEqual(report["unhomed"], ["src/other.ts"])
        self.assertEqual(report["summary"]["rowsTouched"], 2)

    def test_links_use_the_issue_tracker_repo_and_the_head_sha(self) -> None:
        report = self.report()
        link = next(r for r in report["rows"] if r["id"] == "C-6")["link"]
        self.assertRegex(link, r"^https://github\.com/o/r/blob/[0-9a-f]{40}/docs/map/map\.json#L\d+$")
        self.assertIsNone(next(r for r in report["rows"] if r["id"] == "C-3")["link"],
                          "a removed row has no line at the head")

    def label_map(self, features_key: str, feature_key: str, extra: dict = None, extra_row: dict = None) -> str:
        """Commit a map that labels C-2 and C-5 with the given key spellings; the branch name."""
        d = self.dir
        git(d, "checkout", "-qb", "labels")
        c2 = row("C-2", "the newer then", verdict="under-proven")
        c2[feature_key] = "reports"
        c5 = row("C-5", "quiet")
        c5[feature_key] = "billing"
        c5.update(extra_row or {})
        top = {"version": 1, features_key: [
            {"id": "reports", "name": "Reports", "plain": "The reports a client reads."},
            {"id": "billing", "name": "Billing", "plain": "What a client pays."}], "rows": [
            row("C-1", "a report downloads", tests=["tests/export.test.ts::downloads"], doc="docs/designs/export.md"),
            c2, row("C-4", "unchanged", story="The handler (lib/handler.ts:12) answers 200."), c5,
            row("C-6", "a new promise", verdict="not-built")]}
        top.update(extra or {})
        (d / "docs" / "map" / "map.json").write_text(json.dumps(top, indent=1) + "\n", encoding="utf-8")
        git(d, "commit", "-qam", "labels")
        return "labels"

    def check_label_report(self, done) -> dict:
        self.assertEqual(done.returncode, 0, done.stderr)
        report = json.loads(done.stdout)
        rows = {r["id"]: r for r in report["rows"]}
        self.assertEqual({k: v["change"] for k, v in rows.items()}, {"C-2": "changed", "C-5": "relabelled"})
        self.assertEqual(rows["C-5"]["featureChanged"], {"before": None, "after": "billing"})
        self.assertEqual(rows["C-2"]["feature"], "reports")
        self.assertNotIn("area", rows["C-2"])
        self.assertNotIn("areas", report)
        self.assertEqual(report["features"], [{"id": "reports", "name": "Reports",
                                               "plain": "The reports a client reads.", "rows": ["C-2"]}])
        self.assertEqual(report["summary"]["rowsRelabelled"], 1)
        self.assertEqual(report["featuresRelabelled"], [{"id": "billing", "name": "Billing",
                                                         "plain": "What a client pays.", "rows": ["C-5"]}])
        return report

    def test_features_group_the_rows_and_a_new_label_is_no_promise_change(self) -> None:
        self.label_map("features", "feature")
        d = self.dir
        self.check_label_report(run(CHANGED, "--base", "feat", "--head", "labels", "--json", cwd=str(d)))
        md = run(CHANGED, "--base", "feat", "--head", "labels", "--markdown", cwd=str(d)).stdout
        self.assertIn("Features: Reports (1).", md)
        self.assertIn("Feature changed, the promise unchanged: [C-5](", md)
        self.assertIn("(none \u2192 billing)", md)
        self.assertIn("1 relabelled", md)

    def test_the_older_area_keys_report_as_features(self) -> None:
        self.label_map("areas", "area")
        self.check_label_report(run(CHANGED, "--base", "feat", "--head", "labels", "--json", cwd=str(self.dir)))

    def test_a_map_with_both_spellings_is_the_error_feature_and_area(self) -> None:
        both_top = {"areas": [{"id": "reports", "name": "Reports", "plain": "The reports a client reads."}]}
        self.label_map("features", "feature", extra=both_top)
        done = run(CHANGED, "--base", "feat", "--head", "labels", "--json", cwd=str(self.dir))
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("FEATURE_AND_AREA", done.stderr)
        self.assertIn("'features' and 'areas'", done.stderr)

    def test_a_row_with_both_spellings_is_the_error_feature_and_area(self) -> None:
        self.label_map("features", "feature", extra_row={"area": "billing"})
        done = run(CHANGED, "--base", "feat", "--head", "labels", "--json", cwd=str(self.dir))
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("FEATURE_AND_AREA", done.stderr)
        self.assertIn("row C-5 has both 'feature' and 'area'", done.stderr)

    def test_the_report_feeds_the_lint_end_to_end(self) -> None:
        self.label_map("features", "feature")
        report = self.check_label_report(run(CHANGED, "--base", "feat", "--head", "labels", "--json",
                                             cwd=str(self.dir)))
        out = Path(tempfile.mkdtemp())
        (out / "changed.json").write_text(json.dumps(report), encoding="utf-8")
        body = (self.dir / "pr.md")
        body.write_text(
            "<!-- promise:pr -->\n## Where this is\n\nThis change is about one part of the product:\n\n"
            "- **Reports**: the reports a client reads.\n\n**Needed from you:** nothing yet.\n\n"
            "## Words\n\nNone.\n\n## What changes for people\n\nA report reads faster.\n"
            "<!-- /promise:pr -->\n", encoding="utf-8")
        done = run(LINT, "--kind", "pr", str(body), "--map", str(self.dir / "docs" / "map" / "map.json"),
                   "--changed", str(out / "changed.json"), "--json", cwd=str(self.dir))
        rules = {f["rule"] for f in json.loads(done.stdout)["findings"]}
        self.assertNotIn("AREA_UNKNOWN", rules)
        self.assertNotIn("AREA_MISSING", rules, "C-2's feature (reports) is named; C-5 is relabelled only")
        self.assertNotIn("FEATURE_AND_AREA", rules)
        # The positive control: the same report, and a body that does not name
        # the feature, must fail -- so the lint read the features from the map.
        body.write_text(body.read_text(encoding="utf-8").replace(
            "- **Reports**: the reports a client reads.", "- **Billing**: what a client pays."), encoding="utf-8")
        self.assertNotIn("Reports", body.read_text(encoding="utf-8"))
        done = run(LINT, "--kind", "pr", str(body), "--map", str(self.dir / "docs" / "map" / "map.json"),
                   "--changed", str(out / "changed.json"), "--json", cwd=str(self.dir))
        missing = [f for f in json.loads(done.stdout)["findings"] if f["rule"] == "AREA_MISSING"]
        self.assertEqual(len(missing), 1, done.stdout)
        self.assertIn("Reports", missing[0]["message"])

    def test_a_mass_relabel_is_counted_by_feature(self) -> None:
        sys.path.insert(0, str(SCRIPTS_DIR))
        import changed_rows
        ids = [f"C-{n}" for n in (2, 10, 1, 30, 4, 5, 6, 7, 8, 9, 11, 12, 13)]
        self.assertEqual(sorted(ids, key=changed_rows.id_key)[:3], ["C-1", "C-2", "C-4"])
        rows = [{"id": i, "change": "relabelled", "feature": "billing" if i != "C-30" else None,
                 "featureChanged": {"before": None, "after": "billing"}} for i in ids]
        report = {"rows": rows, "features": [], "docs": [], "unhomed": [], "prose": [], "warnings": [],
                  "leftOut": {"added": [], "removed": []}, "outsideProject": [],
                  "map": {"configured": True}, "summary": {"files": 1, "rowsAdded": 0, "rowsChanged": 0,
                  "rowsRemoved": 0, "rowsTouched": 0, "rowsRelabelled": 13, "verdictsMoved": 0,
                  "docsChanged": 0, "unhomedFiles": 0, "proseFiles": 0, "filesOutsideProject": 0,
                  "leftOutAdded": 0, "leftOutRemoved": 0},
                  "featuresRelabelled": changed_rows.features_of(rows, {"billing": {"name": "Billing"}}, relabelled=True)}
        md = changed_rows.format_markdown(report)
        self.assertIn("Feature changed, the promise unchanged: 13 rows. Their new features: Billing (12), none (1).", md)
        self.assertNotIn("[C-1]", md)

    def test_link_flag_prints_one_line_per_row(self) -> None:
        done = run(CHANGED, "--head", "feat", "--link", "C-2", "--link", "C-6", cwd=str(self.dir))
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertEqual([ln.split()[0] for ln in lines], ["C-2", "C-6"])
        self.assertEqual(run(CHANGED, "--head", "feat", "--link", "C-99", cwd=str(self.dir)).returncode, 2)

    def test_markdown_lists_moved_rows_in_a_table_and_touched_rows_on_one_line(self) -> None:
        done = run(CHANGED, "--base", "main", "--head", "feat", "--markdown", cwd=str(self.dir))
        self.assertEqual(done.returncode, 0, done.stderr)
        text = done.stdout
        self.assertIn("| [C-6](https://github.com/o/r/blob/", text)
        self.assertIn("proven → under-proven", text)
        touched = next(ln for ln in text.splitlines() if ln.startswith("Touched"))
        self.assertIn("C-1", touched)
        self.assertIn("C-4", touched)
        self.assertIn("- `src/other.ts`", text)

    def test_unknown_ref_is_a_usage_error(self) -> None:
        done = run(CHANGED, "--base", "nope", cwd=str(self.dir))
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown git ref", done.stderr)


class LintGithubText(unittest.TestCase):
    def lint(self, kind: str, text: str, *extra: str) -> subprocess.CompletedProcess:
        return run(LINT, "--kind", kind, "-", "--map", FIX / "map.json", "--json", *extra, stdin=text)

    def rules(self, kind: str, text: str, *extra: str) -> list:
        done = self.lint(kind, text, *extra)
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return sorted({f["rule"] for f in json.loads(done.stdout)["findings"]})

    def issue(self) -> str:
        return (FIX / "issue_good.md").read_text(encoding="utf-8")

    def pr(self) -> str:
        return (FIX / "pr_good.md").read_text(encoding="utf-8")

    def test_the_good_bodies_pass(self) -> None:
        self.assertEqual(self.lint("issue", self.issue()).returncode, 0)
        done = self.lint("pr", self.pr(), "--changed", FIX / "changed.json")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(json.loads(done.stdout)["findings"], [])

    def test_a_map_whose_features_or_glossary_is_not_a_list_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for key, value in (("features", 5), ("areas", 5), ("glossary", 7), ("glossary", {"Seat": 1})):
                with self.subTest(key=key, value=value):
                    path = Path(tmp) / "map.json"
                    path.write_text(json.dumps({"rows": [{"id": "C-1"}], key: value}), encoding="utf-8")
                    done = run(LINT, "--kind", "pr", "-", "--map", path, stdin=self.pr())
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertIn(f"'{key}' is not a list", done.stderr)
            path.write_text(json.dumps({"rows": [{"id": "C-1"}],
                                        "glossary": [{"term": "Export", "plain": "x", "aliases": 3}]}),
                            encoding="utf-8")
            self.assertIn(run(LINT, "--kind", "pr", "-", "--map", path, stdin=self.pr()).returncode, (0, 1))

    def test_no_block_and_repeated_markers(self) -> None:
        self.assertEqual(self.rules("pr", "Just text."), ["NO_BLOCK"])
        self.assertEqual(self.rules("pr", self.pr() + "\n<!-- promise:pr -->\n"), ["NO_BLOCK"])

    def test_empty_templates_fail_until_filled(self) -> None:
        pr = run(LINT, "--kind", "pr", PR_TEMPLATE, "--no-map")
        self.assertEqual(pr.returncode, 1)
        self.assertEqual(pr.stdout.count("EMPTY_SECTION"), 7)
        issue = run(LINT, "--kind", "issue", ISSUE_TEMPLATE, "--no-map")
        self.assertEqual(issue.returncode, 1)
        self.assertEqual(issue.stdout.count("MISSING_SECTION"), 6)
        self.assertNotIn("NO_INTRO", issue.stdout)

    def test_each_template_carries_one_pair_of_markers(self) -> None:
        for path, kind in ((ISSUE_TEMPLATE, "issue"), (ISSUE_TEMPLATE, "intro"), (PR_TEMPLATE, "pr")):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count(f"<!-- promise:{kind} -->"), 1, path)
            self.assertEqual(text.count(f"<!-- /promise:{kind} -->"), 1, path)
        issue = ISSUE_TEMPLATE.read_text(encoding="utf-8")
        self.assertLess(issue.index("<!-- promise:intro -->"), issue.index("## What we want"),
                        "the intro opens the body, above the person's words")

    def test_people_section_rules(self) -> None:
        good = "Before, the export button did nothing when a report was empty. Now it downloads an empty report and says so."
        for bad, rule in (
            ("Now `exportReport` returns early.", "CODE_WORDS"),
            ("Now src/export.ts returns early.", "CODE_WORDS"),
            ("Now POST /reports/export answers 200.", "CODE_WORDS"),
            ("Now the report_id is kept.", "CODE_WORDS"),
            ("Now C-2 holds.", "CODE_WORDS"),
            ("Now " + "very " * 20 + "long.", "SENTENCE_TOO_LONG"),
            (" ".join(["It works now."] * 4), "TOO_LONG"),
            ("Now it downloads <what the person sees>.", "PLACEHOLDER"),
        ):
            with self.subTest(rule=rule, text=bad):
                self.assertIn(rule, self.rules("pr", self.pr().replace(good, bad)))

    def test_why_needs_a_link(self) -> None:
        text = self.pr().replace("Closes #12. ", "")
        self.assertIn("NO_LINK", self.rules("pr", text))
        self.assertNotIn("NO_LINK", self.rules("pr", self.pr().replace("Closes #12.", "No issue.")))

    def test_check_items(self) -> None:
        text = self.pr().replace("1. `src/export.ts:41`: the early return is gone.", "1. the handler.")
        self.assertIn("CHECK_ITEMS", self.rules("pr", text))
        four = "\n".join(f"{n}. `a.ts:{n}`: x." for n in range(1, 5))
        text = re.sub(r"(## Check these first\n\n)(?:.+\n)+", lambda m: m.group(1) + four + "\n", self.pr())
        self.assertIn("CHECK_ITEMS", self.rules("pr", text))

    def test_rows_missing_or_unknown(self) -> None:
        text = self.pr().replace("- Touched, verdicts unchanged: C-4.\n", "")
        done = self.lint("pr", text, "--changed", FIX / "changed.json")
        findings = json.loads(done.stdout)["findings"]
        self.assertEqual([(f["rule"], f["severity"]) for f in findings], [("ROW_MISSING", "warn")])
        text = self.pr().replace("- [C-3](https://github.com/o/r/blob/abc/map.json#L40) new: ", "- New: ")
        self.assertIn("ROW_MISSING", self.rules("pr", text, "--changed", FIX / "changed.json"))
        self.assertIn("ROW_UNKNOWN", self.rules("pr", self.pr().replace("C-4.", "C-44.")))

    def test_a_feature_size_is_the_capability_alias(self) -> None:
        line = "Size: small — one new behaviour on C-2, the report download."
        self.assertIn(line, self.pr())
        done = self.lint("pr", self.pr().replace(line, "Size: feature — a new export job."))
        found = [(f["rule"], f["severity"]) for f in json.loads(done.stdout)["findings"] if f["rule"].startswith("SIZE")]
        self.assertEqual(found, [("SIZE_ALIAS", "warn")])  # a warning, never an error
        self.assertEqual(done.returncode, 0, done.stdout)
        sys.path.insert(0, str(SCRIPTS_DIR))
        import lint_github_text  # noqa: PLC0415
        self.assertEqual(lint_github_text.size_lines("Size: feature — x"), [(1, "feature")])
        self.assertEqual(lint_github_text.canonical_size("feature"), "capability")
        capability = self.lint("pr", self.pr().replace(line, "Size: capability — a new export job."))
        self.assertEqual([f["rule"] for f in json.loads(capability.stdout)["findings"]
                          if f["rule"].startswith("SIZE")], [])

    def test_the_size_line_is_one_of_the_four_sizes(self) -> None:
        line = "Size: small — one new behaviour on C-2, the report download."
        self.assertIn(line, self.pr())
        for good in ("Size: tiny — keeps C-2.", "**Size:** risky, it moves a payment.", "Size: Capability."):
            self.assertNotIn("SIZE", self.rules("pr", self.pr().replace(line, good)))
        for bad in ("Size: medium — a bit.", "Size:", "Size: <tiny|small|capability|risky>"):
            done = self.lint("pr", self.pr().replace(line, bad))
            sizes = [f for f in json.loads(done.stdout)["findings"] if f["rule"] == "SIZE"]
            self.assertEqual([f["severity"] for f in sizes], ["error"], bad)
            self.assertEqual(done.returncode, 1, bad)
        twice = self.rules("pr", self.pr().replace(line, line + "\n\nSize: tiny — keeps C-2."))
        self.assertEqual(twice.count("SIZE"), 1)
        # none at all is a warning: a body written before the Size line still passes
        done = self.lint("pr", self.pr().replace(line, ""))
        found = json.loads(done.stdout)["findings"]
        self.assertEqual([(f["rule"], f["severity"]) for f in found], [("SIZE", "warn")])
        self.assertEqual(done.returncode, 0, done.stdout)
        # a Size line in a comment or outside the block is not the claim
        hidden = self.pr().replace(line, "<!-- Size: huge -->")
        self.assertEqual([f["severity"] for f in json.loads(self.lint("pr", hidden).stdout)["findings"]
                          if f["rule"] == "SIZE"], ["warn"])
        # only the Why section holds the claim: a Size line elsewhere is just words
        elsewhere = self.pr().replace("## Proof\n", "## Proof\n\n- Size: 3 MB after the build.\n")
        self.assertNotEqual(elsewhere, self.pr())
        self.assertNotIn("SIZE", self.rules("pr", elsewhere))
        # a dash with no space before it still ends the word
        self.assertNotIn("SIZE", self.rules("pr", self.pr().replace(line, "Size: tiny—keeps C-2.")))
        # case is ignored, and a size under another heading is still the claim
        sys.path.insert(0, str(SCRIPTS_DIR))
        import lint_github_text  # noqa: PLC0415
        lower = self.pr().replace(line, "size: tiny — keeps C-2.")
        self.assertEqual([w for _n, w in lint_github_text.size_lines(lower)], ["tiny"])
        moved = self.pr().replace(line, "").replace("## Proof\n", "## Proof\n\nSize: tiny — keeps C-2.\n")
        self.assertEqual([w for _n, w in lint_github_text.size_lines(moved)], ["tiny"])
        for marked in ("Size: `tiny` — keeps C-2.", "Size: *tiny* — keeps C-2.", "Size: _tiny_ — keeps C-2."):
            self.assertEqual([w for _n, w in lint_github_text.size_lines(self.pr().replace(line, marked))], ["tiny"])

    def test_unhomed_files_need_a_line(self) -> None:
        text = self.pr().replace("- No row names: README.md, because it is a doc change only.\n", "")
        self.assertIn("UNHOMED", self.rules("pr", text, "--changed", FIX / "changed.json"))

    def test_details_do_not_count_against_the_budget(self) -> None:
        many = "\n".join(f"| C-{n} | x |" for n in range(100))
        text = self.pr().replace("| C-2 | changed |", "| C-2 | changed |\n" + many)
        self.assertNotIn("TOO_LONG", self.rules("pr", text, "--no-map"))
        text = self.pr().replace("- npm test: 42 passed, 0 skipped.",
                                 "\n".join(["- a line of eight plain words for the budget."] * 30))
        self.assertIn("TOO_LONG", self.rules("pr", text))
        nested = "<details><summary>a</summary>\n<details><summary>b</summary>\nx\n</details>\n" + (
            "word " * 300) + "\n</details>"
        self.assertNotIn("TOO_LONG", self.rules("pr", self.pr().replace("## Proof", nested + "\n\n## Proof")))

    def test_a_link_counts_as_its_text_and_a_path_as_one_word(self) -> None:
        link = "[C-2](https://github.com/o/r/blob/0123456789abcdef0123456789abcdef01234567/docs/capabilities/map.json#L20)"
        text = self.issue().replace("The spreadsheet format does not exist.",
                                    f"The format named in {link} is read by apps/api/src/routes/export-format.ts:41-72 "
                                    "and nothing else writes it today.")
        self.assertNotIn("SENTENCE_TOO_LONG", self.rules("issue", text))

    def test_a_removed_row_can_be_named(self) -> None:
        changed = json.loads((FIX / "changed.json").read_text(encoding="utf-8"))
        changed["rows"].append({"id": "C-9", "change": "removed"})
        path = Path(tempfile.mkdtemp()) / "changed.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        text = self.pr().replace("- No row names:", "- [C-9](https://x/y) removed: it moved to C-3.\n- No row names:")
        self.assertNotIn("ROW_UNKNOWN", self.rules("pr", text, "--changed", str(path)))
        self.assertNotIn("ROW_MISSING", self.rules("pr", text, "--changed", str(path)))

    def test_many_rows_may_be_given_as_a_count(self) -> None:
        changed = {"rows": [{"id": "C-1", "change": "added"}] * 1, "unhomed": []}
        changed["rows"] = [{"id": f"C-{n}", "change": "added"} for n in range(100, 130)]
        path = Path(tempfile.mkdtemp()) / "changed.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        text = self.pr().replace("- No row names: README.md, because it is a doc change only.\n", "")
        found = self.lint("pr", text, "--changed", str(path), "--no-map")
        missing = [f for f in json.loads(found.stdout)["findings"] if f["rule"] == "ROW_MISSING"]
        self.assertEqual(len(missing), 13)
        text = text.replace("## Check these first", "- 30 rows added, one for each route.\n\n## Check these first")
        self.assertNotIn("ROW_MISSING", self.rules("pr", text, "--changed", str(path), "--no-map"))

    def test_intake_relation_names_and_the_relation_comes_first(self) -> None:
        self.assertEqual(self.rules("issue", self.issue().replace("DEFECT [C-2]", "EXISTING-SCENARIO [C-2]")), [])
        self.assertEqual(self.rules("issue", self.issue().replace("DEFECT [C-2]", "KEEPS [C-2]")), [])
        self.assertIn("RELATION", self.rules("issue", self.issue().replace("DEFECT [C-2]", "This is not a DEFECT; [C-2]")))

    def test_nothing_to_build_needs_no_build_relation(self) -> None:
        text = self.issue().replace(
            "1. Reproduce it, add a red test for C-2 S1, the download, fix the handler, then `/promise reconcile` C-2, "
            "the export row.\n"
            "2. `/promise new` for the spreadsheet export; a human agrees it; `/promise arm`, build, `/promise reconcile`.",
            "Nothing to build.")
        self.assertIn("NO_ROUTE", self.rules("issue", text))

    def test_a_decision_ask_needs_a_decision(self) -> None:
        text = self.issue().replace("NEW-ROW: no row", "DECISION: no row").replace(
            "- [ ] Is a spreadsheet export worth building this quarter? (owner: Ollie)", "None.")
        self.assertIn("DECISIONS", self.rules("issue", text))
        text = self.issue().replace(" (owner: Ollie)", "")
        findings = json.loads(self.lint("issue", text).stdout)["findings"]
        self.assertEqual([(f["rule"], f["severity"]) for f in findings], [("DECISIONS", "warn")])

    def test_a_verdict_beside_a_row_must_be_the_maps(self) -> None:
        rows = json.loads((FIX / "map.json").read_text(encoding="utf-8"))
        for row in rows["rows"]:
            row["verdict"] = "under-proven"
        path = Path(tempfile.mkdtemp()) / "map.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        done = run(LINT, "--kind", "issue", "-", "--map", str(path), "--json", stdin=self.issue())
        self.assertIn("VERDICT_WRONG", done.stdout)
        done = run(LINT, "--kind", "issue", "-", "--map", str(path), "--json",
                   stdin=self.issue().replace("(proven)", "(under-proven)"))
        self.assertEqual(done.returncode, 0, done.stdout)

    def test_a_verdict_after_a_scenario_id_and_in_details_is_checked(self) -> None:
        rows = json.loads((FIX / "map.json").read_text(encoding="utf-8"))
        for row in rows["rows"]:
            row["verdict"] = "proven"
        path = Path(tempfile.mkdtemp()) / "map.json"
        path.write_text(json.dumps(rows), encoding="utf-8")

        def rules(text: str) -> list:
            done = run(LINT, "--kind", "issue", "-", "--map", str(path), "--json", stdin=text)
            return sorted({f["rule"] for f in json.loads(done.stdout)["findings"]})

        self.assertIn("VERDICT_WRONG", rules(self.issue().replace("#L20) (proven)", "#L20) S1 (under-proven)")))
        self.assertEqual(rules(self.issue().replace("#L20) (proven)", "#L20) S1 and S2 (proven)")), [])
        details = ("\n<details><summary>Each ask in full</summary>\n\nC-2 (not-built) and C-404 hold it.\n\n"
                   "</details>\n<!-- /promise:issue -->")
        self.assertEqual(rules(self.issue().replace("<!-- /promise:issue -->", details)),
                         ["ROW_UNKNOWN", "VERDICT_WRONG"])

    def test_the_capability_check_starts_with_what_it_read(self) -> None:
        text = self.issue().replace("Read: docs/designs/export.md.", "Searched the map for: export.")
        findings = json.loads(self.lint("issue", text).stdout)["findings"]
        self.assertEqual([(f["rule"], f["severity"]) for f in findings], [("READ_LINE", "warn")])

    def test_an_answered_decision_needs_no_owner(self) -> None:
        answered = ('- [x] Is a spreadsheet export worth building? answered by [Ollie, 2026-09-25]'
                    '(https://github.com/o/r/issues/1#issuecomment-1): "yes"')
        text = self.issue().replace("- [ ] Is a spreadsheet export worth building this quarter? (owner: Ollie)", answered)
        self.assertEqual(self.rules("issue", text), [])
        self.assertIn("DECISIONS", self.rules("issue", text.replace("- [x]", "- [ ]")))

    def test_placeholders_are_template_text_only(self) -> None:
        for fine in ("`Promise<void>`", "<https://example.com/runbook>", "<ollie@example.com>",
                     "`Given <one client> has a key`"):
            with self.subTest(fine=fine):
                text = self.issue().replace("The spreadsheet format does not exist.", f"See {fine}.")
                self.assertNotIn("PLACEHOLDER", self.rules("issue", text))
        self.assertIn("PLACEHOLDER", self.rules("issue", self.issue().replace("(owner: Ollie)", "(owner: <name>)")))

    def test_markers_in_a_code_fence_are_text(self) -> None:
        fence = "```markdown\n<!-- promise:issue -->\n<!-- /promise:issue -->\n```\n\n"
        after_intro = self.issue().replace("<!-- /promise:intro -->\n", "<!-- /promise:intro -->\n\n" + fence, 1)
        self.assertEqual(self.rules("issue", after_intro), [])
        self.assertEqual(self.rules("issue", fence + self.issue()), ["INTRO_FIRST"])
        spaced = self.issue().replace("<!-- promise:issue -->", "<!--promise:issue  -->")
        self.assertEqual(self.rules("issue", spaced), [])

    def test_check_items_and_links(self) -> None:
        pr = self.pr()
        start = pr.index("## Check these first")
        section = pr[start:pr.index("## Proof")]
        for item in ("1. `Dockerfile:12`: the image.\n", "1. https://github.com/o/r/blob/abc/src/a.ts#L41: the line.\n",
                     "1. `src/a.ts:4`: the check.\n   - it reads one column.\n   - and nothing else.\n"):
            with self.subTest(item=item):
                text = pr.replace(section, "## Check these first\n\n" + item + "\n")
                self.assertNotIn("CHECK_ITEMS", self.rules("pr", text, "--no-map"))
        why = pr[pr.index("## Why"):pr.index("## Capabilities")]
        self.assertNotIn("NO_LINK", self.rules("pr", pr.replace(why, "## Why\n\nCloses GH-12. The export.\n\n"),
                                               "--no-map"))
        self.assertIn("NO_LINK", self.rules("pr", pr.replace(why, "## Why\n\nThere is no issue with the export.\n\n"),
                                            "--no-map"))

    def test_row_patterns(self) -> None:
        import lint_github_text as lint_mod
        both = lint_mod.row_pattern("^C-\\d+$|^OPS-\\d+$")
        self.assertEqual(both.findall("C-1 and OPS-2"), ["C-1", "OPS-2"])
        plain = lint_mod.row_pattern(None)
        self.assertEqual(plain.findall("UTF-8, SHA-256, ISO-8601 and CAP-3"), ["CAP-3"])
        derived = lint_mod.row_pattern(None, {"CAP-1", "CAP-2"})
        self.assertEqual(derived.findall("GH-12 and CAP-7"), ["CAP-7"])
        self.assertEqual(lint_mod.words("It is e.g. fine, per Dr. Who."), 7)
        self.assertEqual(len(lint_mod.sentences([(1, "It is e.g. fine. Dr. Who is **here.** Next.")])), 3)

    def test_issue_rules(self) -> None:
        self.assertIn("RELATION", self.rules("issue", self.issue().replace("DEFECT ", "")))
        text = self.issue().replace("`/promise reconcile` C-2", "reconcile it").replace(
            "`/promise new` for the spreadsheet export; a human agrees it; `/promise arm`, build, `/promise reconcile`.",
            "build the spreadsheet export.")
        self.assertIn("NO_ROUTE", self.rules("issue", text))
        self.assertIn("MISSING_SECTION", self.rules("issue", self.issue().replace("## Gap", "## Gaps")))

    def test_text_outside_the_block_is_not_checked(self) -> None:
        text = "Now `code` and a very long sentence " + "word " * 40 + ".\n\n" + self.issue()
        self.assertEqual(self.lint("issue", text).returncode, 0)

    def test_an_issue_opens_with_its_intro(self) -> None:
        issue = self.issue()
        intro = issue[:issue.index("## What we want")]
        self.assertEqual(self.rules("issue", issue.replace(intro, "")), ["NO_INTRO"])
        done = self.lint("issue", issue.replace(intro, ""))
        found = json.loads(done.stdout)["findings"]
        self.assertIn("`/promise issue` writes one", found[0]["message"])
        # Text from before the first screen has no intro: a warning, so it still passes.
        self.assertEqual(found[0]["severity"], "warn")
        self.assertEqual(done.returncode, 0, done.stdout)
        # An intro whose markers are broken is an error.
        for broken in (intro + "<!-- promise:intro -->\n", intro.replace("<!-- promise:intro -->", "", 1)):
            with self.subTest(broken=broken[:40]):
                done = self.lint("issue", issue.replace(intro, broken))
                self.assertIn(("NO_INTRO", "error"),
                              [(f["rule"], f["severity"]) for f in json.loads(done.stdout)["findings"]])
                self.assertEqual(done.returncode, 1)
        moved = issue.replace(intro, "") + "\n" + intro
        self.assertEqual(self.rules("issue", moved), ["INTRO_FIRST"])
        no_words = issue.replace("## Words\n\n- **Export**: download a report as a file, such as a PDF.\n", "")
        self.assertIn("MISSING_SECTION", self.rules("issue", no_words))

    def test_where_this_is_lists_areas_in_plain_words(self) -> None:
        issue = self.issue()
        area = "- **Reports**: the reports a client reads and downloads.\n"
        for bad, rule in (("- Reports, the reports a client reads.\n", "AREAS"),
                          ("- **Reports**: the page at `src/reports.ts` for CAP-2.\n", "CODE_WORDS"),
                          ("- **Invoices**: the bills a client pays.\n", "AREA_UNKNOWN"),
                          ("".join(f"- **Part {n}**: one part.\n" for n in range(6)), "AREAS")):
            with self.subTest(rule=rule, bad=bad):
                self.assertIn(rule, self.rules("issue", issue.replace(area, bad)))
        self.assertEqual(self.rules("issue", issue.replace(area, "- **reports** - what a client reads.\n")), [])
        self.assertEqual(self.rules("issue", issue.replace("**Needed from you:** one decision", "One decision")),
                         ["NEEDED"])

    def test_a_row_named_needs_its_area(self) -> None:
        issue = self.issue().replace("- **Reports**: the reports a client reads and downloads.\n",
                                     "- **Billing**: what a client pays.\n")
        done = self.lint("issue", issue)
        found = [f for f in json.loads(done.stdout)["findings"] if f["rule"] == "AREA_MISSING"]
        self.assertEqual(len(found), 1, found)
        self.assertIn("C-2", found[0]["message"])
        self.assertIn("Reports", found[0]["message"])
        self.assertEqual(done.returncode, 0)  # a warning

    def test_words_explain_the_glossary_terms_a_reader_meets(self) -> None:
        issue = self.issue()
        term = "- **Export**: download a report as a file, such as a PDF.\n"
        self.assertEqual(self.rules("issue", issue.replace(term, "None.\n")), ["TERM_UNDEFINED"])
        self.assertEqual(self.rules("issue", issue.replace(term, "- Export means a download.\n")),
                         ["TERM_UNDEFINED", "WORDS"])
        nested = "- **Export**: a download.\n  - **Exports, as a PDF**: the first format.\n"
        self.assertEqual(self.rules("issue", issue.replace(term, nested)), [])
        # A term only in <details>, a code span or a link's address is not met by a reader.
        plain = issue.replace(term, "None.\n").replace("export", "download").replace("Export", "Download")
        self.assertEqual(self.rules("issue", plain), [])
        hidden = plain.replace("## What we want\n", "## What we want\n\n`export` [a](https://x/export)\n"
                               "<details><summary>More</summary>\n\nExport it.\n\n</details>\n")
        self.assertEqual(self.rules("issue", hidden), [])
        # An area's own name is explained by its sentence, so it covers its term in
        # the whole body; another area's sentence is still read.
        area = "- **Reports**: the reports a client reads and downloads.\n"
        named = plain.replace(area, area + "- **Exports**: the files a client downloads.\n")
        self.assertEqual(self.rules("issue", named), ["AREA_UNKNOWN"])
        said = plain.replace(area, area + "- **Exports**: the files a client exported.\n")
        self.assertEqual(self.rules("issue", said), ["AREA_UNKNOWN"])
        other = plain.replace(area, area + "- **Files**: the files a client exported.\n")
        self.assertEqual(self.rules("issue", other), ["AREA_UNKNOWN", "TERM_UNDEFINED"])

    def test_a_map_with_both_spellings_fails_the_lint_with_feature_and_area(self) -> None:
        data = json.loads((FIX / "map.json").read_text(encoding="utf-8"))
        both_map = dict(data, areas=data["features"])
        both_row = json.loads(json.dumps(data))
        both_row["rows"][1]["area"] = "reports"
        old_only = json.loads(json.dumps(data))
        old_only["areas"] = old_only.pop("features")
        for row_ in old_only["rows"]:
            if "feature" in row_:
                row_["area"] = row_.pop("feature")
        mixed_rows = json.loads(json.dumps(old_only))
        mixed_rows["rows"][1]["feature"] = mixed_rows["rows"][1].pop("area")
        top_and_rows = json.loads(json.dumps(data))
        for row_ in top_and_rows["rows"]:
            if "feature" in row_:
                row_["area"] = row_.pop("feature")
        for name, top, expected in (("map", both_map, True), ("row", both_row, True), ("old keys", old_only, False),
                                    ("rows mix", mixed_rows, True), ("top features, rows area", top_and_rows, True)):
            with self.subTest(name):
                path = Path(tempfile.mkdtemp()) / "map.json"
                path.write_text(json.dumps(top), encoding="utf-8")
                done = run(LINT, "--kind", "issue", "-", "--map", path, "--json", stdin=self.issue())
                found = [f for f in json.loads(done.stdout)["findings"] if f["rule"] == "FEATURE_AND_AREA"]
                self.assertEqual(bool(found), expected, done.stdout)
                if expected:
                    self.assertEqual(found[0]["severity"], "error")
                    self.assertEqual(done.returncode, 1)
                else:
                    self.assertEqual(done.returncode, 0, done.stdout)

    def lint_with(self, glossary: list, text: str, *extra: str) -> list:
        """The rules found with a map that has the fixture's rows and areas and this glossary."""
        data = json.loads((FIX / "map.json").read_text(encoding="utf-8"))
        data["glossary"] = glossary
        path = Path(tempfile.mkdtemp()) / "map.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        done = run(LINT, "--kind", "issue", "-", "--map", path, "--json", *extra, stdin=text)
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return sorted({f["rule"] for f in json.loads(done.stdout)["findings"]})

    def test_a_term_or_an_area_covers_its_singular_and_its_plural(self) -> None:
        term = "- **Export**: download a report as a file, such as a PDF.\n"
        issue = self.issue().replace("an export button", "an export button for invoices")
        for glossary in ([{"term": "Invoice", "plain": "a bill"}], [{"term": "Invoices", "plain": "bills"}]):
            with self.subTest(glossary=glossary[0]["term"]):
                self.assertEqual(self.lint_with(glossary, issue), ["TERM_UNDEFINED"])
                for said in ("- **Invoice**: a bill.\n", "- **Invoices**: bills.\n"):
                    self.assertEqual(self.lint_with(glossary, issue.replace(term, term + said)), [])
                area = ("- **Reports**: the reports a client reads and downloads.\n"
                        "- **Invoices**: the bills a client pays, not yet in the map.\n")
                self.assertEqual(self.lint_with(glossary, issue.replace(
                    "- **Reports**: the reports a client reads and downloads.\n", area)), [])

    def test_code_paths_urls_and_file_names_are_not_read_for_terms(self) -> None:
        term = "- **Export**: download a report as a file, such as a PDF.\n"
        issue = self.issue().replace(term, "None.\n").replace("export", "download").replace("Export", "Download")
        for code in ("See src/routes/exports.ts:12 and docs/export-guide.md.",
                     "The route is /api/exports/{id}.", "It is in exports.ts.",
                     "It was https://example.com/exports/1 before."):
            with self.subTest(code=code):
                self.assertEqual(self.rules("issue", issue.replace("does nothing.", "does nothing. " + code)), [])
        self.assertEqual(self.rules("issue", issue.replace("does nothing.", "does nothing. It exports.")),
                         ["TERM_UNDEFINED"])

    def test_areas_past_five_go_on_one_also_line(self) -> None:
        issue = self.issue()
        area = "- **Reports**: the reports a client reads and downloads.\n"
        billing = "- **Billing**: what a client pays, not yet in the map.\n"
        self.assertEqual(self.rules("issue", issue.replace(area, billing)), ["AREA_MISSING"])
        for also in ("\nAlso: **Reports**.\n", "\n**Also:** Reports.\n"):
            with self.subTest(also=also):
                self.assertEqual(self.rules("issue", issue.replace(area, billing + also)), [])
        self.assertEqual(self.rules("issue", issue.replace(area, area + "\nAlso: **Invoices**.\n")),
                         ["AREA_UNKNOWN"])
        parts = "".join(f"- **Part {n}**: one part, not yet in the map.\n" for n in range(5))
        self.assertEqual(self.rules("issue", issue.replace(area, parts + "\nAlso: **Reports**.\n")), [])
        # Each name on the line is an area: the two not in the map are said once each.
        done = self.lint("issue", issue.replace(area, parts + "\nAlso: **Part 5**, **Part 6** and **Reports**.\n"))
        found = [f["message"] for f in json.loads(done.stdout)["findings"]]
        self.assertEqual(len(found), 2, found)
        self.assertTrue(all("not a feature in the map" in m for m in found), found)
        six = "".join(f"- **Part {n}**: one part, not yet in the map.\n" for n in range(5)) + area
        done = self.lint("issue", issue.replace(area, six))
        found = [f for f in json.loads(done.stdout)["findings"] if f["rule"] == "AREAS"]
        self.assertEqual(len(found), 1, found)
        self.assertIn("Also:", found[0]["message"])

    def test_a_name_on_the_also_line_explains_no_word(self) -> None:
        issue = self.issue().replace("- **Export**: download a report as a file, such as a PDF.", "None.")
        self.assertIn("TERM_UNDEFINED", self.rules("issue", issue))
        area = "- **Reports**: the reports a client reads and downloads.\n"
        also = issue.replace(area, area + "\nAlso: **Exports**.\n")
        self.assertIn("TERM_UNDEFINED", self.rules("issue", also))
        # an area with its own sentence still explains its name
        named = issue.replace(area, area + "- **Exports**: the files a client downloads.\n")
        self.assertNotIn("TERM_UNDEFINED", self.rules("issue", named))

    def test_counts_give_the_words_against_each_budget(self) -> None:
        done = self.lint("issue", self.issue())
        counts = json.loads(done.stdout)["counts"]
        self.assertEqual(sorted(counts), ["block", "firstScreen"])
        self.assertEqual(counts["firstScreen"]["budget"], 180)
        self.assertEqual(counts["block"]["budget"], 450)
        self.assertTrue(0 < counts["firstScreen"]["words"] < 40, counts)
        done = self.lint("pr", self.pr(), "--changed", FIX / "changed.json")
        counts = json.loads(done.stdout)["counts"]
        self.assertEqual(sorted(counts), ["block", "firstScreen", "people"])
        self.assertEqual(counts["people"]["budget"], 60)
        human = run(LINT, "--kind", "issue", "-", "--map", FIX / "map.json", "--counts", stdin=self.issue())
        self.assertEqual(human.returncode, 0, human.stdout)
        last = human.stdout.strip().splitlines()[-1]
        self.assertRegex(last, r"^-: words: first screen \d+/180, block \d+/450$")
        pr = self.pr()
        bare = pr.replace(pr[pr.index("## Where this is"):pr.index("## What changes for people")], "")
        self.assertNotIn("firstScreen", json.loads(self.lint("pr", bare).stdout)["counts"])

    def test_a_pull_request_opens_with_where_and_words(self) -> None:
        pr = self.pr()
        first = pr[pr.index("## Where this is"):pr.index("## What changes for people")]
        # A block with no first screen, as text from before it, is one warning and passes.
        done = self.lint("pr", pr.replace(first, ""))
        found = json.loads(done.stdout)["findings"]
        self.assertEqual([(f["rule"], f["severity"]) for f in found], [("NO_INTRO", "warn")])
        self.assertEqual(done.returncode, 0, done.stdout)
        # A first screen that is there must be whole.
        where = pr[pr.index("## Where this is"):pr.index("## Words")]
        self.assertIn("MISSING_SECTION", self.rules("pr", pr.replace(where, "")))
        long_area = "- **Reports**: " + "the reports a client reads. " * 40 + "\n"
        found = self.rules("pr", pr.replace("- **Reports**: the reports a client reads and downloads.\n", long_area))
        self.assertIn("TOO_LONG", found)
        # The first screen has its own budget: the block's budget does not count it.
        short = pr.replace("- **Export**: download a report as a file.\n",
                           "- **Export**: " + "a download of a report. " * 40 + "\n")
        done = self.lint("pr", short)
        msgs = [f["message"] for f in json.loads(done.stdout)["findings"] if f["rule"] == "TOO_LONG"]
        self.assertTrue(msgs and all("first screen" in m for m in msgs), msgs)

    def test_a_pull_request_names_the_features_of_the_rows_it_moved(self) -> None:
        changed = json.loads((FIX / "changed.json").read_text(encoding="utf-8"))
        for r in changed["rows"]:
            r.setdefault("feature", "reports" if r["id"] in ("C-2", "C-3") else None)
        path = Path(tempfile.mkdtemp()) / "changed.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        pr = self.pr().replace("- **Reports**: the reports a client reads and downloads.\n",
                               "- **Billing**: what a client pays.\n")
        done = self.lint("pr", pr, "--changed", str(path))
        self.assertIn("AREA_MISSING", [f["rule"] for f in json.loads(done.stdout)["findings"]])
        self.assertNotIn("AREA_MISSING", self.rules("pr", self.pr(), "--changed", str(path)))


class ModeInference(unittest.TestCase):
    def mode(self, text: str) -> tuple:
        mode, _signals, _warnings, ambiguous = orient.suggest_mode(text, [], None)
        return mode, ambiguous

    def test_issue_phrases(self) -> None:
        for text in ("file an issue for the export bug", "check issue #96 against the map",
                     "triage these issues", "Review the current platform issues against the promises",
                     "which capabilities does this issue touch", "update the issues to think about the promises"):
            with self.subTest(text=text):
                self.assertEqual(self.mode(text), ("issue", False))

    def test_pr_phrases(self) -> None:
        for text in ("write the PR description for #12", "describe this PR", "PR body for #34",
                     "draft the pull request text"):
            with self.subTest(text=text):
                self.assertEqual(self.mode(text)[0], "pr")

    def test_other_modes_are_not_taken(self) -> None:
        self.assertEqual(self.mode("review the billing doc")[0], "review")
        self.assertEqual(self.mode("we shipped PR #12, update the map")[0], "reconcile")
        self.assertEqual(self.mode("add an issue tracker to the portal")[0], "new")
        self.assertEqual(self.mode("design a way for clients to issue refunds")[0], "new")
        self.assertEqual(self.mode("check the doc for issues")[0], "review")
        self.assertEqual(self.mode("write the red tests")[0], "new")

    def test_first_word_names_the_mode_only_before_a_pointer(self) -> None:
        for text, want in (("issue 12", "issue"), ("issue #96", "issue"), ("pr", "pr"),
                           ("pr for #34", "pr"), ("PR #12 merged, update the map", "reconcile"),
                           ("PR 34 landed; the export row should be proven now", "reconcile"),
                           ("Issue #12 is fixed by PR #13, update the map", "reconcile"),
                           ("PR feedback: the login page is broken", "intake"),
                           ("issue refunds to customers who were double charged", "new")):
            with self.subTest(text=text):
                self.assertEqual(self.mode(text)[0], want)

    def test_pr_phrases_that_ask_for_code_are_not_pr_text(self) -> None:
        for text, want in (("write a PR to fix the export", "new"), ("draft a PR that adds CSV export", "new"),
                           ("write up the PR feedback as scenarios", "intake"),
                           ("summarise this PR", "pr"), ("write the description for pull request #34", "pr"),
                           ("review the PR description", "pr")):
            with self.subTest(text=text):
                self.assertEqual(self.mode(text)[0], want)

    def test_more_issue_phrases(self) -> None:
        for text in ("map issue #12 to rows", "check the capabilities for issue #12",
                     "open a GitHub issue for the flaky export"):
            with self.subTest(text=text):
                self.assertEqual(self.mode(text), ("issue", False))
        self.assertEqual(self.mode("there are open issues in the export")[0], "new")
        self.assertEqual(self.mode("add a create issue button to the portal")[0], "new")

    def test_a_product_feature_is_not_issue_text(self) -> None:
        self.assertEqual(self.mode("build a feature that lets users file issues from the app"), ("new", True))

    def test_a_named_doc_beside_a_weak_phrase_is_ambiguous(self) -> None:
        docs = [{"path": "docs/promises/billing.md", "title": "Billing export", "status": "agreed", "slug": "billing"}]
        for text in ("check the issue in the billing doc", "review issues in the billing doc",
                     "the pr description is wrong in the billing doc"):
            with self.subTest(text=text):
                self.assertTrue(orient.suggest_mode(text, docs, None)[3])
        for text in ("file an issue for the billing export bug", "check issue #12 against the billing map"):
            with self.subTest(text=text):
                mode, _s, _w, ambiguous = orient.suggest_mode(text, docs, None)
                self.assertEqual((mode, ambiguous), ("issue", False))

    def test_issue_and_pr_together_are_ambiguous(self) -> None:
        mode, ambiguous = self.mode("write the issue and the PR description")
        self.assertIn(mode, ("issue", "pr"))
        self.assertTrue(ambiguous)


if __name__ == "__main__":
    unittest.main()
