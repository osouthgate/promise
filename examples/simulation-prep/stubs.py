#!/usr/bin/env python3
"""Fixed fictional outcomes only. No product behaviour, eval or service assessment."""
import argparse
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "workflows.json"


def load_fixture(path=FIXTURES):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_fixture(data):
    """Validate preparation inputs, not the fictional products or Promise itself."""
    assert data["fixtureVersion"] == 1
    assert data["synthetic"] is True
    assert len(data["projects"]) == 2
    saw_false = saw_unchecked = False
    for project in data["projects"].values():
        catalog = project["scenarioCatalogue"]
        previous = set()
        stage_ids = set()
        for stage in project["stages"]:
            assert stage["id"] not in stage_ids, "duplicate stage id"
            stage_ids.add(stage["id"])
            ids = [sid for group in stage["jobs"].values() for sid in group]
            assert len(ids) == len(set(ids)), "scenario appears in two jobs"
            assert set(ids) <= set(catalog), "unknown scenario"
            assert previous <= set(ids), "a scenario vanished during evolution"
            assert set(stage["stubResults"]) == set(ids), "missing or extra stub result"
            for value in stage["stubResults"].values():
                assert value is None or type(value) is bool, "stub result must be Boolean or unchecked"
                saw_false |= value is False
                saw_unchecked |= value is None
            for reference in stage["serviceObservationRefs"]:
                observation = data["sharedServiceFixtures"][reference]
                assert observation["synthetic"] is True
                assert observation["scope"] and observation["testPurpose"]
            previous = set(ids)
    assert saw_false and saw_unchecked, "fixture must exercise failure and no evidence"


def _stage(data, project, stage):
    return next(item for item in data["projects"][project]["stages"] if item["id"] == stage)


def fixed_result(project, stage, scenario, *, data=None):
    """Return a scripted result; never inspect an application or its input data."""
    data = load_fixture() if data is None else data
    return _stage(data, project, stage)["stubResults"][scenario]


def fixed_service_observations(project, stage, *, data=None):
    """Return neutral fake observations for the pinned replay adapter."""
    data = load_fixture() if data is None else data
    # Copy so a caller cannot mutate a shared fixture while translating formats.
    return json.loads(json.dumps([data["sharedServiceFixtures"][reference]
                                  for reference in _stage(data, project, stage)["serviceObservationRefs"]]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True,
                        help="check fixture integrity only; no eval or simulation runs")
    parser.parse_args()
    try:
        check_fixture(load_fixture())
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Fixture integrity failed: {error}\n")
    print("Synthetic fixture integrity: PASS. No product tests, evals or Promise simulation ran.")


if __name__ == "__main__":
    main()
