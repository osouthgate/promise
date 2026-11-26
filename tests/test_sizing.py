"""Sizing and batching (SKILL.md § Size the ask first, references/sizing.md): most asks
are small, and the full procedure is for the ones that need it."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "promise"
ORIENT = SKILL / "scripts" / "orient.py"


def flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def orient_on(text: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        ask = Path(tmp) / "ask.txt"
        ask.write_text(text, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(ORIENT), "--cwd", tmp, "--input-file", str(ask)],
                              capture_output=True, text=True)
    return json.loads(proc.stdout)


class SizeHint(unittest.TestCase):
    def test_the_words_of_the_ask_give_a_hint(self) -> None:
        for text, size in (("change the empty-state copy on the settings page", None),  # tiny is the agent's call
                           ("refactor checkout so it charges tax per region", None),
                           ("add a mute toggle to channels", None),
                           ("add refunds to billing", "risky"),
                           ("let admins change member permissions", "risky"),
                           ("fix the typo in the password reset email", "risky"),  # a protected word wins
                           ("make the tooltip show the user's email address", "risky"),
                           ("rename the users.email column", "risky"),
                           ("rename the user_id field in the API response", "risky"),
                           ("reword the terms checkbox label", "risky"),
                           ("bump the stripe sdk to v12", "risky"),
                           ("let admins remove members", "risky"),
                           ("delete a channel", "risky"),
                           ("rename the authorisation middleware", "risky"),
                           ("bump bcrypt to v6", "risky"),
                           ("bump the jsonwebtoken dependency", "risky"),
                           ("rename the /v1/orders route", "risky"),
                           ("show the post author under the title", None),  # words that only look protected
                           ("use a two-column layout on the settings page", None),
                           ("add an aria role to the button", None),
                           ("describe it in terms of days", None),
                           ("let admin roles see the audit page", "risky")):
            with self.subTest(text=text):
                data = orient_on(text)
                self.assertEqual(data["suggestedSize"], size, data["sizeSignals"])
                self.assertEqual(bool(data["sizeSignals"]), size is not None)

    def test_no_input_no_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads(subprocess.run([sys.executable, str(ORIENT), "--cwd", tmp],
                                             capture_output=True, text=True).stdout)
        self.assertIsNone(data["suggestedSize"])
        self.assertEqual(data["decisionPolicy"], "auto")


class TheTextDrivesIt(unittest.TestCase):
    def test_skill_md_sizes_before_the_mode_with_all_four_sizes(self) -> None:
        text = flat(SKILL / "SKILL.md")
        self.assertLess(text.index("## Size the ask first"), text.index("## Modes"))
        for phrase in ("**tiny**", "**small**", "**capability**", "**risky**", "**No doc, no row, no mode, no question but the session's first-command yes**",
                       "release note", "In doubt, take the larger", "**Batch, don't interrupt**",
                       "**Needs you**", "**Decided for you**", "**Not checked**"):
            self.assertIn(phrase, text)

    def test_the_claude_md_block_leads_with_sizing(self) -> None:
        text = flat(SKILL / "templates" / "claude-md-section.md")
        self.assertIn("**Size every ask first**", text)
        self.assertIn("`decisionPolicy`", text)
        self.assertLess(text.index("Size every ask first"), text.index("One doc per capability"))

    def test_the_reference_names_the_four_stops_and_the_closing_message(self) -> None:
        text = flat(SKILL / "references" / "sizing.md")
        for phrase in ("## The one-step test", "## Batch", "`arm`'s red gate before `building`",
                       "deleting files, or committing on the default branch", "**Needs you**",
                       "**Decided for you**", "**Not checked**"):
            self.assertIn(phrase, text)

    def test_modes_stop_less(self) -> None:
        intake = flat(SKILL / "modes" / "intake.md")
        self.assertIn("**stop once, for approval, before Apply**", intake)
        self.assertIn("a non-blocking §9 note", intake)  # a defect no longer turns an agreed doc red
        self.assertIn("The rule decides, not a question", flat(SKILL / "modes" / "reconcile.md"))
        self.assertIn("send research agents first, and say so", flat(SKILL / "references" / "research.md"))
        new = flat(SKILL / "modes" / "new.md")
        self.assertIn("Ask only for the ones missing, all in one turn", new)
        self.assertNotIn("wait for a yes — `render_outcome.py` requires", new)


class RowsAreJobs(unittest.TestCase):
    """A row is one job with its own "so that"; its rules, limits and edges are scenarios."""

    def test_sizing_says_how_big_a_row_is(self) -> None:
        text = flat(SKILL / "references" / "sizing.md")
        for phrase in ("## How big a row is", "one job an actor does, with its own \"so that\"",
                       "**No line**", "a scenario on that row"):
            self.assertIn(phrase, text)

    def test_the_recipes_link_to_the_rule_and_do_not_hold_it(self) -> None:
        for recipe, link in ((SKILL / "templates" / "starter-map" / "recipe.md",
                              "`${CLAUDE_SKILL_DIR}/references/sizing.md` § How big a row is"),
                             (REPO / "examples" / "minimap" / "recipe.md",
                              "`../../skills/promise/references/sizing.md` § How big a row is")):
            with self.subTest(recipe=recipe.name, where=recipe.parent.name):
                text = flat(recipe)
                self.assertIn(link, text)
                self.assertNotIn("**No line**", text)
                self.assertNotIn("**A line naming a new job", text)

    def test_every_pointer_names_sizing_not_the_recipe(self) -> None:
        for path in (SKILL / "modes" / "arm.md", SKILL / "modes" / "intake.md"):
            with self.subTest(path=path.name):
                text = flat(path)
                self.assertIn("`references/sizing.md` § How big a row is", text)
                self.assertNotIn("the recipe's § How big a row is", text)
        for path in (REPO / "examples" / "minimap" / "README.md", REPO / "examples" / "minimap" / "map.json"):
            with self.subTest(path=path.name):
                self.assertNotIn("recipe's § How big a row is", flat(path))
                self.assertNotIn("recipe § How big a row is", flat(path))


class TheSkillDecidesWhether(unittest.TestCase):
    """Whether anything is filed, and at what size, is the skill's; how is the recipe's."""

    def test_skill_md_states_the_precedence(self) -> None:
        text = flat(SKILL / "SKILL.md")
        self.assertIn("The skill decides whether anything is filed and at what size", text)
        self.assertIn("the project's recipe decides how", text)

    def test_sizing_states_the_precedence(self) -> None:
        text = flat(SKILL / "references" / "sizing.md")
        for phrase in ("## The skill decides whether, the recipe decides how",
                       "**This skill decides whether anything is filed and at what size**",
                       "**The project's recipe decides how**", "this file wins",
                       "a recipe with no row-size section needs none"):
            self.assertIn(phrase, text)

    def test_the_references_on_the_recipe_name_the_limit(self) -> None:
        for path in (SKILL / "references" / "architecture.md", SKILL / "references" / "config.md"):
            with self.subTest(path=path.name):
                self.assertIn("is the skill's", flat(path))

    def test_arm_groups_by_the_job_and_intake_extends_by_the_so_that(self) -> None:
        arm = flat(SKILL / "modes" / "arm.md")
        self.assertIn("**by the job they serve**", arm)
        self.assertNotIn("**by the §0 rule each row is tagged from**", arm)
        intake = flat(SKILL / "modes" / "intake.md")
        self.assertIn("does the item serve the row's \"so that\"? Yes → EXTEND", intake)
        self.assertIn("| KEEPS |", intake)
        self.assertIn("First the release-note test", flat(SKILL / "modes" / "new.md"))

    def test_the_example_files_one_job_as_one_row(self) -> None:
        data = json.loads((REPO / "examples" / "minimap" / "map.json").read_text(encoding="utf-8"))
        cap1 = next(r for r in data["rows"] if r["id"] == "CAP-1")
        self.assertEqual([s["at"] for s in cap1["scenarios"]], ["AT-1", "AT-2", "AT-3"])
        self.assertNotIn("CAP-2", {r["id"] for r in data["rows"]})
        self.assertEqual([r["id"] for r in data["retired"]], ["CAP-2"])


class ATinyFixCitesByTheVerdict(unittest.TestCase):
    """A tiny fix starts with a failing test; the row's verdict decides whether the
    citation lands now (a proven row: the proof had a hole) or waits for reconcile."""

    def test_sizing_says_the_verdict_decides_the_citation(self) -> None:
        text = flat(SKILL / "references" / "sizing.md")
        section = text[text.index("## A tiny fix"):text.index("## Batch")]
        for phrase in ("A fix still starts with a failing test for the promise it restores",
                       "**The row is `proven`** → cite the test on the row now",
                       "the proof had a hole", "The closing message says so",
                       "**The row is `under-proven` or `not-built`** → the test declares the row",
                       "the recipe's header declaration, or a comment naming the row",
                       "**Decided for you** as a follow-up for `reconcile`",
                       "the verdict moves only by the recipe's rule", "a bigger row needs more tests, never fewer"):
            self.assertIn(phrase, section)
        self.assertNotIn("restores, cited on that row", text)
        self.assertIn("§ A tiny fix", flat(SKILL / "SKILL.md"))

    def test_the_recipe_and_reconcile_point_at_the_rule(self) -> None:
        recipe = flat(SKILL / "templates" / "starter-map" / "recipe.md")
        self.assertIn("cited in its row's lane now when the row is `proven`, else declared on the row "
                      "and cited by `reconcile`", recipe)
        self.assertIn("A bigger row needs more tests, never fewer", recipe)
        reconcile = flat(SKILL / "modes" / "reconcile.md")
        self.assertIn("a tiny fix on an `under-proven` or `not-built` row leaves exactly that", reconcile)
        self.assertIn("or for a comment naming a row", reconcile)
        self.assertIn("probe 3 is what finds it", reconcile)

    def test_the_row_size_rule_does_not_contradict_the_tiny_fix_rule(self) -> None:
        text = flat(SKILL / "references" / "sizing.md")
        section = text[text.index("## How big a row is"):text.index("## The skill decides whether")]
        self.assertNotIn("cited in its row's lane.", section)
        self.assertIn("cited as § A tiny fix says (on a `proven` row now, else by `reconcile`)", section)
        self.assertNotIn("once for every fix in the pull request", text)


class AdoptWritesThePolicy(unittest.TestCase):
    def test_a_fresh_config_carries_auto(self) -> None:
        sys.path.insert(0, str(SKILL / "scripts"))
        import adopt  # noqa: PLC0415
        self.assertEqual(adopt.build_config("docs/designs", {})["decisionPolicy"], "auto")

    def test_the_chosen_policy_is_written_and_the_default_stays_auto(self) -> None:
        import subprocess  # noqa: PLC0415
        import tempfile  # noqa: PLC0415
        for flag, want in ((None, "auto"), ("fast", "fast"), ("spec", "spec"), ("auto", "auto"), ("prototype", "fast")):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                args = [sys.executable, str(SKILL / "scripts" / "adopt.py"), "--cwd", tmp, "--docs-home", "docs/designs"]
                if flag:
                    args += ["--policy", flag]
                done = subprocess.run(args, capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                config = json.loads((Path(tmp) / ".claude" / "promise.config.json").read_text(encoding="utf-8"))
                self.assertEqual(config["decisionPolicy"], want)

    def test_an_unknown_policy_is_refused_and_an_existing_config_is_kept_and_said(self) -> None:
        import subprocess  # noqa: PLC0415
        import tempfile  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            base = [sys.executable, str(SKILL / "scripts" / "adopt.py"), "--cwd", tmp, "--docs-home", "docs/designs"]
            self.assertEqual(subprocess.run(base + ["--policy", "quick"], capture_output=True, text=True).returncode, 2)
            subprocess.run(base + ["--policy", "spec"], capture_output=True, text=True)
            again = subprocess.run(base + ["--policy", "fast"], capture_output=True, text=True)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn("the existing config is kept, so --policy fast was not applied", again.stderr)
            config = json.loads((Path(tmp) / ".claude" / "promise.config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["decisionPolicy"], "spec")
            quiet = subprocess.run(base, capture_output=True, text=True)
            self.assertNotIn("was not applied", quiet.stderr)

    def test_adopt_asks_the_policy_once_in_plain_words(self) -> None:
        text = " ".join((SKILL / "modes" / "adopt.md").read_text(encoding="utf-8").split())
        for phrase in ("Ask only the risky things", "Ask me everything", "Let me move fast", "never asked again",
                       "Decided for you"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
