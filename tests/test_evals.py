"""The behaviour evals in evals/ (run with `claude plugin eval`, evals/README.md) keep
their shape: each case asks through /promise, is tagged train or test, builds its
fixture, and grades both the result and the steps. The evals themselves call a model
and are not run here; the fixture script is, since every case depends on it."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"
SCRIPTS = REPO / "skills" / "promise" / "scripts"


def cases():
    return sorted(p.parent for p in EVALS.glob("*/prompt.md"))


def frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


class Shape(unittest.TestCase):
    def test_there_are_cases_on_both_sides_of_the_split(self) -> None:
        tags = []
        for c in cases():
            m = re.search(r"(?m)^tags: \[(.*)\]$", frontmatter(c / "prompt.md"))
            self.assertIsNotNone(m, c.name)
            tags.append({t.strip() for t in m.group(1).split(",")})
        self.assertGreaterEqual(len(tags), 8)
        self.assertTrue(all(len(t & {"train", "test"}) == 1 for t in tags), "each case is train or test, not both")
        train = sum("train" in t for t in tags)
        self.assertLessEqual(abs(train - (len(tags) - train)), 2)

    def test_every_case_asks_through_promise_and_builds_its_fixture(self) -> None:
        for case in cases():
            with self.subTest(case=case.name):
                body = (case / "prompt.md").read_text(encoding="utf-8").split("\n---\n", 1)[1]
                self.assertTrue(body.strip().startswith("/promise "), body[:60])
                self.assertIn("scaffold_script: fixture.sh", (case / "case.yaml").read_text(encoding="utf-8"))
                self.assertIn("_fixture/make-project.sh", (case / "fixture.sh").read_text(encoding="utf-8"))
                self.assertTrue((case / "fixture.sh").stat().st_mode & 0o111, "fixture.sh is executable")

    def test_every_case_grades_the_result_and_shows_the_skill_ran(self) -> None:
        for case in cases():
            with self.subTest(case=case.name):
                graders = {g.stem: frontmatter(g) for g in (case / "graders").glob("*.md")}
                self.assertIn("skill-fired", graders)
                self.assertIn("arm: with-only", graders["skill-fired"])
                self.assertGreaterEqual(len(graders), 3, "one grader on the result and one on the steps, at least")
                for name, fm in graders.items():
                    self.assertRegex(fm, r"(?m)^type: (regex|tool_used|tool_order|file_exists|llm|baseline)$", name)

    def test_the_skill_fired_pattern_names_the_skills_folder(self) -> None:
        # the trace keeps no copy of the skill's text, only the paths the run touched
        for case in cases():
            with self.subTest(case=case.name):
                self.assertIn('pattern: "skills/promise/"\n', (case / "graders" / "skill-fired.md").read_text(encoding="utf-8"))


class GradersFitTheFixture(unittest.TestCase):
    """A grader on a fixture file passes on the file as built only when it should."""

    def test_untouched_graders_pass_on_the_fixture_and_the_helper_grader_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["bash", str(EVALS / "_fixture" / "make-project.sh")], cwd=root, check=True,
                           capture_output=True)
            for case, grader, path, want in (("trap-tax", "checkout-untouched", "app/checkout.py", True),
                                             ("trap-rename-column", "schema-untouched", "db/schema.sql", True),
                                             ("tiny-refactor", "helper-added", "app/checkout.py", False)):
                with self.subTest(grader=grader):
                    fm = frontmatter(EVALS / case / "graders" / f"{grader}.md")
                    pattern = re.search(r"(?m)^pattern: (['\"])(.*)\1$", fm).group(2).replace("\\\\", "\\")
                    flags = re.M if re.search(r"(?m)^flags: m$", fm) else 0
                    text = (root / path).read_text(encoding="utf-8")
                    self.assertEqual(bool(re.search(pattern, text, flags)), want, pattern)


class Fixture(unittest.TestCase):
    def build(self, *args: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        proc = subprocess.run(["bash", str(EVALS / "_fixture" / "make-project.sh"), *args], cwd=root,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return root

    def orient(self, root: Path) -> dict:
        return json.loads(subprocess.run([sys.executable, str(SCRIPTS / "orient.py"), "--cwd", str(root)],
                                         capture_output=True, text=True).stdout)

    def test_the_plain_project_is_adopted_with_the_repo_policy_and_its_tests_pass(self) -> None:
        root = self.build()
        data = self.orient(root)
        self.assertTrue(data["adopted"])
        self.assertEqual((data["decisionPolicy"], data["docsHome"]), ("auto", "docs/designs"))
        self.assertFalse(data["mapUsable"])
        run = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=root,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("No channels yet.", (root / "app" / "settings.html").read_text(encoding="utf-8"))

    def test_the_map_project_has_one_row_and_its_agreed_doc(self) -> None:
        root = self.build("--map")
        self.assertTrue(self.orient(root)["mapUsable"])
        rows = json.loads((root / "docs" / "capabilities" / "map.json").read_text(encoding="utf-8"))["rows"]
        self.assertEqual([r["id"] for r in rows], ["CAP-1"])
        check = subprocess.run([sys.executable, "docs/capabilities/capability_find.py", "--check"], cwd=root,
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("Status: agreed", (root / "docs" / "designs" / "channel-muting.md").read_text(encoding="utf-8"))

    def test_service_and_onboarding_case_scaffolds_are_exercised_without_a_model(self):
        for name in ("service-conditions", "service-stale-evidence", "onboard-idea", "onboard-pilot",
                     "prototype-door"):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                built = subprocess.run(["bash", str(EVALS / name / "fixture.sh")], cwd=root,
                                       capture_output=True, text=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                if name == "prototype-door":
                    # the prototype is committed and its tests pass: nothing to turn red
                    self.assertTrue((root / "app" / "pins.py").is_file())
                    status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True)
                    self.assertEqual(status.stdout, "", "the prototype is committed")
                    sys.path.insert(0, str(root / "app"))
                    try:
                        import pins  # noqa: PLC0415
                        pins.pin("general", 1)
                        pins.pin("general", 1)
                        self.assertEqual(pins.pinned("general"), [1])
                    finally:
                        sys.path.remove(str(root / "app"))
                        sys.modules.pop("pins", None)
                if name == "service-stale-evidence":
                    export = root / "service-observations.json"
                    original = export.read_bytes()
                    result = subprocess.run([sys.executable, str(SCRIPTS / "service_report.py"),
                                             "--map", str(root / "docs/capabilities/map.json"),
                                             "--row", "CAP-1", "--observations", str(export), "--json"],
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    data = json.loads(result.stdout)
                    self.assertEqual(data["targets"][0]["status"], "stale")
                    self.assertFalse(data["replay"])
                    self.assertEqual(export.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
