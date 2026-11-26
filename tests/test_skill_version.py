"""The skill's own version: VERSION beside SKILL.md, orient.py's skillVersion, and
the config's minSkillVersion.

Run from the repo root:

    python3 -m unittest discover -s tests -v

A vendored or linked copy of the skill carries no plugin.json, so VERSION is the
only place its version lives. Locked here: VERSION equals plugin.json's version;
orient.py reports it (null when it is absent); adopt.py writes it into a fresh
config as minSkillVersion; and orient.py warns, naming both versions and how to
update, when the running skill is older than the project expects.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "promise"
ORIENT = SKILL / "scripts" / "orient.py"
ADOPT = SKILL / "scripts" / "adopt.py"
PLUGIN_VERSION = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def orientation(cwd: Path, orient: Path = ORIENT) -> dict:
    out = subprocess.run([sys.executable, str(orient), "--cwd", str(cwd)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def write_config(cwd: Path, config: dict) -> None:
    (cwd / ".claude").mkdir(exist_ok=True)
    (cwd / ".claude" / "promise.config.json").write_text(json.dumps(config), encoding="utf-8")


def version_warnings(data: dict) -> list:
    return [w for w in data["warnings"] if "minSkillVersion" in w]


class VersionFile(unittest.TestCase):
    def test_version_file_equals_plugin_version(self) -> None:
        text = (SKILL / "VERSION").read_text(encoding="utf-8")
        self.assertEqual(text, PLUGIN_VERSION + "\n",
                         "skills/promise/VERSION must equal .claude-plugin/plugin.json's version; "
                         "a release bumps both")


class TempProject(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.cwd = self.root / "project"
        self.cwd.mkdir()

    def copy_skill(self, version: "str | None") -> Path:
        """A copy of the skill, as a vendored copy would be, with VERSION set or removed."""
        dest = self.root / "skill"
        shutil.copytree(SKILL, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if version is None:
            (dest / "VERSION").unlink()
        else:
            (dest / "VERSION").write_text(version + "\n", encoding="utf-8")
        return dest / "scripts" / "orient.py"


class SkillVersionReported(TempProject):
    def test_skill_version_is_read_from_version_file(self) -> None:
        self.assertEqual(orientation(self.cwd)["skillVersion"], PLUGIN_VERSION)

    def test_skill_version_is_null_without_version_file(self) -> None:
        self.assertIsNone(orientation(self.cwd, self.copy_skill(None))["skillVersion"])

    def test_skill_version_is_null_when_version_file_holds_no_version(self) -> None:
        self.assertIsNone(orientation(self.cwd, self.copy_skill("not a version"))["skillVersion"])


class MinSkillVersion(TempProject):
    def test_no_warning_when_the_skill_is_current_or_newer(self) -> None:
        for wanted in (PLUGIN_VERSION, "1.3.0", "0.9.99"):
            write_config(self.cwd, {"version": 1, "minSkillVersion": wanted})
            data = orientation(self.cwd)
            self.assertEqual(version_warnings(data), [], wanted)
            self.assertFalse(any("unknown config key" in w for w in data["warnings"]), data["warnings"])

    def test_older_skill_warns_with_both_versions_and_how_to_update(self) -> None:
        write_config(self.cwd, {"version": 1, "minSkillVersion": "1.28.0"})
        data = orientation(self.cwd, self.copy_skill("1.3.0"))
        self.assertEqual(data["skillVersion"], "1.3.0")
        warnings = version_warnings(data)
        self.assertEqual(len(warnings), 1, data["warnings"])
        self.assertIn("this project expects promise >= 1.28.0", warnings[0])
        self.assertIn("this copy is 1.3.0", warnings[0])
        self.assertIn("install_skill.py", warnings[0])
        self.assertIn("plugin", warnings[0])

    def test_versions_compare_as_numbers_not_text(self) -> None:
        write_config(self.cwd, {"version": 1, "minSkillVersion": "1.10.0"})
        self.assertEqual(len(version_warnings(orientation(self.cwd, self.copy_skill("1.9.0")))), 1)
        write_config(self.cwd, {"version": 1, "minSkillVersion": "1.9.0"})
        shutil.rmtree(self.root / "skill")
        self.assertEqual(version_warnings(orientation(self.cwd, self.copy_skill("1.10.0"))), [])

    def test_a_copy_with_no_version_file_warns(self) -> None:
        write_config(self.cwd, {"version": 1, "minSkillVersion": "1.28.0"})
        warnings = version_warnings(orientation(self.cwd, self.copy_skill(None)))
        self.assertEqual(len(warnings), 1)
        self.assertIn("no VERSION file", warnings[0])

    def test_a_value_that_is_not_a_version_warns_and_is_ignored(self) -> None:
        for bad in ("latest", 128, "1.28"):
            write_config(self.cwd, {"version": 1, "minSkillVersion": bad})
            warnings = version_warnings(orientation(self.cwd))
            self.assertEqual(len(warnings), 1, bad)
            self.assertIn("is not a version", warnings[0])


class AdoptWritesMinSkillVersion(TempProject):
    def test_fresh_config_carries_the_running_skill_version(self) -> None:
        out = subprocess.run([sys.executable, str(ADOPT), "--cwd", str(self.cwd)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        config = json.loads((self.cwd / ".claude" / "promise.config.json").read_text(encoding="utf-8"))
        self.assertEqual(list(config)[:2], ["version", "minSkillVersion"])
        self.assertEqual(config["minSkillVersion"], PLUGIN_VERSION)
        self.assertEqual(version_warnings(orientation(self.cwd)), [])

    def test_an_existing_config_is_not_given_one(self) -> None:
        write_config(self.cwd, {"version": 1})
        subprocess.run([sys.executable, str(ADOPT), "--cwd", str(self.cwd)], capture_output=True, text=True)
        config = json.loads((self.cwd / ".claude" / "promise.config.json").read_text(encoding="utf-8"))
        self.assertNotIn("minSkillVersion", config)


if __name__ == "__main__":
    unittest.main()
