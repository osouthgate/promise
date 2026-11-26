"""Tests for session_report.py: what a session did with promise, as facts, and a scrub
check for a draft that leaves the project.

A transcript is Claude Code's session file: one JSON record per line, tool calls in the
assistant's message and their results in the next user record. The report counts; the
retro mode judges.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "promise" / "scripts" / "session_report.py"


def run(*args: str, cwd: Path, env: dict = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=str(cwd),
                          env={**os.environ, **(env or {})})


def use(n: int, name: str, **args) -> dict:
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{n}", "name": name,
                                                           "input": args}]}}


def result(n: int, text: str = "ok", error: bool = False) -> dict:
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{n}",
                                                     "content": text, "is_error": error}]}}


SHEET = "python3 .cache/promise/abc/skills/promise/scripts/decisions.py sheet --out s.html --md out/decisions-blocking.md"
SESSION = [
    {"type": "user", "origin": {"kind": "human"}, "message": {"content": "answer the open questions"}},
    use(1, "Bash", command=SHEET), result(1, "Exit code 2\ndecisions.py: the sheet leans on …", error=True),
    use(2, "Bash", command=SHEET), result(2, "promise decisions: 12 items"),
    use(3, "Bash", command="cat .cache/promise/abc/skills/promise/references/quickstart.md"), result(3),
    use(4, "Bash", command='git commit -m "decisions.py embeds the sheet"'), result(4),
    use(5, "Write", file_path="docs/muting.md", content="Q1 — owner: A — BLOCKING: which tiers?\nAnswer (2026-01-01): all\n"),
    result(5),
    use(6, "Write", file_path="tools/decisions.py", content="# rebuilt from the promise repo\n"), result(6),
    use(12, "Edit", file_path="docs/muting.md", old_string="which tiers?", new_string="which tiers?\nAnswer (2026-01-02): paid"),
    result(12),
    use(13, "Write", file_path="tools/check.py", content="# the project's own check\n"), result(13),
    use(14, "Bash", command="python3 tools/check.py --all"), result(14),
    use(25, "Bash", command="/usr/bin/python3.12 .cache/skills/promise/scripts/decisions.py apply a.json"), result(25),
    use(26, "Bash", command='cd "${CLAUDE_SKILL_DIR}" && python3 scripts/decisions.py apply b.json'), result(26),
    use(27, "Bash", command='cd "${CLAUDE_SKILL_DIR}/scripts" && python3 decisions.py apply c.json'), result(27),
    use(28, "Bash", command="cd tools && python3 decisions.py apply d.json"), result(28),
    use(22, "Bash", command="python3 -m py_compile a.py skills/promise/scripts/decisions.py"), result(22),
    use(23, "Bash", command="cp x.py skills/promise/scripts/decisions.py"), result(23),
    use(24, "Bash", command='python3 - <<EOF\np = Path("skills/promise/scripts/decisions.py")\nEOF'), result(24),
    use(15, "Bash", command="make test"), result(15, "Exit code 1\nfailed", error=True),
    use(16, "Bash", command="make test"), result(16),
    use(17, "Bash", command="make test"), result(17),
    use(18, "mcp__acme-billing__search", query="x"), result(18),
    use(7, "SendUserFile", files=["out/decisions-blocking.md", "out/notes.txt", "docs/decisions.md"]), result(7),
    use(19, "Bash", command='cat "${CLAUDE_SKILL_DIR}/references/decision-sheet.md"'), result(19),
    use(8, "Bash", command="ls"), result(8), use(9, "Bash", command="ls"), result(9),
    use(10, "Bash", command="ls"), result(10),
    use(11, "Edit", file_path="docs/muting.md", old_string="Answer (2026-01-01): all", new_string="Answer (2026-01-01): all tiers"),
    result(11),
    {"type": "cost-state", "totalCostUSD": 1.5},
    "not json at all",
]


class SessionReport(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.transcript = self.root / "session.jsonl"
        self.transcript.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in SESSION) + "\n",
                                   encoding="utf-8")

    def report(self, *args: str) -> dict:
        proc = run(str(self.transcript), "--json", *args, cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_scripts_runs_failures_and_retries(self) -> None:
        r = self.report()
        self.assertEqual((r["turns"], r["costUSD"]), (1, 1.5))
        self.assertEqual(r["promise"]["scripts"], [
            {"script": "decisions.py", "sub": "apply", "runs": 3, "failed": 0, "exitCodes": {"0": 3}},
            {"script": "decisions.py", "sub": "sheet", "runs": 2, "failed": 1, "exitCodes": {"0": 1, "2": 1}}])
        # "make test" passed on its second run: its third is no retry
        self.assertEqual(r["promise"]["retries"], [{"command": SHEET, "times": 1}, {"command": "make test", "times": 1}])

    def test_what_was_read_and_what_never_was(self) -> None:
        r = self.report()
        self.assertFalse(r["promise"]["skillLoaded"])
        self.assertEqual(r["promise"]["read"], ["references/decision-sheet.md", "references/quickstart.md"])
        self.assertEqual(r["promise"]["notRead"], ["SKILL.md"])

    def test_each_signal_is_counted(self) -> None:
        signals = {s["kind"]: s for s in self.report()["signals"]}
        self.assertEqual(sorted(signals), ["hand-answers", "no-skill", "rebuilt-script", "repeated-command",
                                           "script-refused", "sheet-files-sent", "sheet-not-published"])
        # the Edit that adds an Answer line; not the whole-file Write, not the edit that rewords one
        self.assertEqual(signals["hand-answers"]["count"], 1)
        self.assertEqual(signals["sheet-files-sent"]["detail"], ["out/decisions-blocking.md"])
        self.assertEqual(signals["rebuilt-script"]["detail"], ["tools/decisions.py"])  # not the project's check.py
        self.assertEqual(signals["repeated-command"]["detail"], [{"command": "ls", "times": 3},
                                                                  {"command": "make test", "times": 3}])

    def test_a_published_page_and_a_loaded_skill_clear_their_signals(self) -> None:
        extra = [use(20, "Skill", skill="promise"), result(20),
                 use(21, "Artifact", file_path="/tmp/s.html", capabilities={"db": {}}), result(21)]
        with self.transcript.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r) for r in extra) + "\n")
        kinds = {s["kind"] for s in self.report()["signals"]}
        self.assertNotIn("no-skill", kinds)
        self.assertNotIn("sheet-not-published", kinds)

    def test_the_decision_pane_counts_as_the_sheet_published(self) -> None:
        refused = [use(21, "mcp__promise__decision_pane", sheet="/tmp/nope.json"),
                   result(21, "/tmp/nope.json is not a promise sheet", error=True)]
        with self.transcript.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r) for r in refused) + "\n")
        self.assertIn("sheet-not-published", {s["kind"] for s in self.report()["signals"]},
                      "a call the mod refused showed the human nothing")
        base = self.transcript.read_text(encoding="utf-8")
        for text, shown in (("The sheet has no items: nothing is waiting on the person.", False),
                            ("The decision pane is waiting for a wider terminal (narrow); …", True),
                            ("The decision pane is open with 3 decisions. End your turn now …", True)):
            pane = [use(22, "mcp__promise__decision_pane", sheet="/tmp/sheet.json"), result(22, text)]
            self.transcript.write_text(base + "\n".join(json.dumps(r) for r in pane) + "\n", encoding="utf-8")
            signals = {s["kind"] for s in self.report()["signals"]}
            self.assertEqual("sheet-not-published" not in signals, shown, text)

    def test_the_pane_and_the_report_spell_its_result_and_name_alike(self) -> None:
        module = (SCRIPT.parents[3] / "hooks" / "decisions-pane.js").read_text(encoding="utf-8")
        sys.path.insert(0, str(SCRIPT.parent))
        import session_report
        self.assertIn(f"const PANE_SHOWN = '{session_report.PANE_SHOWN}'", module)
        self.assertIn(f"const TOOL = '{session_report.PANE_TOOL}'", module)

    def test_a_typed_slash_command_loads_the_skill_and_costs_add_up(self) -> None:
        typed = {"type": "user", "message": {"content": "<command-name>/promise</command-name> fix the doc"}}
        with self.transcript.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(typed) + "\n")
        second = self.root / "second.jsonl"
        second.write_text(json.dumps({"type": "cost-state", "totalCostUSD": 2.25}) + "\n", encoding="utf-8")
        r = json.loads(run(str(self.transcript), str(second), "--json", cwd=self.root).stdout)
        self.assertTrue(r["promise"]["skillLoaded"])
        self.assertEqual(r["costUSD"], 3.75)

    def test_scrub_drops_commands_and_project_paths(self) -> None:
        text = json.dumps(self.report("--scrub"))
        for leak in ("docs/muting.md", "tools/", "out/", "git commit", ".cache", "session.jsonl", "acme"):
            self.assertNotIn(leak, text)
        self.assertIn("decisions.py", text)
        self.assertIn("mcp (connector)", text)

    def test_the_newest_transcript_of_the_project_is_found(self) -> None:
        home = self.root / "home"
        project = self.root / "my.project"
        project.mkdir()
        folder = home / "projects" / ("".join(c if c.isalnum() else "-" for c in str(project)))
        folder.mkdir(parents=True)
        (folder / "old.jsonl").write_text("", encoding="utf-8")
        os.utime(folder / "old.jsonl", (1, 1))
        (folder / "new.jsonl").write_text(self.transcript.read_text(encoding="utf-8"), encoding="utf-8")
        proc = run("--cwd", str(project), "--json", cwd=self.root, env={"CLAUDE_CONFIG_DIR": str(home)})
        self.assertEqual(json.loads(proc.stdout)["transcripts"], ["new.jsonl"])
        missing = run("--cwd", str(self.root), cwd=self.root, env={"CLAUDE_CONFIG_DIR": str(home)})
        self.assertEqual(missing.returncode, 2)
        self.assertIn("no session transcripts", missing.stderr)


RECORD = 'python3 "${CLAUDE_SKILL_DIR}/scripts/session_report.py" --record'


class RecordedRuns(unittest.TestCase):
    """Each run records its size, stops and close-out counts; the report reads them back
    from the transcript and sums them."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def report(self, *records: dict, args: tuple = ()) -> dict:
        path = self.root / "runs.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        proc = run(str(path), "--json", *args, cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_record_checks_its_flags_and_writes_nothing(self) -> None:
        ok = run("--record", "--size", "tiny", "--reason", "copy change", "--stop", "first-command",
                 "--decided", "2", cwd=self.root)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("recorded a tiny run, mode none, 1 stops", ok.stdout)
        self.assertEqual(list(self.root.iterdir()), [])
        for bad in (["--size", "huge"], ["--size", "tiny", "--stop", "question"], ["--size", "small", "--decided", "-1"],
                    []):
            proc = run("--record", *bad, cwd=self.root)
            self.assertEqual(proc.returncode, 2, bad)
            self.assertIn("session_report.py:", proc.stderr)

    def test_a_feature_size_is_recorded_as_capability(self) -> None:
        ok = run("--record", "--size", "feature", "--reason", "a new job", cwd=self.root)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("recorded a capability run", ok.stdout)
        r = self.report(use(1, "Bash", command=RECORD + " --size feature --mode new"), result(1))
        self.assertEqual(r["runs"][0]["size"], "capability")
        self.assertEqual(r["runTotals"]["bySize"], {"capability": 1})

    def test_runs_are_read_back_and_summed(self) -> None:
        r = self.report(
            use(1, "Bash", command=RECORD + ' --size tiny --reason "copy change; keeps CAP-12" --mode none'), result(1),
            use(2, "Bash", command=RECORD + " --size capability --reason 'a new job' --mode new --stop first-command "
                                            "--stop checkpoint --stop checkpoint --needs-you 2 --decided 5 "
                                            "--not-checked 1 && ls"), result(2),
            use(3, "Bash", command=RECORD + " --size small --mode revise --stop no-outcome --decided 1"), result(3),
            use(4, "Bash", command=RECORD + " --size huge"), result(4, "Exit code 2", error=True),  # refused: no run
            use(5, "Bash", command="echo session_report.py --record --size tiny"), result(5))  # not a run of it
        self.assertEqual(r["runs"][0], {"size": "tiny", "reason": "copy change; keeps CAP-12", "mode": None,
                                        "stops": {}, "needsYou": 0, "decidedForYou": 0, "notChecked": 0})
        self.assertEqual(r["runs"][1]["stops"], {"first-command": 1, "checkpoint": 2})
        self.assertEqual(r["runTotals"], {"runs": 3, "bySize": {"tiny": 1, "small": 1, "capability": 1},
                                          "stops": {"first-command": 1, "checkpoint": 2, "no-outcome": 1},
                                          "stopsTotal": 4, "needsYou": 2, "decidedForYou": 6, "notChecked": 1})
        self.assertEqual(r["promise"]["scripts"], [])  # recording is not a promise script run

    def test_scrub_drops_the_reason_and_the_summary_names_each_run(self) -> None:
        rec = (use(1, "Bash", command=RECORD + " --size tiny --reason 'acme billing copy'"), result(1))
        scrubbed = self.report(*rec, args=("--scrub",))
        self.assertIsNone(scrubbed["runs"][0]["reason"])
        self.assertNotIn("acme", json.dumps(scrubbed))
        path = self.root / "runs.jsonl"
        text = run(str(path), cwd=self.root).stdout
        self.assertIn("run: tiny (acme billing copy), mode none; stops: none", text)
        self.assertIn("runs: 1 (tiny 1); 0 stops", text)
        # a mode that is not one of the skill's is free text too
        rec = (use(1, "Bash", command=RECORD + " --size small --mode acme-billing"), result(1),
               use(2, "Bash", command=RECORD + " --size small --mode revise"), result(2))
        scrubbed = self.report(*rec, args=("--scrub",))
        self.assertEqual([r["mode"] for r in scrubbed["runs"]], ["other", "revise"])
        self.assertNotIn("acme", json.dumps(scrubbed))

    def test_a_session_with_no_record_has_no_runs(self) -> None:
        r = self.report(use(1, "Bash", command="ls"), result(1))
        self.assertEqual((r["runs"], r["runTotals"]["runs"]), ([], 0))


class ScrubCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "acme-portal"
        (self.root / "billing-engine").mkdir(parents=True)
        (self.root / "src").mkdir()
        (self.root / "templates").mkdir()  # a word promise uses too

    def check(self, text: str) -> subprocess.CompletedProcess:
        (self.root.parent / "draft.md").write_text(text, encoding="utf-8")
        return run("--scrub-check", str(self.root.parent / "draft.md"), "--cwd", str(self.root), "--json", cwd=self.root)

    def test_a_draft_that_names_the_project_is_refused_with_each_reason(self) -> None:
        proc = self.check("In acme-portal the billing-engine sheet (see src/billing/plan.ts and #87) went to "
                          "https://github.com/acme/portal/issues/3; ask ops@acme.io.")
        self.assertEqual(proc.returncode, 1)
        found = " ".join(json.loads(proc.stdout)["found"])
        for part in ("'acme-portal'", "'billing-engine'", "'src/billing/plan.ts': a path outside the skill",
                     "'#87'", "'https://github.com/acme/portal/issues/3': a link outside the promise repository",
                     "'ops@acme.io'"):
            self.assertIn(part, found)

    def test_a_project_path_that_looks_like_the_skills_and_other_links_are_caught(self) -> None:
        found = " ".join(json.loads(self.check("See other/portal#87, billing/scripts/export_customers.py and "
                                                "https://gitlab.acme.io/x/y and https://jira.acme.io/X-1.").stdout)["found"])
        for part in ("'other/portal#87': another repository's issue", "'billing/scripts/export_customers.py': a path outside the skill", "gitlab.acme.io",
                     "jira.acme.io"):
            self.assertIn(part, found)

    def test_absolute_paths_are_caught_even_to_a_promise_file(self) -> None:
        found = " ".join(json.loads(self.check(
            "It read /home/alice/acme/src/billing.py, ~/work/clientco/notes.txt, "
            "/Users/bob/clientco/skills/promise/SKILL.md and C:\\Users\\carol\\x.md.").stdout)["found"])
        for part in ("'/home/alice/acme/src/billing.py': an absolute path", "'~/work/clientco/notes.txt'",
                     "'/Users/bob/clientco/skills/promise/SKILL.md'", "C:\\Users"):
            self.assertIn(part, found)

    def test_a_proposed_new_skill_file_is_clean(self) -> None:
        self.assertEqual(self.check("Add skills/promise/scripts/sheet_guard.py and a line in "
                                    "skills/promise/references/decision-sheet.md; the run key in "
                                    ".claude/promise.config.json and the version in .claude-plugin/plugin.json "
                                    "stay; run ${CLAUDE_SKILL_DIR}/scripts/decisions.py, read "
                                    "skills/promise/outcome-framework.md and agents/openai.yaml, and see "
                                    "<https://github.com/osouthgate/promise>.").returncode, 0)

    def test_a_project_folder_named_like_a_common_word_is_not_a_project_name(self) -> None:
        api = Path(self.tmp.name) / "api"
        api.mkdir()
        (Path(self.tmp.name) / "d.md").write_text("The api sheet sent a file.", encoding="utf-8")
        proc = run("--scrub-check", str(Path(self.tmp.name) / "d.md"), "--cwd", str(api), cwd=api)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_generic_draft_is_clean(self) -> None:
        proc = self.check("An agent with no skill loaded sent the sheet's .md file instead of publishing it. "
                          "decisions.py sheet printed its next step; references/decision-sheet.md §2 has the rule, "
                          "and skills/promise/templates/decision-sheet.html draws it. "
                          "See https://github.com/osouthgate/promise/blob/main/README.md.")
        self.assertEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
