"""Tests for a read-only sibling map: ``"map": false`` plus a ``sibling`` object.

Run from the repo root:

    python3 -m unittest discover -s tests -v

A project whose rows live in another repository's map sets ``"map": false``
and names that repository in ``sibling``. orient.py reports the object as
``sibling`` and keeps ``mapUsable`` false (no mode writes to a map it does
not own); adapter.py runs ``sibling.find`` and
``sibling.row`` with the sibling checkout as the working directory, and
refuses every other map operation, so nothing runs or writes there.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"
ORIENT = SCRIPTS_DIR / "orient.py"
ADAPTER = SCRIPTS_DIR / "adapter.py"

# The sibling's reader: prints where it ran and what it was given.
ECHO_READER = (
    "import json, os, sys\n"
    "print(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv[1:]}))\n"
)


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


class SiblingMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.project = root / "project"
        self.sibling = root / "sibling-repo"
        self.project.mkdir()
        self.sibling.mkdir()
        (self.sibling / "reader.py").write_text(ECHO_READER, encoding="utf-8")
        reader = f"{shlex.quote(sys.executable)} reader.py"
        self.sibling_config = {"repo": "owner/sibling-repo", "path": "../sibling-repo",
                               "find": f"{reader} find", "row": f"{reader} --row"}

    def write_config(self, config: dict) -> None:
        folder = self.project / ".claude"
        folder.mkdir(exist_ok=True)
        (folder / "promise.config.json").write_text(json.dumps(config), encoding="utf-8")

    def orient(self) -> dict:
        result = run(ORIENT, "--cwd", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def adapter(self, *args: str) -> subprocess.CompletedProcess:
        return run(ADAPTER, "--cwd", str(self.project), *args)

    def sibling_files(self) -> List[str]:
        return sorted(os.listdir(self.sibling))

    # --- orient.py ---------------------------------------------------------

    def test_orient_reports_the_sibling_map(self) -> None:
        self.write_config({"version": 1, "map": False, "sibling": self.sibling_config})
        data = self.orient()
        self.assertIs(data["map"], False)
        self.assertIs(data["mapUsable"], False)  # no map of its own: writing modes take the no-map path
        sibling = data["sibling"]
        self.assertEqual(sibling["repo"], "owner/sibling-repo")
        self.assertEqual(sibling["path"], "../sibling-repo")
        self.assertEqual(sibling["find"], self.sibling_config["find"])
        self.assertEqual(sibling["row"], self.sibling_config["row"])
        self.assertEqual(os.path.realpath(sibling["dir"]), os.path.realpath(self.sibling))
        self.assertIs(sibling["checkout"], True)
        self.assertFalse([w for w in data["warnings"] if "sibling" in w], data["warnings"])

    def test_orient_warns_when_the_path_has_no_checkout(self) -> None:
        self.write_config({"map": False, "sibling": dict(self.sibling_config, path="../not-cloned")})
        data = self.orient()
        self.assertIs(data["mapUsable"], False)
        self.assertIs(data["sibling"]["checkout"], False)
        self.assertTrue(any(w.startswith("sibling.path has no checkout: ../not-cloned") for w in data["warnings"]),
                        data["warnings"])

    def test_orient_ignores_a_sibling_beside_a_map_of_its_own(self) -> None:
        # a row has one home: a project with its own map has no sibling map
        for map_value in (None, {"find": "x"}):
            with self.subTest(map=map_value):
                self.write_config({"map": map_value, "sibling": self.sibling_config})
                data = self.orient()
                self.assertIsNone(data["sibling"])
                self.assertIn('sibling is read only beside "map": false; ignored', data["warnings"])

    def test_orient_ignores_an_incomplete_sibling(self) -> None:
        partial = {k: v for k, v in self.sibling_config.items() if k != "row"}
        self.write_config({"map": False, "sibling": partial})
        data = self.orient()
        self.assertIsNone(data["sibling"])
        self.assertIs(data["mapUsable"], False)
        self.assertIn("sibling incomplete: missing row; ignored", data["warnings"])

    def test_sibling_is_a_known_config_key(self) -> None:
        self.write_config({"map": False, "sibling": self.sibling_config})
        self.assertNotIn("unknown config key: sibling", self.orient()["warnings"])

    def test_no_sibling_leaves_map_false_as_it_was(self) -> None:
        self.write_config({"map": False})
        data = self.orient()
        self.assertIs(data["mapUsable"], False)
        self.assertIsNone(data["sibling"])

    # --- adapter.py --------------------------------------------------------

    def test_find_runs_in_the_sibling_checkout(self) -> None:
        self.write_config({"map": False, "sibling": self.sibling_config})
        query = 'a "quoted" ask; $(touch pwned)'
        result = self.adapter("--json", "find", query)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(json.loads(result.stdout)["stdout"])
        self.assertEqual(os.path.realpath(out["cwd"]), os.path.realpath(self.sibling))
        self.assertEqual(out["argv"], ["find", query])
        self.assertEqual(self.sibling_files(), ["reader.py"])

    def test_row_runs_in_the_sibling_checkout(self) -> None:
        self.write_config({"map": False, "sibling": self.sibling_config})
        result = self.adapter("--json", "row", "CAP-40")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(json.loads(result.stdout)["stdout"])
        self.assertEqual(os.path.realpath(out["cwd"]), os.path.realpath(self.sibling))
        self.assertEqual(out["argv"], ["--row", "CAP-40"])

    def test_every_other_map_operation_refuses(self) -> None:
        self.write_config({"map": False, "sibling": self.sibling_config})
        query = self.project / "ask.txt"
        query.write_text("an ask\n", encoding="utf-8")
        refs = self.project / "refs.json"
        refs.write_text("[]", encoding="utf-8")
        for op in (["next-id"], ["learn", "--query-file", str(query), "--row", "CAP-40", "--source", "person"],
                   ["refs-sync", "--input", str(refs)], ["code", "CAP-40"], ["checks"], ["surfaces"]):
            with self.subTest(op=op[0]):
                result = self.adapter("--json", *op)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(result.stdout, "")
                self.assertIn("read-only: only find and row run there", result.stderr)
                self.assertIn(f"not '{op[0]}'", result.stderr)
        self.assertEqual(self.sibling_files(), ["reader.py"])

    def test_row_refuses_an_id_that_reads_as_an_option(self) -> None:
        self.write_config({"map": False, "sibling": self.sibling_config})
        result = self.adapter("row", "--", "--help")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertIn("starts with '-'", result.stderr)

    def test_find_and_row_refuse_with_no_checkout(self) -> None:
        self.write_config({"map": False, "sibling": dict(self.sibling_config, path="../not-cloned")})
        for op in (["find", "an ask"], ["row", "CAP-40"]):
            with self.subTest(op=op[0]):
                result = self.adapter(*op)
                self.assertEqual(result.returncode, 2)
                self.assertIn("no checkout of owner/sibling-repo at ../not-cloned", result.stderr)

    def test_verify_still_runs_in_the_project(self) -> None:
        reader = f"{shlex.quote(sys.executable)} -c \"import os; print(os.getcwd())\""
        self.write_config({"map": False, "sibling": self.sibling_config, "commands": {"test": reader}})
        result = self.adapter("--json", "verify")
        self.assertEqual(result.returncode, 0, result.stderr)
        cwd = json.loads(result.stdout)[0]["stdout"].strip()
        self.assertEqual(os.path.realpath(cwd), os.path.realpath(self.project))

    def test_show_lists_the_sibling_commands(self) -> None:
        self.write_config({"map": False, "sibling": self.sibling_config})
        result = self.adapter("show")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"sibling.find: {self.sibling_config['find']}", result.stdout)
        self.assertIn(f"sibling.row: {self.sibling_config['row']}", result.stdout)
        self.assertIn("# sibling map of owner/sibling-repo: runs in ../sibling-repo, read-only", result.stdout)


if __name__ == "__main__":
    unittest.main()
