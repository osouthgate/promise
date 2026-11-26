#!/usr/bin/env python3
"""Dated service observations alongside (never as) functional proof.

Project servicePolicies, referenced by capability rows, declare quantitative
bands or qualitative assessment criteria. The quantitative adapter supports
optional guardrails and conditions for the middle band. This reader neither
collects telemetry nor verifies its truth. See references/service-targets.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

PASSING = {"target", "acceptable"}
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_MAP_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 10000
MAX_TEXT = 1000
MAX_EVIDENCE = 20
DISPLAY_LIMIT = 15


class Errors(list):
    """Bound error output independently of a malformed export's record count."""
    def append(self, message):
        self.total = getattr(self, "total", 0) + 1
        if len(self) < 8:
            super().append(message)
        elif len(self) == 8:
            super().append("further validation errors omitted; fix these first")


def read_json_bytes(path, kind):
    limit = MAX_MAP_BYTES if kind == "map" else MAX_INPUT_BYTES
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("capability map exceeds the 64 MiB limit" if kind == "map" else
                         "observation export exceeds the 8 MiB limit; use bounded aggregate evidence or a scoped export")
    return raw


def read_json(path, kind="observations"):
    return json.loads(read_json_bytes(path, kind))


def display(value):
    """One bounded terminal line: supplier controls cannot alter report status."""
    escaped = json.dumps(str(value), ensure_ascii=True)[1:-1]
    return escaped if len(escaped) <= 1000 else escaped[:980] + "... [truncated]"


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def text(value, limit=MAX_TEXT):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit and all(c.isprintable() for c in value)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must include a timezone")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def policy_errors(policy):
    if not isinstance(policy, dict):
        return ["service target must be an object"]
    errors = Errors()
    for key in ("id", "revision"):
        if not text(policy.get(key)):
            errors.append(f"{key} must be non-empty text")
    if type(policy.get("maxAgeSeconds")) is not int or policy["maxAgeSeconds"] <= 0:
        errors.append("maxAgeSeconds must be a positive integer")
    if policy.get("kind") == "assessment":
        for key in ("basis", "scope", "method"):
            if not text(policy.get(key)):
                errors.append(f"{key} must be non-empty text")
        criteria = policy.get("criteria")
        if not isinstance(criteria, dict) or any(not text(criteria.get(k)) for k in ("target", "unacceptable")):
            errors.append("criteria must define target and unacceptable in words")
        elif "acceptable" in criteria and not text(criteria["acceptable"]):
            errors.append("optional acceptable criteria must be non-empty")
        if isinstance(criteria, dict) and set(criteria) - {"target", "acceptable", "unacceptable"}:
            errors.append("criteria may define only target, acceptable and unacceptable bands")
        standard = policy.get("standard")
        if standard is not None and (not isinstance(standard, dict) or
                                     any(not text(standard.get(k)) for k in ("name", "version"))):
            errors.append("standard must name the standard and its version")
        return errors
    if policy.get("kind") != "quantitative":
        return errors + ["kind must be quantitative or assessment; use explicit assessment criteria for other service promises"]
    for key in ("boundary", "workload", "metric", "unit"):
        if not text(policy.get(key)):
            errors.append(f"{key} must be non-empty text")
    for key in ("target", "unacceptable"):
        if not number(policy.get(key)):
            errors.append(f"{key} must be a finite number")
    for key in ("windowSeconds", "minSamples"):
        if type(policy.get(key)) is not int or policy[key] <= 0:
            errors.append(f"{key} must be a positive integer")
    if policy.get("direction") not in ("lower", "higher"):
        errors.append("direction must be lower or higher")
    if policy.get("aggregation") not in ("each-sample", "request-success-ratio"):
        errors.append("aggregation must be each-sample or request-success-ratio")
    units = {}
    if text(policy.get("metric")) and text(policy.get("unit")):
        units[policy["metric"]] = policy["unit"]
    for group in ("guardrails", "acceptableWhen"):
        conditions = policy.get(group, [])
        if not isinstance(conditions, list):
            errors.append(f"{group} must be an array")
            continue
        for i, condition in enumerate(conditions):
            label = f"{group}[{i}]"
            if not isinstance(condition, dict):
                errors.append(f"{label} must be an object")
                continue
            if not text(condition.get("metric")) or not text(condition.get("unit")):
                errors.append(f"{label} must name metric and unit")
            else:
                metric, unit = condition["metric"], condition["unit"]
                if metric in units and units[metric] != unit:
                    errors.append(f"{label}: conflicting units for {metric}")
                units[metric] = unit
            if condition.get("operator") not in ("at-least", "at-most") or not number(condition.get("value")):
                errors.append(f"{label} needs at-least/at-most and a finite value")
    if errors:
        return errors
    if policy["direction"] == "lower" and not policy["target"] < policy["unacceptable"]:
        errors.append("lower-is-better requires target < unacceptable")
    if policy["direction"] == "higher" and not policy["target"] > policy["unacceptable"]:
        errors.append("higher-is-better requires target > unacceptable")
    if policy["aggregation"] == "request-success-ratio":
        if policy["direction"] != "higher" or policy["unit"] != "%":
            errors.append("request-success-ratio requires higher direction and % unit")
        if not 0 <= policy["unacceptable"] < policy["target"] <= 100:
            errors.append("request-success-ratio thresholds must lie in [0, 100]")
        if any(c["metric"] == policy["metric"] for g in ("guardrails", "acceptableWhen") for c in policy.get(g, [])):
            errors.append("ratio conditions must name separately observed metrics")
    return errors


def units_for(policy):
    units = {policy["metric"]: policy["unit"]}
    for group in ("guardrails", "acceptableWhen"):
        units.update({c["metric"]: c["unit"] for c in policy.get(group, [])})
    return units


def conditions_hold(conditions, values):
    return all(values[c["metric"]] >= c["value"] if c["operator"] == "at-least"
               else values[c["metric"]] <= c["value"] for c in conditions)


def ratio_band(policy, successful, total, guardrails_ok, conditional_ok):
    # Counts stay exact even when a huge cohort's percentage rounds to 100.0.
    ratio = Fraction(100 * successful, total)
    if not guardrails_ok or ratio < Fraction(str(policy["unacceptable"])):
        return "unacceptable"
    if ratio >= Fraction(str(policy["target"])):
        return "target"
    return "acceptable" if conditional_ok else "unacceptable"


def classify(policy, value, values):
    if not conditions_hold(policy.get("guardrails", []), values):
        return "unacceptable"
    if policy["direction"] == "lower":
        if value >= policy["unacceptable"]:
            return "unacceptable"
        on_target = value < policy["target"]
    else:
        if value < policy["unacceptable"]:
            return "unacceptable"
        on_target = value >= policy["target"]
    if on_target:
        return "target"
    return "acceptable" if conditions_hold(policy.get("acceptableWhen", []), values) else "unacceptable"


def assess(policy, observation, now):
    """Validate a supplied assessment; never infer conformance from its prose."""
    errors = []
    for key in ("scope", "method", "revision"):
        if observation.get(key) != policy[key]:
            errors.append(f"{key} does not match the policy")
    for key in ("assessor", "rationale"):
        if not text(observation.get(key), 200 if key == "assessor" else MAX_TEXT):
            errors.append(f"{key} must be non-empty text")
    band = observation.get("band")
    if not isinstance(band, str) or band not in policy["criteria"]:
        errors.append("band must name one of this policy's defined criteria")
    evidence = observation.get("evidence")
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= MAX_EVIDENCE or any(
            not isinstance(e, dict) or not text(e.get("ref"), 500) or not text(e.get("description")) for e in evidence):
        errors.append("evidence must include a reference and description for each cited assessment")
    try:
        at = timestamp(observation.get("observedAt"))
        if at > now:
            errors.append("assessment is in the future")
    except (ValueError, OverflowError):
        at = None
        errors.append("observedAt must include a timezone")
    if errors:
        return {"status": "invalid-evidence", "reasons": errors}
    result = {k: observation[k] for k in ("scope", "method", "revision", "assessor", "rationale", "observedAt")}
    result["evidence"] = [{"ref": e["ref"], "description": e["description"]} for e in evidence]
    result.update(assessmentBand=band, evaluation="supplied-assessment")
    if (now - at).total_seconds() > policy["maxAgeSeconds"]:
        result.update(status="stale", reasons=["assessment is older than maxAgeSeconds"])
    else:
        result["status"] = band
    return result


def evaluate(policy, observation, now):
    if policy["kind"] == "assessment":
        return assess(policy, observation, now)
    errors = Errors()
    if observation.get("revision") != policy["revision"]:
        errors.append("revision does not match the policy")
    for key in ("boundary", "workload"):
        if observation.get(key) != policy[key]:
            errors.append(f"{key} does not match the service target")
    units = units_for(policy)
    if observation.get("units") != units:
        errors.append("units must exactly match the policy's metric and condition units")
    if not text(observation.get("source"), 200):
        errors.append("source must identify the telemetry export or collector")
    try:
        start, end = timestamp(observation.get("windowStart")), timestamp(observation.get("windowEnd"))
        if (end - start).total_seconds() != policy["windowSeconds"]:
            errors.append("observation duration does not match windowSeconds")
        if end > now:
            errors.append("observation window ends in the future")
    except (ValueError, OverflowError):
        start = end = None
        errors.append("windowStart and windowEnd must include timezones")
    if "buckets" in observation:
        if "samples" in observation:
            errors.append("provide buckets or samples, never both")
        if policy["aggregation"] != "request-success-ratio":
            errors.append("buckets require request-success-ratio aggregation")
        if errors:
            return {"status": "invalid-evidence", "reasons": errors}
        return evaluate_buckets(policy, observation, now, start, end)
    samples = observation.get("samples")
    if not isinstance(samples, list):
        errors.append("samples must be an array")
        samples = []
    if len(samples) > MAX_RECORDS:
        return {"status": "invalid-evidence", "reasons": ["more than 10000 samples; use aggregate ratio buckets or a scoped assessment"]}
    observed_metrics = set(units)
    if policy["aggregation"] == "request-success-ratio":
        observed_metrics.remove(policy["metric"])
    ids = set()
    for i, sample in enumerate(samples):
        if not isinstance(sample, dict):
            errors.append(f"samples[{i}] must be an object")
            continue
        sid = sample.get("id")
        if not text(sid) or sid in ids:
            errors.append(f"samples[{i}].id must be non-empty and unique")
        else:
            ids.add(sid)
        values = sample.get("values")
        if not isinstance(values, dict) or set(values) != observed_metrics or any(not number(v) for v in values.values()):
            errors.append(f"samples[{i}].values must hold exactly the finite observed metrics")
        if policy["aggregation"] == "request-success-ratio" and type(sample.get("successful")) is not bool:
            errors.append(f"samples[{i}].successful must be a boolean")
        try:
            at = timestamp(sample.get("at"))
            if start is not None and not start <= at < end:
                errors.append(f"samples[{i}].at must lie in [windowStart, windowEnd)")
        except (ValueError, OverflowError):
            errors.append(f"samples[{i}].at must include a timezone")
    if errors:
        return {"status": "invalid-evidence", "reasons": errors, "errorCount": errors.total}
    result = {key: observation[key] for key in ("source", "windowStart", "windowEnd")}
    result.update(sampleCount=len(samples), aggregation=policy["aggregation"])
    counts = {"target": 0, "acceptable": 0, "unacceptable": 0}
    measurements = {}
    hard_breach = False
    if samples:
        measurements = {m: {"unit": units[m], "min": min(s["values"][m] for s in samples),
                             "max": max(s["values"][m] for s in samples)} for m in sorted(observed_metrics)}
        if policy["aggregation"] == "request-success-ratio":
            successes = sum(s["successful"] for s in samples)
            ratio = 100 * successes / len(samples)
            measurements[policy["metric"]] = {"unit": "%", "value": ratio, "successful": successes, "total": len(samples)}
            # Conditions still apply to the same cohort; a good aggregate cannot
            # compensate for a failed hard guardrail or conditional observation.
            guardrails_ok = all(conditions_hold(policy.get("guardrails", []), s["values"]) for s in samples)
            hard_breach = not guardrails_ok
            band = ratio_band(policy, successes, len(samples), guardrails_ok,
                              all(conditions_hold(policy.get("acceptableWhen", []), s["values"]) for s in samples))
            counts[band] = 1
        else:
            for sample in samples:
                counts[classify(policy, sample["values"][policy["metric"]], sample["values"])] += 1
            hard_breach = bool(counts["unacceptable"])
    result.update(counts=counts, measurements=measurements, hardBreach=hard_breach)
    if (now - end).total_seconds() > policy["maxAgeSeconds"]:
        result.update(status="stale", reasons=["windowEnd is older than maxAgeSeconds"])
    elif hard_breach:
        result["status"] = "unacceptable"
    elif len(samples) < policy["minSamples"]:
        result.update(status="insufficient", reasons=["fewer than minSamples in this window"])
    else:
        result["status"] = "unacceptable" if counts["unacceptable"] else "acceptable" if counts["acceptable"] else "target"
    return result


def evaluate_buckets(policy, observation, now, start, end):
    """Exact cohort counts and extrema suffice for ratio + universal conditions."""
    buckets = observation["buckets"]
    if not isinstance(buckets, list) or not buckets or len(buckets) > MAX_RECORDS:
        return {"status": "invalid-evidence", "reasons": ["buckets must contain 1 to 10000 entries"]}
    errors, previous, total, successful = Errors(), start, 0, 0
    metrics = set(units_for(policy)) - {policy["metric"]}
    extrema = {m: {"min": float("inf"), "max": -float("inf")} for m in metrics}
    guardrails_ok, conditional_ok = True, True
    for i, bucket in enumerate(buckets):
        if not isinstance(bucket, dict):
            errors.append(f"buckets[{i}] must be an object")
            continue
        try:
            left, right = timestamp(bucket.get("start")), timestamp(bucket.get("end"))
            if left != previous or not left < right <= end:
                errors.append(f"buckets[{i}] must form ordered, contiguous, non-overlapping coverage")
            previous = right
        except (ValueError, OverflowError):
            errors.append(f"buckets[{i}] boundaries must include timezones")
        n, good = bucket.get("total"), bucket.get("successful")
        if type(n) is not int or type(good) is not int or not 0 <= good <= n <= 10**15:
            errors.append(f"buckets[{i}] requires integer 0 <= successful <= total <= 10^15")
            continue
        total += n
        successful += good
        values = bucket.get("extrema")
        expected = metrics if n else set()
        if not isinstance(values, dict) or set(values) != expected:
            errors.append(f"buckets[{i}].extrema must match condition metrics (empty for zero traffic)")
            continue
        valid = True
        for metric, limits in values.items():
            if (not isinstance(limits, dict) or set(limits) != {"min", "max"}
                    or not all(number(v) for v in limits.values()) or limits["min"] > limits["max"]):
                errors.append(f"buckets[{i}].extrema has invalid min/max")
                valid = False
            else:
                extrema[metric]["min"] = min(extrema[metric]["min"], limits["min"])
                extrema[metric]["max"] = max(extrema[metric]["max"], limits["max"])
        if valid and n:
            def holds(group):
                return all(values[c["metric"]]["min"] >= c["value"] if c["operator"] == "at-least"
                           else values[c["metric"]]["max"] <= c["value"] for c in policy.get(group, []))
            guardrails_ok &= holds("guardrails")
            conditional_ok &= holds("acceptableWhen")
    if previous != end:
        errors.append("buckets must cover the entire observation window")
    if errors:
        return {"status": "invalid-evidence", "reasons": errors, "errorCount": errors.total}
    result = {k: observation[k] for k in ("source", "windowStart", "windowEnd")}
    result.update(sampleCount=total, bucketCount=len(buckets), aggregation=policy["aggregation"],
                  counts={"target": 0, "acceptable": 0, "unacceptable": 0}, measurements={}, hardBreach=not guardrails_ok)
    if total:
        ratio = 100 * successful / total
        result["measurements"][policy["metric"]] = {"unit": "%", "value": ratio, "successful": successful, "total": total}
        for metric, limits in extrema.items():
            result["measurements"][metric] = {"unit": units_for(policy)[metric], **limits}
        band = ratio_band(policy, successful, total, guardrails_ok, conditional_ok)
        result["counts"][band] = 1
    if (now - end).total_seconds() > policy["maxAgeSeconds"]:
        result.update(status="stale", reasons=["windowEnd is older than maxAgeSeconds"])
    elif not guardrails_ok:
        result["status"] = "unacceptable"
    elif total < policy["minSamples"]:
        result.update(status="insufficient", reasons=["fewer than minSamples in this window"])
    else:
        result["status"] = band
    return result


def policy_index(data):
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise ValueError("map must have a rows array")
    policies = data.get("servicePolicies", [])
    if not isinstance(policies, list):
        raise ValueError("servicePolicies must be an array")
    by_id = {}
    for policy in policies:
        if not isinstance(policy, dict) or not text(policy.get("id")) or policy["id"] in by_id:
            raise ValueError("servicePolicies must have unique non-empty ids")
        by_id[policy["id"]] = policy
    return by_id, {pid: policy_errors(policy) for pid, policy in by_id.items()}


def policies_summary(data):
    """Whole-map validation with bounded output, not one result per row/ref."""
    policies, validation = policy_index(data)
    invalid = sum(bool(errors) for errors in validation.values())
    issues = []
    for pid, errors in validation.items():
        if errors and len(issues) < DISPLAY_LIMIT:
            issues.append({"policy": pid, "reasons": list(errors)})
    row_ids, refs_count, invalid_refs = set(), 0, 0
    for row in data["rows"]:
        if not isinstance(row, dict) or not text(row.get("id")) or row["id"] in row_ids:
            raise ValueError("map rows must have unique non-empty ids")
        row_ids.add(row["id"])
        refs = row.get("servicePolicyRefs", [])
        seen = set()
        if not isinstance(refs, list):
            invalid_refs += 1
            if len(issues) < DISPLAY_LIMIT:
                issues.append({"row": row["id"], "reasons": ["servicePolicyRefs must be an array"]})
            continue
        for pid in refs:
            refs_count += 1
            if not text(pid) or pid not in policies or pid in seen:
                invalid_refs += 1
                if len(issues) < DISPLAY_LIMIT:
                    issues.append({"row": row["id"], "reasons": ["unknown, invalid or duplicate policy reference"]})
            if isinstance(pid, str):
                seen.add(pid)
    return {"mode": "policy-validation", "rows": len(row_ids), "policies": len(policies),
            "references": refs_count, "invalidPolicies": invalid, "invalidReferences": invalid_refs,
            "issues": issues, "note": "Policy validation only; no service evidence or compliance assessed."}


def report(data, observations, now, selected_rows=None):
    by_id, validation = policy_index(data)
    if not isinstance(observations, dict) or not isinstance(observations.get("observations"), list):
        raise ValueError("observations must have an observations array")
    batches = observations["observations"]
    if any(not isinstance(b, dict) or not text(b.get("row")) or not text(b.get("target")) for b in batches):
        raise ValueError("every observation must name row and target")
    indexed = {}
    for batch in batches:
        indexed.setdefault((batch["row"], batch["target"]), []).append(batch)
    targets, known, row_ids, used = [], set(), set(), set()
    for row in data["rows"]:
        if not isinstance(row, dict) or not text(row.get("id")) or row["id"] in row_ids:
            raise ValueError("map rows must have unique non-empty ids")
        row_ids.add(row["id"])
        if "servicePolicyRefs" not in row:
            continue
        refs = row["servicePolicyRefs"]
        if not isinstance(refs, list):
            targets.append({"row": row["id"], "target": None, "status": "invalid-policy",
                            "reasons": ["servicePolicyRefs must be an array"]})
            continue
        seen = set()
        for pid in refs:
            entry = {"row": row["id"], "target": pid if isinstance(pid, str) else None,
                     "functionalVerdict": row.get("verdict")}
            errors = []
            if not text(pid) or pid not in by_id:
                errors.append("servicePolicyRefs must name existing project service policies")
            else:
                policy = by_id[pid]
                errors += validation[pid]
                entry.update(kind=policy.get("kind"), revision=policy.get("revision"))
                known.add((row["id"], pid))
                used.add(pid)
                if pid in seen:
                    errors.append("duplicate service policy reference")
                seen.add(pid)
            if selected_rows and row["id"] not in selected_rows:
                continue
            if errors:
                entry.update(status="invalid-policy", reasons=errors)
            else:
                matches = indexed.get((row["id"], pid), [])
                if not matches:
                    entry.update(status="missing", reasons=["no observation for this row and policy"])
                elif len(matches) != 1:
                    entry.update(status="invalid-evidence", reasons=["provide exactly one observation per row and policy"])
                else:
                    entry.update(evaluate(policy, matches[0], now))
            targets.append(entry)
    for pid in sorted(set(by_id) - used):
        errors = validation[pid]
        if errors:
            targets.append({"row": None, "target": pid, "status": "invalid-policy", "reasons": errors})
    unknown = sorted(indexed.keys() - known)
    if unknown:
        raise ValueError(f"observations name {len(unknown)} unknown row/target references; first entries: "
                         + ", ".join(f"{r}/{t}" for r, t in unknown[:8]))
    if selected_rows:
        if set(selected_rows) - row_ids:
            raise ValueError("row selection names an unknown capability")
        targets = [r for r in targets if r["row"] in selected_rows]
    result = {"referenceTime": now.isoformat(), "targets": targets,
            "unreferencedPolicies": sorted(set(by_id) - used) if not selected_rows else [],
            "note": "Dated observations only; functional verdicts are unchanged. No targets means unconfigured."}
    if selected_rows:
        result["scope"] = {"rows": sorted(set(selected_rows)),
                           "note": "Selected capabilities only; other capabilities and unreferenced policies are not assessed."}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--observations", type=Path, help="collector export; omit to validate policies and report missing evidence")
    parser.add_argument("--now", help="timezone-aware reference time for replay; default current UTC")
    parser.add_argument("--replay", action="store_true", help="explicit historical replay; requires --now and never establishes current compliance")
    parser.add_argument("--policies-only", action="store_true", help="validate shared policies and refs once, with a bounded summary and no evidence")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--row", action="append", help="report only this capability (repeatable)")
    parser.add_argument("--strict", action="store_true", help="fail unless all configured targets are target or acceptable")
    args = parser.parse_args(argv)
    try:
        if bool(args.now) != args.replay:
            raise ValueError("historical --now requires explicit --replay, and --replay requires --now")
        if args.policies_only and (args.observations or args.now or args.row):
            raise ValueError("--policies-only cannot be combined with observations, row selection or replay")
        map_bytes = read_json_bytes(args.map, "map")
        data = json.loads(map_bytes)
        observations = read_json(args.observations) if args.observations else {"observations": []}
        clock = datetime.now(timezone.utc)
        result = (policies_summary(data) if args.policies_only else
                  report(data, observations, timestamp(args.now) if args.now else clock, args.row))
        result.update(replay=args.replay, generatedAt=clock.isoformat())
        if args.json:
            result["mapDigest"] = hashlib.sha256(map_bytes).hexdigest()
        if args.replay:
            result["note"] = "HISTORICAL REPLAY ONLY: statuses are relative to the reference clock, never current service compliance."
        rendered = json.dumps(result, indent=2, allow_nan=False)
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        print(display(f"service report: {exc}"), file=sys.stderr)
        return 2
    if args.json:
        print(rendered)
    elif args.policies_only:
        print(f"Policies: {result['policies']}; rows: {result['rows']}; references: {result['references']}; "
              f"invalid policies: {result['invalidPolicies']}; invalid references: {result['invalidReferences']}")
        for issue in result["issues"]:
            print(display(issue))
        print(result["note"])
    else:
        print(("HISTORICAL REPLAY, not current compliance; reference " if args.replay else "Current reference ") + result["referenceTime"])
        if "scope" in result:
            print(result["scope"]["note"])
        statuses = {}
        for target in result["targets"]:
            statuses[target["status"]] = statuses.get(target["status"], 0) + 1
        print(f"Service results: {statuses}")
        entries = result["targets"] if args.row else [t for t in result["targets"] if t["status"] not in PASSING]
        for target in entries[:DISPLAY_LIMIT]:
            print(display(f"{target['row']} / {target['target']}: {target['status']} (functional: {target.get('functionalVerdict', 'not recorded')})"))
            if target.get("evaluation") == "supplied-assessment":
                print(display(f"  supplied assessment by {target['assessor']}; evidence not independently verified"))
            if "counts" in target:
                print(display(f"  {target['aggregation']}: {target['counts']}; measurements: {target['measurements']}"))
            for reason in target.get("reasons", []):
                print(display(f"  {reason}"))
        if len(entries) > DISPLAY_LIMIT:
            print(f"{len(entries) - DISPLAY_LIMIT} further entries omitted; use --row for details.")
        print(result["note"])
    if args.policies_only:
        return int(bool(result["invalidPolicies"] or result["invalidReferences"]))
    return int(any(t["status"] == "invalid-policy" for t in result["targets"]) or
               args.strict and any(t["status"] not in PASSING for t in result["targets"]))


if __name__ == "__main__":
    raise SystemExit(main())
