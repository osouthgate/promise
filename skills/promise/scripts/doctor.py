#!/usr/bin/env python3
"""Inspect Promise feature adoption and setup without running project commands."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from check import map_file
import orient
import service_report

RECENT_RESULTS = {"target", "acceptable", "unacceptable"}
SAMPLE_LIMIT = 5


def map_source(root: Path, explicit: str | None):
    if explicit is not None:
        location, reason = explicit, "explicit map"
    else:
        config, path, warnings = orient.load_config(str(root))
        if config is None and path:
            return None, warnings[0]
        config = config or {}
        mapping = config.get("map")
        if mapping is False and config.get("sibling"):
            return None, "capabilities are held in a sibling repo; run Doctor from that project root"
        if mapping is False:
            return None, "local map disabled in the Promise config"
        if mapping is None:
            return None, "no map located; pass --map for a custom map inside the project"
        if not isinstance(mapping, dict):
            return None, "configured map is not an object"
        location, reason = map_file(mapping)
        if not location:
            return None, reason
    path = (root / location).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None, "map resolves outside the project; choose the intended project root"
    return path, reason


def recommendation(code, action, file, **evidence):
    return {"code": code, "action": action, "evidence": {"file": str(file), **evidence}}


def audit_map(data, stats, file):
    """Use only explicit map signals; counts alone do not diagnose sprawl."""
    rows = data["rows"]
    by_id = {row["id"]: row for row in rows}
    policies = data.get("servicePolicies", [])
    roots = defaultdict(list)
    continuations = []
    root_rows = 0
    unresolved_parents = 0
    case_counts = []
    surfaces = set()
    for row in rows:
        scenarios = row.get("scenarios")
        case_counts.append(sum(isinstance(case, dict) for case in scenarios) if isinstance(scenarios, list) else 0)
        declared = row.get("surfaces")
        if isinstance(declared, list):
            surfaces.update(surface.strip() for surface in declared if isinstance(surface, str) and surface.strip())
        parent = row.get("parent")
        if isinstance(parent, str) and parent in by_id and parent != row["id"]:
            continuations.append(row["id"])
        elif parent:
            unresolved_parents += 1
        else:
            root_rows += 1
            if isinstance(row.get("story"), str):
                story = " ".join(row["story"].casefold().split())
                if story:
                    roots[story].append(row["id"])

    footprint = {
        "rows": len(rows),
        "rootRows": root_rows,
        "continuations": len(continuations),
        "unresolvedParents": unresolved_parents,
        "scenarios": sum(case_counts),
        "singleScenarioRows": case_counts.count(1),
        "declaredSurfaces": len(surfaces) if surfaces else None,
        "policyReferences": stats["references"],
        "evidence": str(file),
    }
    advice = []
    if rows and not policies and not stats["invalidReferences"]:
        advice.append(recommendation(
            "start-with-one-policy",
            "If a service commitment matters here, start with one policy for an existing capability and agree how to observe it.",
            file, capabilityCount=stats["rows"],
        ))
    repeated = [ids for ids in roots.values() if len(ids) > 1]
    if repeated:
        advice.append(recommendation(
            "review-repeated-jobs",
            "Compare these rows with the same user story. Keep distinct user outcomes separate and group new variants under their existing job where the map rules allow.",
            file, groups=[ids[:SAMPLE_LIMIT] for ids in repeated[:SAMPLE_LIMIT]], count=len(repeated),
        ))
    if continuations:
        advice.append(recommendation(
            "review-continuations",
            "Review these continuations as part of their parent job. Keep scenario coverage and any continuation the current map rules require.",
            file, rowIds=continuations[:SAMPLE_LIMIT], count=len(continuations),
        ))
    if stats["invalidPolicies"] or stats["invalidReferences"]:
        advice.append(recommendation(
            "repair-policy-configuration",
            "Resolve these policy or reference errors before treating the affected capabilities as configured.",
            file, issues=stats["issues"][:SAMPLE_LIMIT],
        ))
        return footprint, advice

    used = {policy for row in rows for policy in row.get("servicePolicyRefs", [])}
    unused = [policy["id"] for policy in policies if policy["id"] not in used]
    if unused:
        advice.append(recommendation(
            "review-unused-policies",
            "Check whether these unlinked policies are planned. Link them to the capabilities they cover, or retire them after confirming scope.",
            file, policyIds=unused[:SAMPLE_LIMIT], count=len(unused),
        ))
    same = defaultdict(list)
    for policy in policies:
        definition = json.dumps({key: value for key, value in policy.items() if key != "id"}, sort_keys=True)
        same[definition].append(policy["id"])
    duplicate = [ids for ids in same.values() if len(ids) > 1]
    if duplicate:
        advice.append(recommendation(
            "share-identical-policies",
            "Compare the scope of these identical policy definitions. Where the commitment is shared, reference one policy and retain the evidence for each capability.",
            file, groups=[ids[:SAMPLE_LIMIT] for ids in duplicate[:SAMPLE_LIMIT]], count=len(duplicate),
        ))
    return footprint, advice


def inspect_project(cwd, explicit_map=None, observations=None):
    root = Path(cwd).resolve()
    try:
        path, reason = map_source(root, explicit_map)
    except (OSError, ValueError, RecursionError) as exc:
        path, reason = None, str(exc)
    feature = {
        "id": "service-assurance",
        "availability": {"status": "available", "evidence": "bundled service_report.py"},
        "configuration": {"status": "unknown", "evidence": reason},
        "observation": {"status": "unknown", "evidence": "no observation export supplied"},
    }
    result = {"features": [feature], "recommendations": []}
    if path is None:
        if reason == "local map disabled in the Promise config":
            feature["configuration"]["status"] = "not-configured"
        return result

    try:
        if not path.is_file():
            raise ValueError("expected a readable regular map file")
        data = service_report.read_json(path, "map")
        if isinstance(data, list):
            data = {"rows": data}
        stats = service_report.policies_summary(data)
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        feature["configuration"]["evidence"] = f"{path}: {exc}"
        return result

    status = ("invalid" if stats["invalidPolicies"] or stats["invalidReferences"]
              else "configured" if stats["references"]
              else "defined-unlinked" if stats["policies"] else "not-configured")
    feature["configuration"] = {
        "status": status, "evidence": str(path),
        **{key: stats[key] for key in ("policies", "references", "invalidPolicies", "invalidReferences")},
    }
    result["mapFootprint"], result["recommendations"] = audit_map(data, stats, path)
    if not observations:
        if stats["references"] and status == "configured":
            result["recommendations"].append(recommendation(
                "inspect-observations",
                "Supply the project's observation export to check for dated SLA evidence.",
                path, references=stats["references"],
            ))
        return result

    export_path = root / observations
    evidence = {"status": "unknown", "evidence": str(export_path)}
    feature["observation"] = evidence
    try:
        if not export_path.is_file():
            raise ValueError("expected a readable regular observation export")
        export = service_report.read_json(export_path)
        now = datetime.now(timezone.utc)
        checked = service_report.report(data, export, now)
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        evidence.update(status="invalid-export", reason=str(exc))
        return result

    targets = checked["targets"]
    counts = Counter(target["status"] for target in targets)
    usable = [target for target in targets if target["status"] in RECENT_RESULTS]
    examples = (usable + [target for target in targets if target["status"] not in RECENT_RESULTS])[:SAMPLE_LIMIT]
    synthetic = bool(data.get("synthetic") or export.get("synthetic") or export.get("replay"))
    evidence.update(
        status=("synthetic-or-replay" if synthetic else "observed" if usable else
                "stale-only" if counts["stale"] and counts["stale"] == len(targets) else "no-current-evidence"),
        referenceTime=checked["referenceTime"],
        results=dict(sorted(counts.items())),
        examples=[{key: target[key] for key in
                   ("row", "target", "status", "source", "windowEnd", "observedAt", "method", "evaluation")
                   if key in target} for target in examples],
    )
    if status == "configured" and not synthetic and not usable:
        result["recommendations"].append(recommendation(
            "check-observation-collection",
            "Check that the collector supplies dated observations for the linked capabilities. Inspect missing, stale or invalid evidence before judging compliance.",
            export_path, results=evidence["results"],
        ))
    return result


def format_report(result):
    feature = result["features"][0]
    lines = ["Promise Doctor · SLA adoption"]
    for area in ("availability", "configuration", "observation"):
        entry = feature[area]
        lines.append(f"  {area}: {entry['status']} ({service_report.display(entry['evidence'])})")
        if "policies" in entry:
            lines.append(f"    {entry['policies']} policies, {entry['references']} references")
        if entry.get("results"):
            lines.append("    " + ", ".join(f"{key}: {value}" for key, value in entry["results"].items()))
        for example in entry.get("examples", []):
            fields = ", ".join(f"{key}: {service_report.display(value)}" for key, value in example.items())
            lines.append(f"    {fields}")
        if "reason" in entry:
            lines.append("    " + service_report.display(entry["reason"]))
    footprint = result.get("mapFootprint")
    if footprint is not None:
        surface_count = footprint["declaredSurfaces"]
        surfaces = f"{surface_count} declared surfaces" if surface_count is not None else "surface count unknown"
        parent_note = f", {footprint['unresolvedParents']} with unresolved parents" if footprint["unresolvedParents"] else ""
        lines.append(f"  Map footprint: {footprint['rows']} rows, including {footprint['rootRows']} roots "
                     f"and {footprint['continuations']} continuations{parent_note}. {footprint['scenarios']} scenarios, "
                     f"{footprint['singleScenarioRows']} single-scenario rows, {surfaces}. "
                     f"[{service_report.display(footprint['evidence'])}]")
    for item in result["recommendations"]:
        source = item["evidence"]
        pointers = {key: value for key, value in source.items() if key != "file"}
        lines.append(f"  {item['action']} [{service_report.display(source['file'])}]")
        if pointers:
            lines.append("    " + json.dumps(pointers, sort_keys=True))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="project root")
    parser.add_argument("--map", help="explicit map JSON path")
    parser.add_argument("--observations", help="explicit service observation export")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = inspect_project(args.cwd, args.map, args.observations)
    print(json.dumps(report, indent=2) if args.json else format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
