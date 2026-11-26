"""Tests for junit_unittest.py and orient's unittest detection.

A project whose tests are plain unittest gets a JUnit run the map can join:
each case records its file, class and method, a module that fails to import
is one failing case, and map_report.py matches a citation by method or by
Class::method.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "promise" / "scripts"
JUNIT = SCRIPTS / "junit_unittest.py"
ORIENT = SCRIPTS / "orient.py"
MAP_REPORT = SCRIPTS / "map_report.py"

SUITE = '''import unittest
import notes


class TestNotes(unittest.TestCase):
    def test_save(self):
        self.assertEqual(notes.save(1), 1)

    def test_fails(self):
        self.assertEqual(notes.save(1), 2)

    @unittest.skip("later")
    def test_later(self):
        pass

    def test_sub(self):
        for i in range(2):
            with self.subTest(i=i):
                self.assertEqual(i, 0)
'''


def run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, cwd=str(cwd))


class JunitUnittest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "tests").mkdir()
        (self.root / "notes.py").write_text("def save(x):\n    return x\n", encoding="utf-8")
        (self.root / "tests" / "test_notes.py").write_text(SUITE, encoding="utf-8")
        (self.root / "tests" / "test_broken.py").write_text("import nosuchmodule\n", encoding="utf-8")

    def cases(self):
        root = ET.parse(self.root / "out" / "unit.xml").getroot()
        return {c.get("name"): c for c in root.iter("testcase")}

    def test_each_case_records_file_class_and_outcome(self) -> None:
        proc = run(JUNIT, "--out", "out/unit.xml", "-s", "tests", cwd=self.root)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        cases = self.cases()
        self.assertEqual(set(cases), {"test_save", "test_fails", "test_later", "test_sub", "import"})
        save = cases["test_save"]
        self.assertEqual((save.get("file"), save.get("classname")), ("tests/test_notes.py", "TestNotes"))
        self.assertEqual(list(save), [])
        self.assertEqual([c.tag for c in cases["test_fails"]], ["failure"])
        self.assertEqual([c.tag for c in cases["test_later"]], ["skipped"])
        self.assertEqual([c.tag for c in cases["test_sub"]], ["failure"])
        broken = cases["import"]
        self.assertEqual((broken.get("file"), [c.tag for c in broken]), ("tests/test_broken.py", ["error"]))

    def test_an_import_failure_keeps_its_file_under_a_top_level_dir(self) -> None:
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        run(JUNIT, "--out", "out/unit.xml", "-s", "tests", "-t", ".", cwd=self.root)
        self.assertEqual(self.cases()["import"].get("file"), "tests/test_broken.py")

    def test_a_failed_class_fixture_names_its_class_and_file(self) -> None:
        (self.root / "tests" / "test_broken.py").unlink()
        (self.root / "tests" / "test_cls.py").write_text(
            "import unittest\n\nclass A(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls):\n"
            "        raise RuntimeError('no db')\n\n    def test_x(self):\n        pass\n", encoding="utf-8")
        proc = run(JUNIT, "--out", "out/unit.xml", "-s", "tests", cwd=self.root)
        self.assertEqual(proc.returncode, 1)
        case = self.cases()["setUpClass"]
        self.assertEqual((case.get("classname"), case.get("file"), [c.tag for c in case]),
                         ("A", "tests/test_cls.py", ["error"]))

    def test_a_green_suite_exits_0(self) -> None:
        (self.root / "tests" / "test_broken.py").unlink()
        (self.root / "tests" / "test_notes.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n", encoding="utf-8")
        self.assertEqual(run(JUNIT, "--out", "out/unit.xml", "-s", "tests", cwd=self.root).returncode, 0)

    def test_map_report_joins_the_run(self) -> None:
        run(JUNIT, "--out", "out/unit.xml", "-s", "tests", cwd=self.root)
        row = {"id": "CAP-1", "story": "s", "doc": None,
               "scenarios": [{"id": "CAP-1.1", "at": None, "given": "g", "when": "w", "then": "t", "altitude": "data"}],
               "tests": ["tests/test_notes.py::test_save", "tests/test_notes.py::TestNotes::test_fails"],
               "e2eTests": [], "evalTests": [], "siblingTests": [], "verdict": "not-built"}
        (self.root / "map.json").write_text(json.dumps({"version": 1, "rows": [row]}), encoding="utf-8")
        proc = run(MAP_REPORT, "--map", "map.json", "--junit", "out/unit.xml", "--json", cwd=self.root)
        report = json.loads(proc.stdout)
        statuses = {(c["file"], c["name"]): (c["status"], c["matches"]) for c in report["rows"][0]["citations"]}
        self.assertEqual(statuses, {("tests/test_notes.py", "test_save"): ("passing", 1),
                                    ("tests/test_notes.py", "TestNotes::test_fails"): ("failing", 1)})

    def test_usage_errors_exit_2(self) -> None:
        self.assertEqual(run(JUNIT, "--out", "x.xml", "-s", "nowhere", cwd=self.root).returncode, 2)
        self.assertEqual(run(JUNIT, cwd=self.root).returncode, 2)


class OrientFindsUnittest(unittest.TestCase):
    def runners(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in files.items():
                (Path(tmp) / name).parent.mkdir(parents=True, exist_ok=True)
                (Path(tmp) / name).write_text(text, encoding="utf-8")
            return json.loads(run(ORIENT, cwd=Path(tmp)).stdout)["testRunners"]

    def test_a_unittest_suite_is_found_with_its_junit_route(self) -> None:
        runners = self.runners({"tests/test_notes.py": "import unittest\n"})
        self.assertEqual([(r["runner"], r["where"]) for r in runners], [("unittest", "tests/")])
        self.assertIn("junit_unittest.py", runners[0]["junit"])

    def test_pytest_wins_over_unittest_and_plain_files_are_not_suites(self) -> None:
        runners = self.runners({"tests/test_notes.py": "import unittest\n", "pytest.ini": "[pytest]\n"})
        self.assertEqual([r["runner"] for r in runners], ["pytest"])
        self.assertEqual(self.runners({"tests/test_notes.py": "def test_x():\n    pass\n"}), [])


if __name__ == "__main__":
    unittest.main()
