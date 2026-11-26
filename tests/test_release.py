"""A promise release is tagged and published by .github/scripts/release.sh (#61), which
the release-tags workflow runs and a maintainer can run by hand when Actions cannot.

Each case builds a repository whose plugin.json names releases over several commits,
with a bare "origin" beside it and a fake `gh` that logs what it is asked to create.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SCRIPTS = REPO / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import changelog_entry  # noqa: E402

CHANGELOG = textwrap.dedent("""\
    # Changelog

    ## 1.2.0

    Two.

    ## [1.1.0] - later

    One and a bit.

    ## 1.0.0

    One.
    """)
FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import os, sys
    args = sys.argv[1:]
    with open(os.environ["FAKE_GH_LOG"], "a") as fh:
        fh.write(" ".join(args) + "\\n")
        if args[:2] == ["release", "create"]:
            fh.write("NOTES " + open(args[args.index("--notes-file") + 1]).read().replace("\\n", "|") + "\\n")
    if args[:2] == ["release", "view"]:
        sys.exit(0 if args[2] in os.environ.get("FAKE_GH_EXISTING", "").split() else 1)
    ''')


def git(cwd: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()


class ChangelogEntry(unittest.TestCase):
    def test_an_entry_is_its_body_up_to_the_next_version(self) -> None:
        self.assertEqual(changelog_entry.entry(CHANGELOG, "1.2.0"), "Two.")
        self.assertEqual(changelog_entry.entry(CHANGELOG, "1.1.0"), "One and a bit.")
        self.assertEqual(changelog_entry.entry(CHANGELOG, "1.0.0"), "One.")
        self.assertEqual(changelog_entry.entry(CHANGELOG, "1.0"), "")
        self.assertEqual(changelog_entry.entry(CHANGELOG, "2.0.0"), "")


class ReleaseScript(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.work = self.tmp / "work"
        git(self.tmp, "clone", "-q", str(self.origin), str(self.work))
        (self.work / ".github").mkdir()
        shutil.copytree(SCRIPTS, self.work / ".github" / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.work / ".claude-plugin").mkdir()
        (self.work / "CHANGELOG.md").write_text(CHANGELOG)
        self.commits = {}
        for version in ("1.0.0", "1.1.0"):
            self.bump(version)
        (self.work / "other.txt").write_text("a later commit, no new version\n")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", "later")
        git(self.work, "push", "-q", "origin", "main")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        fake.write_text(FAKE_GH.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        fake.chmod(0o755)
        self.log = self.tmp / "gh.log"
        self.env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", FAKE_GH_LOG=str(self.log),
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")

    def bump(self, version: str) -> None:
        (self.work / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "promise", "version": version}))
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", version)
        self.commits[version] = git(self.work, "rev-parse", "HEAD")

    def release(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", ".github/scripts/release.sh", *args], cwd=self.work, capture_output=True,
                              text=True, env=dict(self.env, **env))

    def origin_tags(self) -> dict:
        out = git(self.work, "ls-remote", "--tags", "origin")
        return {line.split()[1][len("refs/tags/"):]: line.split()[0] for line in out.splitlines()}

    def gh_calls(self) -> list:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_check_fails_until_the_version_is_tagged(self) -> None:
        done = self.release("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("v1.1.0 has no tag", done.stdout)
        self.assertEqual(self.release().returncode, 0)
        self.assertEqual(self.release("--check").returncode, 0)

    def test_the_tag_goes_on_the_commit_that_first_names_the_version(self) -> None:
        done = self.release()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        tags = self.origin_tags()
        self.assertEqual(tags["v1.1.0"], self.commits["1.1.0"], "not the later commit that kept the version")
        self.assertEqual(tags["v1"], self.commits["1.1.0"])
        creates = [c for c in self.gh_calls() if c.startswith("release create")]
        self.assertEqual(len(creates), 1)
        self.assertIn("release create v1.1.0 --title promise 1.1.0", creates[0])
        self.assertIn("--latest=true", creates[0])
        self.assertIn("NOTES One and a bit.||**Full changelog:**", self.log.read_text())

    def test_a_release_tag_never_moves_and_a_second_run_does_nothing_new(self) -> None:
        self.assertEqual(self.release().returncode, 0)
        before = self.origin_tags()
        done = self.release(FAKE_GH_EXISTING="v1.1.0")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("a release tag never moves", done.stdout)
        self.assertEqual(self.origin_tags(), before)
        self.assertIn("v1.1.0: release exists", done.stdout)

    def test_all_publishes_a_release_for_every_tag_and_only_the_newest_is_latest(self) -> None:
        git(self.work, "tag", "v1.0.0", self.commits["1.0.0"])
        git(self.work, "push", "-q", "origin", "v1.0.0")
        done = self.release("--all")
        self.assertEqual(done.returncode, 0, done.stderr)
        creates = [c for c in self.gh_calls() if c.startswith("release create")]
        self.assertEqual([c.split()[2] for c in creates], ["v1.0.0", "v1.1.0"])
        self.assertIn("--latest=false", creates[0])
        self.assertIn("--latest=true", creates[1])

    def test_a_version_that_is_not_x_y_z_tags_nothing(self) -> None:
        self.bump("1.2.0-rc1")
        git(self.work, "push", "-q", "origin", "main")
        done = self.release()
        self.assertEqual(done.returncode, 1)
        self.assertIn("is not X.Y.Z", done.stdout)
        self.assertEqual(self.origin_tags(), {})

    def test_a_pre_release_tag_is_never_the_newest(self) -> None:
        git(self.work, "tag", "v1.9.0-rc1", self.commits["1.0.0"])
        git(self.work, "tag", "v1.1.0.4", self.commits["1.0.0"])
        git(self.work, "push", "-q", "origin", "--tags")
        done = self.release("--all")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.origin_tags()["v1"], self.commits["1.1.0"])
        creates = [c.split()[2] for c in self.gh_calls() if c.startswith("release create")]
        self.assertEqual(creates, ["v1.1.0"])

    def test_a_bump_reverted_and_made_again_is_tagged_where_it_was_made_again(self) -> None:
        self.bump("1.2.0")
        self.bump("1.1.0")  # reverted
        self.bump("1.2.0")  # made again, with the fix
        git(self.work, "push", "-q", "origin", "main")
        self.assertEqual(self.release().returncode, 0)
        self.assertEqual(self.origin_tags()["v1.2.0"], self.commits["1.2.0"])

    def test_a_backport_moves_its_own_major_tag(self) -> None:
        git(self.work, "tag", "v2.0.0", self.commits["1.0.0"])
        git(self.work, "push", "-q", "origin", "v2.0.0")
        done = self.release()
        self.assertEqual(done.returncode, 0, done.stderr)
        tags = self.origin_tags()
        self.assertEqual(tags["v1"], self.commits["1.1.0"])
        self.assertNotIn("v2", tags)
        create = next(c for c in self.gh_calls() if c.startswith("release create"))
        self.assertIn("--latest=false", create, "v2.0.0 is the latest release, not the backport")

    def test_the_notes_come_from_main_not_the_checkout(self) -> None:
        git(self.work, "checkout", "-q", "-b", "stale", self.commits["1.0.0"])
        (self.work / "CHANGELOG.md").write_text("# Changelog\n")
        done = self.release()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("NOTES One and a bit.", self.log.read_text())

    def test_the_workflow_runs_the_script(self) -> None:
        workflow = (REPO / ".github" / "workflows" / "release-tags.yml").read_text(encoding="utf-8")
        self.assertIn("bash .github/scripts/release.sh", workflow)
        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)
        self.assertIn("group: release-tags", workflow)


if __name__ == "__main__":
    unittest.main()
