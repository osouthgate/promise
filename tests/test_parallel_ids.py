"""Tests for row ids and merges across parallel branches (the starter map's reader).

Two branches that each add a row both used to take the same id from --next-id, and a
merge that kept one side of the conflict dropped the other side's row while --check
still passed. --next-id now skips every number another branch holds, and --check on a
merge commit finds a lost row, a lost leftOut entry and one id given to two rows.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

READER = Path(__file__).resolve().parents[1] / "skills" / "promise" / "templates" / "starter-map" / "capability_find.py"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def row(n: int, story: str) -> dict:
    return {"id": f"CAP-{n}", "title": story.rstrip("."), "story": story, "doc": None,
            "scenarios": [{"id": f"CAP-{n}.1", "at": None, "given": "a member", "when": "they act",
                           "then": "it happens", "altitude": "data"}],
            "tests": [], "e2eTests": [], "evalTests": [], "siblingTests": [], "verdict": "not-built"}


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class ParallelBranches(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        (self.root / "map").mkdir(parents=True)
        shutil.copy(READER, self.root / "map" / "capability_find.py")
        self.write([row(1, "A member mutes a channel.")])
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-qm", "map")

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True,
                              env={**os.environ, **GIT_ENV})

    def write(self, rows: list, left_out: list = None) -> None:
        data = {"version": 1, "rows": rows}
        if left_out is not None:
            data["leftOut"] = left_out
        (self.root / "map" / "map.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def reader(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.root / "map" / "capability_find.py"),
                               "--map", str(self.root / "map" / "map.json"), *args],
                              cwd=self.root, capture_output=True, text=True, env={**os.environ, **GIT_ENV})

    def branch_with(self, name: str, rows: list, left_out: list = None) -> None:
        self.git("checkout", "-q", "-b", name, "main")
        self.write(rows, left_out)
        self.git("commit", "-qam", name)
        self.git("checkout", "-q", "main")

    def test_next_id_skips_a_number_another_branch_holds(self) -> None:
        self.assertEqual(self.reader("--next-id").stdout.strip(), "CAP-2")
        self.branch_with("feat-a", [row(1, "A member mutes a channel."), row(2, "A muted channel shows no badge.")])
        proc = self.reader("--next-id")
        self.assertEqual(proc.stdout.strip(), "CAP-3")
        self.assertIn("skipped CAP-2 (feat-a): taken on another branch", proc.stderr)

    def test_a_merge_that_keeps_one_side_is_caught(self) -> None:
        base = [row(1, "A member mutes a channel.")]
        self.branch_with("feat-a", base + [row(2, "A muted channel shows no badge.")],
                         [{"test": "tests/a.py::x", "reason": "r", "date": "2026-01-01"}])
        self.branch_with("feat-b", base + [row(2, "An admin sees who muted what.")],
                         [{"test": "tests/b.py::y", "reason": "r", "date": "2026-01-01"}])
        self.git("checkout", "-q", "feat-a")
        merged = self.git("merge", "-q", "feat-b", "-m", "merge")
        self.assertNotEqual(merged.returncode, 0)  # the rows conflict on the same lines
        self.git("checkout", "--ours", "map/map.json")  # the usual reflex: take one side
        self.git("add", "map/map.json")
        before = self.reader("--check")  # resolved, not yet committed: the recipe's moment
        self.assertEqual(before.returncode, 1, before.stderr)
        self.assertIn("the merge lost row CAP-2 (An admin sees who muted what.)", before.stderr)
        self.git("commit", "-qm", "merge feat-b")
        proc = self.reader("--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("the merge lost row CAP-2 (An admin sees who muted what.)", proc.stderr)
        self.assertIn("the merge lost the leftOut entry for tests/b.py::y", proc.stderr)

    def test_a_merge_that_keeps_both_rows_under_one_id_is_caught_and_a_renumber_passes(self) -> None:
        base = [row(1, "A member mutes a channel.")]
        self.branch_with("feat-a", base + [row(2, "A muted channel shows no badge.")])
        self.branch_with("feat-b", base + [row(2, "An admin sees who muted what.")])
        self.git("checkout", "-q", "feat-a")
        self.git("merge", "-q", "feat-b", "-m", "merge")
        both = base + [row(2, "A muted channel shows no badge."), row(2, "An admin sees who muted what.")]
        self.write(both)
        self.git("commit", "-qam", "merge feat-b, both rows")
        proc = self.reader("--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("both sides of the merge gave CAP-2 to a new row", proc.stderr)
        self.write(base + [row(2, "A muted channel shows no badge."), row(3, "An admin sees who muted what.")])
        self.git("commit", "-qam", "renumber")  # a later commit: HEAD is no merge any more
        self.assertEqual(self.reader("--check").returncode, 0)
        self.git("reset", "-q", "--soft", "HEAD~1")  # the fix inside the merge commit itself
        self.git("commit", "-q", "--amend", "-am", "merge feat-b, renumbered")
        self.assertEqual(self.reader("--check").returncode, 0, self.reader("--check").stderr)

    def test_a_row_reworded_on_both_sides_is_not_lost(self) -> None:
        self.branch_with("feat-a", [row(1, "A member mutes one channel.")])
        self.branch_with("feat-b", [row(1, "A member silences a channel.")])
        self.git("checkout", "-q", "feat-a")
        self.git("merge", "-q", "feat-b", "-m", "merge")
        self.git("checkout", "--ours", "map/map.json")
        self.git("commit", "-qam", "merge feat-b, one wording")
        self.assertEqual(self.reader("--check").returncode, 0, self.reader("--check").stderr)

    def test_a_row_lost_when_main_was_merged_into_the_branch_is_caught_at_the_pull_requests_merge(self) -> None:
        base = [row(1, "A member mutes a channel.")]
        self.branch_with("feat-b", base + [row(2, "An admin sees who muted what.")])
        self.write(base + [row(2, "A muted channel shows no badge.")])
        self.git("commit", "-qam", "main gains CAP-2")
        self.git("checkout", "-q", "feat-b")
        self.git("merge", "-q", "main", "-m", "merge main")
        self.git("checkout", "--ours", "map/map.json")  # the branch keeps its side: main's row is gone
        self.git("commit", "-qam", "merge main into feat-b")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "feat-b", "-m", "merge feat-b")  # what CI checks: main + the branch
        proc = self.reader("--check")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("lost row CAP-2 (A muted channel shows no badge.)", proc.stderr)

    def test_a_row_reworded_while_merging_is_not_lost(self) -> None:
        self.branch_with("feat-b", [row(1, "A member mutes a channel."), row(2, "An admin sees.")])
        self.git("merge", "-q", "--no-commit", "--no-ff", "feat-b")
        self.write([row(1, "A member mutes a channel."), row(2, "An admin sees who muted what.")])
        self.assertEqual(self.reader("--check").returncode, 0, self.reader("--check").stderr)

    def test_a_row_removed_on_purpose_after_a_merge_is_no_loss_of_the_merges(self) -> None:
        self.branch_with("fa", [row(1, "A member mutes a channel."), row(2, "An admin sees.")])
        self.git("merge", "-q", "--no-ff", "fa", "-m", "merge fa")
        self.write([row(1, "A member mutes a channel.")])  # removed now, not by the merge
        self.assertEqual(self.reader("--check").returncode, 0, self.reader("--check").stderr)

    def test_a_duplicate_dropped_on_purpose_is_retired_and_its_number_never_comes_back(self) -> None:
        base = [row(1, "A member mutes a channel.")]
        self.branch_with("fa", base + [row(2, "A muted channel has no badge.")])
        self.branch_with("fb", base + [row(3, "No badge from a muted channel.")])
        self.git("checkout", "-q", "fa")
        self.git("merge", "-q", "fb", "-m", "merge")
        self.write(base + [row(2, "A muted channel has no badge.")])  # the duplicate dropped
        self.git("commit", "-qam", "merge fb, one row for the badge")
        proc = self.reader("--check")
        self.assertIn("or, dropped on purpose, list CAP-3 under retired with a reason", proc.stderr)
        data = json.loads((self.root / "map" / "map.json").read_text(encoding="utf-8"))
        data["retired"] = [{"id": "CAP-3", "reason": "same as CAP-2", "date": "2026-01-01"}]
        (self.root / "map" / "map.json").write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.reader("--check").returncode, 0, self.reader("--check").stderr)
        self.assertEqual(self.reader("--next-id").stdout.strip(), "CAP-4")
        data["retired"] = [{"id": "CAP-2", "reason": "x", "date": "2026-02-30"}]
        (self.root / "map" / "map.json").write_text(json.dumps(data), encoding="utf-8")
        bad = self.reader("--check").stderr
        self.assertIn("retired[0]: CAP-2 is retired and still a row", bad)
        self.assertIn("is not a real YYYY-MM-DD date", bad)

    def test_one_side_of_a_clash_dropped_on_purpose_is_retired_by_its_story(self) -> None:
        base = [row(1, "A member mutes a channel.")]
        self.branch_with("fa", base + [row(2, "A muted channel has no badge.")])
        self.branch_with("fb", base + [row(2, "No badge from a muted channel.")])
        self.git("checkout", "-q", "fa")
        self.git("merge", "-q", "fb", "-m", "merge")
        self.git("checkout", "--ours", "map/map.json")
        self.git("commit", "-qam", "merge fb, one badge row")
        self.assertIn("or, dropped on purpose, list its story under retired", self.reader("--check").stderr)
        data = json.loads((self.root / "map" / "map.json").read_text(encoding="utf-8"))
        data["retired"] = [{"story": "No badge from a muted channel.", "reason": "same as CAP-2", "date": "2026-01-01"}]
        (self.root / "map" / "map.json").write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.reader("--check").returncode, 0, self.reader("--check").stderr)

    def test_an_id_from_the_work_item_takes_the_next_free_letters_across_branches(self) -> None:
        self.assertEqual(self.reader("--next-id", "--from", "issue:1890").stdout.strip(), "CAP-i1890a")
        self.write([row(1, "A member mutes a channel."), dict(row(2, "Badge row."), id="CAP-i1890a")])
        self.git("commit", "-qam", "CAP-i1890a")
        self.assertEqual(self.reader("--next-id", "--from", "issue:1890").stdout.strip(), "CAP-i1890b")
        self.branch_with("other", [row(1, "A member mutes a channel."), dict(row(2, "Badge row."), id="CAP-i1890a"),
                                   dict(row(3, "Admin row."), id="CAP-i1890b")])
        self.assertEqual(self.reader("--next-id", "--from", "issue:1890").stdout.strip(), "CAP-i1890c")
        data = json.loads((self.root / "map" / "map.json").read_text(encoding="utf-8"))
        data["retired"] = [{"id": "CAP-i1890c", "reason": "dropped", "date": "2026-01-01"}]
        (self.root / "map" / "map.json").write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.reader("--next-id", "--from", "issue:1890").stdout.strip(), "CAP-i1890d")
        self.assertEqual(self.reader("--next-id", "--from", "pr:2091").stdout.strip(), "CAP-p2091a")
        self.assertEqual(self.reader("--next-id", "--from", "linear:ENG-421").stdout.strip(), "CAP-ENG-421a")
        self.assertEqual(self.reader("--next-id", "--from", "linear:ops-421").stdout.strip(), "CAP-OPS-421a")
        self.assertEqual(self.reader("--check").returncode, 0, self.reader("--check").stderr)
        for bad in ("issue:0", "jira:12", "issue:x", "linear:421", "linear:E-5"):  # Linear numbers each team apart
            with self.subTest(bad=bad):
                self.assertEqual(self.reader("--next-id", "--from", bad).returncode, 2)
        self.assertEqual(self.reader("--from", "issue:1").returncode, 2)

    def test_an_id_without_the_cap_prefix_is_told_how_to_rename(self) -> None:
        self.write([row(1, "A member mutes a channel."), dict(row(2, "Badge row."), id="i1890a")])  # 1.25's form
        proc = self.reader("--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("'i1890a' needs the CAP- prefix: rename it CAP-i1890a", proc.stderr)
        data = json.loads((self.root / "map" / "map.json").read_text(encoding="utf-8"))
        data["rows"][1]["id"] = "CAP-i1890b"
        data["rows"][1]["parent"] = "i1890c"
        data["retired"] = [{"id": "i1890a", "reason": "dropped", "date": "2026-01-01"}]
        (self.root / "map" / "map.json").write_text(json.dumps(data), encoding="utf-8")
        stderr = self.reader("--check").stderr
        self.assertIn("parent 'i1890c' is not a row id: 1.25's form, rename it CAP-i1890c", stderr)
        self.assertIn("'i1890a' is not a row id", stderr)
        self.assertIn("rename it CAP-i1890a", stderr)

    def test_every_row_id_starts_cap_so_everyday_words_are_no_rows_in_text(self) -> None:
        sys.path.insert(0, str(READER.parents[2] / "scripts"))
        import lint_github_text as lint  # noqa: PLC0415
        pattern = r"^CAP-(\d+|[ip]\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\d+[a-z]{1,2})$"
        text = ("adds GPT-4o, COVID-19s, i18n, i3wm and mid-90s; rows CAP-i1890a, CAP-ENG-421a, CAP-W3B-2b, "
                "CAP-p2091a and CAP-3, UTF-8")
        found = [m.group(0) for m in lint.row_pattern(pattern, None).finditer(text)]
        self.assertEqual(found, ["CAP-i1890a", "CAP-ENG-421a", "CAP-W3B-2b", "CAP-p2091a", "CAP-3"])

    def test_orient_reads_a_row_in_every_form_and_none_in_an_everyday_word(self) -> None:
        orient = READER.parents[2] / "scripts" / "orient.py"
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "promise.config.json").write_text(json.dumps({"map": {
            "find": 'python3 "tools/capability_find.py" --map map/map.json',
            "rowIdPattern": r"^CAP-(\d+|[ip]\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\d+[a-z]{1,2})$"}}), encoding="utf-8")

        def reasons(text: str) -> str:
            proc = subprocess.run([sys.executable, str(orient), "--cwd", str(self.root), "--input", text],
                                  capture_output=True, text=True)
            return json.dumps(json.loads(proc.stdout).get("modeCandidates", json.loads(proc.stdout)))

        for words in ("switch the summary to GPT-4o for the mid-90s archive", "switch the tiling to i3wm"):
            with self.subTest(words=words):
                self.assertNotIn("matches map.rowIdPattern", reasons(words))
        for text in ("CAP-i1890a still fails", "CAP-ENG-421a still fails", "cap-3 is wrong"):
            with self.subTest(text=text):
                self.assertIn("matches map.rowIdPattern", reasons(text))

    def test_a_project_still_on_1_25s_form_is_warned_and_reads_no_word_as_a_row(self) -> None:
        sys.path.insert(0, str(READER.parents[2] / "scripts"))
        sys.path.insert(0, str(READER.parent))
        import capability_find as cf  # noqa: PLC0415
        import lint_github_text as lint  # noqa: PLC0415
        old = r"^(?!(?:i18n|p2p|i2c)$)(CAP-\d+|[ip]\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\d+[a-z]{1,2})$"  # 1.25's
        # a row 1.25 wrote holds its letters until renamed, on this branch or another
        self.assertEqual(cf.next_id_from("issue:1890", {"i1890a"}), "CAP-i1890b")
        found = [m.group(0) for m in lint.row_pattern(old, None).finditer("GPT-4o, i3wm, i1890a and CAP-3")]
        self.assertEqual(found, ["CAP-3"])
        orient = READER.parents[2] / "scripts" / "orient.py"
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "promise.config.json").write_text(json.dumps({"map": {
            "find": 'python3 "tools/capability_find.py" --map map/map.json', "rowIdPattern": old}}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(orient), "--cwd", str(self.root), "--input",
                               "Make the GPT-4o summary shorter"], capture_output=True, text=True)
        data = json.loads(proc.stdout)
        self.assertNotIn("matches map.rowIdPattern", json.dumps(data.get("modeCandidates", data)))
        self.assertIn("without the CAP- prefix", " ".join(data["warnings"]))
        # a project's own scheme is its own: no guard, no warning
        found = [m.group(0) for m in lint.row_pattern(r"^[A-Z][A-Z0-9]+-\d+[a-z]?$", {"WEB-12", "WEB-12a"}).finditer(
            "see WEB-12 and WEB-12a")]
        self.assertEqual(found, ["WEB-12", "WEB-12a"])
        (self.root / ".claude" / "promise.config.json").write_text(json.dumps({"map": {
            "find": 'python3 "tools/capability_find.py" --map map/map.json',
            "rowIdPattern": r"^[A-Z][A-Z0-9]+-\d+[a-z]?$"}}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(orient), "--cwd", str(self.root), "--input",
                               "WEB-12a still fails"], capture_output=True, text=True)
        data = json.loads(proc.stdout)
        self.assertIn("matches map.rowIdPattern", json.dumps(data.get("modeCandidates", data)))
        self.assertNotIn("without the CAP- prefix", " ".join(data["warnings"]))

    def test_letters_run_past_z(self) -> None:
        sys.path.insert(0, str(READER.parent))
        import capability_find as cf  # noqa: PLC0415
        self.assertEqual([cf.letters(n) for n in (0, 25, 26, 27, 51, 52, 701, 702)],
                         ["a", "z", "aa", "ab", "az", "ba", "zz", "aaa"])
        self.assertEqual(cf.next_id_from("issue:5", {f"CAP-i5{cf.letters(n)}" for n in range(26)}), "CAP-i5aa")
        # a row deleted without being retired never gives its id to another row
        self.assertEqual(cf.next_id_from("issue:7", {"CAP-i7a", "CAP-i7c"}), "CAP-i7d")
        # with the prefix, no id is a word: issue 2's third row is CAP-i2c
        self.assertEqual(cf.next_id_from("issue:2", {"CAP-i2a", "CAP-i2b"}), "CAP-i2c")
        with self.assertRaises(ValueError):
            cf.next_id_from("issue:5", {f"CAP-i5{cf.letters(n)}" for n in range(702)})

    def test_outside_git_next_id_and_check_work_as_before(self) -> None:
        shutil.rmtree(self.root / ".git")
        self.assertEqual(self.reader("--next-id").stdout.strip(), "CAP-2")
        self.assertEqual(self.reader("--check").returncode, 0)


if __name__ == "__main__":
    unittest.main()
