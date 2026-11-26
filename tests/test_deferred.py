"""A change built first, under pressure, is deferred (references/sizing.md § Deferred):
the lint takes `Size: deferred — owes: …` with only Why and Proof, orient hints it from
the person's words, and deferred.py lists what is still owed until a `Paid:` line."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "promise"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import deferred  # noqa: E402
import orient  # noqa: E402

BLOCK = """Fixed under pressure.

<!-- promise:pr -->
## Why

Closes #40. Checkout failed for cards saved before the migration.

Size: deferred — owes: a scenario on CAP-12 for a card saved before the migration, and its test.
{paid}
## Proof

- `npm test`: 212 passed.
<!-- /promise:pr -->
"""


def lint(body: str) -> dict:
    done = subprocess.run([sys.executable, str(SCRIPTS / "lint_github_text.py"), "--kind", "pr", "-", "--no-map",
                           "--json"], input=body, capture_output=True, text=True)
    assert done.returncode in (0, 1), done.stderr
    return json.loads(done.stdout)


class Lint(unittest.TestCase):
    def test_a_deferred_block_needs_only_why_and_proof(self) -> None:
        data = lint(BLOCK.format(paid=""))
        self.assertEqual(data["stats"]["errors"], 0, data["findings"])
        self.assertTrue(any(f["rule"] == "MISSING_SECTION" and f["severity"] == "warn" for f in data["findings"]))

    def test_a_deferred_size_says_what_it_owes(self) -> None:
        body = BLOCK.format(paid="").replace(" — owes: a scenario on CAP-12 for a card saved before the migration, and its test", "")
        errors = [f for f in lint(body)["findings"] if f["severity"] == "error"]
        self.assertEqual([f["rule"] for f in errors], ["SIZE"])
        self.assertIn("owes:", errors[0]["message"])

    def test_without_deferred_the_sections_are_still_required(self) -> None:
        body = BLOCK.format(paid="").replace("Size: deferred — owes:", "Size: small —")
        rules = {f["rule"] for f in lint(body)["findings"] if f["severity"] == "error"}
        self.assertIn("MISSING_SECTION", rules)


class Hint(unittest.TestCase):
    def test_the_persons_words_say_deferred_and_a_protected_category_is_still_named(self) -> None:
        for text in ("ship it first, promise it later", "hotfix the redirect", "spike a ranking idea",
                     "yolo it, backfill later", "no time for the paperwork, just fix it",
                     "just ship it, deal with it later", "quick and dirty fix for the export",
                     "no time, just get it working"):
            with self.subTest(text=text):
                self.assertEqual(orient.suggest_size(text)[0], "deferred")
        size, signals = orient.suggest_size("hotfix the refunds page")
        self.assertEqual(size, "deferred")
        self.assertTrue(any("every decision in it is still asked" in s for s in signals))

    def test_ordinary_asks_are_not_deferred(self) -> None:
        for text in ("fix the typo on the about page", "write tests first for the parser", "get the build green",
                     "release notes page", "add a spike chart to the dashboard", "fix the hotfix docs link",
                     "fix it first then refactor", "build the feature first", "ship the release first",
                     "get the tests first", "add tests later in the pipeline view", "fix the map later",
                     "write the doc without the map legend", "skip the doc comments"):
            with self.subTest(text=text):
                self.assertNotEqual(orient.suggest_size(text)[0], "deferred")


class LintOwes(unittest.TestCase):
    def test_owes_in_a_comment_is_not_seen_and_owes_in_bold_is(self) -> None:
        hidden = BLOCK.format(paid="").replace("— owes: a scenario on CAP-12", "<!-- owes: a scenario on CAP-12 -->")
        self.assertIn("SIZE", {f["rule"] for f in lint(hidden)["findings"] if f["severity"] == "error"})
        bold = BLOCK.format(paid="").replace("Size: deferred — owes:", "**Size:** deferred — **owes**:")
        self.assertEqual(lint(bold)["stats"]["errors"], 0, lint(bold)["findings"])


class Owed(unittest.TestCase):
    def run_list(self, prs: list) -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(prs, fh)
        done = subprocess.run([sys.executable, str(SCRIPTS / "deferred.py"), "--input", fh.name, "--json"],
                              capture_output=True, text=True)
        Path(fh.name).unlink()
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_an_unpaid_deferred_pr_is_listed_with_what_it_owes_oldest_first(self) -> None:
        prs = [{"number": 9, "title": "later", "mergedAt": "2026-09-02", "body": BLOCK.format(paid="")},
               {"number": 7, "title": "first", "mergedAt": "2026-09-01", "body": BLOCK.format(paid="")},
               {"number": 8, "title": "not deferred", "mergedAt": "2026-09-01",
                "body": BLOCK.format(paid="").replace("deferred", "small")}]
        data = self.run_list(prs)
        self.assertEqual([d["number"] for d in data["owed"]], [7, 9])
        self.assertTrue(data["owed"][0]["owes"].startswith("a scenario on CAP-12"))

    def test_a_paid_line_closes_it_and_paid_in_part_does_not(self) -> None:
        prs = [{"number": 7, "mergedAt": "1", "body": BLOCK.format(paid="\nPaid: #31, CAP-12 S4\n")},
               {"number": 8, "mergedAt": "2", "body": BLOCK.format(paid="\nPaid in part: #31, the scenario\n")}]
        owed = self.run_list(prs)["owed"]
        self.assertEqual([d["number"] for d in owed], [8])
        self.assertIn("(paid in part: #31, the scenario)", owed[0]["owes"])
        self.assertIsNone(deferred.owed(BLOCK.format(paid="\n**Paid:** #31\n")))

    def test_a_pr_with_no_merge_date_sorts_last(self) -> None:
        prs = [{"number": 1, "body": BLOCK.format(paid="")},
               {"number": 2, "mergedAt": "2026-09-01", "body": BLOCK.format(paid="")}]
        self.assertEqual([d["number"] for d in self.run_list(prs)["owed"]], [2, 1])

    def test_record_takes_deferred(self) -> None:
        done = subprocess.run([sys.executable, str(SCRIPTS / "session_report.py"), "--record", "--size", "deferred",
                               "--reason", "hotfix; owes a CAP-12 scenario"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class Docs(unittest.TestCase):
    def test_the_router_sizing_and_reconcile_carry_it(self) -> None:
        flat = lambda p: " ".join(p.read_text(encoding="utf-8").split())
        self.assertIn("| **deferred** |", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("## Deferred", (SKILL / "references" / "sizing.md").read_text(encoding="utf-8"))
        self.assertIn("scripts/deferred.py", flat(SKILL / "modes" / "reconcile.md"))
        self.assertIn("never the decisions that are hard to undo", flat(SKILL / "references" / "sizing.md"))


if __name__ == "__main__":
    unittest.main()
