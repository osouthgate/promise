"""The prototype door: a person who built first can start from the prototype.

The phrasings route to `new` (the door's start), never to `deferred` or `backfill`, and
the skill text states the door's rules: the person writes §0, working code is never
stubbed to force a red run, and proof is a watched mutation.
"""
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

PHRASES = [
    "I built a prototype",
    "I built a prototype of channel pinning and want to lock it in",
    "start from my prototype",
    "promise this prototype",
    "lock in what I built",
]


def flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class RoutingGuard(unittest.TestCase):
    """A guard, not proof of a change: orient routed these phrasings to `new`
    before the door was named, too. It keeps them from drifting to
    `deferred` or `backfill` later."""

    def test_phrases_stay_in_new_and_are_not_deferred_or_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for phrase in PHRASES:
                with self.subTest(phrase=phrase):
                    proc = subprocess.run([sys.executable, str(ORIENT), "--cwd", tmp, "--input", phrase],
                                          capture_output=True, text=True, encoding="utf-8")
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    data = json.loads(proc.stdout)
                    self.assertEqual(data["suggestedMode"], "new", data["signals"])
                    self.assertIsNone(data["suggestedSize"], "the prototype door is not the deferred path")

    def test_router_names_every_phrase(self) -> None:
        text = flat(SKILL / "SKILL.md")
        for phrase in ("I built a prototype", "start from my prototype", "promise this prototype",
                       "lock in what I built"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("references/sizing.md` § The prototype door", text)


class DoorRules(unittest.TestCase):
    def test_sizing_states_the_three_rules(self) -> None:
        text = flat(SKILL / "references" / "sizing.md")
        section = text.split("## The prototype door", 1)[1].split("## How big a row is", 1)[0]
        for phrase in ("writes §0 in their own words", "never sets `agreed` or `shipped`", "Protected categories are asked",
                       "watched mutation", "Do not stub working code"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)

    def test_arm_files_prototype_lines_without_a_red_run(self) -> None:
        text = flat(SKILL / "modes" / "arm.md")
        step = text.split("0. **Code that already exists needs no red test.**", 1)[1].split(" 1. **No test command yet**", 1)[0]
        for phrase in ("passes at once", "never stub or break it", "prototype", "watches the kill",
                       "no red gate and no `building`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step)

    def test_reconcile_and_new_and_onboard_point_at_the_door(self) -> None:
        for mode in ("new", "reconcile", "onboard"):
            with self.subTest(mode=mode):
                self.assertIn("The prototype door", flat(SKILL / "modes" / f"{mode}.md"))

    def test_readme_presents_two_doors_and_the_unattended_rule(self) -> None:
        text = flat(REPO / "README.md")
        for phrase in ("## Two front doors", "Start from an idea", "Start from a prototype",
                       "protected category", "watched mutation", "### Run it unattended",
                       "A promise no person made is the agent's guess", "`fast`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertLess(text.index("## Two front doors"), text.index("## The smallest useful path"))


if __name__ == "__main__":
    unittest.main()
