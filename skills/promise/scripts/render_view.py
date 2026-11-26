#!/usr/bin/env python3
"""Render a local, read-only view of a Promise outcome document."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from bridge_validate import exact_text
from changed_rows import norm_path
import lint_outcome
from outcome_rows import extract_lines


def document_view(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as source:
        text = source.read()
    original_lines = text.splitlines(keepends=True)
    lines = text.splitlines()
    bounds = lint_outcome.tldr_block_bounds(lines)
    if bounds is None:
        raise ValueError("the source has no §0 TLDR section")
    start, end = bounds
    header = lines[:start]
    title = next((line[2:].strip() for line in header if line.startswith("# ")), None)
    if not title:
        raise ValueError("the source has no document title")

    sections = []
    for number in range(1, 11):
        bounds = lint_outcome.section_bounds(lines, number)
        if bounds is not None:
            first, last = bounds
            sections.append({
                "number": number,
                "heading": lines[first][3:],
                "markdown": "".join(original_lines[first + 1:last]),
            })
    return {
        "title": title,
        "header": "".join(original_lines[1:start]),
        "tldr": "".join(original_lines[start:end]),
        "agentNotes": "".join(original_lines[end:(lint_outcome.section_bounds(lines, 0) or bounds)[1]]),
        **extract_lines(lines),
        "sections": sections,
    }


REPORT_LIMIT = 64 * 1024 * 1024
SERVICE_FIELDS = (
    "target", "status", "kind", "revision", "source", "windowStart", "windowEnd",
    "observedAt", "scope", "method", "assessor", "rationale", "evidence",
    "measurements", "reasons", "hardBreach", "evaluation", "assessmentBand",
    "sampleCount", "counts", "aggregation",
)
LANE_RESULTS = {"proven": "lane-green", "under-proven": "under-proven", "not-built": "not-built"}
FIELD_LABELS = {
    "target": "Service target", "status": "Result", "referenceTime": "Evidence reference time",
    "observedAt": "Observed at", "hardBreach": "Hard limit breached",
    "acceptableWhen": "Conditions for acceptance", "evaluation": "Evaluation method",
    "sampleCount": "Number of samples", "sampleTotal": "Total samples",
    "minSamples": "Minimum samples", "unit": "Unit", "p95": "95th percentile",
    "rows": "Capabilities", "verdicts": "Computed lane verdicts", "recorded": "Recorded verdicts",
    "mustNotProven": "Required capabilities without a green lane",
    "lanesNotInRun": "Test lanes outside this run", "cases": "Test cases",
    "orphanCount": "Tests without a capability", "run": "Test run",
    "buckets": "Test results", "rowsWithoutDoc": "Capabilities without an outcome document",
    "optimistic": "Recorded verdicts above the test result",
    "promotable": "Candidates for reconciliation",
    "passingButUnderProven": "Passing capabilities needing more evidence",
    "leftOutCount": "Tests deliberately left out",
    "leftOutProblemCount": "Problems with tests left out",
    "staleLeftOutCount": "Left-out tests absent from this run",
    "failingLeftOutCount": "Left-out tests that failed",
    "skippedCitationCount": "Cited tests that were skipped",
    "fingerprint": "Report fingerprint", "ref": "Evidence reference",
    "leftOutOutOfScopeCount": "Left-out notes outside the supplied test files",
}
RESULT_LABELS = {
    "target": "Target met", "acceptable": "Acceptable", "unacceptable": "Unacceptable",
    "missing": "Evidence missing", "stale": "Evidence out of date",
    "insufficient": "Insufficient evidence", "invalid-evidence": "Invalid evidence",
    "invalid-policy": "Invalid policy", "supplied-assessment": "Supplied assessment",
    "lane-green": "Lane green", "under-proven": "More evidence needed",
    "not-built": "Not built", "not-run": "Not checked", "never-ran": "Test did not run",
    "missing-citation": "Citation missing", "invalid-citation": "Invalid citation",
}
EVIDENCE_TABLE_STYLE = """
.evidence-table { width: 100%; border-collapse: collapse; margin-block: .6rem; table-layout: fixed; }
.evidence-table th, .evidence-table td { padding: .55rem; border: 1px solid #d3dae3; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.evidence-table th { width: 32%; font-weight: 600; background: #f5f7fa; }
.evidence-table ul { margin: 0; padding-left: 1.2rem; }
.evidence-table .evidence-table { margin: 0; }
@media (max-width: 600px) {
  .evidence-table, .evidence-table tbody, .evidence-table tr, .evidence-table th, .evidence-table td { display: block; width: auto; }
  .evidence-table td { border-top: 0; }
}
"""


def field_label(key: str) -> str:
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", key).replace("_", " ").replace("-", " ").lower()
    return words[:1].upper() + words[1:]


def result_label(value):
    return RESULT_LABELS.get(value, value) if isinstance(value, str) else value


def readable_table(value, field: str = "") -> str:
    """Display every supplied value as escaped text, lists or labelled table rows."""
    if isinstance(value, dict):
        if not value:
            return "None reported"
        rows = []
        for key, item in value.items():
            label = "Lane green" if field == "verdicts" and key == "proven" else field_label(key)
            if field == "counts":
                label = field_label(result_label(key))
            if field == "measurements" and label != key:
                label += f" ({key})"
            rows.append(f'<tr><th scope="row">{escape(label)}</th>'
                        f'<td>{readable_table(item, key)}</td></tr>')
        return '<table class="evidence-table"><tbody>' + "".join(rows) + "</tbody></table>"
    if isinstance(value, list):
        if not value:
            return "None reported"
        return "<ul>" + "".join(f"<li>{readable_table(item, field)}</li>" for item in value) + "</ul>"
    if value is None:
        return "Not reported"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str) and field in ("status", "evaluation", "assessmentBand"):
        return escape(result_label(value))
    return escape(str(value))


def read_report(path: Path, key: str) -> tuple[dict, list]:
    with path.open("rb") as handle:
        raw = handle.read(REPORT_LIMIT + 1)
    if len(raw) > REPORT_LIMIT:
        raise ValueError(f"{path.name}: report exceeds 64 MiB")
    report = json.loads(raw)
    entries = report.get(key) if isinstance(report, dict) else None
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ValueError(f"{path.name}: expected a report with a {key} array")
    return report, entries


def report_scope(report: dict) -> list[str] | None:
    if "scope" not in report:
        return None
    scope = report["scope"]
    rows = scope.get("rows") if isinstance(scope, dict) else None
    if (not isinstance(rows, list) or not rows
            or not all(isinstance(row, str) and row for row in rows)
            or len(set(rows)) != len(rows)):
        raise ValueError("report scope must name unique non-empty capability IDs")
    supporting = scope.get("supportingRows", [])
    if (not isinstance(supporting, list)
            or not all(isinstance(row, str) and row for row in supporting)
            or len(set(supporting)) != len(supporting) or set(supporting) & set(rows)):
        raise ValueError("supporting capability IDs must be unique and outside the selected scope")
    return rows


def add_evidence(view: dict, args: argparse.Namespace) -> None:
    """Join explicit report exports to §6 without promoting a verdict."""
    view["provenance"] = {
        "sourceRevision": args.source_revision,
        "renderedAt": datetime.now(timezone.utc).isoformat(),
    }
    view["evidenceSources"] = {}
    map_rows = {}
    map_digest = None
    map_scope = None
    if args.map_report:
        try:
            doc = args.doc.resolve().relative_to(args.project_root.resolve()).as_posix()
        except ValueError:
            raise ValueError("the source document must be inside --project-root when using reports") from None
        report, entries = read_report(args.map_report, "rows")
        if not isinstance(report.get("summary"), dict) or not isinstance(report.get("lanes"), dict):
            raise ValueError(f"{args.map_report.name}: expected map_report.py --json output")
        map_digest = report.get("mapDigest")
        view["evidenceSources"]["capabilityMap"] = args.map_report.name
        map_scope = report_scope(report)
        if map_scope:
            ids = [entry.get("id") for entry in entries]
            if (not all(isinstance(row_id, str) for row_id in ids)
                    or set(ids) != set(map_scope) or len(ids) != len(map_scope)):
                raise ValueError("map report scope does not match its capabilities")
            view["evidenceSources"]["capabilityScope"] = map_scope
            view["evidenceSources"]["supportingCapabilities"] = report["scope"].get("supportingRows", [])
        linked_ids = {row["row"] for row in view["rows"] if row["row"]}
        for entry in entries:
            row_id = entry.get("id")
            if isinstance(row_id, str) and row_id in linked_ids:
                if row_id in map_rows:
                    raise ValueError(f"{args.map_report.name}: duplicate row {row_id}")
                map_rows[row_id] = entry

    services = {}
    if args.service_report:
        report, entries = read_report(args.service_report, "targets")
        if type(report.get("replay")) is not bool or not isinstance(report.get("referenceTime"), str):
            raise ValueError(f"{args.service_report.name}: expected service_report.py --json output")
        if (not isinstance(map_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", map_digest)
                or report.get("mapDigest") != map_digest):
            raise ValueError("map and SLA reports must be regenerated from the same map snapshot")
        view["evidenceSources"]["service"] = {
            "file": args.service_report.name,
            "referenceTime": report["referenceTime"],
            "replay": report["replay"],
            "rows": report_scope(report),
        }
        for entry in entries:
            row_id = entry.get("row")
            if isinstance(row_id, str) and row_id in map_rows:
                services.setdefault(row_id, []).append({key: entry[key] for key in SERVICE_FIELDS if key in entry})

    for row in view["rows"]:
        row_id = row["row"]
        evidence = row["evidence"] = {"status": "not-linked" if not row_id else "missing"}
        if map_scope is not None and row_id and row_id not in map_scope:
            evidence["status"] = "outside-scope"
            continue
        candidate = map_rows.get(row_id)
        if candidate is None:
            continue
        row_doc = candidate.get("doc")
        if row_doc is not None and not isinstance(row_doc, str):
            raise ValueError(f"capability {row_id}: expected a document path or null")
        document_recorded = bool(row_doc and row_doc.strip())
        if document_recorded and norm_path(row_doc) != doc:
            evidence["status"] = "doc-mismatch"
            continue
        scenarios = candidate.get("scenarios")
        if not isinstance(scenarios, list):
            raise ValueError(f"capability {row_id}: expected a scenarios array")
        matches = [
            scenario for scenario in scenarios
            if isinstance(scenario, dict) and isinstance(scenario.get("then"), str)
            and scenario.get("altitude") == row["altitude"]
            and exact_text(scenario["then"]) == exact_text(row["then"])
        ]
        if not row["then"] or len(matches) != 1:
            evidence["status"] = "scenario-mismatch"
            continue
        scenario = matches[0]
        lane = scenario.get("lane")
        citations = candidate.get("citations")
        if not isinstance(citations, list):
            raise ValueError(f"capability {row_id}: expected a citations array")
        computed = candidate.get("computed")
        evidence.update(
            status="linked",
            mapDocumentRecorded=document_recorded,
            recordedVerdict=candidate.get("recorded"),
            computedRowStatus=LANE_RESULTS.get(computed) if isinstance(computed, str) else None,
            testLane=lane if isinstance(lane, str) else None,
            testCitations=[
                {key: citation.get(key) for key in ("file", "name", "status")}
                for citation in citations
                if isinstance(citation, dict) and isinstance(lane, str) and citation.get("lane") == lane
            ],
            serviceTargets=services.get(row_id, []),
        )
        service_rows = view["evidenceSources"].get("service", {}).get("rows")
        if service_rows is not None:
            evidence["serviceInScope"] = row_id in service_rows
        if "evidence" in scenario:
            explicit = scenario["evidence"]
            if (not isinstance(explicit, dict) or not isinstance(explicit.get("status"), str)
                    or not isinstance(explicit.get("citations"), list)
                    or not all(isinstance(c, dict) for c in explicit["citations"])):
                raise ValueError(f"capability {row_id}: invalid explicit scenario evidence")
            evidence["scenarioEvidenceStatus"] = explicit["status"]
            evidence["testCitations"] = [
                {key: citation.get(key) for key in ("file", "name", "status")}
                for citation in explicit["citations"]
            ]


def evidence_html(evidence: dict, service_reported: bool) -> str:
    status = evidence["status"]
    if status != "linked":
        messages = {
            "not-linked": "No capability row is linked.",
            "missing": "No matching capability-map evidence was supplied.",
            "doc-mismatch": "The capability-map report links this row to another document.",
            "scenario-mismatch": "The report could not uniquely match this acceptance scenario.",
            "outside-scope": "This capability is outside the supplied capability-map report.",
        }
        return f'<p>{messages[status]}</p>'
    recorded = escape(str(evidence["recordedVerdict"] or "not reported"))
    computed = escape(str(evidence["computedRowStatus"] or "not reported"))
    details = [f"<p>Recorded map verdict: {recorded}. Computed row status: {computed}.</p>"]
    if "scenarioEvidenceStatus" in evidence:
        explicit = escape(evidence["scenarioEvidenceStatus"])
        details.append(f"<p>Explicit scenario evidence: {explicit}.</p>")
    else:
        details.append("<p>Test citations apply to the lane. A green lane does not establish scenario proof.</p>")
    if not evidence["mapDocumentRecorded"]:
        details.append("<p>The map does not record a document for this capability. The link comes from the acceptance row.</p>")
    for citation in evidence["testCitations"]:
        name = escape(str(citation["name"] or "unnamed"))
        file = escape(str(citation["file"] or "unknown file"))
        result = escape(str(citation["status"] or "not reported"))
        details.append(f"<p>Test: <code>{file}::{name}</code> · {result}</p>")
    if service_reported and not evidence["serviceTargets"]:
        details.append("<p>This capability is outside the supplied SLA report.</p>"
                       if evidence.get("serviceInScope") is False
                       else "<p>The supplied SLA report has no targets for this row.</p>")
    for target in evidence["serviceTargets"]:
        name = escape(str(target.get("target") or "unnamed"))
        result = escape(str(target.get("status") or "not reported"))
        detail = {key: value for key, value in target.items() if key not in ("target", "status")}
        assessment = " · supplied assessment, independently unverified" if target.get("evaluation") == "supplied-assessment" else ""
        details.append(f'<details><summary>SLA: {name} · {result}{assessment}</summary>'
                       f'{readable_table(detail)}</details>')
    return "".join(details)


def provenance_html(view: dict) -> str:
    metadata = view["provenance"]
    sources = view["evidenceSources"]
    lines = [
        "Source revision (supplied): " + (metadata["sourceRevision"] or "not supplied"),
        "Rendered at: " + metadata["renderedAt"],
    ]
    if "capabilityMap" in sources:
        lines.append("Capability map and test report: " + sources["capabilityMap"])
    if sources.get("capabilityScope"):
        lines.append("Selected capabilities only: " + ", ".join(sources["capabilityScope"])
                     + ". Coverage outside the supplied run and entry points is not assessed.")
    if sources.get("supportingCapabilities"):
        lines.append("Other map capabilities covering supplied inputs: " + ", ".join(sources["supportingCapabilities"])
                     + ". Their other tests were not assessed.")
    if "service" in sources:
        service = sources["service"]
        lines.append("SLA report: " + service["file"] + " · reference time " + service["referenceTime"])
        if service["replay"]:
            lines.append("Historical SLA replay. These statuses do not establish current compliance.")
        else:
            lines.append("SLA statuses are as of the report’s reference time.")
        if service.get("rows"):
            lines.append("SLA report covers selected capabilities only: " + ", ".join(service["rows"])
                         + ". Other capabilities and unreferenced policies are not assessed.")
    return "<p>" + "<br>".join(escape(line) for line in lines) + "</p>"


def render_html(view: dict) -> str:
    """Put source strings in escaped text nodes. The page needs no script."""
    title = escape(view["title"])
    rows_by_id = {}
    for row in view["rows"]:
        rows_by_id.setdefault(row["id"], []).append(row)
    service_reported = "service" in view["evidenceSources"]

    def row_list(rows):
        items = "".join(
            f'<li><strong>{escape(row["id"])}</strong> {escape(row["then"])}'
            f'{evidence_html(row["evidence"], service_reported)}</li>'
            for row in rows
        )
        return f"<ul>{items}</ul>" if items else ""

    tagged = set()
    rule_items = []
    for rule in view["rules"]:
        tagged.update(rule["tags"])
        related = [row for tag in rule["tags"] for row in rows_by_id.get(tag, [])]
        rule_items.append(f'<li>{escape(rule["text"])}{row_list(related)}</li>')
    rules = f'<section><h2>Rules and acceptance rows</h2><ol>{"".join(rule_items)}</ol></section>' if rule_items else ""
    remaining = row_list(row for row in view["rows"] if row["id"] not in tagged)
    untagged = f'<section><h2>Acceptance rows without a rule tag</h2>{remaining}</section>' if remaining else ""
    navigation = "".join(
        f'<li><a href="#section-{section["number"]}">{escape(section["heading"])}</a></li>'
        for section in view["sections"]
    )
    sections = "".join(
        f'<section id="section-{section["number"]}"><h2>{escape(section["heading"])}</h2>'
        f'<pre>{escape(section["markdown"])}</pre></section>'
        for section in view["sections"]
    )
    notes = f'<section aria-label="Agent notes"><pre>{escape(view["agentNotes"])}</pre></section>' if view["agentNotes"] else ""
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font: 1rem/1.55 system-ui, sans-serif; margin: 2rem auto; padding: 0 1rem; max-width: 55rem; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; }}
section {{ margin-block: 2rem; }}
li {{ margin-block: .3rem; }}
{EVIDENCE_TABLE_STYLE}
</style>
<main>
<h1>{title}</h1>
{provenance_html(view)}
<pre>{escape(view["header"])}</pre>
<section aria-label="TLDR"><pre>{escape(view["tldr"])}</pre></section>
{notes}
{rules}
{untagged}
<nav aria-label="Outcome document sections"><ul>{navigation}</ul></nav>
{sections}
</main>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("doc", type=Path)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--json", action="store_true", help="print the structured document")
    output.add_argument("--out", type=Path, help="write a new standalone HTML file")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="root for map document paths")
    parser.add_argument("--map-report", type=Path, help="explicit map_report.py --json output, optionally joined to JUnit")
    parser.add_argument("--service-report", type=Path, help="explicit service_report.py --json output from the same map")
    parser.add_argument("--source-revision", help="caller-supplied revision of the rendered source")
    args = parser.parse_args()
    if args.service_report and not args.map_report:
        parser.error("--service-report needs --map-report from the same map")
    try:
        view = document_view(args.doc)
        add_evidence(view, args)
        if args.json:
            print(json.dumps(view))
        else:
            page = render_html(view).encode("utf-8")
            with TemporaryDirectory(dir=args.out.parent) as temporary:
                staged = Path(temporary) / "view.html"
                staged.write_bytes(page)
                os.link(staged, args.out)
    except (OSError, ValueError, RecursionError) as error:
        print(f"render_view.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
