"""Tests for changed_rows.py beyond the two-commit repo in test_github_text.py:
renames, bare file names, where the docs and the map live, a project in a
subfolder, what diff_row reports, the map's leftOut list, the Markdown cap,
and the docs that name a row with no doc of its own.

Run from the repo root:

    python3 -m unittest discover -s tests -v

Each test builds a small git repository: a base commit on main, and a head
commit on feat.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_github_text import CHANGED, DOC, SCRIPTS_DIR, git, row, run  # noqa: E402

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
import changed_rows  # noqa: E402

MORE = "and {n} more; run changed_rows.py --json for the full list"


def config(**changes) -> str:
    value = {
        "version": 1, "docsHome": "docs/designs",
        "map": {"file": "docs/map/map.json", "lanes": {"data": "tests[]"}, "rowIdPattern": "^C-\\d+$",
                "issueTracker": {"kind": "github", "repo": "o/r", "template": ".github/x.md"}},
    }
    for key, v in changes.items():
        if key.startswith("map_"):
            if v is None:
                value["map"].pop(key[4:], None)
            else:
                value["map"][key[4:]] = v
        elif v is None:
            value.pop(key, None)
        else:
            value[key] = v
    return json.dumps(value, indent=1)


def map_text(rows, indent=1) -> str:
    return json.dumps({"version": 1, "rows": rows}, indent=indent) + "\n"


def doc(status: str, rule: str = "- A rule.") -> str:
    return DOC.format(status=status, rule=rule)


class Repo(unittest.TestCase):
    """A base commit on main and a head commit on feat, from two dicts of
    files (text, or None to delete) and optional renames made with git mv."""

    CONFIG = ".claude/promise.config.json"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "repo"
        self.dir.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, files: dict) -> None:
        for path, text in files.items():
            full = self.dir / path
            if text is None:
                full.unlink()
                continue
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(text, encoding="utf-8")

    def build(self, base: dict, head: dict, renames=()) -> None:
        self.write(base)
        git(self.dir, "init", "-q")
        git(self.dir, "add", "-A")
        git(self.dir, "commit", "-qm", "base")
        git(self.dir, "checkout", "-qb", "feat")
        for before, after in renames:
            (self.dir / after).parent.mkdir(parents=True, exist_ok=True)
            git(self.dir, "mv", before, after)
        self.write(head)
        git(self.dir, "add", "-A")
        git(self.dir, "commit", "-qm", "head", "--allow-empty")

    def run_script(self, *extra: str, cwd: Path = None):
        return run(CHANGED, "--base", "main", "--head", "feat", *extra, cwd=str(cwd or self.dir))

    def report(self, *extra: str, cwd: Path = None) -> dict:
        done = self.run_script("--json", *extra, cwd=cwd)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def rows(self, *extra: str) -> dict:
        return {r["id"]: r for r in self.report(*extra)["rows"]}


class MarkdownCap(Repo):
    """A large change still fits a pull request body."""

    def test_markdown_caps_each_list_and_json_keeps_every_row(self) -> None:
        long_then = "the response is fine and " * 30
        quiet = [row(f"C-{i}", "quiet", tests=["tests/t.test.ts::x"]) for i in range(1, 61)]
        added = [row(f"C-{i}", long_then) for i in range(100, 220)]
        self.build({self.CONFIG: config(), "docs/map/map.json": map_text(quiet), "tests/t.test.ts": "a\n"},
                   {"docs/map/map.json": map_text(quiet + added), "tests/t.test.ts": "b\n"})
        report = self.report()
        self.assertEqual((report["summary"]["rowsAdded"], report["summary"]["rowsTouched"]), (120, 60))
        self.assertEqual(len(report["rows"]), 180, "the JSON is complete")
        done = self.run_script("--markdown")
        self.assertEqual(done.returncode, 0, done.stderr)
        text = done.stdout
        self.assertLess(len(text), 30000)
        self.assertEqual(len([ln for ln in text.splitlines() if ln.startswith("| [C-")]), 40)
        self.assertEqual(text.count(MORE.format(n=80)), 2, "the table and the scenario lines")
        self.assertIn(MORE.format(n=20), text, "the touched ids")
        touched = next(ln for ln in text.splitlines() if ln.startswith("Touched"))
        self.assertEqual(len(re.findall(r"\[C-\d+\]", touched)), 40)


    def test_markdown_ends_with_a_cut_line_past_its_budget(self) -> None:
        long_path = "docs/designs/" + "x" * 3000 + ".md"
        docs = [{"path": f"{long_path}{i}", "change": "changed", "title": "T", "section0Changed": False,
                 "status": {"before": "draft", "after": "agreed"}} for i in range(40)]
        summary = dict.fromkeys(("files", "rowsAdded", "rowsChanged", "rowsRemoved", "rowsTouched",
                                 "verdictsMoved", "docsChanged", "unhomedFiles"), 0)
        report = {"summary": summary, "map": {}, "rows": [], "docs": docs, "unhomed": []}
        text = changed_rows.format_markdown(report)
        self.assertLessEqual(len(text), changed_rows.MD_BUDGET)
        self.assertTrue(text.endswith(changed_rows.CUT), text[-200:])


class Renames(Repo):
    """A file the change moved counts by its path before the move."""

    def test_a_row_whose_cited_test_moved_away_is_touched(self) -> None:
        self.build({self.CONFIG: config(),
                    "docs/map/map.json": map_text([row("C-1", "downloads", tests=["tests/export.test.ts::downloads"]),
                                                   row("C-2", "quiet")]),
                    "tests/export.test.ts": "test('downloads')\n"},
                   {}, renames=[("tests/export.test.ts", "tests/export_v2.test.ts")])
        report = self.report()
        self.assertEqual([(r["id"], r["change"]) for r in report["rows"]], [("C-1", "touched")])
        c1 = report["rows"][0]
        self.assertEqual(c1["testsChanged"], ["tests/export.test.ts"])
        self.assertEqual(c1["filesMoved"], [{"from": "tests/export.test.ts", "to": "tests/export_v2.test.ts"}])
        self.assertEqual(c1["missingCitations"], ["tests/export.test.ts"])
        self.assertEqual(report["unhomed"], [], "the new path is homed by the row that cites the old one")
        done = self.run_script("--markdown")
        self.assertIn("1 file(s) it cites or names moved", done.stdout)

    def test_missing_citations_name_the_files_the_head_lacks(self) -> None:
        self.build({self.CONFIG: config(),
                    "docs/map/map.json": map_text([row("C-1", "old", tests=["tests/gone.test.ts::x",
                                                                            "tests/here.test.ts::y"])]),
                    "tests/here.test.ts": "y\n"},
                   {"docs/map/map.json": map_text([row("C-1", "new", tests=["tests/gone.test.ts::x",
                                                                            "tests/here.test.ts::y"])])})
        self.assertEqual(self.rows()["C-1"]["missingCitations"], ["tests/gone.test.ts"])


class BareNames(Repo):
    """A file a row names without its folder."""

    def build_named(self, story: str, files: dict, changed: dict) -> None:
        self.build({self.CONFIG: config(), "docs/map/map.json": map_text([row("C-1", "t", story=story)]), **files},
                   changed)

    def test_a_bare_name_with_a_line_names_every_file_of_that_name(self) -> None:
        self.build_named("The handler (handler.ts:12) answers.",
                         {"src/a/handler.ts": "1\n", "src/b/handler.ts": "1\n"}, {"src/a/handler.ts": "2\n"})
        report = self.report()
        self.assertEqual(report["rows"][0]["change"], "touched")
        self.assertEqual(report["rows"][0]["filesNamed"], ["src/a/handler.ts"])
        self.assertEqual(report["unhomed"], [])

    def test_a_bare_name_no_other_file_holds_names_it(self) -> None:
        self.build_named("The cases live in `kinds-cases.ts`.",
                         {"tests/kinds-cases.ts": "1\n"}, {"tests/kinds-cases.ts": "2\n"})
        report = self.report()
        self.assertEqual(report["rows"][0]["filesNamed"], ["tests/kinds-cases.ts"])
        self.assertEqual(report["unhomed"], [])

    def test_a_common_name_without_a_line_names_nothing(self) -> None:
        self.build_named("Its index.ts exports it.",
                         {"src/a/index.ts": "1\n", "src/b/index.ts": "1\n"}, {"src/a/index.ts": "2\n"})
        report = self.report()
        self.assertEqual(report["rows"], [])
        self.assertEqual(report["unhomed"], ["src/a/index.ts"])


class DocsHome(Repo):
    """Where outcome docs and the map are read, and what counts as an outcome doc."""

    MAP = map_text([row("C-1", "t")])

    def docs(self, *extra: str) -> list:
        return [(d["path"], d["change"], d["status"]["before"], d["status"]["after"]) for d in self.report(*extra)["docs"]]

    def test_a_docs_home_with_dot_slash_and_a_trailing_slash(self) -> None:
        self.build({self.CONFIG: config(docsHome="./docs/designs/"), "docs/map/map.json": self.MAP,
                    "docs/designs/export.md": doc("draft")},
                   {"docs/designs/export.md": doc("agreed")})
        self.assertEqual(self.docs(), [("docs/designs/export.md", "changed", "draft", "agreed")])
        self.assertEqual(self.report()["docsHome"], "docs/designs")

    def test_a_doc_one_folder_down_is_read(self) -> None:
        self.build({self.CONFIG: config(), "docs/map/map.json": self.MAP,
                    "docs/designs/billing/refunds.md": doc("draft")},
                   {"docs/designs/billing/refunds.md": doc("agreed")})
        report = self.report()
        self.assertEqual([d["path"] for d in report["docs"]], ["docs/designs/billing/refunds.md"])
        self.assertEqual(report["unhomed"], [])

    def test_a_readme_in_docs_home_is_not_an_outcome_doc(self) -> None:
        self.build({self.CONFIG: config(), "docs/map/map.json": self.MAP},
                   {"docs/designs/README.md": "# Designs\n\nStatus: how we write them.\n"})
        report = self.report()
        self.assertEqual(report["docs"], [])
        self.assertEqual(report["prose"], ["docs/designs/README.md"])

    def test_with_no_docs_home_configured_the_detected_folder_is_read(self) -> None:
        self.build({self.CONFIG: config(docsHome=None), "docs/map/map.json": self.MAP,
                    "docs/designs/export.md": doc("draft")},
                   {"docs/designs/export.md": doc("agreed")})
        report = self.report()
        self.assertEqual(report["docsHome"], "docs/designs")
        self.assertEqual([d["path"] for d in report["docs"]], ["docs/designs/export.md"])

    def test_a_doc_renamed_out_of_docs_home_is_removed(self) -> None:
        self.build({self.CONFIG: config(), "docs/map/map.json": self.MAP, "docs/designs/export.md": doc("agreed")},
                   {}, renames=[("docs/designs/export.md", "archive/export.md")])
        report = self.report()
        self.assertEqual([(d["path"], d["change"]) for d in report["docs"]], [("docs/designs/export.md", "removed")])
        self.assertEqual(report["docs"][0]["renamed"], {"from": "docs/designs/export.md", "to": "archive/export.md"})
        self.assertEqual(report["unhomed"], [])

    def test_a_map_the_config_moved_is_read_at_its_path_at_the_base(self) -> None:
        rows = [row(f"C-{i}", f"then {i}") for i in range(1, 6)]
        self.build({self.CONFIG: config(), "docs/map/map.json": map_text(rows)},
                   {self.CONFIG: config(map_file="docs/capabilities/map.json"), "docs/map/map.json": None,
                    "docs/capabilities/map.json": map_text(rows, indent=None)})
        report = self.report()
        self.assertEqual(report["rows"], [], "the rows did not change, the map moved")
        self.assertEqual(report["map"]["basePath"], "docs/map/map.json")
        self.assertEqual(report["unhomed"], [self.CONFIG])

    def test_a_renamed_map_is_read_at_its_path_before_the_rename(self) -> None:
        rows = [row(f"C-{i}", f"then {i}") for i in range(1, 6)]
        self.build({self.CONFIG: config(map_file=None), "docs/map/map.json": map_text(rows)},
                   {}, renames=[("docs/map/map.json", "docs/capabilities/map.json")])
        report = self.report("--map", "docs/capabilities/map.json")
        self.assertEqual(report["rows"], [])
        self.assertEqual(report["map"]["basePath"], "docs/map/map.json")


class MapText(Repo):
    """The map's own text: one that does not parse, a minified one, a ./ path."""

    def test_a_base_map_that_does_not_parse_is_a_warning(self) -> None:
        self.build({self.CONFIG: config(), "docs/map/map.json": "{ not json"},
                   {"docs/map/map.json": map_text([row("C-1", "t")])})
        report = self.report()
        self.assertEqual([(r["id"], r["change"]) for r in report["rows"]], [("C-1", "added")])
        self.assertTrue(any("does not parse" in w for w in report["warnings"]), report["warnings"])

    def test_a_head_map_that_does_not_parse_is_a_usage_error(self) -> None:
        self.build({self.CONFIG: config(), "docs/map/map.json": map_text([row("C-1", "t")])},
                   {"docs/map/map.json": "{ not json"})
        done = self.run_script("--json")
        self.assertEqual(done.returncode, 2)
        self.assertIn("does not parse", done.stderr)

    def test_a_minified_map_links_every_row(self) -> None:
        rows = [row("C-1", "a", tests=["tests/a.test.ts::a"]), row("C-2", "b", tests=["tests/b.test.ts::b"])]
        self.build({self.CONFIG: config(), "docs/map/map.json": map_text(rows, indent=None),
                    "tests/a.test.ts": "a\n", "tests/b.test.ts": "b\n"},
                   {"tests/a.test.ts": "a2\n", "tests/b.test.ts": "b2\n"})
        links = {r["id"]: r["link"] for r in self.report()["rows"]}
        self.assertEqual(sorted(links), ["C-1", "C-2"])
        for link in links.values():
            self.assertRegex(link, r"/docs/map/map\.json#L1$")
        done = run(CHANGED, "--head", "feat", "--link", "C-2", cwd=str(self.dir))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stdout.strip(), r"^C-2 https://github\.com/o/r/blob/[0-9a-f]{40}/docs/map/map\.json#L1$")

    def test_a_map_file_with_dot_slash_is_not_unhomed(self) -> None:
        self.build({self.CONFIG: config(map_file="./docs/map/map.json"), "docs/map/map.json": map_text([row("C-1", "a")])},
                   {"docs/map/map.json": map_text([row("C-1", "b")])})
        report = self.report()
        self.assertEqual(report["unhomed"], [])
        self.assertEqual(report["map"]["path"], "docs/map/map.json")


class LeftOut(Repo):
    """The map's leftOut list: tests left without a row on purpose."""

    def test_left_out_entries_are_reported_and_home_their_file(self) -> None:
        kept = {"test": "tests/kept.test.ts::kept", "reason": "a guard's own test", "date": "YYYY-MM-DD"}
        gone = {"test": "tests/old.test.ts::old", "reason": "checks a fixture file", "date": "YYYY-MM-DD"}
        new = {"test": "tests/journal.test.ts::names a file", "reason": "proves no product behaviour",
               "date": "YYYY-MM-DD"}
        rows = [row("C-1", "t")]
        self.build({self.CONFIG: config(),
                    "docs/map/map.json": json.dumps({"rows": rows, "leftOut": [kept, gone]}, indent=1)},
                   {"docs/map/map.json": json.dumps({"rows": rows, "leftOut": [kept, new]}, indent=1),
                    "tests/journal.test.ts": "test('names a file')\n", "tests/kept.test.ts": "x\n"})
        report = self.report()
        self.assertEqual(report["leftOut"], {"added": [new], "removed": [gone]})
        self.assertEqual((report["summary"]["leftOutAdded"], report["summary"]["leftOutRemoved"]), (1, 1))
        self.assertEqual(report["unhomed"], [], "a test file only a leftOut entry names has a home")
        text = self.run_script("--markdown").stdout
        self.assertIn("Tests left out of the map on purpose: 1 added, 1 removed.", text)
        self.assertIn("- `tests/journal.test.ts::names a file` (added): proves no product behaviour", text)
        self.assertIn("- `tests/old.test.ts::old` (removed): checks a fixture file", text)


class Prose(Repo):
    """Notes and learnings are listed apart from code no row names."""

    def test_prose_files_are_not_unhomed_code(self) -> None:
        rows = [row("C-1", "t")]
        self.build({self.CONFIG: config(), "docs/map/map.json": map_text(rows)},
                   {"docs/learnings/trap.md": "a trap\n", "src/app.ts": "x\n"})
        report = self.report()
        self.assertEqual(report["unhomed"], ["src/app.ts"])
        self.assertEqual(report["prose"], ["docs/learnings/trap.md"])
        self.assertIn("Prose files no row names", self.run_script("--markdown").stdout)


class GitEdges(Repo):
    """A shallow clone, and a file name outside ASCII."""

    def test_a_shallow_clone_names_the_fetch_that_deepens_it(self) -> None:
        self.build({"a.txt": "1\n"}, {"b.txt": "1\n"})
        git(self.dir, "checkout", "-q", "main")
        (self.dir / "c.txt").write_text("1\n", encoding="utf-8")
        git(self.dir, "add", "-A")
        git(self.dir, "commit", "-qm", "main moves on")
        clone = Path(self.tmp.name) / "clone"
        git(Path(self.tmp.name), "clone", "-q", "--depth", "1", "--no-single-branch",
            self.dir.as_uri(), str(clone))
        done = run(CHANGED, "--base", "origin/main", "--head", "origin/feat", cwd=str(clone))
        self.assertEqual(done.returncode, 2)
        self.assertIn("shallow clone", done.stderr)
        self.assertIn("git fetch --deepen=<n>", done.stderr)

    def test_a_non_ascii_path_reads_as_written(self) -> None:
        self.build({self.CONFIG: config(),
                    "docs/map/map.json": map_text([row("C-1", "t", tests=["tests/café.test.ts::x"])]),
                    "tests/café.test.ts": "a\n"},
                   {"tests/café.test.ts": "b\n"})
        report = self.report()
        self.assertEqual(report["rows"][0]["testsChanged"], ["tests/café.test.ts"])
        self.assertEqual(report["unhomed"], [])


class DiffRow(Repo):
    """What diff_row reports inside one row."""

    def change(self, before: dict, after: dict) -> dict:
        self.build({self.CONFIG: config(), "docs/map/map.json": map_text([before])},
                   {"docs/map/map.json": map_text([after])})
        return self.report()

    def test_parent_aliases_and_origin_are_listed_in_fields(self) -> None:
        before = row("C-1", "t")
        report = self.change(before, dict(before, parent="C-9", aliases=["OLD-1"], origin="backfill"))
        self.assertEqual(report["rows"][0]["change"], "changed")
        self.assertEqual(report["rows"][0]["fields"], ["aliases", "origin", "parent"])

    def test_reordered_surfaces_are_no_change(self) -> None:
        before = dict(row("C-1", "t"), surfaces=["GET /a", "POST /b"])
        report = self.change(before, dict(before, surfaces=["POST /b", "GET /a"]))
        self.assertEqual(report["rows"], [])

    def test_a_scenario_without_an_id_inserted_first_is_the_only_one_added(self) -> None:
        def sc(n: int) -> dict:
            return {"given": f"g{n}", "when": f"w{n}", "then": f"t{n}", "altitude": "response"}
        before = dict(row("C-1", "t"), scenarios=[sc(1), sc(2)])
        after = dict(row("C-1", "t"), scenarios=[sc(0), sc(1), sc(2)])
        scenarios = self.change(before, after)["rows"][0]["scenarios"]
        self.assertEqual([s["then"] for s in scenarios["added"]], ["t0"])
        self.assertEqual((scenarios["removed"], scenarios["changed"]), ([], []))

    def test_repeated_scenario_ids_warn_and_are_each_compared(self) -> None:
        def sc(then: str) -> dict:
            return {"id": "S1", "given": "g", "when": "w", "then": then, "altitude": "response"}
        before = dict(row("C-1", "t"), scenarios=[sc("a"), sc("b")])
        report = self.change(before, dict(before, scenarios=[sc("a"), sc("b2")]))
        changed = report["rows"][0]["scenarios"]["changed"]
        self.assertEqual([(c["id"], c["then"]["before"], c["then"]["after"]) for c in changed], [("S1#2", "b", "b2")])
        self.assertTrue(any("more than one scenario with id S1" in w for w in report["warnings"]), report["warnings"])


class SubfolderProject(Repo):
    """A project below the top of its git work tree."""

    def test_the_config_and_the_paths_are_the_project_folders(self) -> None:
        self.build({"proj/" + self.CONFIG: config(),
                    "proj/docs/map/map.json": map_text([row("C-1", "t", tests=["tests/x.test.ts::x"])]),
                    "proj/tests/x.test.ts": "1\n", "other/y.ts": "1\n"},
                   {"proj/tests/x.test.ts": "2\n", "other/y.ts": "2\n"})
        report = self.report(cwd=self.dir / "proj")
        self.assertEqual([(r["id"], r["change"], r["testsChanged"]) for r in report["rows"]],
                         [("C-1", "touched", ["tests/x.test.ts"])])
        self.assertEqual(report["outsideProject"], ["other/y.ts"])
        self.assertEqual(report["unhomed"], [])
        self.assertRegex(report["rows"][0]["link"], r"/blob/[0-9a-f]{40}/proj/docs/map/map\.json#L\d+$")


class DocsNaming(Repo):
    """A row with no doc of its own: the outcome docs whose text names it."""

    def setUp(self) -> None:
        super().setUp()
        rows = [row("C-1", "one", tests=["tests/t.test.ts::x"]), row("C-12", "twelve", tests=["tests/t.test.ts::x"]),
                row("C-3", "three", doc="docs/designs/b.md", tests=["tests/t.test.ts::x"])]
        self.build({self.CONFIG: config(), "docs/map/map.json": map_text(rows), "tests/t.test.ts": "1\n",
                    "docs/designs/a.md": doc("agreed", "- C-12 and C-3 hold this."),
                    "docs/designs/b.md": doc("agreed", "- Only C-123 and C-3 here."),
                    "docs/designs/README.md": "# Designs\n\nC-12 is an example.\n",
                    "docs/other.md": doc("agreed", "- C-12 again.")},
                   {"tests/t.test.ts": "2\n"})

    def test_link_ends_with_the_docs_that_name_a_row_without_a_doc(self) -> None:
        done = run(CHANGED, "--head", "feat", "--link", "C-12", "--link", "C-1", "--link", "C-3", cwd=str(self.dir))
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertRegex(lines[0], r"^C-12 https://github\.com/o/r/blob/[0-9a-f]{40}/docs/map/map\.json#L\d+ "
                                   r"docs: docs/designs/a\.md$")
        self.assertNotIn("docs:", lines[1], "C-1 is inside C-12 and C-123 only, never a word")
        self.assertNotIn("docs:", lines[2], "C-3 has a doc of its own")

    def test_json_lists_docs_naming_for_a_row_without_a_doc(self) -> None:
        rows = self.rows()
        self.assertEqual(rows["C-12"]["docsNaming"], ["docs/designs/a.md"])
        self.assertEqual(rows["C-1"]["docsNaming"], [])
        self.assertNotIn("docsNaming", rows["C-3"])


ACCEPTANCE = """# Export

Status: agreed

## 0. TLDR

- A rule.

## 1. Problem

Exports fail.

## 5. Mechanism

How it works.

## 6. Acceptance

| id | given | when | then |
|---|---|---|---|
| AT-1 | a report | export | {then} |

## 7. Build phases
"""


class TinyClaim(Repo):
    """A change sized tiny never changes what a row promises and never touches a
    protected category: the diff says whether it did."""

    MAP = map_text([row("C-1", "the export downloads", tests=["tests/export.test.ts::x"])])
    BASE = {Repo.CONFIG: config(protectedPaths=["billing/", "infra/*.tf"]), "docs/map/map.json": MAP,
            "docs/designs/export.md": ACCEPTANCE.format(then="a file"), "src/export.ts": "a\n",
            "tests/export.test.ts": "a\n", "billing/charge.ts": "a\n"}

    def claim(self, head: dict, *extra: str):
        self.build(dict(self.BASE), head)
        return self.run_script("--json", *extra)

    def touches(self, head: dict, *extra: str) -> list:
        done = self.claim(head, *extra)
        size = json.loads(done.stdout)["size"]
        self.assertEqual(done.returncode, 1 if size["touches"] else 0, done.stderr)
        if size["touches"]:
            self.assertIn("sized tiny, but touches", done.stderr)
            self.assertIn("size it again", done.stderr)
        return size["touches"]

    def test_a_tiny_change_that_keeps_every_promise_passes(self) -> None:
        done = self.claim({"src/export.ts": "b\n", "docs/designs/export.md":
                           ACCEPTANCE.format(then="a file").replace("How it works.", "How it works, now faster.")},
                          "--size", "tiny")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["size"], {"claimed": "tiny", "source": "--size", "touches": []})

    def test_a_changed_scenario_fails_a_tiny_claim(self) -> None:
        head = {"docs/map/map.json": map_text([row("C-1", "the export downloads a file",
                                                   tests=["tests/export.test.ts::x"])])}
        self.assertEqual(self.touches(head, "--size", "tiny"), ["C-1's scenarios"])

    def test_a_new_row_fails_a_tiny_claim(self) -> None:
        head = {"docs/map/map.json": map_text([row("C-1", "the export downloads", tests=["tests/export.test.ts::x"]),
                                               row("C-2", "a new promise")])}
        self.assertEqual(self.touches(head, "--size", "tiny"), ["C-2's scenarios (the row is added)"])

    def test_section_0_and_section_6_fail_a_tiny_claim(self) -> None:
        six = {"docs/designs/export.md": ACCEPTANCE.format(then="a named file")}
        self.assertEqual(self.touches(six, "--size", "tiny"), ["docs/designs/export.md §6"])
        report = json.loads(self.run_script("--json").stdout)
        self.assertTrue(report["docs"][0]["section6Changed"])
        self.assertIsNone(report["size"], "no claim, no check")

    def test_section_0_fails_a_tiny_claim(self) -> None:
        zero = {"docs/designs/export.md": ACCEPTANCE.format(then="a file").replace("- A rule.", "- Another rule.")}
        self.assertEqual(self.touches(zero, "--size", "tiny"), ["docs/designs/export.md §0"])

    def test_migrations_schemas_and_protected_paths_fail_a_tiny_claim(self) -> None:
        head = {"db/migrations/0002_add_column.sql": "alter\n", "prisma/schema.prisma": "model\n",
                "billing/charge.ts": "b\n", "infra/main.tf": "x\n", "infra/modules/x.txt": "x\n"}
        self.assertEqual(sorted(self.touches(head, "--size", "tiny")), [
            "billing/charge.ts (protected: billing/)", "db/migrations/0002_add_column.sql (a migration or schema file)",
            "infra/main.tf (protected: infra/*.tf)", "prisma/schema.prisma (a migration or schema file)"])

    def test_a_feature_size_is_read_as_capability(self) -> None:
        body = self.dir.parent / "body.md"
        body.write_text("<!-- promise:pr -->\n## Why\n\nCloses #1.\n\nSize: feature — a new job.\n"
                        "<!-- /promise:pr -->\n", encoding="utf-8")
        self.build(dict(self.BASE), {"src/export.ts": "b\n"})
        for extra in (("--body", str(body)), ("--size", "feature"), ("--size", "capability")):
            done = self.run_script("--json", *extra)
            self.assertEqual((done.returncode, json.loads(done.stdout)["size"]["claimed"]), (0, "capability"), extra)

    def test_the_body_size_line_is_the_claim(self) -> None:
        body = self.dir.parent / "body.md"
        head = {"billing/charge.ts": "b\n"}
        body.write_text("<!-- promise:pr -->\n## Why\n\nCloses #1.\n\nSize: tiny — keeps C-1.\n"
                        "<!-- /promise:pr -->\n", encoding="utf-8")
        done = self.claim(head, "--body", str(body))
        self.assertEqual(done.returncode, 1)
        self.assertEqual(json.loads(done.stdout)["size"]["source"], "--body")
        self.assertIn("billing/charge.ts (protected: billing/)", done.stderr)
        # another size checks nothing; --size wins over the body
        body.write_text(body.read_text(encoding="utf-8").replace("Size: tiny", "Size: risky"), encoding="utf-8")
        done = self.run_script("--json", "--body", str(body))
        self.assertEqual((done.returncode, json.loads(done.stdout)["size"]["claimed"]), (0, "risky"))
        self.assertEqual(self.run_script("--body", str(body), "--size", "tiny").returncode, 1)
        # a body with no Size line: no claim
        body.write_text("Just words.\n", encoding="utf-8")
        done = self.run_script("--json", "--body", str(body))
        self.assertEqual((done.returncode, json.loads(done.stdout)["size"]["claimed"]), (0, None))

    def test_the_protected_list_is_the_merge_base_s(self) -> None:
        # a change sized tiny cannot drop the list that checks it
        head = {Repo.CONFIG: config(), "billing/charge.ts": "b\n"}
        self.assertEqual(self.touches(head, "--size", "tiny"), [
            "billing/charge.ts (protected: billing/)",
            ".claude/promise.config.json protectedPaths (the list of protected paths itself changed)"])

    def test_dropping_a_protected_path_fails_a_tiny_claim(self) -> None:
        head = {Repo.CONFIG: config(protectedPaths=["billing/"])}
        self.assertEqual(self.touches(head, "--size", "tiny"), [
            ".claude/promise.config.json protectedPaths (the list of protected paths itself changed)"])

    def test_moving_the_config_does_not_lose_the_list_that_checks_it(self) -> None:
        # the head's config sits at the other location with no list: the merge base's list still holds
        head = {Repo.CONFIG: None, "promise.config.json": config(), "billing/charge.ts": "b\n"}
        touched = self.touches(head, "--size", "tiny")
        self.assertIn("billing/charge.ts (protected: billing/)", touched)
        self.assertTrue(any("protected paths itself changed" in t for t in touched), touched)

    def test_any_tiny_size_line_is_checked_as_tiny(self) -> None:
        sys.path.insert(0, str(SCRIPTS_DIR))
        import changed_rows  # noqa: PLC0415
        import argparse  # noqa: PLC0415
        body = Path(self.dir) / "body.md"
        body.write_text("<!-- promise:pr -->\n## Why\n\nSize: small — one change.\n\nSize: tiny — keeps C-1.\n"
                        "<!-- /promise:pr -->\n", encoding="utf-8")
        self.assertEqual(changed_rows.size_claim(argparse.Namespace(size=None, body=str(body))), ("tiny", "--body"))

    def test_a_protected_path_with_a_leading_slash_is_from_the_root(self) -> None:
        sys.path.insert(0, str(SCRIPTS_DIR))
        import changed_rows  # noqa: PLC0415
        self.assertEqual(changed_rows._protected_list(["/billing/", "/infra/*.tf"], []), ["billing/", "infra/*.tf"])

    def test_adding_a_protected_path_passes_a_tiny_claim(self) -> None:
        # a wider list only checks more
        wider = {Repo.CONFIG: config(protectedPaths=["billing/", "infra/*.tf", "auth/"])}
        self.assertEqual(self.touches(wider, "--size", "tiny"), [])

    def test_a_schema_that_is_not_a_database_s_passes_and_other_migrations_fail(self) -> None:
        head = {"tests/fixtures/order.schema.json": "{}\n", "src/schema.ts": "x\n",
                "tests/test_schema_validation.py": "x\n",
                "alembic/versions/0001_init.py": "x\n", "db/migrate/20260101_add.rb": "x\n",
                "db/schema.rb": "x\n", "sql/schema_v2.sql": "x\n"}
        self.assertEqual(sorted(self.touches(head, "--size", "tiny")), [
            "alembic/versions/0001_init.py (a migration or schema file)",
            "db/migrate/20260101_add.rb (a migration or schema file)",
            "db/schema.rb (a migration or schema file)",
            "sql/schema_v2.sql (a migration or schema file)"])

    def test_the_human_summary_keeps_its_space(self) -> None:
        self.build(dict(self.BASE), {"src/export.ts": "b\n"})
        done = self.run_script()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("\nsummary: 0 added, 0 changed", done.stdout)

    def test_protected_paths_that_are_not_a_list_warn(self) -> None:
        self.build({**self.BASE, Repo.CONFIG: config(protectedPaths="billing/")}, {"billing/charge.ts": "b\n"})
        done = self.run_script("--json", "--size", "tiny")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("protectedPaths is not a list of path patterns; it is left out",
                      json.loads(done.stdout)["warnings"])



class SharedServicePolicies(Repo):
    def build_policies(self, before, after, before_refs=None, after_refs=None):
        def mapped(policies, refs):
            rows = [dict(row('C-1', 'search'), servicePolicyRefs=refs),
                    dict(row('C-2', 'checkout'), servicePolicyRefs=refs)]
            return json.dumps({'version': 1, 'rows': rows, 'servicePolicies': policies})
        refs = ['shared'] if before_refs is None else before_refs
        self.build({self.CONFIG: config(), 'docs/map/map.json': mapped(before, refs)},
                   {'docs/map/map.json': mapped(after, refs if after_refs is None else after_refs)})

    def test_shared_policy_edit_changes_all_referring_rows_and_rejects_tiny(self):
        self.build_policies([{'id': 'shared', 'ceiling': 10}], [{'id': 'shared', 'ceiling': 60}])
        report = self.report()
        self.assertEqual([(r['id'], r['change'], r['fields']) for r in report['rows']],
                         [('C-1', 'changed', ['servicePolicies.shared']), ('C-2', 'changed', ['servicePolicies.shared'])])
        self.assertEqual(self.run_script('--size', 'tiny').returncode, 1)
        self.assertIn('shared: changed', self.run_script('--markdown').stdout)

    def test_policy_removal_includes_base_references_even_when_head_detaches(self):
        self.build_policies([{'id': 'shared'}], [], after_refs=[])
        self.assertTrue(all('servicePolicies.shared' in r['fields'] for r in self.report()['rows']))
        self.assertEqual(self.run_script('--size', 'tiny').returncode, 1)

    def test_unreferenced_policy_change_still_rejects_tiny(self):
        self.build_policies([{'id': 'shared', 'x': 1}], [{'id': 'shared', 'x': 2}], before_refs=[])
        self.assertEqual(self.report()['rows'], [])
        self.assertEqual(self.run_script('--size', 'tiny').returncode, 1)
        self.assertIn('service policy shared', self.run_script('--size', 'tiny').stdout)

    def test_detaching_existing_policy_alone_is_not_tiny(self):
        self.build_policies([{'id': 'shared'}], [{'id': 'shared'}], after_refs=[])
        self.assertEqual(self.report()['servicePolicies'], [])
        self.assertEqual(self.run_script('--size', 'tiny').returncode, 1)

    def test_adding_policy_and_refs_changes_rows_and_policy_reordering_does_not(self):
        self.build_policies([], [{'id': 'shared'}], before_refs=[], after_refs=['shared'])
        self.assertTrue(all(r['change'] == 'changed' for r in self.report()['rows']))
        self.assertEqual(self.run_script('--size', 'tiny').returncode, 1)

    def test_policy_order_and_json_formatting_do_not_change_promises(self):
        self.build_policies([{'id': 'shared'}, {'id': 'other'}], [{'id': 'other'}, {'id': 'shared'}])
        self.assertEqual(self.report()['servicePolicies'], [])
        self.assertEqual(self.report()['rows'], [])
        self.assertEqual(self.run_script('--size', 'tiny').returncode, 0)

    def test_malformed_base_policies_can_be_repaired_with_a_warning(self):
        for bad in ({'not': 'a list'}, [{'id': 'shared'}, {'id': 'shared'}], [None]):
            with self.subTest(bad=bad):
                with tempfile.TemporaryDirectory() as tmp:
                    old_dir = self.dir
                    self.dir = Path(tmp)
                    self.build_policies(bad, [{'id': 'shared'}])
                    report = self.report()
                    self.assertTrue(any('merge base' in w and 'malformed service policies read as empty' in w for w in report['warnings']))
                    self.assertTrue(all(r['change'] == 'changed' for r in report['rows']))
                    self.dir = old_dir

    def test_malformed_base_refs_can_be_fixed_but_bad_head_refs_are_rejected(self):
        before = {'rows': [dict(row('C-1', 'search'), servicePolicyRefs=None)], 'servicePolicies': [{'id': 'shared'}]}
        after = {'rows': [dict(row('C-1', 'search'), servicePolicyRefs=['shared'])], 'servicePolicies': [{'id': 'shared'}]}
        self.build({self.CONFIG: config(), 'docs/map/map.json': json.dumps(before)}, {'docs/map/map.json': json.dumps(after)})
        report = self.report()
        self.assertTrue(any('base references read as empty' in w for w in report['warnings']))
        self.assertEqual(report['rows'][0]['fields'], ['servicePolicyRefs'])
        bad_head = dict(before, rows=[dict(row('C-1', 'search'), servicePolicyRefs='new bad refs')])
        self.write({'docs/map/map.json': json.dumps(bad_head)})
        git(self.dir, 'add', '-A')
        git(self.dir, 'commit', '-qm', 'bad head')
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIn('at head', result.stderr)

    def test_bad_head_policies_remain_strict(self):
        self.build_policies([{'id': 'shared'}], [{'id': 'shared'}, {'id': 'shared'}])
        self.assertEqual(self.run_script().returncode, 2)

    def test_unchanged_inherited_malformed_policies_and_refs_only_warn(self):
        rows = [dict(row('C-1', 'search'), servicePolicyRefs=None)]
        malformed = {'rows': rows, 'servicePolicies': [{'id': 'shared'}, {'id': 'shared'}]}
        self.build({self.CONFIG: config(), 'docs/map/map.json': json.dumps(malformed), 'src/other.txt': 'old'},
                   {'src/other.txt': 'new'})
        report = self.report()
        self.assertEqual(report['rows'], [])
        self.assertGreaterEqual(len(report['warnings']), 2)

    def test_new_bad_entry_is_rejected_even_when_other_bad_entries_are_inherited(self):
        self.build_policies([{'id': 'shared'}, {'id': 'shared'}], [{'id': 'shared'}, {'id': 'shared'}, None])
        self.assertEqual(self.run_script().returncode, 2)

    def test_disabling_base_configured_map_cannot_hide_policy_changes_as_tiny(self):
        self.build_policies([{'id': 'shared', 'ceiling': 10}], [{'id': 'shared', 'ceiling': 60}])
        self.write({self.CONFIG: config(map=False)})
        git(self.dir, 'add', '-A')
        git(self.dir, 'commit', '-qm', 'disable map')
        result = self.run_script('--size', 'tiny')
        self.assertEqual(result.returncode, 1)
        self.assertIn('map configured at merge base', result.stderr)

    def test_deleting_standard_config_does_not_bypass_tiny_map_check(self):
        self.build_policies([{'id': 'shared', 'ceiling': 10}], [{'id': 'shared', 'ceiling': 60}])
        self.write({self.CONFIG: None})
        git(self.dir, 'add', '-A')
        git(self.dir, 'commit', '-qm', 'remove config')
        self.assertEqual(self.run_script('--size', 'tiny').returncode, 1)

    def test_policy_only_changes_skip_repeated_docs_search(self):
        self.build_policies([{'id': 'shared', 'ceiling': 10}], [{'id': 'shared', 'ceiling': 60}])
        import argparse
        from unittest.mock import patch
        args = argparse.Namespace(cwd=str(self.dir), config=None, map=None, docs_home=None,
                                  base='main', head='feat', repo_url=None, size=None, body=None)
        with patch.object(changed_rows.DocsNaming, 'naming', side_effect=AssertionError('unnecessary docs scan')):
            report = changed_rows.build_report(args)
        self.assertTrue(all(r['docsNamingSkipped'] == 'only shared service policy changed' for r in report['rows']))


if __name__ == "__main__":
    unittest.main()
