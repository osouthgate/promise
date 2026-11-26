"""pin_check.py says whether a repository's promise pin is behind upstream; upgrade.py
moves the repository's pins; pin_machine.py moves a machine's plugin to the pin.

Each case builds a consumer repository and a local "upstream" git repository with
release tags, with the files upstream serves at each commit under a file:// raw tree,
so nothing here reaches the network. pin_machine.py runs against a fake `claude` on
PATH that writes Claude Code's files the way the real one was seen to. After every
pin_check run the consumer's `git status` must be clean: the check changes no file.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "promise"
SCRIPTS = SKILL / "scripts"
PIN_CHECK = SCRIPTS / "pin_check.py"
UPGRADE = SCRIPTS / "upgrade.py"
PIN_MACHINE = SCRIPTS / "pin_machine.py"
sys.path.insert(0, str(SCRIPTS))

import orient  # noqa: E402
import pin_check  # noqa: E402

TEMPLATE_V1 = "<!-- promise:begin -->\nrules at the pinned release\n<!-- promise:end -->\n"
TEMPLATE_V2 = "<!-- promise:begin -->\nrules at the newer release\n<!-- promise:end -->\n"
CHANGELOG = "# Changelog\n\n## 1.31.0\n\nb\n\n## 1.30.0\n\na\n\n## 1.29.0\n\nstart\n\n## 1.28.0\n\nearlier\n"


def git(cwd: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()


def stamp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class PinCase(unittest.TestCase):
    """An upstream with two tagged releases: `old` (v1.29.0) and `new` (v1.31.0)."""

    TAGS = True

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        up = self.tmp / "upstream"
        up.mkdir()
        git(up, "init", "-q", "-b", "main")
        (up / "f").write_text("1\n")
        git(up, "add", "f")
        git(up, "commit", "-q", "-m", "old")
        self.old = git(up, "rev-parse", "HEAD")
        (up / "f").write_text("2\n")
        git(up, "commit", "-q", "-am", "new")
        self.new = git(up, "rev-parse", "HEAD")
        if self.TAGS:
            git(up, "tag", "v1.29.0", self.old)
            git(up, "tag", "-a", "v1.31.0", "-m", "annotated", self.new)
        self.upstream = str(up)
        raw = self.tmp / "raw"
        for sha, version, template in ((self.old, "1.29.0", TEMPLATE_V1), (self.new, "1.31.0", TEMPLATE_V2)):
            base = raw / sha
            (base / ".claude-plugin").mkdir(parents=True)
            (base / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "promise", "version": version}))
            (base / "CHANGELOG.md").write_text(CHANGELOG)
            tpl = base / "skills" / "promise" / "templates"
            tpl.mkdir(parents=True)
            (tpl / "claude-md-section.md").write_text(template)
        self.raw = raw.as_uri()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.config_dir = self.tmp / "claude-config"
        self.config_dir.mkdir()
        patcher = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config_dir)})
        patcher.start()
        self.addCleanup(patcher.stop)

    # -- the consumer repository ------------------------------------------------

    def pin(self, ref: str = None, sha: str = None) -> None:
        source = {"source": "github", "repo": "osouthgate/promise"}
        if ref:
            source["ref"] = ref
        if sha:
            source["sha"] = sha
        (self.repo / ".claude").mkdir(exist_ok=True)
        (self.repo / ".claude" / "settings.json").write_text(json.dumps({
            "extraKnownMarketplaces": {"promise": {"source": source}},
            "enabledPlugins": {"promise@promise": True},
        }, indent=2) + "\n")

    def config(self, **keys) -> None:
        (self.repo / ".claude").mkdir(exist_ok=True)
        (self.repo / ".claude" / "promise.config.json").write_text(json.dumps({"version": 1, **keys}, indent=2) + "\n")

    def run_sh(self, sha: str, version: str = None) -> None:
        (self.repo / "scripts" / "promise").mkdir(parents=True, exist_ok=True)
        body = f"#!/bin/sh\nREF={sha}\n" + (f"REF_VERSION={version}\n" if version else "") + "exec true\n"
        (self.repo / "scripts" / "promise" / "run.sh").write_text(body)
        sites = [{"path": "scripts/promise/run.sh", "pattern": "REF=([0-9a-f]{40})"}]
        if version:
            sites.append({"path": "scripts/promise/run.sh", "pattern": r"REF_VERSION=(v?\d+\.\d+\.\d+)",
                          "kind": "version"})
        self.config(pinFiles=sites)

    def section(self, template: str) -> None:
        begin = f"<!-- promise:begin (managed by the promise skill) template:{stamp(template)} -->"
        (self.repo / "AGENTS.md").write_text(f"# Agents\n\n{begin}\nrules\n<!-- promise:end -->\n")

    def installed(self, sha: str, version: str, scope: str = "project") -> None:
        entry = {"scope": scope, "installPath": str(self.tmp / "cache" / version), "version": version,
                 "gitCommitSha": sha}
        if scope != "user":
            entry["projectPath"] = str(self.repo)
        plugins = self.config_dir / "plugins"
        plugins.mkdir(exist_ok=True)
        (plugins / "installed_plugins.json").write_text(json.dumps(
            {"version": 2, "plugins": {"promise@promise": [entry]}}, indent=2))

    def commit(self) -> None:
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "pin")

    def run_check(self, *args: str, upstream: str = None) -> subprocess.CompletedProcess:
        proc = subprocess.run(
            [sys.executable, str(PIN_CHECK), "--cwd", str(self.repo), "--upstream", upstream or self.upstream,
             "--raw-base", self.raw, *args],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(git(self.repo, "status", "--porcelain", "--untracked-files=all"), "",
                         "pin_check.py changed a file in the repository")
        return proc


class Reports(PinCase):
    def test_a_tag_pin_at_the_newest_release_is_up_to_date(self) -> None:
        self.pin(ref="v1.31.0")
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "promise pin: up to date (1.31.0)")

    def test_behind_names_both_versions_and_the_count(self) -> None:
        self.pin(ref="v1.29.0")
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(),
                         f"promise pin: 1.29.0 ({self.old[:7]}), upstream 1.31.0 ({self.new[:7]}), 2 releases behind")
        self.assertEqual(self.run_check("--strict").returncode, 1)

    def test_json_gives_the_same_as_fields(self) -> None:
        self.pin(ref="v1.29.0")
        self.commit()
        data = json.loads(self.run_check("--json").stdout)
        self.assertEqual(data["state"], "behind")
        self.assertEqual(data["pinned"], {"ref": "v1.29.0", "sha": self.old, "version": "1.29.0"})
        self.assertEqual(data["upstream"], {"ref": "v1.31.0", "sha": self.new, "version": "1.31.0"})
        self.assertEqual(data["releases"], ["1.31.0", "1.30.0"])
        self.assertEqual(data["behind"], 2)
        self.assertEqual(data["pins"], [{"path": ".claude/settings.json", "kind": "ref", "value": "v1.29.0"}])
        self.assertEqual(data["notices"], [])

    def test_a_sha_pin_is_read_and_said_to_pin_nothing(self) -> None:
        self.pin(sha=self.new)
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0)
        first, second = proc.stdout.strip().splitlines()
        self.assertEqual(first, "promise pin: up to date (1.31.0)")
        self.assertIn("pins by source.sha, which Claude Code does not read", second)
        self.assertEqual(self.run_check("--strict").returncode, 1)

    def test_a_branch_ref_moves_and_says_so(self) -> None:
        self.pin(ref="main")
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0)
        self.assertIn("source.ref 'main' is a branch, which moves", proc.stdout)

    def test_a_ref_upstream_lacks_says_so(self) -> None:
        self.pin(ref="v9.9.9")
        self.commit()
        self.assertIn("names no tag upstream", self.run_check().stdout)

    def test_a_release_on_main_with_no_tag_is_named_and_strict_is_not_failed_by_it(self) -> None:
        up = Path(self.upstream)
        (up / "f").write_text("4\n")
        git(up, "commit", "-q", "-am", "untagged release")
        untagged = git(up, "rev-parse", "HEAD")
        base = Path(self.raw[len("file://"):]) / untagged / ".claude-plugin"
        base.mkdir(parents=True)
        (base / "plugin.json").write_text(json.dumps({"version": "1.32.0"}))
        self.pin(ref="v1.31.0")
        self.commit()
        proc = self.run_check()
        self.assertIn("upstream main is at 1.32.0, but its newest release tag is v1.31.0", proc.stdout)
        self.assertEqual(self.run_check("--strict").returncode, 0)

    def test_a_moving_tag_is_not_a_pin(self) -> None:
        git(Path(self.upstream), "tag", "v1", self.new)
        self.pin(ref="v1")
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0)
        self.assertIn("source.ref 'v1' is a tag that moves", proc.stdout)
        self.assertEqual(self.run_check("--strict").returncode, 1)

    def test_a_relative_upstream_path_resolves(self) -> None:
        self.pin(ref="v1.31.0")
        self.commit()
        proc = subprocess.run([sys.executable, str(PIN_CHECK), "--cwd", str(self.repo), "--upstream", "./upstream",
                               "--raw-base", self.raw], capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(proc.stdout.strip(), "promise pin: up to date (1.31.0)")

    def test_no_network_is_not_checked_and_exit_0(self) -> None:
        self.pin(ref="v1.29.0")
        self.commit()
        for flags in ((), ("--strict",)):
            proc = self.run_check(*flags, upstream=str(self.tmp / "no-such-upstream"))
            self.assertEqual(proc.returncode, 0, flags)
            first, hint = proc.stdout.strip().splitlines()
            self.assertEqual(first, "promise pin: upstream not reachable, not checked")
            self.assertIn("upstream may be private", hint)

    def test_versions_not_readable_still_reports_the_shas(self) -> None:
        self.pin(sha=self.old)
        self.commit()
        proc = subprocess.run([sys.executable, str(PIN_CHECK), "--cwd", str(self.repo), "--upstream", self.upstream,
                               "--raw-base", (self.tmp / "empty").as_uri()], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn(f"? ({self.old[:7]}), upstream 1.31.0 ({self.new[:7]})", proc.stdout)

    def test_no_pin_is_not_checked(self) -> None:
        (self.repo / "README.md").write_text("x\n")
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0)
        self.assertIn("no pin found", proc.stdout)


class NoReleaseTags(PinCase):
    TAGS = False

    def test_with_no_release_tag_upstream_is_main(self) -> None:
        self.pin(sha=self.old)
        self.commit()
        data = json.loads(self.run_check("--json").stdout)
        self.assertEqual(data["upstream"], {"ref": "main", "sha": self.new, "version": "1.31.0"})
        self.assertEqual(data["behind"], 2)


class PrivateUpstream(PinCase):
    """A private upstream is read through a local checkout the person keeps: git runs
    there, with that checkout's own access (#57)."""

    def clone(self) -> Path:
        checkout = self.tmp / "promise-checkout"
        subprocess.run(["git", "clone", "-q", self.upstream, str(checkout)], check=True, capture_output=True)
        return checkout

    def test_the_config_names_a_checkout_and_the_check_reads_through_it(self) -> None:
        checkout = self.clone()
        self.pin(ref="v1.29.0")
        self.config(upstreamPath=os.path.relpath(checkout, self.repo))
        self.commit()
        data = json.loads(self.run_check("--json", upstream=str(self.tmp / "unreachable")).stdout)
        self.assertEqual(data["via"], str(checkout))
        self.assertEqual((data["state"], data["upstream"]["ref"], data["pinned"]["sha"]), ("behind", "v1.31.0", self.old))

    def test_a_commit_the_checkout_lacks_is_fetched_without_moving_its_branches(self) -> None:
        checkout = self.clone()
        up = Path(self.upstream)
        (up / "f").write_text("3\n")
        git(up, "commit", "-q", "-am", "newer")
        newer = git(up, "rev-parse", "HEAD")
        git(up, "tag", "v1.32.0", newer)
        before = git(checkout, "show-ref")
        self.pin(ref="v1.32.0")
        self.commit()
        self.assertIsNotNone(pin_check.checkout_file(str(checkout), newer, "f", 5.0))
        self.assertEqual(git(checkout, "show-ref"), before, "no branch or tag of the checkout moves")
        proc = self.run_check("--upstream-path", str(checkout), upstream=str(self.tmp / "unreachable"))
        self.assertEqual(proc.stdout.strip(), "promise pin: up to date (1.32.0)")

    def test_the_flag_wins_over_the_environment_and_a_bad_path_is_named_not_skipped(self) -> None:
        checkout = self.clone()
        self.pin(ref="v1.31.0")
        self.commit()
        with mock.patch.dict(os.environ, {pin_check.UPSTREAM_PATH_ENV: str(self.tmp / "nope")}):
            proc = self.run_check()  # the network upstream works; the named checkout does not
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout.strip().splitlines(),
                             ["promise pin: upstream not reachable, not checked",
                              f"promise pin: the upstream checkout {str(self.tmp / 'nope')!r} does not exist"])
            proc = self.run_check("--upstream-path", str(checkout))
            self.assertEqual(proc.stdout.strip(), "promise pin: up to date (1.31.0)")

    def test_a_hooks_git_dir_does_not_aim_git_at_the_checked_repository(self) -> None:
        checkout = self.clone()
        self.pin(ref="v1.31.0")
        self.config(upstreamPath=str(checkout))
        self.commit()
        before = git(self.repo, "count-objects", "-v")
        env = dict(os.environ, GIT_DIR=str(self.repo / ".git"), GIT_WORK_TREE=str(self.repo))
        proc = subprocess.run([sys.executable, str(PIN_CHECK), "--cwd", str(self.repo), "--upstream",
                               str(self.tmp / "unreachable"), "--raw-base", self.raw],
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.stdout.strip(), "promise pin: up to date (1.31.0)")
        self.assertEqual(git(self.repo, "count-objects", "-v"), before)

    def test_a_folder_that_is_not_a_checkouts_root_is_refused(self) -> None:
        (self.repo / "vendor" / "promise").mkdir(parents=True)
        (self.repo / "vendor" / "promise" / "x").write_text("x\n")
        self.pin(ref="v1.31.0")
        self.config(upstreamPath="vendor/promise")
        self.commit()
        proc = self.run_check()
        self.assertIn("is not the root of a git checkout", proc.stdout)
        self.config(upstreamPath=".")
        self.commit()
        self.assertIn("is this repository itself", self.run_check().stdout)

    def test_upgrade_and_the_machine_step_say_why_a_named_checkout_failed(self) -> None:
        self.pin(sha=self.old)
        self.config(upstreamPath="nowhere")
        self.commit()
        proc = subprocess.run([sys.executable, str(UPGRADE), "--cwd", str(self.repo), "--upstream", self.upstream,
                               "--to", "v1.31.0"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("the upstream checkout 'nowhere' does not exist", proc.stderr)

    def test_the_checkouts_git_never_prompts(self) -> None:
        with mock.patch.dict(os.environ, {"GIT_DIR": "/x"}, clear=False):
            os.environ.pop("GIT_SSH_COMMAND", None)
            env = pin_check.checkout_env()
        self.assertNotIn("GIT_DIR", env)
        self.assertEqual((env["GIT_TERMINAL_PROMPT"], env["GIT_SSH_COMMAND"]), ("0", "ssh -o BatchMode=yes"))

    def test_unreachable_says_the_upstream_may_be_private(self) -> None:
        self.pin(ref="v1.31.0")
        self.commit()
        self.assertIn("upstream may be private", self.run_check(upstream=str(self.tmp / "gone")).stdout)

    def test_upgrade_reads_the_tag_through_the_checkout(self) -> None:
        checkout = self.clone()
        self.pin(sha=self.old)
        self.config(upstreamPath=str(checkout))
        self.commit()
        proc = subprocess.run([sys.executable, str(UPGRADE), "--cwd", str(self.repo), "--upstream",
                               str(self.tmp / "unreachable"), "--to", "v1.31.0"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"ref": "v1.31.0"', (self.repo / ".claude" / "settings.json").read_text())


class VendoredCopy(PinCase):
    def test_a_vendored_site_does_not_move_alone(self) -> None:
        self.pin(ref="v1.29.0")
        (self.repo / ".promise-source").write_text(f"{self.old}\n")
        self.config(pinFiles=[{"path": ".promise-source", "pattern": "^([0-9a-f]{40})$", "vendored": True}])
        self.commit()
        proc = subprocess.run([sys.executable, str(UPGRADE), "--cwd", str(self.repo), "--upstream", self.upstream,
                               "--to", "v1.31.0"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("vendored copy of the skill", proc.stderr)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_a_vendored_site_already_synced_lets_the_rest_move(self) -> None:
        self.pin(ref="v1.29.0")
        (self.repo / ".promise-source").write_text(f"{self.new}\n")
        self.config(pinFiles=[{"path": ".promise-source", "pattern": "^([0-9a-f]{40})$", "vendored": True}])
        self.commit()
        proc = subprocess.run([sys.executable, str(UPGRADE), "--cwd", str(self.repo), "--upstream", self.upstream,
                               "--to", "v1.31.0"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.repo / ".promise-source").read_text(), f"{self.new}\n")

    def test_a_copy_under_a_folder_that_is_no_repository_root_is_not_named(self) -> None:
        shutil.copytree(SKILL, self.tmp / "home" / ".claude" / "plugins" / "promise",
                        ignore=shutil.ignore_patterns("__pycache__"))
        proc = subprocess.run([sys.executable, str(self.tmp / "home" / ".claude" / "plugins" / "promise" / "scripts"
                                                   / "pin_check.py"), "--cwd", str(self.tmp / "home"),
                               "--upstream", self.upstream], capture_output=True, text=True)
        self.assertNotIn("runs from a copy", proc.stdout)

    def test_a_copy_inside_the_repo_with_no_pin_is_named(self) -> None:
        shutil.copytree(SKILL, self.repo / "tools" / "promise", ignore=shutil.ignore_patterns("__pycache__"))
        self.commit()
        proc = subprocess.run([sys.executable, str(self.repo / "tools" / "promise" / "scripts" / "pin_check.py"),
                               "--cwd", str(self.repo), "--upstream", self.upstream], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("runs from a copy inside this repository (tools/promise)", proc.stdout)
        self.assertIn('"vendored": true', proc.stdout)


class Disagreement(PinCase):
    def test_a_tag_and_a_sha_site_that_disagree_exit_1_naming_both(self) -> None:
        self.pin(ref="v1.29.0")
        self.run_sh(self.new)
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("pins disagree", proc.stdout)
        self.assertIn(f"scripts/promise/run.sh {self.new[:7]}", proc.stdout)
        self.assertIn(f".claude/settings.json (v1.29.0) {self.old[:7]}", proc.stdout)

    def test_a_tag_and_a_version_site_disagree_offline(self) -> None:
        self.pin(ref="v1.31.0")
        self.run_sh(self.new, "1.29.0")
        self.commit()
        proc = self.run_check(upstream=str(self.tmp / "gone"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("scripts/promise/run.sh 1.29.0", proc.stdout)

    def test_two_full_shas_behind_one_short_pin_still_disagree(self) -> None:
        other = self.new[:7] + ("0" if self.new[7] != "0" else "1") + self.new[8:]
        self.pin(sha=self.new[:7])
        (self.repo / "a.sh").write_text(f"REF={self.new}\n")
        (self.repo / "b.sh").write_text(f"REF={other}\n")
        self.config(pinFiles=[{"path": "a.sh", "pattern": "REF=([0-9a-f]{40})"},
                              {"path": "b.sh", "pattern": "REF=([0-9a-f]{40})"}])
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("pins disagree", proc.stdout)

    def test_agreeing_sites_are_one_pin(self) -> None:
        self.pin(ref="v1.31.0")
        self.run_sh(self.new, "v1.31.0")
        self.commit()
        proc = self.run_check()
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, "promise pin: up to date (1.31.0)"))

    def test_a_configured_site_with_no_value_exits_1(self) -> None:
        self.pin(ref="v1.31.0")
        self.run_sh(self.new)
        (self.repo / "scripts" / "promise" / "run.sh").write_text("#!/bin/sh\nREF=main\n")
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("scripts/promise/run.sh", proc.stdout)

    def test_a_disagreement_still_names_upstream_for_the_fix(self) -> None:
        self.pin(ref="v1.31.0")
        self.run_sh(self.new, "1.29.0")
        self.commit()
        data = json.loads(self.run_check("--json").stdout)
        self.assertEqual(data["state"], "disagree")
        self.assertEqual(data["upstream"]["ref"], "v1.31.0")

    def test_a_config_that_is_not_json_is_a_broken_pin_site(self) -> None:
        self.pin(ref="v1.31.0")
        (self.repo / ".claude" / "promise.config.json").write_text("{bad")
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("pinFiles are unknown", proc.stdout)

    def test_an_unknown_kind_exits_1(self) -> None:
        self.pin(ref="v1.31.0")
        self.config(pinFiles=[{"path": "x", "pattern": "x", "kind": "branch"}])
        self.commit()
        self.assertEqual(self.run_check().returncode, 1)


class Section(PinCase):
    def test_a_section_from_another_template_warns_on_a_second_line(self) -> None:
        self.pin(ref="v1.31.0")
        self.section(TEMPLATE_V1)
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0)
        first, second = proc.stdout.strip().splitlines()
        self.assertEqual(first, "promise pin: up to date (1.31.0)")
        self.assertIn("AGENTS.md was not written by the pinned 1.31.0 template", second)
        self.assertIn("/promise adopt", second)
        self.assertEqual(self.run_check("--strict").returncode, 1)

    def test_a_section_from_the_pinned_template_says_nothing(self) -> None:
        self.pin(ref="v1.29.0")
        self.section(TEMPLATE_V1)
        self.commit()
        self.assertEqual(len(self.run_check().stdout.strip().splitlines()), 1)

    def test_the_stamp_matches_what_adopt_writes(self) -> None:
        text = (SKILL / "templates" / "claude-md-section.md").read_text(encoding="utf-8")
        self.assertEqual(stamp(text), orient.template_stamp(str(SKILL)))


class Machine(PinCase):
    def test_a_machine_on_another_commit_is_named(self) -> None:
        self.pin(ref="v1.31.0")
        self.installed(self.old, "1.29.0")
        self.commit()
        proc = self.run_check()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip().splitlines()[-1],
                         f"promise machine: this machine runs 1.29.0 ({self.old[:7]}), the repo pins 1.31.0: "
                         "run pin_machine.py, then restart Claude Code")
        self.assertEqual(self.run_check("--strict").returncode, 1)

    def test_a_machine_on_the_pin_says_nothing(self) -> None:
        self.pin(ref="v1.31.0")
        self.installed(self.new, "1.31.0")
        self.commit()
        self.assertEqual(self.run_check().stdout.strip(), "promise pin: up to date (1.31.0)")

    def test_the_user_scope_install_counts_when_there_is_no_project_one(self) -> None:
        self.pin(ref="v1.31.0")
        self.installed(self.old, "1.29.0", scope="user")
        self.commit()
        self.assertIn("promise machine:", self.run_check().stdout)

    def test_orient_reports_the_pin_and_the_machine_and_warns(self) -> None:
        self.pin(ref="v1.31.0")
        self.installed(self.old, "1.29.0")
        data = json.loads(subprocess.run([sys.executable, str(SCRIPTS / "orient.py"), "--cwd", str(self.repo)],
                                         capture_output=True, text=True).stdout)
        self.assertEqual(data["promisePin"], {"ref": "v1.31.0", "sha": None, "version": "1.31.0"})
        self.assertEqual(data["machinePlugin"]["gitCommitSha"], self.old)
        self.assertTrue(any("this machine runs promise 1.29.0" in w for w in data["warnings"]), data["warnings"])

    def test_orient_warns_on_a_sha_pin(self) -> None:
        self.pin(sha=self.new)
        data = json.loads(subprocess.run([sys.executable, str(SCRIPTS / "orient.py"), "--cwd", str(self.repo)],
                                         capture_output=True, text=True).stdout)
        self.assertTrue(any("which Claude Code's marketplace source does not read" in w for w in data["warnings"]))


class Safety(PinCase):
    def test_a_vendored_copy_inside_the_repo_leaves_no_files(self) -> None:
        shutil.copytree(SCRIPTS, self.repo / "tools" / "promise", ignore=shutil.ignore_patterns("__pycache__"))
        self.pin(ref="v1.29.0")
        self.commit()
        proc = subprocess.run([sys.executable, str(self.repo / "tools" / "promise" / "pin_check.py"),
                               "--cwd", str(self.repo), "--upstream", self.upstream, "--raw-base", self.raw],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(git(self.repo, "status", "--porcelain", "--untracked-files=all"), "")

    def test_a_url_with_a_token_is_refused_and_never_printed(self) -> None:
        self.pin(ref="v1.29.0")
        self.commit()
        proc = self.run_check(upstream="https://ghp_SECRET123@github.com/osouthgate/promise.git")
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("ghp_SECRET123", proc.stdout + proc.stderr)

    def test_an_ssh_upstream_is_refused(self) -> None:
        self.pin(ref="v1.29.0")
        self.commit()
        self.assertEqual(self.run_check(upstream="git@github.com:osouthgate/promise.git").returncode, 2)

    def test_a_checkouts_auth_header_never_reaches_git(self) -> None:
        """actions/checkout leaves a token in .git/config as an extra header."""
        self.pin(ref="v1.31.0")
        self.commit()
        git(self.repo, "config", "http.extraheader", "AUTHORIZATION: basic c2VjcmV0")
        seen = {}
        real_run = subprocess.run

        def spy(cmd, **kwargs):
            seen["cwd"] = kwargs.get("cwd")
            return real_run(cmd, **kwargs)

        with mock.patch.object(pin_check.subprocess, "run", spy):
            refs = pin_check.remote_refs(self.upstream, 5.0)
        self.assertEqual(refs["refs/tags/v1.31.0"], self.new, "an annotated tag reads as its commit")
        self.assertFalse(str(seen["cwd"]).startswith(str(self.repo)))

    def test_git_runs_with_no_credentials_no_prompt_and_a_timeout(self) -> None:
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"], seen["kwargs"] = cmd, kwargs
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

        with mock.patch.object(pin_check.subprocess, "run", fake_run):
            self.assertIsNone(pin_check.remote_refs(pin_check.UPSTREAM, 5.0))
        self.assertEqual(seen["kwargs"]["timeout"], 5.0)
        self.assertIn("credential.helper=", seen["cmd"])
        self.assertIn("http.extraHeader=", seen["cmd"])
        env = seen["kwargs"]["env"]
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual((env["GIT_CONFIG_NOSYSTEM"], env["GIT_CONFIG_GLOBAL"]), ("1", os.devnull))
        self.assertNotEqual(env["HOME"], os.environ.get("HOME"), "~/.netrc must not be read")
        self.assertEqual(seen["cmd"][-3:], [pin_check.UPSTREAM, "refs/heads/main", "refs/tags/*"])

    def test_a_timeout_reads_as_not_reachable(self) -> None:
        self.pin(ref="v1.29.0")
        self.commit()
        with mock.patch.object(pin_check, "remote_refs", return_value=None):
            report = pin_check.check(str(self.repo), self.upstream, self.raw, 5.0)
        self.assertEqual(report["state"], "unreachable")
        self.assertEqual(pin_check.exit_code(report, strict=True), 0)

    def test_every_network_call_has_the_default_timeout(self) -> None:
        text = PIN_CHECK.read_text(encoding="utf-8")
        self.assertIn('"--timeout", type=float, default=5.0', text)
        self.assertIn("urlopen(request, timeout=timeout)", text)


class Upgrade(PinCase):
    def run_upgrade(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(UPGRADE), "--cwd", str(self.repo), "--upstream", self.upstream,
                               *args], capture_output=True, text=True)

    def test_dry_run_writes_nothing(self) -> None:
        self.pin(sha=self.old)
        self.run_sh(self.old, "1.29.0")
        self.commit()
        proc = self.run_upgrade("--to", "v1.31.0", "--dry-run")
        self.assertIn("Promise Doctor", proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('+        "ref": "v1.31.0"', proc.stdout)
        self.assertIn(f"+REF={self.new}", proc.stdout)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_the_move_sets_every_site_the_config_and_then_the_check_agrees(self) -> None:
        self.pin(sha=self.old)
        self.run_sh(self.old, "v1.29.0")
        self.commit()
        proc = self.run_upgrade("--to", "v1.31.0")  # no --sha: the tag's commit is read upstream
        self.assertEqual(proc.returncode, 0, proc.stderr)
        source = json.loads((self.repo / ".claude" / "settings.json").read_text())["extraKnownMarketplaces"]["promise"]["source"]
        self.assertEqual(source, {"source": "github", "repo": "osouthgate/promise", "ref": "v1.31.0"})
        self.assertEqual((self.repo / "scripts" / "promise" / "run.sh").read_text(),
                         f"#!/bin/sh\nREF={self.new}\nREF_VERSION=v1.31.0\nexec true\n")
        config = json.loads((self.repo / ".claude" / "promise.config.json").read_text())
        self.assertEqual(list(config)[:2], ["version", "minSkillVersion"])
        self.assertEqual((config["minSkillVersion"], config["decisionPolicy"]), ("1.31.0", "auto"))
        self.assertIn("pin_machine.py", proc.stdout)
        self.commit()
        self.assertEqual(self.run_check().stdout.strip(), "promise pin: up to date (1.31.0)")

    def test_only_the_pin_values_change_in_each_file(self) -> None:
        """A one-line settings file with a BOM and CRLF, and a config with its own layout."""
        settings = self.repo / ".claude" / "settings.json"
        settings.parent.mkdir()
        one_line = ('\ufeff{"extraKnownMarketplaces":{"promise":{"source":{"source":"github",'
                    f'"repo":"osouthgate/promise","sha":"{self.old}"}}}}}},"$comment":"keep"}}\r\n')
        settings.write_bytes(one_line.encode("utf-8"))
        config = self.repo / ".claude" / "promise.config.json"
        config.write_bytes(b'{\r\n    "version": 1,\r\n    "docsHome":   "docs"\r\n}\r\n')
        self.commit()
        self.assertEqual(self.run_upgrade("--to", "v1.31.0").returncode, 0)
        self.assertEqual(settings.read_bytes().decode("utf-8"), one_line.replace(f'"sha":"{self.old}"', '"ref": "v1.31.0"'))
        self.assertEqual(config.read_bytes(), b'{\r\n    "version": 1,\r\n    "minSkillVersion": "1.31.0",\r\n'
                         b'    "decisionPolicy": "auto",\r\n    "docsHome":   "docs"\r\n}\r\n')

    def test_a_ref_and_a_sha_become_one_ref(self) -> None:
        self.pin(ref="v1.29.0", sha=self.old)
        self.commit()
        self.assertEqual(self.run_upgrade("--to", "v1.31.0").returncode, 0)
        source = json.loads((self.repo / ".claude" / "settings.json").read_text())["extraKnownMarketplaces"]["promise"]["source"]
        self.assertEqual(source, {"source": "github", "repo": "osouthgate/promise", "ref": "v1.31.0"})

    def test_another_spelling_of_the_settings_path_is_one_file(self) -> None:
        self.pin(sha=self.old)
        settings = self.repo / ".claude" / "settings.json"
        data = json.loads(settings.read_text())
        data["env"] = {"PROMISE_VERSION": "1.29.0"}
        settings.write_text(json.dumps(data, indent=2) + "\n")
        self.config(pinFiles=[{"path": "./.claude//settings.json", "pattern": r'"PROMISE_VERSION": "(\d+\.\d+\.\d+)"',
                               "kind": "version"}])
        self.commit()
        self.assertEqual(self.run_upgrade("--to", "v1.31.0").returncode, 0)
        self.commit()
        self.assertEqual(self.run_check().stdout.strip(), "promise pin: up to date (1.31.0)")

    def test_a_pin_files_entry_on_the_config_is_refused(self) -> None:
        self.pin(sha=self.old)
        self.config(pinFiles=[{"path": "./.claude/promise.config.json", "pattern": '"version": (1)', "kind": "sha"}])
        self.commit()
        self.assertEqual(self.run_upgrade("--to", "v1.31.0").returncode, 2)

    def test_a_site_the_move_would_erase_is_refused(self) -> None:
        self.pin(sha=self.old)
        self.config(pinFiles=[{"path": ".claude/settings.json", "pattern": '"sha": "([0-9a-f]{40})"'}])
        self.commit()
        proc = self.run_upgrade("--to", "v1.31.0")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("would match nothing after the move", proc.stderr)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_the_tag_is_checked_upstream_even_with_a_sha(self) -> None:
        self.pin(sha=self.old)
        self.commit()
        self.assertEqual(self.run_upgrade("--to", "v9.9.9").returncode, 2)
        self.assertEqual(self.run_upgrade("--to", "v1.31.0", "--sha", self.old).returncode, 2)
        offline = subprocess.run([sys.executable, str(UPGRADE), "--cwd", str(self.repo), "--upstream",
                                  str(self.tmp / "gone"), "--to", "v1.31.0"], capture_output=True, text=True)
        self.assertEqual(offline.returncode, 2)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_a_higher_min_skill_version_and_a_set_policy_are_kept(self) -> None:
        self.pin(ref="v1.29.0")
        self.config(minSkillVersion="9.0.0", decisionPolicy="spec")
        self.commit()
        self.assertEqual(self.run_upgrade("--to", "v1.31.0", "--sha", self.new).returncode, 0)
        config = json.loads((self.repo / ".claude" / "promise.config.json").read_text())
        self.assertEqual((config["minSkillVersion"], config["decisionPolicy"]), ("9.0.0", "spec"))

    def test_the_old_policy_name_is_rewritten_to_fast_and_said(self) -> None:
        self.pin(ref="v1.29.0")
        self.config(minSkillVersion="9.0.0", decisionPolicy="prototype")
        self.commit()
        proc = self.run_upgrade("--to", "v1.31.0", "--sha", self.new)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        config = json.loads((self.repo / ".claude" / "promise.config.json").read_text())
        self.assertEqual(config["decisionPolicy"], "fast")
        self.assertIn('config: "decisionPolicy": "prototype" → "fast"', proc.stdout)

    def test_a_pin_files_entry_on_the_settings_file_keeps_the_settings_move(self) -> None:
        self.pin(sha=self.old)
        settings = self.repo / ".claude" / "settings.json"
        data = json.loads(settings.read_text())
        data["env"] = {"PROMISE_VERSION": "1.29.0"}
        settings.write_text(json.dumps(data, indent=2) + "\n")
        self.config(pinFiles=[{"path": ".claude/settings.json", "pattern": r'"PROMISE_VERSION": "(\d+\.\d+\.\d+)"',
                               "kind": "version"}])
        self.commit()
        self.assertEqual(self.run_upgrade("--to", "v1.31.0", "--sha", self.new).returncode, 0)
        data = json.loads(settings.read_text())
        self.assertEqual(data["extraKnownMarketplaces"]["promise"]["source"]["ref"], "v1.31.0")
        self.assertNotIn("sha", data["extraKnownMarketplaces"]["promise"]["source"])
        self.assertEqual(data["env"]["PROMISE_VERSION"], "1.31.0")

    def test_a_bad_tag_or_sha_is_refused_and_writes_nothing(self) -> None:
        self.pin(sha=self.old)
        self.run_sh(self.old)
        self.commit()
        for args in (("--to", "1.31.0"), ("--to", "main"), ("--to", "v1.31.0", "--sha", self.new[:7]),
                     ("--to", "v9.9.9")):
            with self.subTest(args=args):
                self.assertEqual(self.run_upgrade(*args).returncode, 2)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_the_starter_report_lists_what_the_projects_copies_lack_and_writes_nothing(self) -> None:
        self.pin(ref="v1.29.0")
        (self.repo / "recipe.md").write_text("# Recipe\n\n## Why keep a map\n\nours\n")
        (self.repo / "find.py").write_text('import argparse\nap = argparse.ArgumentParser()\nap.add_argument("--row")\n')
        self.config(map={"recipe": "recipe.md", "find": "python3 find.py", "row": "python3 find.py --row",
                         "lanes": {}})
        self.commit()
        before = (self.repo / "recipe.md").read_text()
        proc = self.run_upgrade("--to", "v1.31.0", "--sha", self.new)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("recipe.md lacks the starter recipe's section ### How big a row is", proc.stdout)
        self.assertNotIn("section ## Why keep a map", proc.stdout)
        self.assertIn("find.py lacks the starter reader's flag --next-id", proc.stdout)
        self.assertIn("find.py lacks the starter reader's subcommand learn", proc.stdout)
        self.assertIn("find.py lacks the starter reader's map key 'retired'", proc.stdout)
        self.assertNotIn("flag --row", proc.stdout)
        self.assertEqual((self.repo / "recipe.md").read_text(), before)

    def test_the_starter_report_skips_fenced_headings_and_readers_that_are_not_python(self) -> None:
        self.pin(ref="v1.29.0")
        (self.repo / "recipe.md").write_text("# Recipe\n\n```\n## Finding a row\n```\n")
        (self.repo / "find.js").write_text("console.log('reader')\n")
        self.config(map={"recipe": "recipe.md", "find": "node find.js", "row": "node find.js", "lanes": {}})
        self.commit()
        proc = self.run_upgrade("--to", "v1.31.0", "--sha", self.new, "--dry-run")
        self.assertIn("section ## Finding a row", proc.stdout, "a heading inside a fence is not the section")
        self.assertNotIn("find.js lacks", proc.stdout)


FAKE_CLAUDE = textwrap.dedent('''\
    #!/usr/bin/env python3
    """A stand-in for `claude plugin ...`: it writes Claude Code's files the way the real
    CLI was seen to, and logs each call."""
    import json, os, sys
    base = os.environ["CLAUDE_CONFIG_DIR"]
    os.makedirs(os.path.join(base, "plugins"), exist_ok=True)
    with open(os.path.join(base, "calls.log"), "a") as fh:
        fh.write(" ".join(sys.argv[1:]) + "\\n")
    args = sys.argv[1:]
    if args[:3] == ["plugin", "marketplace", "add"]:
        repo, _, ref = args[3].partition("#")
        with open(os.path.join(base, "plugins", "known_marketplaces.json"), "w") as fh:
            json.dump({"promise": {"source": {"source": "github", "repo": repo, "ref": ref}}}, fh)
        settings = os.path.join(os.getcwd(), ".claude", "settings.json")
        data = json.load(open(settings))
        reordered = {"enabledPlugins": data.pop("enabledPlugins", {}), **data}
        json.dump(reordered, open(settings, "w"), indent=2)
        print("Marketplace 'promise' was already added and now points at " + args[3])
        sys.exit(1)
    if args[:2] == ["plugin", "update"]:
        entry = {"scope": "project", "projectPath": os.getcwd(), "version": os.environ["FAKE_VERSION"],
                 "gitCommitSha": os.environ["FAKE_SHA"], "installPath": "/cache/promise"}
        with open(os.path.join(base, "plugins", "installed_plugins.json"), "w") as fh:
            json.dump({"version": 2, "plugins": {"promise@promise": [entry]}}, fh)
        print("updated")
    ''')


class MachineStep(PinCase):
    def setUp(self) -> None:
        super().setUp()
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "claude"
        fake.write_text(FAKE_CLAUDE.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        fake.chmod(0o755)
        self.path = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"

    def run_machine(self, *args: str, sha: str, version: str, path: str = None) -> subprocess.CompletedProcess:
        env = dict(os.environ, PATH=path or self.path, FAKE_SHA=sha, FAKE_VERSION=version)
        return subprocess.run([sys.executable, str(PIN_MACHINE), "--cwd", str(self.repo), "--upstream", self.upstream,
                               *args], capture_output=True, text=True, env=env)

    def calls(self) -> list:
        log = self.config_dir / "calls.log"
        return log.read_text().splitlines() if log.exists() else []

    def test_it_moves_the_machine_checks_it_and_leaves_the_checkout_clean(self) -> None:
        self.pin(ref="v1.31.0")
        self.commit()
        proc = self.run_machine(sha=self.new, version="1.31.0")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.calls(), ["plugin marketplace add osouthgate/promise#v1.31.0 --scope project",
                                        "plugin update promise@promise --scope project"])
        self.assertIn("this machine now runs 1.31.0", proc.stdout)
        self.assertIn("Restart Claude Code", proc.stdout)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "", "the reordered settings are put back")

    def test_an_install_that_is_not_the_pin_exits_1(self) -> None:
        self.pin(ref="v1.31.0")
        self.commit()
        proc = self.run_machine(sha=self.old, version="1.29.0")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("this machine runs 1.29.0", proc.stdout)

    def test_a_sha_pin_is_refused_since_re_declaring_would_move_it(self) -> None:
        self.pin(sha=self.new)
        self.commit()
        proc = self.run_machine(sha=self.new, version="1.31.0")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_a_settings_change_claude_makes_is_always_put_back(self) -> None:
        self.pin(ref="v1.31.0")
        settings = self.repo / ".claude" / "settings.json"
        data = json.loads(settings.read_text())
        data["$comment"] = "a key the fake drops"
        settings.write_text(json.dumps(data, indent=2) + "\n")
        self.commit()
        fake = self.tmp / "bin" / "claude"
        fake.write_text(fake.read_text().replace('reordered = {', 'data.pop("$comment", None); reordered = {'))
        proc = self.run_machine(sha=self.new, version="1.31.0")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("changed what it says; its bytes are put back", proc.stdout)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_a_value_that_reads_as_an_option_is_refused(self) -> None:
        for repo, ref in (("--plugin-dir=/x", "v1.31.0"), ("osouthgate/promise", "-h"),
                          ("osouthgate/promise", "v1..2"), ("a b/c", "v1.31.0")):
            with self.subTest(repo=repo, ref=ref):
                (self.repo / ".claude").mkdir(exist_ok=True)
                (self.repo / ".claude" / "settings.json").write_text(json.dumps({"extraKnownMarketplaces": {
                    "promise": {"source": {"source": "github", "repo": repo, "ref": ref}}}}))
                self.assertEqual(self.run_machine(sha=self.new, version="1.31.0").returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_dry_run_and_no_claude_run_nothing(self) -> None:
        self.pin(ref="v1.31.0")
        self.commit()
        self.assertEqual(self.run_machine("--dry-run", sha=self.new, version="1.31.0").returncode, 0)
        self.assertEqual(self.run_machine(sha=self.new, version="1.31.0", path=str(self.tmp / "nobin")).returncode, 2)
        self.assertEqual(self.calls(), [])


class Wiring(unittest.TestCase):
    def test_pin_files_is_a_known_config_key(self) -> None:
        self.assertIn("pinFiles", orient.KNOWN_CONFIG_KEYS)

    def test_upgrade_is_inferred_only_for_promise_itself(self) -> None:
        for text, mode in (("upgrade", "upgrade"), ("upgrade promise", "upgrade"), ("upgrade to 1.31.1", "upgrade"),
                           ("bump the promise plugin", "upgrade"), ("update the promise pin", "upgrade"),
                           ("upgrade the checkout page", "new"), ("pin a message in a channel", "new"),
                           ("update the promise doc for billing", "new"), ("upgrade to React 19", "new"),
                           ("upgrade to postgres 16 in the api", "new"), ("upgrade 2.0 API", "new"),
                           ("upgrade now the checkout page", "new"), ("upgrade the plugin loader", "new"),
                           ("upgrade pins in the lockfile", "new"), ("upgrade the promise doc for checkout", "new"),
                           ("update promise docs for checkout", "new"), ("update our promise docs", "new"),
                           ("upgrade now", "upgrade"), ("upgrade the pin", "upgrade")):
            with self.subTest(text=text):
                self.assertEqual(orient.suggest_mode(text, [], None)[0], mode)

    def test_pr_mode_runs_the_check_and_says_not_checked(self) -> None:
        text = flat(SKILL / "modes" / "pr.md")
        self.assertIn("scripts/pin_check.py", text)
        self.assertIn("`Not checked: <pin_check.py's lines>`", text)

    def test_upgrade_mode_moves_pins_then_the_machine_then_adopts_from_the_new_release(self) -> None:
        text = flat(SKILL / "modes" / "upgrade.md")
        order = [text.index("`upgrade.py --to <tag> --sha <sha>`"), text.index('scripts/pin_machine.py"`. Exit 0'),
                 text.index('"<installPath>/skills/promise/scripts/adopt.py"')]
        self.assertEqual(order, sorted(order))
        self.assertIn("Never merge it.", text)
        self.assertIn("uninstall is refused", text)
        self.assertIn("a `source.sha` there pins nothing", text)

    def test_adopt_never_moves_a_pin(self) -> None:
        text = (SCRIPTS / "adopt.py").read_text(encoding="utf-8")
        for name in ("upgrade.py", "pin_machine", "extraKnownMarketplaces"):
            self.assertNotIn(name, text)

    def test_every_release_is_tagged(self) -> None:
        script = (HERE.parent / ".github" / "scripts" / "release.sh").read_text(encoding="utf-8")
        self.assertIn('git tag "$tag" "$commit"', script)
        self.assertIn("a release tag never moves", script)
        self.assertIn('=~ ^[0-9]+\\.[0-9]+\\.[0-9]+$', script)
        workflow = (HERE.parent / ".github" / "workflows" / "release-tags.yml").read_text(encoding="utf-8")
        self.assertIn("group: release-tags", workflow)

if __name__ == "__main__":
    unittest.main()
