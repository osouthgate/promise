"""Doctor distinguishes configuration, observation and simulation without writes."""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_service_report import data_for, observation, search_policy

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/promise/scripts"


class Doctor(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.project = Path(scratch.name)

    def write_json(self, name, value):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def inspect(self, *args):
        process = subprocess.run(
            [sys.executable, str(SCRIPTS / "doctor.py"), "--cwd", str(self.project), "--json", *args],
            capture_output=True, text=True, check=True,
        )
        return json.loads(process.stdout)

    def test_reads_configured_map_without_running_its_commands(self):
        self.write_json("promise.config.json", {
            "map": {"file": "map.json", "find": ["sh", "-c", "touch ran"]},
        })
        first = search_policy()
        data = data_for(first)
        data["servicePolicies"].append({**first, "id": "duplicate"})
        data["rows"][0].update(story="Search notes", scenarios=[{"then": "one"}, {"then": "two"}],
                               surfaces=["search", "search"])
        data["rows"].extend([
            {"id": "CAP-2", "story": " search  notes "},
            {"id": "CAP-3", "parent": "CAP-1", "story": "Search notes",
             "scenarios": [{"then": "three"}], "surfaces": ["search", "settings"]},
            {"id": "CAP-4", "parent": "missing"},
        ])
        path = self.write_json("map.json", data)
        original = path.read_bytes()
        result = self.inspect()
        service = result["features"][0]
        self.assertEqual(service["availability"]["status"], "available")
        self.assertEqual(service["configuration"]["status"], "configured")
        self.assertEqual(service["configuration"]["references"], 1)
        self.assertEqual(service["observation"]["status"], "unknown")
        self.assertEqual(result["mapFootprint"], {
            "rows": 4, "rootRows": 2, "continuations": 1, "unresolvedParents": 1,
            "scenarios": 3, "singleScenarioRows": 1,
            "declaredSurfaces": 2, "policyReferences": 1, "evidence": str(path),
        })
        advice = {item["code"]: item["evidence"] for item in result["recommendations"]}
        self.assertEqual(advice["review-repeated-jobs"]["groups"], [["CAP-1", "CAP-2"]])
        self.assertEqual(advice["review-continuations"]["rowIds"], ["CAP-3"])
        self.assertEqual(advice["review-unused-policies"]["policyIds"], ["duplicate"])
        self.assertIn("share-identical-policies", advice)
        self.assertFalse((self.project / "ran").exists())
        self.assertEqual(path.read_bytes(), original)

    def test_distinguishes_real_breach_stale_and_synthetic_observations(self):
        policy = search_policy()
        self.write_json("map.json", data_for(policy))
        sample = observation(values={"duration": 12000, "relevance": 1, "correct": 1})
        now = datetime.now(timezone.utc)
        sample["windowStart"] = (now - timedelta(hours=1, seconds=1)).isoformat()
        sample["windowEnd"] = (now - timedelta(seconds=1)).isoformat()
        for record in sample["samples"]:
            record["at"] = (now - timedelta(minutes=30)).isoformat()
        for synthetic, expected in ((False, "observed"), (True, "synthetic-or-replay")):
            with self.subTest(synthetic=synthetic):
                self.write_json("observations.json", {"observations": [sample], "synthetic": synthetic})
                result = self.inspect("--map", "map.json", "--observations", "observations.json")
                evidence = result["features"][0]["observation"]
                self.assertEqual(evidence["status"], expected)
                self.assertEqual(evidence["results"], {"unacceptable": 1})
                self.assertEqual(evidence["examples"][0]["row"], "CAP-1")
                self.assertEqual(evidence["examples"][0]["windowEnd"], sample["windowEnd"])
        self.write_json("observations.json", {"observations": [observation(policy)]})
        result = self.inspect("--map", "map.json", "--observations", "observations.json")
        self.assertEqual(result["features"][0]["observation"]["status"], "stale-only")

    def test_missing_or_invalid_map_is_not_evidence_of_disuse(self):
        self.assertEqual(self.inspect()["features"][0]["configuration"]["status"], "unknown")
        self.write_json("promise.config.json", {"map": False})
        self.assertEqual(self.inspect()["features"][0]["configuration"]["status"], "not-configured")
        self.write_json("promise.config.json", {"map": False, "sibling": {"repo": "shared"}})
        self.assertEqual(self.inspect()["features"][0]["configuration"]["status"], "unknown")
        self.write_json("map.json", {"rows": [{"id": "CAP-1", "servicePolicyRefs": ["missing"]}]})
        result = self.inspect("--map", "map.json")
        self.assertEqual(result["features"][0]["configuration"]["status"], "invalid")
        self.assertEqual(result["recommendations"][0]["code"], "repair-policy-configuration")


    def test_explicit_and_configured_map_cannot_follow_a_link_outside_the_project(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "map.json"
            external.write_text(json.dumps(data_for(search_policy())), encoding="utf-8")
            (self.project / "map.json").symlink_to(external)
            self.write_json("promise.config.json", {"map": {"file": "map.json"}})
            for args in ((), ("--map", "map.json")):
                with self.subTest(args=args):
                    setup = self.inspect(*args)["features"][0]["configuration"]
                    self.assertEqual(setup["status"], "unknown")
                    self.assertIn("outside the project", setup["evidence"])
