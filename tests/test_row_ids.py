"""A row id never stands alone: lint_github_text.py flags a range of row ids (ID_RANGE)
and an id with no meaning beside it (ID_BARE), in issue and pull request blocks, and in
any Markdown file in the repo with --kind doc."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "promise"
SCRIPTS = SKILL / "scripts"
LINT = SCRIPTS / "lint_github_text.py"
FIX = HERE / "fixtures" / "github"
sys.path.insert(0, str(SCRIPTS))

import lint_github_text  # noqa: E402

ROW_RE = lint_github_text.row_pattern(None)


def ids(text: str, known=None, titles=None) -> list:
    return [(f["rule"], f["line"]) for f in lint_github_text.id_rules(text.split("\n"), 0, ROW_RE, known, titles)]


def run(kind: str, body: str, *extra: str) -> tuple:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(body)
    done = subprocess.run([sys.executable, str(LINT), "--kind", kind, fh.name, "--json", *extra],
                          capture_output=True, text=True)
    Path(fh.name).unlink()
    assert done.returncode in (0, 1), done.stderr
    return done.returncode, json.loads(done.stdout)["findings"]


GAP_DOC = """# Gap analysis

The suite covers CAP-430 to CAP-434, CAP-506.
Mail is CAP-446 to CAP-449; the calendar is CAP-609–CAP-611.
Drafts are CAP-563, CAP-564.
Short form: CAP-12–14.
"""

GAP_DOC_FIXED = """# Gap analysis

- CAP-430, the inbox loads; CAP-431, a thread opens.
- **CAP-506**: a reply keeps its thread.
- A draft is saved as typed (CAP-563).
- CAP-564 — a saved draft opens where it was left.
"""


class Ranges(unittest.TestCase):
    def test_each_range_shape_is_an_error(self):
        found = ids(GAP_DOC)
        self.assertEqual([n for r, n in found if r == "ID_RANGE"], [3, 4, 4, 6])

    def test_hyphen_joined_range(self):
        self.assertEqual(ids("Rows CAP-20-CAP-22 here."), [("ID_RANGE", 1)])

    def test_prose_urls_and_numbers_are_not_ranges(self):
        for line in ("Moved from CAP-3 to CAP-4 in the doc.", "Renamed CAP-3 to CAP-4.",
                     "CAP-5 (proven) to CAP-6 (failing)", "See https://x/CAP-1-CAP-2/file.md for the list.",
                     "See docs/CAP-1-CAP-2.md for the list.", "See [notes](docs/CAP-1-CAP-2.md) here.",
                     "Branch fix/CAP-12-CAP-13 here.", "CAP-12 to 14 people", "CAP-12 through 2027",
                     "CAP-12 ... 3 more", "Version CAP-12–2 x", "CAP-1 S2 to CAP-1 S4", "CAP-9 to CAP-2"):
            self.assertNotIn("ID_RANGE", [r for r, _n in ids(line)], line)

    def test_links_in_other_forms_keep_their_meaning(self):
        for line in ("See [the card](https://x/map.json#CAP-1) here",
                     "[CAP-1](<https://x/a b.md>), the saved card", '[CAP-1](https://x/a.md "title"), the saved card',
                     "[CAP-1][ref], the saved card", "[CAP-1](https://x/a_(b).md), the saved card"):
            self.assertEqual(ids(line), [], line)

    def test_bold_and_linked_ranges_are_still_ranges(self):
        self.assertEqual(ids("**CAP-1** to **CAP-4**"), [("ID_RANGE", 1)])
        self.assertEqual(ids("[CAP-1](https://x/a.md) to [CAP-2](https://x/b.md)"), [("ID_RANGE", 1)])

    def test_a_bad_changed_file_does_not_crash(self):
        self.assertEqual(lint_github_text._known({"CAP-1"}, {"rows": 5}), {"CAP-1"})

    def test_an_id_in_a_range_is_not_also_bare(self):
        self.assertNotIn(("ID_BARE", 1), ids("Rows CAP-1 to CAP-4."))

    def test_doc_gives_errors_and_the_fixed_doc_none(self):
        code, found = run("doc", GAP_DOC, "--no-map")
        self.assertEqual(code, 1)
        self.assertEqual(sum(f["rule"] == "ID_RANGE" for f in found), 4)
        code, found = run("doc", GAP_DOC_FIXED, "--no-map")
        self.assertEqual((code, found), (0, []))


class Bare(unittest.TestCase):
    def test_bare_ids_warn(self):
        self.assertEqual(ids("Drafts are CAP-563, CAP-564.\nCAP-15 alone."),
                         [("ID_BARE", 1), ("ID_BARE", 1), ("ID_BARE", 2)])

    def test_a_meaning_beside_the_id_passes(self):
        for line in ("- **CAP-12**: the saved card is kept.",
                     "- CAP-13 — the export keeps its rows.",
                     "CAP-13 - the export keeps its rows.",
                     "The saved card (CAP-12) still works.",
                     "The saved card — CAP-12.",
                     "[CAP-12](docs/x.md#cap-12) S2 (proven), the saved card.",
                     "DEFECT [CAP-2](https://x/map.json#L20) (proven): a client downloads a file.",
                     "- [CAP-3](https://x/map.json#L40) new: the button says the report is empty.",
                     "### CAP-7 · the weekly report"):
            self.assertEqual(ids(line), [], line)

    def test_exempt_places(self):
        text = ("Closes ABC-99.\n`CAP-16` in code.\n| CAP-17 | the row |\n```\nCAP-18\n```\n"
                "- Touched, verdicts unchanged: CAP-4, CAP-7.")
        self.assertEqual(ids(text), [])
        _code, found = run("doc", "<details>\n\nCAP-19, CAP-20\n\n</details>\n", "--no-map")
        self.assertEqual(found, [])

    def test_the_rows_own_title_words_nearby_pass(self):
        titles = {"CAP-12": "A saved card is charged at checkout"}
        self.assertEqual(ids("CAP-12 charges the saved card.", titles=titles), [])
        self.assertEqual(ids("CAP-12 was moved.", titles=titles), [("ID_BARE", 1)])

    def test_only_rows_in_the_map_are_read_with_a_map(self):
        self.assertEqual(ids("See JIRA-4 now.", known={"CAP-1"}), [])
        self.assertEqual(ids("See CAP-1 now.", known={"CAP-1"}), [("ID_BARE", 1)])

    def test_bare_is_a_warning_range_an_error_in_a_pr_block(self):
        body = (FIX / "pr_good.md").read_text(encoding="utf-8")
        code, found = run("pr", body, "--map", str(FIX / "map.json"))
        self.assertEqual(code, 0)
        self.assertEqual([f for f in found if f["rule"].startswith("ID_")], [])
        broken = body.replace("Closes #12.", "Closes #12. It covers C-1 to C-4.")
        code, found = run("pr", broken, "--map", str(FIX / "map.json"))
        self.assertEqual(code, 1)
        self.assertIn("ID_RANGE", [f["rule"] for f in found])

    def test_the_good_issue_fixture_has_no_id_finding(self):
        body = (FIX / "issue_good.md").read_text(encoding="utf-8")
        _code, found = run("issue", body, "--map", str(FIX / "map.json"))
        self.assertEqual([f for f in found if f["rule"].startswith("ID_")], [])


class Doc(unittest.TestCase):
    def test_doc_checks_unknown_rows_and_verdicts_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Path(tmp) / "map.json"
            m.write_text(json.dumps({"rows": [{"id": "CAP-1", "verdict": "proven"}]}), encoding="utf-8")
            _code, found = run("doc", "- CAP-1 (stale), the inbox.\n- CAP-9, a row since removed.\n", "--map", str(m))
        self.assertEqual(sorted(f["rule"] for f in found), ["ROW_UNKNOWN", "VERDICT_WRONG"])

    def test_doc_has_no_section_rules(self):
        code, found = run("doc", "# Notes\n\nNothing about rows.\n", "--no-map")
        self.assertEqual((code, found), (0, []))

    def test_pr_mode_lints_changed_docs(self):
        text = (SKILL / "modes" / "pr.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"--kind doc")
        self.assertIn("--kind doc", (SKILL / "references" / "github-text.md").read_text(encoding="utf-8"))
        self.assertTrue(re.search(r"``ID_BARE``", LINT.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
