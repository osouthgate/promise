"""Tests for scripts/start_map.py and the starter map it installs.

Run from the repo root:

    python3 -m unittest discover -s tests -v

The starter map is what `/promise` recommends a project starts once its first
outcome doc is agreed. These tests hold three promises: it installs into an
adopted project and the rest of the skill sees a usable map straight after;
it never replaces a map a project already has, or writes anything when it
refuses; and the reader the minimap example runs is the same file the
starter ships, so the example cannot drift from what a project receives.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

TESTS_DIR = Path(__file__).resolve().parent
PROMISE_DIR = TESTS_DIR.parent
SKILL_DIR = PROMISE_DIR / "skills" / "promise"
SCRIPTS_DIR = SKILL_DIR / "scripts"
START_MAP = SCRIPTS_DIR / "start_map.py"
ADOPT = SCRIPTS_DIR / "adopt.py"
ORIENT = SCRIPTS_DIR / "orient.py"
TEMPLATE_DIR = SKILL_DIR / "templates" / "starter-map"
MINIMAP_READER = PROMISE_DIR / "examples" / "minimap" / "capability_find.py"


def run(script: Path, *args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def snapshot(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.parts
    }


class StartMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        (self.project / "CLAUDE.md").write_text("# project\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def adopt(self) -> None:
        proc = run(ADOPT, "--cwd", str(self.project), "--docs-home", "docs/designs")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def config(self) -> dict:
        return json.loads((self.project / ".claude" / "promise.config.json").read_text(encoding="utf-8"))

    def test_refuses_without_a_config_and_writes_nothing(self) -> None:
        before = snapshot(self.project)
        proc = run(START_MAP, "--cwd", str(self.project))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("run adopt.py first", proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["changed"], False)
        self.assertEqual(snapshot(self.project), before)

    def test_dry_run_writes_nothing_and_shows_the_config_diff(self) -> None:
        self.adopt()
        before = snapshot(self.project)
        proc = run(START_MAP, "--cwd", str(self.project), "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(snapshot(self.project), before)
        self.assertIn('+    "recipe": "docs/capabilities/recipe.md",', proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["filesWritten"], [])
        self.assertEqual(result["changed"], False)

    def spelling_warnings(self) -> list:
        warnings = json.loads(run(ORIENT, "--cwd", str(self.project)).stdout)["warnings"]
        return [w for w in warnings if "areas/area" in w]

    def test_orient_warns_when_the_map_or_its_reader_keeps_the_alias_spelling(self) -> None:
        self.adopt()
        self.assertEqual(run(START_MAP, "--cwd", str(self.project)).returncode, 0)
        self.assertEqual(self.spelling_warnings(), [], "the starter map and reader use feature")
        map_path = self.project / "docs" / "capabilities" / "map.json"
        data = json.loads(map_path.read_text(encoding="utf-8"))
        data.pop("features", None)
        data["areas"] = []
        map_path.write_text(json.dumps(data), encoding="utf-8")
        found = self.spelling_warnings()
        self.assertEqual(len(found), 1, found)
        self.assertIn("map docs/capabilities/map.json uses the alias spelling areas/area", found[0])
        # a reader from before --features: it reads only the alias keys
        reader = self.project / "docs" / "capabilities" / "capability_find.py"
        text = reader.read_text(encoding="utf-8")
        self.assertIn('"--features", "--areas"', text)
        reader.write_text(text.replace('"--features", "--areas"', '"--areas"'), encoding="utf-8")
        found = self.spelling_warnings()
        self.assertEqual(len(found), 2, found)
        self.assertIn("the map reader docs/capabilities/capability_find.py has no --features", found[1])

    def test_a_projects_own_reader_that_never_had_areas_is_not_warned(self) -> None:
        self.adopt()
        self.assertEqual(run(START_MAP, "--cwd", str(self.project)).returncode, 0)
        reader = self.project / "docs" / "capabilities" / "capability_find.py"
        reader.write_text("#!/usr/bin/env python3\nimport argparse\np = argparse.ArgumentParser()\n"
                          "p.add_argument('--row')\np.add_argument('query', nargs='?')\nprint('[]')\n", encoding="utf-8")
        self.assertEqual(self.spelling_warnings(), [])

    def test_the_modes_that_name_features_say_to_keep_the_maps_spelling(self) -> None:
        for rel in ("modes/backfill.md", "modes/issue.md", "modes/pr.md", "references/first-screen.md"):
            with self.subTest(doc=rel):
                text = " ".join((SKILL_DIR / rel).read_text(encoding="utf-8").split())
                self.assertRegex(text, r"spelling (the project's map|the map) already uses")
                self.assertIn("`feature` in a new map", text)

    def test_install_gives_a_usable_map_the_skill_can_run(self) -> None:
        self.adopt()
        proc = run(START_MAP, "--cwd", str(self.project))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(
            result["filesWritten"],
            ["docs/capabilities/map.json", "docs/capabilities/capability_find.py", "docs/capabilities/recipe.md"],
        )

        config = self.config()
        self.assertEqual(config["map"]["recipe"], "docs/capabilities/recipe.md")
        self.assertNotIn("$comment", config, "adopt's 'map is not configured yet' note must go")

        orientation = json.loads(run(ORIENT, "--cwd", str(self.project)).stdout)
        self.assertTrue(orientation["mapUsable"])

        reader = self.project / "docs" / "capabilities" / "capability_find.py"
        self.assertEqual(run(reader, "--next-id").stdout.strip(), "CAP-1")
        check = run(reader, "--check")
        self.assertEqual(check.returncode, 0, check.stderr)

        recipe = (self.project / "docs" / "capabilities" / "recipe.md").read_text(encoding="utf-8")
        self.assertNotIn("{dir}", recipe)
        self.assertIn("python3 docs/capabilities/capability_find.py --check", recipe)

    def test_doc_citations_resolve_from_the_project_root(self) -> None:
        """A row's doc is its project-relative path, although the map sits
        two folders down: docRoot carries the difference."""
        self.adopt()
        self.assertEqual(run(START_MAP, "--cwd", str(self.project)).returncode, 0)
        doc = self.project / "docs" / "designs" / "mute.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "| #    | Given | When | Then | Altitude | Row |\n"
            "|------|-------|------|------|----------|-----|\n"
            "| AT-1 | Ana is in a channel | she mutes it | she gets no push | perception | CAP-1 |\n",
            encoding="utf-8",
        )
        map_path = self.project / "docs" / "capabilities" / "map.json"
        data = json.loads(map_path.read_text(encoding="utf-8"))
        self.assertEqual(data["docRoot"], "../..")
        data["rows"].append({
            "id": "CAP-1",
            "story": "A member mutes a channel.",
            "doc": "docs/designs/mute.md",
            "scenarios": [{"id": "CAP-1.1", "at": "AT-1", "given": "Ana is in a channel",
                           "when": "she mutes it", "then": "she gets no push", "altitude": "perception"}],
            "tests": [], "e2eTests": [], "evalTests": [], "siblingTests": [],
            "verdict": "not-built",
        })
        map_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        check = run(map_path.parent / "capability_find.py", "--check")
        self.assertEqual(check.returncode, 0, check.stderr)

        doc.write_text("no table here\n", encoding="utf-8")
        check = run(map_path.parent / "capability_find.py", "--check")
        self.assertEqual(check.returncode, 1)
        self.assertIn("has no §6 line citing it", check.stderr)

    def test_never_replaces_an_existing_map(self) -> None:
        self.adopt()
        config_path = self.project / ".claude" / "promise.config.json"
        config = self.config()
        config["map"] = {"recipe": "docs/testing/recipe.md"}
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        before = snapshot(self.project)
        proc = run(START_MAP, "--cwd", str(self.project))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("never replaced", proc.stderr)
        self.assertEqual(snapshot(self.project), before)

    def test_refuses_a_map_set_to_false(self) -> None:
        self.adopt()
        config_path = self.project / ".claude" / "promise.config.json"
        config = self.config()
        config["map"] = False
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        before = snapshot(self.project)
        for args in ((), ("--dry-run",)):
            with self.subTest(args=args):
                proc = run(START_MAP, "--cwd", str(self.project), *args)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("sets map to false: this project keeps no map, on purpose", proc.stderr)
                self.assertEqual(snapshot(self.project), before)

    def test_the_modes_that_offer_the_starter_map_skip_a_map_set_to_false(self) -> None:
        # arm, adopt and backfill are the modes that offer start_map.py; each
        # names "map": false as the case where it never does
        modes = SKILL_DIR / "modes"
        for mode, phrase in (("arm.md", "A config whose `map` is `false` keeps no map, on purpose"),
                             ("adopt.md", "The config already sets `map` to `false`"),
                             ("backfill.md", "`map: false` (none, on purpose) → say so and stop")):
            with self.subTest(mode=mode):
                self.assertIn(phrase, (modes / mode).read_text(encoding="utf-8"))
        config_doc = (SKILL_DIR / "references" / "config.md").read_text(encoding="utf-8")
        self.assertIn("`\"map\": false` means this project keeps no map, on purpose", config_doc)
        # the framework's lifecycle, which says arm and adopt offer the starter
        # map, names the same exception in that paragraph
        framework = (SKILL_DIR / "outcome-framework.md").read_text(encoding="utf-8")
        start = framework.index("- **The capability map is the goal.**")
        paragraph = " ".join(framework[start:framework.index("\n- **", start + 1)].split())
        self.assertIn("offered the skill's starter map", paragraph)
        self.assertIn("The exception is a project whose config holds `\"map\": false`", paragraph)
        self.assertIn("neither mode offers the starter map there, and `start_map.py` refuses", paragraph)

    def test_refuses_a_destination_that_holds_files_or_escapes(self) -> None:
        self.adopt()
        occupied = self.project / "docs" / "capabilities"
        occupied.mkdir(parents=True)
        (occupied / "notes.md").write_text("mine\n", encoding="utf-8")
        before = snapshot(self.project)
        for dest in ("docs/capabilities", "../elsewhere", ".", "has space"):
            with self.subTest(dest=dest):
                proc = run(START_MAP, "--cwd", str(self.project), "--dest", dest)
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertEqual(snapshot(self.project), before)

    def test_custom_destination_sets_every_path(self) -> None:
        self.adopt()
        proc = run(START_MAP, "--cwd", str(self.project), "--dest", "capabilities")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.config()["map"]["find"], "python3 capabilities/capability_find.py")
        data = json.loads((self.project / "capabilities" / "map.json").read_text(encoding="utf-8"))
        self.assertEqual(data["docRoot"], "..")


class StarterReaderFieldTests(unittest.TestCase):
    """The reader's optional row fields: `aliases` (ids from an older
    register) and `surfaces` (entry points), both matched by find, and
    `origin` (doc, intake or backfill), each validated by --check only when
    present; and the map's optional top-level `leftOut` list."""

    READER = TEMPLATE_DIR / "capability_find.py"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.map_path = Path(self._tmp.name) / "map.json"

    @staticmethod
    def row(rid: str = "CAP-1", **extra) -> dict:
        base = {
            "id": rid, "story": "A member mutes a channel.", "doc": None,
            "scenarios": [{"id": f"{rid}.1", "at": None, "given": "Ana is in a channel",
                           "when": "she mutes it", "then": "she gets no push", "altitude": "data"}],
            "tests": [], "e2eTests": [], "evalTests": [], "siblingTests": [], "verdict": "not-built",
        }
        base.update(extra)
        return base

    def reader(self, rows, *args: str, **top) -> subprocess.CompletedProcess:
        self.map_path.write_text(json.dumps({"version": 1, "rows": rows, **top}), encoding="utf-8")
        return run(self.READER, "--map", str(self.map_path), *args)

    def test_find_matches_an_alias_and_scores_it(self) -> None:
        rows = [self.row("CAP-1"), self.row("CAP-2", aliases=["J4", "journey-mute"], story="A member exports a note.")]
        proc = self.reader(rows, "J4")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hits = json.loads(proc.stdout)
        self.assertEqual([h["id"] for h in hits], ["CAP-2"])
        self.assertTrue(hits[0]["why"].startswith("names this row"), hits[0]["why"])
        hits = json.loads(self.reader(rows, "journey mute").stdout)
        self.assertEqual(hits[0]["id"], "CAP-2", "the alias's own tokens outscore a story that shares one")

    def test_check_accepts_well_formed_aliases_and_every_origin(self) -> None:
        rows = [self.row("CAP-1", aliases=["J4"], origin="backfill"),
                self.row("CAP-2", origin="intake"), self.row("CAP-3", aliases=[])]
        proc = self.reader(rows, "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("3 rows, 0 problems", proc.stdout)

    def test_check_rejects_malformed_aliases(self) -> None:
        for aliases in ("J4", ["J4", ""], ["  "], [4]):
            with self.subTest(aliases=aliases):
                proc = self.reader([self.row(aliases=aliases)], "--check")
                self.assertEqual(proc.returncode, 1)
                self.assertIn("CAP-1: aliases must be an array of non-empty strings", proc.stderr)

    def test_check_rejects_an_unknown_origin(self) -> None:
        for origin in ("feedback", "", 1):
            with self.subTest(origin=origin):
                proc = self.reader([self.row(origin=origin)], "--check")
                self.assertEqual(proc.returncode, 1)
                self.assertIn("origin", proc.stderr)
                self.assertIn("is not one of ('doc', 'intake', 'backfill')", proc.stderr)

    def test_recipe_names_both_fields(self) -> None:
        recipe = (TEMPLATE_DIR / "recipe.md").read_text(encoding="utf-8")
        self.assertIn("| `aliases` |", recipe)
        self.assertIn("carries `origin: backfill` and `doc: null` until an outcome doc promises it", recipe)

    def test_find_matches_a_surface(self) -> None:
        rows = [self.row("CAP-1"), self.row("CAP-2", surfaces=["GET /exports", "page /exports"],
                                            story="A member downloads a note.")]
        hits = json.loads(self.reader(rows, "exports").stdout)
        self.assertEqual([h["id"] for h in hits], ["CAP-2"])

    def test_check_accepts_surfaces_and_rejects_malformed_ones(self) -> None:
        proc = self.reader([self.row(surfaces=["GET /me", "cron weekly-digest"]), self.row("CAP-2", surfaces=[])],
                           "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for surfaces in ("GET /me", ["GET /me", ""], [None]):
            with self.subTest(surfaces=surfaces):
                proc = self.reader([self.row(surfaces=surfaces)], "--check")
                self.assertEqual(proc.returncode, 1)
                self.assertIn("CAP-1: surfaces must be an array of non-empty strings", proc.stderr)

    LEFT_OUT = {"test": "tests/unit/slug.test.ts::slugify trims", "reason": "a helper's own test",
                "date": "2026-02-03"}

    def test_check_accepts_a_well_formed_left_out_list(self) -> None:
        for left_out in ([], [self.LEFT_OUT]):
            with self.subTest(left_out=left_out):
                proc = self.reader([self.row()], "--check", leftOut=left_out)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("1 rows, 0 problems", proc.stdout)

    def test_check_rejects_a_malformed_left_out_list(self) -> None:
        cases = [
            ({"a": 1}, "leftOut is not a list"),
            (["tests/a.py::t"], "leftOut[0]: not an object"),
            ([dict(self.LEFT_OUT, test="tests/unit/slug.test.ts")], "leftOut[0]: test 'tests/unit/slug.test.ts' is not <file>::<name>"),
            ([dict(self.LEFT_OUT, test="::slugify trims")], "is not <file>::<name>"),
            ([dict(self.LEFT_OUT, test="tests/a.py:: ")], "is not <file>::<name>"),
            ([dict(self.LEFT_OUT, reason="")], "leftOut[0]: reason must be one non-empty line"),
            ([dict(self.LEFT_OUT, reason="one\ntwo")], "reason must be one non-empty line"),
            ([{"test": "tests/a.py::t", "date": "2026-02-03"}], "reason must be one non-empty line"),
            ([dict(self.LEFT_OUT, date="2026-02-30")], "leftOut[0]: date '2026-02-30' is not a real YYYY-MM-DD date"),
            ([dict(self.LEFT_OUT, date="20260203")], "is not a real YYYY-MM-DD date"),
            ([dict(self.LEFT_OUT, date=None)], "date None is not a real YYYY-MM-DD date"),
            ([dict(self.LEFT_OUT, test="tests/a.test.ts::Bil%s")], "names a pattern of tests, not one test"),
            ([dict(self.LEFT_OUT, test="tests/a.test.ts::adds ${n} rows")], "names a pattern of tests"),
        ]
        for left_out, message in cases:
            with self.subTest(left_out=left_out):
                proc = self.reader([self.row()], "--check", leftOut=left_out)
                self.assertEqual(proc.returncode, 1)
                self.assertIn(message, proc.stderr)
                self.assertIn("1 rows, 1 problems", proc.stdout)

    FEATURES = [{"id": "chat", "name": "Chat", "plain": "Where members talk."},
             {"id": "billing", "name": "Billing", "plain": "What a member pays."}]
    AREAS = FEATURES  # the older spelling of the same list
    GLOSSARY = [{"term": "Seat", "plain": "A paid account.", "aliases": ["seats"]},
                {"term": "Channel", "plain": "A room members talk in."}]

    def test_features_label_rows_and_a_query_matches_the_feature_name(self) -> None:
        rows = [self.row("CAP-1", feature="chat"), self.row("CAP-2", story="A member pays.", feature="billing"),
                self.row("CAP-3", story="A member signs in.")]
        proc = self.reader(rows, "--check", features=self.FEATURES, glossary=self.GLOSSARY)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        listed = json.loads(self.reader(rows, "--features", features=self.FEATURES).stdout)
        self.assertEqual([(a["id"], a["rows"]) for a in listed], [("chat", 1), ("billing", 1), (None, 1)])
        in_area = json.loads(self.reader(rows, "--feature", "billing", features=self.FEATURES).stdout)
        self.assertEqual([r["id"] for r in in_area], ["CAP-2"])
        self.assertEqual(self.reader(rows, "--feature", "nope", features=self.FEATURES).returncode, 2)
        hits = json.loads(self.reader(rows, "billing", features=self.FEATURES).stdout)
        self.assertEqual([h["id"] for h in hits], ["CAP-2"])
        self.assertEqual(json.loads(self.reader(rows, "--glossary", glossary=self.GLOSSARY).stdout), self.GLOSSARY)

    def test_the_older_area_keys_and_flags_mean_the_same(self) -> None:
        rows = [self.row("CAP-1", area="chat"), self.row("CAP-2", story="A member pays.", area="billing"),
                self.row("CAP-3", story="A member signs in.")]
        self.assertEqual(self.reader(rows, "--check", areas=self.AREAS).returncode, 0)
        for flag in ("--features", "--areas"):
            listed = json.loads(self.reader(rows, flag, areas=self.AREAS).stdout)
            self.assertEqual([(a["id"], a["rows"]) for a in listed], [("chat", 1), ("billing", 1), (None, 1)])
        for flag in ("--feature", "--area"):
            in_feature = json.loads(self.reader(rows, flag, "billing", areas=self.AREAS).stdout)
            self.assertEqual([r["id"] for r in in_feature], ["CAP-2"])
        hits = json.loads(self.reader(rows, "billing", areas=self.AREAS).stdout)
        self.assertEqual([h["id"] for h in hits], ["CAP-2"])
        bad = self.reader([self.row(area="nope")], "--check", areas=self.AREAS)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("feature 'nope' is not an id in areas", bad.stderr)

    def test_check_rejects_both_spellings_in_one_map_or_one_row(self) -> None:
        both_map = self.reader([self.row(feature="chat")], "--check", features=self.FEATURES, areas=self.AREAS)
        self.assertEqual(both_map.returncode, 1, both_map.stdout)
        self.assertIn("FEATURE_AND_AREA: the map has both 'features' and 'areas'", both_map.stderr)
        both_row = self.reader([self.row(feature="chat", area="chat")], "--check", features=self.FEATURES)
        self.assertEqual(both_row.returncode, 1, both_row.stdout)
        self.assertIn("FEATURE_AND_AREA: CAP-1 has both 'feature' and 'area'", both_row.stderr)

    def test_check_rejects_rows_that_mix_spellings_or_differ_from_the_top_level(self) -> None:
        cases = (
            ("rows mix", [self.row("CAP-1", area="chat"), self.row("CAP-2", feature="chat")], {"features": self.FEATURES},
             "FEATURE_AND_AREA: the rows mix the spellings: CAP-2 has 'feature' and CAP-1 has 'area'"),
            ("top areas, row feature", [self.row("CAP-1", feature="chat")], {"areas": self.AREAS},
             "FEATURE_AND_AREA: the map lists 'areas' but CAP-1 has 'feature'"),
            ("top features, row area", [self.row("CAP-1", area="chat")], {"features": self.FEATURES},
             "FEATURE_AND_AREA: the map lists 'features' but CAP-1 has 'area'"),
        )
        for name, rows, top, message in cases:
            with self.subTest(name):
                proc = self.reader(rows, "--check", **top)
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn(message, proc.stderr)
        one = self.reader([self.row("CAP-1", area="chat"), self.row("CAP-2", area="chat")], "--check", areas=self.AREAS)
        self.assertEqual(one.returncode, 0, one.stderr)

    def test_a_malformed_list_does_not_break_a_query(self) -> None:
        for top in ({"features": 5}, {"areas": 5}, {"glossary": 7}, {"features": True, "glossary": "x"}):
            with self.subTest(top=top):
                hits = self.reader([self.row()], "mutes", **top)
                self.assertEqual(hits.returncode, 0, hits.stderr)
                self.assertEqual([h["id"] for h in json.loads(hits.stdout)], ["CAP-1"])
                self.assertEqual(self.reader([self.row()], "--features", **top).returncode, 0)
                self.assertEqual(self.reader([self.row()], "--glossary", **top).returncode, 0)
                self.assertEqual(self.reader([self.row()], "--check", **top).returncode, 1)

    def test_check_rejects_malformed_features_and_glossary(self) -> None:
        cases = [
            ([self.row(feature="chat")], {}, "CAP-1: feature 'chat' but the map has no features list"),
            ([self.row(feature="nope")], {"features": self.FEATURES}, "CAP-1: feature 'nope' is not an id in features"),
            ([self.row()], {"features": {"chat": 1}}, "features is not a list"),
            ([self.row()], {"features": [dict(self.FEATURES[0], id="Chat Room")]}, "is not a lower-case kebab-case id"),
            ([self.row()], {"features": self.FEATURES + [dict(self.FEATURES[0], name="x")]}, "duplicate id chat"),
            ([self.row()], {"features": self.FEATURES + [dict(self.FEATURES[0], id="talk", name="chat")]},
             "another feature has the name 'chat'"),
            ([self.row()], {"features": [dict(self.FEATURES[0], plain="")]}, "plain must be one non-empty line"),
            ([self.row()], {"features": [dict(self.FEATURES[0], doc="docs/none.md")]}, "doc 'docs/none.md' is not a file"),
            ([self.row()], {"glossary": {"Seat": 1}}, "glossary is not a list"),
            ([self.row()], {"glossary": [{"term": "", "plain": "x"}]}, "term must be one non-empty line"),
            ([self.row()], {"glossary": [{"term": "Seat", "plain": "a\nb"}]}, "plain must be one non-empty line"),
            ([self.row()], {"glossary": [{"term": "Seat", "plain": "x", "aliases": "seats"}]},
             "aliases must be an array of non-empty strings"),
            ([self.row()], {"glossary": self.GLOSSARY + [{"term": "seat", "plain": "again"}]},
             "'seat' is also a word of 'Seat'"),
            ([self.row()], {"glossary": self.GLOSSARY + [{"term": "Room", "plain": "x", "aliases": ["Seats"]}]},
             "'Seats' is also a word of 'Seat'"),
        ]
        for rows, top, message in cases:
            with self.subTest(message=message):
                proc = self.reader(rows, "--check", **top)
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn(message, proc.stderr)

    def test_recipe_names_features_and_glossary(self) -> None:
        recipe = (TEMPLATE_DIR / "recipe.md").read_text(encoding="utf-8")
        self.assertIn("| `feature` |", recipe)
        self.assertIn("`glossary`", recipe)
        self.assertIn("references/first-screen.md", recipe)

    def test_check_refuses_a_placeholder_outside_a_code_span(self) -> None:
        # §6 copies given, when and then word for word, and the doc lint reads a
        # bare <word> there as an unfilled slot (PLACEHOLDER)
        for key, text in (("then", "the usage line reads mute <channel|all>"),
                          ("when", "she runs mute <channel>"), ("given", "a `lone backtick <x>")):
            with self.subTest(key=key):
                rr = self.row()
                rr["scenarios"][0][key] = text
                proc = self.reader([rr], "--check")
                self.assertEqual(proc.returncode, 1)
                self.assertIn(f"CAP-1: scenarios[0].{key} holds <", proc.stderr)
                self.assertIn("outside a code span", proc.stderr)

    def test_check_accepts_a_placeholder_in_a_code_span(self) -> None:
        rr = self.row()
        rr["scenarios"][0]["then"] = "the usage line reads `mute <channel|all>`"
        rr["scenarios"][0]["when"] = "she runs ``mute <channel> `x` ``"
        proc = self.reader([rr], "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_the_reader_reads_placeholders_as_the_doc_lint_does(self) -> None:
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.addCleanup(sys.path.remove, str(SCRIPTS_DIR))
        import importlib.util
        import lint_outcome
        spec = importlib.util.spec_from_file_location("starter_reader", self.READER)
        reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reader)
        for text in ("plain", "mute <channel>", "`mute <channel>`", "``a <b> ` c``", "a `lone <x>",
                     "`a` <b> `c`", "x < y > z", "<a><b>", "``` <x>", "`<x>` and <y>"):
            with self.subTest(text=text):
                self.assertEqual(reader.bare_placeholders(text),
                                 lint_outcome.ANGLE_PLACEHOLDER_RE.findall(lint_outcome.strip_code_spans(text)))

    def test_recipe_names_surfaces_and_left_out(self) -> None:
        recipe = (TEMPLATE_DIR / "recipe.md").read_text(encoding="utf-8")
        self.assertIn("| `surfaces` |", recipe)
        self.assertIn("top-level `leftOut` list", recipe)
        self.assertIn('"date": "YYYY-MM-DD"', recipe)


class StarterTemplateTests(unittest.TestCase):
    def test_minimap_runs_the_reader_the_starter_ships(self) -> None:
        self.assertEqual(
            MINIMAP_READER.read_bytes(),
            (TEMPLATE_DIR / "capability_find.py").read_bytes(),
            "examples/minimap/capability_find.py must be a byte-for-byte copy of "
            "templates/starter-map/capability_find.py; change the template, then copy it",
        )

    def test_template_placeholders_are_the_ones_start_map_fills(self) -> None:
        self.assertIn("{docRoot}", (TEMPLATE_DIR / "map.json").read_text(encoding="utf-8"))
        self.assertIn("{dir}", (TEMPLATE_DIR / "recipe.md").read_text(encoding="utf-8"))
        self.assertNotIn("{dir}", (TEMPLATE_DIR / "capability_find.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
