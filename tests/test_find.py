"""Tests for the starter map's reader as a finder: BM25 `find`, row titles, `--eval`.

`find` is how an agent answers "is there a promise for this?", so it is held to a
fixture of real-looking work items in the engineer's words (examples/minimap/
find-eval.json), and to the substring scorer it replaced: it must do at least as
well there, and better on one case.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
READER = REPO / "skills" / "promise" / "templates" / "starter-map" / "capability_find.py"
MINIMAP = REPO / "examples" / "minimap"
# The example map as it stood with three rows: a fixture for find, learn and refs, whose
# ranks and misses these tests pin; the example itself may change shape.
THREE_ROWS = Path(__file__).resolve().parent / "fixtures" / "find" / "three-rows"


def run(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(READER), *args], capture_output=True, text=True, cwd=str(cwd))


def old_find(rows, query):
    """The substring scorer `find` used before BM25, kept here as the baseline."""
    def text(row):
        parts = [row.get("id", ""), row.get("story", "")] + list(row.get("aliases", [])) + list(row.get("surfaces", []))
        for s in row.get("scenarios", []):
            parts.extend(str(s.get(k, "")) for k in ("given", "when", "then"))
        return " ".join(parts).lower()
    wanted = sorted(set(re.findall(r"[a-z0-9#]+", query.lower())))
    ranked = []
    for pos, row in enumerate(rows):
        body = text(row)
        score = sum(1 for t in wanted if t in body)
        if score:
            ranked.append((-score, -sum(body.count(t) for t in wanted), pos, row["id"]))
    return [r[3] for r in sorted(ranked)]


class Ranking(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.map = Path(self.tmp.name) / "map.json"

    def row(self, rid, story, **extra):
        base = {"id": rid, "story": story, "doc": None,
                "scenarios": [{"id": rid + ".1", "at": None, "given": "Ana is signed in", "when": "she acts",
                               "then": "it works", "altitude": "data"}],
                "tests": [], "e2eTests": [], "evalTests": [], "siblingTests": [], "verdict": "not-built"}
        base.update(extra)
        return base

    def find(self, rows, query):
        self.map.write_text(json.dumps({"version": 1, "rows": rows}), encoding="utf-8")
        proc = run("--map", str(self.map), query)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_stopwords_never_match(self) -> None:
        rows = [self.row("CAP-1", "A member mutes a channel."), self.row("CAP-2", "The member is in the list.")]
        self.assertEqual(self.find(rows, "the a i is of"), [])

    def test_stems_meet(self) -> None:
        rows = [self.row("CAP-1", "A member exports notes."), self.row("CAP-2", "A member mutes a channel.")]
        for query in ("muting", "muted channels", "mute"):
            with self.subTest(query=query):
                self.assertEqual(self.find(rows, query)[0]["id"], "CAP-2")

    def test_rare_word_outranks_common_word(self) -> None:
        rows = [self.row("CAP-1", "A member reads a channel."), self.row("CAP-2", "A member reads a channel digest."),
                self.row("CAP-3", "A member reads a channel topic.")]
        hits = self.find(rows, "channel digest")
        self.assertEqual(hits[0]["id"], "CAP-2")
        self.assertTrue(hits[0]["why"].startswith("shared words: digest, channel"), hits[0]["why"])

    def test_title_finds_the_row(self) -> None:
        rows = [self.row("CAP-1", "A member reads a channel."),
                self.row("CAP-2", "A member stops a channel from notifying them.", title="Silence a noisy room")]
        self.assertEqual(self.find(rows, "silence a room")[0]["id"], "CAP-2")

    def test_naming_a_row_puts_it_first(self) -> None:
        rows = [self.row("CAP-1", "A member mutes a channel."), self.row("CAP-2", "A member mutes a channel.", aliases=["J4"])]
        hits = self.find(rows, "does CAP-2 cover muting")
        self.assertEqual(hits[0]["id"], "CAP-2")
        self.assertTrue(hits[0]["why"].startswith("names this row"))
        self.assertEqual(self.find(rows, "j4")[0]["id"], "CAP-2")
        self.assertNotIn("CAP-1", [h["id"] for h in self.find(rows, "CAP-10")[:1]])

    def test_the_word_learn_is_a_query(self) -> None:
        rows = [self.row("CAP-1", "A member learns to mute a channel.")]
        self.assertEqual([h["id"] for h in self.find(rows, "learn")], ["CAP-1"])

    def test_a_row_with_no_id_does_not_break_eval_or_learn(self) -> None:
        rows = [self.row("CAP-1", "A member mutes a channel."), {"story": "A member mutes a channel too."}]
        self.map.write_text(json.dumps({"version": 1, "rows": rows}), encoding="utf-8")
        fixture = Path(self.tmp.name) / "f.json"
        fixture.write_text(json.dumps([{"text": "mute a channel", "row": "CAP-1"}]), encoding="utf-8")
        proc = run("--map", str(self.map), "--eval", str(fixture))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        q = Path(self.tmp.name) / "q.txt"
        q.write_text("silence the channel", encoding="utf-8")
        proc = run("learn", "--map", str(self.map), "--query-file", str(q), "--row", "CAP-1", "--source", "person")
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(proc.returncode, (0, 1))

    def test_check_warns_on_a_missing_title_and_fails_on_a_bad_one(self) -> None:
        self.map.write_text(json.dumps({"version": 1, "rows": [self.row("CAP-1", "A story.")]}), encoding="utf-8")
        proc = run("--map", str(self.map), "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("warning: CAP-1: no title", proc.stderr)
        self.assertIn("1 rows, 0 problems, 1 warnings", proc.stdout)
        for bad in ("", "two\nlines", 5):
            with self.subTest(title=bad):
                self.map.write_text(json.dumps({"version": 1, "rows": [self.row("CAP-1", "A story.", title=bad)]}),
                                    encoding="utf-8")
                proc = run("--map", str(self.map), "--check")
                self.assertEqual(proc.returncode, 1)
                self.assertIn("CAP-1: title must be one non-empty line", proc.stderr)


class Eval(unittest.TestCase):
    def evaluate(self, *args: str) -> dict:
        proc = run("--map", str(THREE_ROWS / "map.json"), "--eval", *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_bm25_beats_the_old_scorer_on_the_minimap_fixture(self) -> None:
        rows = json.loads((THREE_ROWS / "map.json").read_text(encoding="utf-8"))["rows"]
        cases = json.loads((THREE_ROWS / "find-eval.json").read_text(encoding="utf-8"))["cases"]
        old_top1 = sum(1 for c in cases if old_find(rows, c["text"])[:1] == [c["row"]]) / len(cases)
        result = self.evaluate()
        self.assertEqual(result["cases"], len(cases))
        self.assertGreater(result["top1"], old_top1)
        self.assertEqual(result["top5"], 1.0)

    def test_fixture_path_bad_fixture_and_circular_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "f.json"
            fixture.write_text(json.dumps([{"text": "stop a channel notifying me", "row": "CAP-1"}]), encoding="utf-8")
            self.assertEqual(self.evaluate(str(fixture))["top1"], 1.0)
            fixture.write_text(json.dumps({"cases": [{"text": ""}]}), encoding="utf-8")
            self.assertEqual(run("--map", str(THREE_ROWS / "map.json"), "--eval", str(fixture)).returncode, 2)
            rows = json.loads((THREE_ROWS / "map.json").read_text(encoding="utf-8"))["rows"]
            rows[0]["asks"] = [{"text": "Mute a room", "source": "person", "date": "2026-01-02"}]
            mapfile = Path(tmp) / "map.json"
            mapfile.write_text(json.dumps({"version": 1, "rows": rows}), encoding="utf-8")
            fixture.write_text(json.dumps([{"text": "mute a room", "row": "CAP-1"},
                                           {"text": "unmute a channel", "row": "CAP-1"}]), encoding="utf-8")
            proc = run("--map", str(mapfile), "--eval", str(fixture))
            result = json.loads(proc.stdout)
            self.assertEqual((result["cases"], result["leftOutAsAsks"]), (1, 1))

    def test_the_minimap_passes_its_own_check(self) -> None:
        proc = subprocess.run([sys.executable, "capability_find.py", "--check"], capture_output=True, text=True,
                              cwd=str(MINIMAP))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("warning", proc.stderr)


class Learn(unittest.TestCase):
    """`learn` records the words `find` missed a row by, and keeps them only when they help."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.map = self.dir / "map.json"
        rows = json.loads((THREE_ROWS / "map.json").read_text(encoding="utf-8"))["rows"]
        for r in rows:
            r["doc"] = None
        self.write(rows)

    def write(self, rows, **top) -> None:
        self.map.write_text(json.dumps({"version": 1, "rows": rows, **top}, indent=2), encoding="utf-8")

    def rows(self):
        return json.loads(self.map.read_text(encoding="utf-8"))["rows"]

    def learn(self, text, row="CAP-2", source="pr:acme/chat#12", *extra):
        q = self.dir / "q.txt"
        q.write_text(text, encoding="utf-8")
        return run("learn", "--map", str(self.map), "--query-file", str(q), "--row", row, "--source", source,
                   "--date", "2026-03-01", *extra)

    def find(self, query):
        return json.loads(run("--map", str(self.map), query).stdout)

    MISSED = "Ben stops getting pushes after Ana mutes"

    def test_a_miss_is_learned_and_then_found_first(self) -> None:
        self.assertEqual(self.find(self.MISSED)[0]["id"], "CAP-1")
        proc = self.learn(self.MISSED)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"learned": True, "row": "CAP-2", "rankBefore": 2, "rankAfter": 1})
        cap2 = [r for r in self.rows() if r["id"] == "CAP-2"][0]
        self.assertEqual(cap2["asks"], [{"text": self.MISSED, "source": "pr:acme/chat#12", "date": "2026-03-01"}])
        hits = self.find("ben stopped getting a push after ana muted")
        self.assertEqual(hits[0]["id"], "CAP-2")
        self.assertIn("repeats a past ask", hits[0]["why"])
        check = run("--map", str(self.map), "--check")
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertNotIn("ask conflict", check.stderr)

    def test_nothing_is_learned_when_the_row_is_already_first(self) -> None:
        before = self.map.read_bytes()
        proc = self.learn("see which channels are muted", row="CAP-3")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["reason"], "find already ranks this row first")
        self.assertEqual(self.map.read_bytes(), before)

    def test_private_words_and_bad_input_are_refused(self) -> None:
        before = self.map.read_bytes()
        for text in ("ana@example.com says pushes keep coming", "@ben says pushes keep coming"):
            with self.subTest(text=text):
                self.assertEqual(self.learn(text).returncode, 2)
        self.assertEqual(self.learn(self.MISSED, source="slack").returncode, 2)
        self.assertEqual(self.learn(self.MISSED, row="nope").returncode, 2)
        self.assertEqual(self.learn(self.MISSED, row="CAP-99").returncode, 2)
        self.assertEqual(self.learn("x" * 301).returncode, 2)
        self.assertEqual(self.map.read_bytes(), before)

    def test_a_near_duplicate_is_skipped(self) -> None:
        self.learn(self.MISSED)
        rows = self.rows()
        for r in rows:  # CAP-1 holds the same words and outranks CAP-2, so CAP-2 is not first
            if r["id"] == "CAP-1":
                r["asks"] = [{"text": self.MISSED, "source": "person", "date": "2026-03-02"}]
        self.write(rows)
        self.assertEqual(self.find(self.MISSED)[0]["id"], "CAP-1")
        proc = self.learn("Ben stops getting pushes after Ana mutes!")
        self.assertIn("near-duplicate", json.loads(proc.stdout)["reason"])
        self.assertEqual(len([r for r in self.rows() if r["id"] == "CAP-2"][0]["asks"]), 1)

    def test_a_full_row_drops_its_oldest_ask(self) -> None:
        rows = self.rows()
        asks = [{"text": f"old wording number {w}", "source": "person", "date": f"2026-01-0{n + 1}"}
                for n, w in enumerate(["one", "two", "three", "four", "five"])]
        asks[0], asks[3] = asks[3], asks[0]  # the oldest is not the first in the list
        for r in rows:
            if r["id"] == "CAP-2":
                r["asks"] = asks
        self.write(rows)
        proc = self.learn(self.MISSED)
        result = json.loads(proc.stdout)
        self.assertTrue(result["learned"], proc.stdout)
        self.assertEqual(result["dropped"]["date"], "2026-01-01")
        kept = [r for r in self.rows() if r["id"] == "CAP-2"][0]["asks"]
        self.assertEqual(len(kept), 5)
        self.assertEqual(kept[-1]["text"], self.MISSED)

    def test_an_ask_that_does_not_help_comes_out_again(self) -> None:
        crowd = [dict(json.loads((THREE_ROWS / "map.json").read_text(encoding="utf-8"))["rows"][0],
                      id=f"CAP-{n}", doc=None, title="alpha beta gamma", story="alpha beta gamma alpha beta gamma")
                 for n in range(1, 6)]
        target = dict(crowd[0], id="CAP-6", title="Export a note to a file",
                      story="A member exports a long note to a file they can keep and share with others later.")
        self.write(crowd + [target])
        before = self.map.read_bytes()
        proc = self.learn("alpha beta gamma", row="CAP-6")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("top 3", proc.stderr)
        self.assertEqual(self.map.read_bytes(), before)

    def test_check_validates_asks_and_warns_on_a_conflict(self) -> None:
        rows = self.rows()
        good = {"text": "mute a room", "source": "issue:acme/chat#3", "date": "2026-02-02"}
        bad = [
            ("asks must be an array", "mute"),
            ("at most 5", [good] * 6),
            ("text must be one non-empty line", [dict(good, text="")]),
            ("holds an email address or a handle", [dict(good, text="ask @ben")]),
            ("is not person", [dict(good, source="slack")]),
            ("is not a real YYYY-MM-DD date", [dict(good, date="2026-02-30")]),
        ]
        for message, asks in bad:
            with self.subTest(message=message):
                rows[0]["asks"] = asks
                self.write(rows)
                proc = run("--map", str(self.map), "--check")
                self.assertEqual(proc.returncode, 1)
                self.assertIn(message, proc.stderr)
        rows[0]["asks"] = [good]
        rows[2]["asks"] = [dict(good, text="see which channels are muted")]  # CAP-3's own words, on CAP-3: fine
        rows[1]["asks"] = [dict(good, text="see which of my channels are muted")]  # CAP-3's words on CAP-2
        self.write(rows)
        proc = run("--map", str(self.map), "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("warning: ask conflict: CAP-2's ask 'see which of my channels are muted' finds CAP-3 first",
                      proc.stderr)

    def test_adapter_learn_passes_the_file_row_and_source_as_argv(self) -> None:
        adapter = REPO / "skills" / "promise" / "scripts" / "adapter.py"
        project = self.dir / "project"
        project.mkdir()
        for name in ("capability_find.py", "recipe.md", "promise.config.json"):
            (project / name).write_bytes((MINIMAP / name).read_bytes())
        rows = json.loads((THREE_ROWS / "map.json").read_text(encoding="utf-8"))["rows"]
        for r in rows:
            r["doc"] = None
        (project / "map.json").write_text(json.dumps({"version": 1, "rows": rows}), encoding="utf-8")
        q = self.dir / "ask.txt"
        q.write_text(self.MISSED + "\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(adapter), "--cwd", str(project), "--json", "learn", "--query-file",
                               str(q), "--row", "CAP-2", "--source", "person"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["argv"][-6:], ["--query-file", str(q.resolve()), "--row", "CAP-2", "--source", "person"])
        self.assertTrue(json.loads(result["stdout"])["learned"])
        refused = subprocess.run([sys.executable, str(adapter), "--cwd", str(project), "learn", "--query-file", str(q),
                                  "--row", "row-2", "--source", "person"], capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("does not match map.rowIdPattern", refused.stderr)


PR_BODY = """Some words a person wrote above the block.

<!-- promise:pr -->
## Where this is

- **Chat**: rooms where members talk.

## Why

Closes #7. Muted rooms still pushed, and Fixes other/tracker#3.

## Capabilities

- [CAP-2](https://example.test/map#CAP-2) changed: a mute is per member. Verdict: not-built → under-proven.
- Touched, verdicts unchanged: CAP-3.
- No row names: README.md, because it is prose.

## Check these first

1. `notify.ts:12`: the per-member check. CAP-1 is mentioned here but not under Capabilities.
<!-- /promise:pr -->
"""


class Refs(unittest.TestCase):
    """`refs` hold identifiers only; `refs sync` adds them from merged pull requests."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.map = self.dir / "map.json"
        rows = json.loads((THREE_ROWS / "map.json").read_text(encoding="utf-8"))["rows"]
        for r in rows:
            r["doc"] = None
        self.map.write_text(json.dumps({"version": 1, "rows": rows}, indent=2), encoding="utf-8")

    def rows(self):
        return {r["id"]: r for r in json.loads(self.map.read_text(encoding="utf-8"))["rows"]}

    def sync(self, pulls, *extra):
        f = self.dir / "pulls.json"
        f.write_text(json.dumps(pulls), encoding="utf-8")
        proc = run("refs", "sync", "--map", str(self.map), "--input", str(f), *extra)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    PULL = {"repo": "acme/chat", "number": 41, "title": "fix(notify): check the mute per member",
            "body": PR_BODY, "merged": True}

    def test_a_merged_pull_request_adds_refs_and_one_eval_case(self) -> None:
        report = self.sync([self.PULL])
        rows = self.rows()
        self.assertEqual(rows["CAP-2"]["refs"], [{"repo": "acme/chat", "kind": "pr", "number": 41},
                                                 {"repo": "acme/chat", "kind": "issue", "number": 7},
                                                 {"repo": "other/tracker", "kind": "issue", "number": 3}])
        self.assertNotIn("refs", rows["CAP-3"], "a Touched line names no row")
        self.assertNotIn("refs", rows["CAP-1"], "only the Capabilities section names rows")
        fixture = json.loads((self.dir / "find-eval.json").read_text(encoding="utf-8"))
        self.assertEqual(fixture["cases"], [{"text": "fix(notify): check the mute per member", "row": "CAP-2",
                                             "source": "pr:acme/chat#41"}])
        self.assertEqual(len(report["refsAdded"]), 3)
        again = self.sync([self.PULL])
        self.assertEqual((again["refsAdded"], again["casesAdded"]), ([], []))
        check = run("--map", str(self.map), "--check")
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_unmerged_blockless_and_malformed_pulls_are_skipped(self) -> None:
        before = self.map.read_bytes()
        report = self.sync([dict(self.PULL, merged=False), dict(self.PULL, body="no block here"),
                            dict(self.PULL, repo="chat"), dict(self.PULL, number="41")])
        self.assertEqual([s["reason"] for s in report["skipped"]],
                         ["not merged", "its promise block names no row",
                          "needs repo as <owner>/<name> and a number", "needs repo as <owner>/<name> and a number"])
        self.assertEqual(self.map.read_bytes(), before)
        self.assertFalse((self.dir / "find-eval.json").exists())

    def test_two_rows_add_refs_but_no_case_and_dry_run_writes_nothing(self) -> None:
        body = PR_BODY.replace("- Touched, verdicts unchanged: CAP-3.", "- [CAP-3](x) new: a marker. Verdict: not-built.")
        before = self.map.read_bytes()
        report = self.sync([dict(self.PULL, body=body)], "--dry-run")
        self.assertEqual(self.map.read_bytes(), before)
        self.assertEqual({r["row"] for r in report["refsAdded"]}, {"CAP-2", "CAP-3"})
        self.assertEqual(report["casesAdded"], [])

    def test_a_commented_placeholder_closes_nothing(self) -> None:
        body = PR_BODY.replace("Closes #7. Muted rooms still pushed, and Fixes other/tracker#3.",
                               "<!-- Closes #12. One sentence: the problem, in the issue's own words. -->")
        self.sync([dict(self.PULL, body=body)])
        self.assertEqual(self.rows()["CAP-2"]["refs"], [{"repo": "acme/chat", "kind": "pr", "number": 41}])

    def test_check_validates_refs(self) -> None:
        good = {"repo": "acme/chat", "kind": "pr", "number": 3}
        for message, refs in [("refs must be an array", "acme/chat#3"),
                              ("a ref holds repo, kind and number only", [dict(good, title="Fix it")]),
                              ("is not <owner>/<name>", [dict(good, repo="chat")]),
                              ("is not issue or pr", [dict(good, kind="commit")]),
                              ("is not a positive integer", [dict(good, number=0)]),
                              ("repeats an earlier ref", [good, dict(good)])]:
            with self.subTest(message=message):
                data = json.loads(self.map.read_text(encoding="utf-8"))
                data["rows"][0]["refs"] = refs
                self.map.write_text(json.dumps(data), encoding="utf-8")
                proc = run("--map", str(self.map), "--check")
                self.assertEqual(proc.returncode, 1)
                self.assertIn(message, proc.stderr)

    def test_adapter_refs_sync_passes_the_input_file(self) -> None:
        adapter = REPO / "skills" / "promise" / "scripts" / "adapter.py"
        project = self.dir / "project"
        project.mkdir()
        for name in ("capability_find.py", "recipe.md", "promise.config.json"):
            (project / name).write_bytes((MINIMAP / name).read_bytes())
        (project / "map.json").write_bytes(self.map.read_bytes())
        f = self.dir / "pulls.json"
        f.write_text(json.dumps([self.PULL]), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(adapter), "--cwd", str(project), "--json", "refs-sync", "--input",
                               str(f)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["argv"][-2:], ["--input", str(f.resolve())])
        self.assertEqual(len(json.loads(result["stdout"])["refsAdded"]), 3)


class Code(unittest.TestCase):
    """`--code` names the local files a row's cited tests import."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        files = {
            "tests/test_mute.py": "import os\nfrom app import notify\nfrom app.mute import is_muted, Mute as M\n"
                                  "from .helpers import build\nimport app.store as store\n",
            "tests/helpers.py": "",
            "app/__init__.py": "", "app/notify.py": "", "app/mute.py": "", "app/store.py": "",
            "web/mute.test.ts": "import { mute } from '../src/mute';\nimport React from 'react';\n"
                                "const api = require('../src/api.js');\nimport '../src/setup';\n"
                                "jest.mock('../src/clock');\nexport { x } from './fixtures';\n",
            "src/mute.ts": "", "src/api.ts": "", "src/setup/index.tsx": "", "src/clock.js": "",
            "web/fixtures.ts": "", "docs/notes.md": "",
        }
        for name, text in files.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(text, encoding="utf-8")
        row = {"id": "CAP-1", "story": "A member mutes a channel.", "doc": None,
               "scenarios": [{"id": "CAP-1.1", "at": None, "given": "g", "when": "w", "then": "t", "altitude": "data"}],
               "tests": ["tests/test_mute.py::test_muted", "tests/test_mute.py::test_unmuted", "tests/gone.py::x"],
               "e2eTests": ["web/mute.test.ts::mutes", "../outside.py::x"], "evalTests": ["docs/notes.md::n"],
               "siblingTests": [], "verdict": "not-built"}
        self.map = self.root / "map.json"
        self.map.write_text(json.dumps({"version": 1, "rows": [row]}), encoding="utf-8")

    def test_python_and_js_imports_are_followed_one_step(self) -> None:
        proc = run("--map", str(self.map), "--code", "CAP-1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["tests"], ["tests/test_mute.py", "web/mute.test.ts", "docs/notes.md"])
        self.assertEqual(result["files"], ["app/__init__.py", "app/mute.py", "app/notify.py", "app/store.py",
                                           "src/api.ts", "src/clock.js", "src/mute.ts", "src/setup/index.tsx",
                                           "tests/helpers.py", "web/fixtures.ts"])
        self.assertEqual(result["missing"], ["tests/gone.py", "../outside.py"])
        self.assertEqual(result["unsupported"], ["docs/notes.md"])

    def test_unknown_or_malformed_row_exits_2(self) -> None:
        self.assertEqual(run("--map", str(self.map), "--code", "CAP-9").returncode, 2)
        self.assertEqual(run("--map", str(self.map), "--code", "nine").returncode, 2)

    def test_doc_root_is_the_project_root(self) -> None:
        sub = self.root / "docs" / "capabilities"
        sub.mkdir(parents=True)
        data = json.loads(self.map.read_text(encoding="utf-8"))
        data["docRoot"] = "../.."
        (sub / "map.json").write_text(json.dumps(data), encoding="utf-8")
        result = json.loads(run("--map", str(sub / "map.json"), "--code", "CAP-1").stdout)
        self.assertIn("app/mute.py", result["files"])

    def test_adapter_code_checks_the_row_id(self) -> None:
        adapter = REPO / "skills" / "promise" / "scripts" / "adapter.py"
        for name in ("capability_find.py", "recipe.md", "promise.config.json"):
            (self.root / name).write_bytes((MINIMAP / name).read_bytes())
        proc = subprocess.run([sys.executable, str(adapter), "--cwd", str(self.root), "--json", "code", "CAP-1"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("app/mute.py", json.loads(json.loads(proc.stdout)["stdout"])["files"])
        refused = subprocess.run([sys.executable, str(adapter), "--cwd", str(self.root), "code", "row-1"],
                                 capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2)


if __name__ == "__main__":
    unittest.main()
