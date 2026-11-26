#!/usr/bin/env python3
"""Render a whole capability map from explicit Promise report exports."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from render_view import (
    EVIDENCE_TABLE_STYLE, LANE_RESULTS, SERVICE_FIELDS,
    evidence_html, provenance_html, read_report, readable_table, result_label, report_scope,
)


def load_view(args: argparse.Namespace) -> dict:
    report, rows = read_report(args.map_report, "rows")
    if not isinstance(report.get("summary"), dict) or not isinstance(report.get("lanes"), dict):
        raise ValueError("expected map_report.py --json output")
    digest = report.get("mapDigest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("regenerate the capability report to include its map digest")
    seen = set()
    for row in rows:
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id or row_id in seen:
            raise ValueError("capability IDs must be non-empty and unique")
        seen.add(row_id)
        if row.get("computed") not in (None, "proven", "under-proven", "not-built"):
            raise ValueError(f"{row_id}: invalid computed verdict")
        for key in ("scenarios", "citations"):
            entries = row.get(key)
            if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
                raise ValueError(f"{row_id}: expected a {key} array")
        for scenario in row["scenarios"]:
            explicit = scenario.get("evidence")
            if explicit is not None and (
                not isinstance(explicit, dict) or not isinstance(explicit.get("status"), str)
                or not isinstance(explicit.get("citations"), list)
                or not all(isinstance(item, dict) for item in explicit["citations"])
            ):
                raise ValueError(f"{row_id}: invalid explicit scenario evidence")
            if explicit is not None and not isinstance(explicit.get("unresolved", []), list):
                raise ValueError(f"{row_id}: invalid unresolved citation list")
        for citation in row["citations"] + [
            c for s in row["scenarios"] for c in (s.get("evidence") or {}).get("citations", [])
        ]:
            if any(key not in citation for key in ("file", "name", "status")):
                raise ValueError(f"{row_id}: incomplete test citation")
    view = {
        "rows": rows, "mapDigest": digest, "summary": report["summary"],
        "provenance": {
            "sourceRevision": args.source_revision,
            "renderedAt": datetime.now(timezone.utc).isoformat(),
        },
        "evidenceSources": {"capabilityMap": args.map_report.name},
        "services": {}, "projectServices": [],
        "simulation": report.get("_simulation"),
    }
    scope = report_scope(report)
    if scope:
        if set(scope) != seen:
            raise ValueError("map report scope does not match its capabilities")
        view["evidenceSources"]["capabilityScope"] = scope
        view["evidenceSources"]["supportingCapabilities"] = report["scope"].get("supportingRows", [])
    if args.service_report:
        service, targets = read_report(args.service_report, "targets")
        if service.get("mapDigest") != digest:
            raise ValueError("map and SLA reports must come from the same map snapshot")
        if type(service.get("replay")) is not bool or not isinstance(service.get("referenceTime"), str):
            raise ValueError("expected service_report.py --json output")
        view["evidenceSources"]["service"] = {
            "file": args.service_report.name,
            "referenceTime": service["referenceTime"], "replay": service["replay"],
            "rows": report_scope(service),
        }
        service_rows = view["evidenceSources"]["service"]["rows"]
        if service_rows and set(service_rows) - seen:
            raise ValueError("SLA report scope includes capabilities absent from the map report")
        for target in targets:
            row_id = target.get("row")
            if service_rows and row_id not in service_rows:
                raise ValueError("SLA target is outside the report's declared scope")
            filtered = {key: target[key] for key in SERVICE_FIELDS if key in target}
            if row_id is None:
                view["projectServices"].append(filtered)
                continue
            if not isinstance(row_id, str) or row_id not in seen:
                if view["evidenceSources"].get("capabilityScope"):
                    raise ValueError("SLA report covers capabilities outside the map report selection; pass the same --row flags")
                raise ValueError("SLA report refers to an unknown capability")
            view["services"].setdefault(row_id, []).append(filtered)
    return view


def text(value) -> str:
    return escape(str(value)) if value is not None else "not reported"


def service_cards(targets: list) -> str:
    return "".join(
        f'<details><summary>{text(target.get("target"))} · '
        f'{text(result_label(target.get("status")))}</summary>'
        f'{readable_table(target)}</details>'
        for target in targets
    )


def render_html(view: dict) -> str:
    cards, navigation = [], []
    service_reported = "service" in view["evidenceSources"]
    for index, row in enumerate(view["rows"]):
        anchor = f"capability-{index}"
        row_id = text(row["id"])
        story = text(row.get("story"))
        navigation.append(f'<li><a href="#{anchor}">{row_id} · {story}</a></li>')
        scenarios = []
        for scenario in row["scenarios"]:
            lane = scenario.get("lane")
            evidence = {
                "status": "linked", "recordedVerdict": row.get("recorded"),
                "computedRowStatus": LANE_RESULTS.get(row.get("computed")),
                "mapDocumentRecorded": True,
                "testCitations": [], "serviceTargets": [],
            }
            explicit = scenario.get("evidence")
            if explicit is not None:
                evidence["scenarioEvidenceStatus"] = explicit["status"]
                evidence["testCitations"] = explicit["citations"]
            lane_link = (
                f'<p><a href="#citations-{index}">See capability citations for this lane</a>.</p>'
                if explicit is None else ""
            )
            unresolved = "".join(
                f'<li><code>{text(ref)}</code> · not cited in this lane</li>'
                for ref in (explicit or {}).get("unresolved", [])
            )
            scenarios.append(
                f'<li><h3>{text(scenario.get("id"))}</h3><p>{text(scenario.get("then"))}</p>'
                f'<p>Altitude · {text(scenario.get("altitude"))}. Test lane · {text(lane)}.</p>'
                f'{evidence_html(evidence, False)}{lane_link}<ul>{unresolved}</ul></li>'
            )
        citations = "".join(
            f'<li><code>{text(c.get("file"))}::{text(c.get("name"))}</code>'
            f' · {text(c.get("lane"))} · {text(c.get("status"))}</li>'
            for c in row["citations"]
        ) or "<li>No test citations recorded.</li>"
        services = view["services"].get(row["id"], [])
        service_html = service_cards(services)
        if not services:
            service_html = "<p>The supplied SLA report has no targets for this capability.</p>" if service_reported else "<p>No SLA report supplied.</p>"
            selected = view["evidenceSources"].get("service", {}).get("rows")
            if selected and row["id"] not in selected:
                service_html = "<p>This capability is outside the supplied SLA report.</p>"
        status = LANE_RESULTS.get(row.get("computed"), "not checked")
        cards.append(f"""
<article id="{anchor}">
<h2>{row_id} · {story}</h2>
<p>Recorded verdict · {text(row.get("recorded"))}. Computed row status · {text(status)}.
Test result · {text(row.get("bucket"))}.</p>
<p>Outcome document · <code>{text(row.get("doc"))}</code></p>
{readable_table({"priority": row.get("priority"), "entryPoints": row.get("surfaces")})}
<details open><summary>Scenarios ({len(scenarios)})</summary>
<ol>{''.join(scenarios) or '<li>No scenarios recorded.</li>'}</ol></details>
<details id="citations-{index}"><summary>All capability test citations ({len(row['citations'])})</summary><ul>{citations}</ul></details>
<h3>Service levels</h3>{service_html}
<p><a href="#top">Back to capabilities</a></p>
</article>""")
    simulation = f'<p class="notice">{text(view["simulation"])}</p>' if view["simulation"] else ""
    project_services = (
        "<section><h2>Service policies without a capability</h2>"
        + service_cards(view["projectServices"]) + "</section>"
        if view["projectServices"] else ""
    )
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Promise capability map</title>
<style>
body {{ margin: 2rem auto; padding: 0 1rem; max-width: 75rem; font: 1rem/1.6 system-ui, sans-serif; color: #17212e; background: #f5f7fa; }}
article, header, nav {{ background: white; padding: 1.5rem; border: 1px solid #d3dae3; border-radius: .6rem; margin-block: 1rem; }}
h1, h2, h3 {{ line-height: 1.3; }}
h2 {{ scroll-margin-top: 1rem; }}
a {{ color: #154f93; }}
pre, code, p, li {{ overflow-wrap: anywhere; }}
pre {{ white-space: pre-wrap; }}
li, details {{ margin-block: .75rem; }}
summary {{ cursor: pointer; font-weight: 600; }}
.notice {{ border-left: .3rem solid #9a6500; padding-left: 1rem; }}
{EVIDENCE_TABLE_STYLE}
@media print {{ article {{ break-inside: avoid; }} nav {{ display: none; }} }}
</style>
<main id="top">
<header><h1>Promise capability map</h1><p>{len(view["rows"])} capabilities</p>
{provenance_html(view)}
<p>Map snapshot · <code>{text(view["mapDigest"])}</code></p>
<p class="notice">This page is a snapshot of supplied reports. A passing citation needs reconciliation
to establish that it asserts the scenario. Re-render after updating the reports.</p>
{simulation}
{project_services}
<details><summary>Report summary and run provenance</summary>
{readable_table(view["summary"])}</details>
</header>
<nav aria-label="Capabilities"><h2>Capabilities</h2>
<p>Choose a capability below, or use your browser’s Find to search this page.</p>
<ul>{''.join(navigation) or '<li>The map has no capabilities.</li>'}</ul></nav>
{''.join(cards)}
</main></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_report", type=Path, help="map_report.py --json output")
    parser.add_argument("--service-report", type=Path, help="service_report.py --json output from the same map")
    parser.add_argument("--source-revision", help="caller-supplied source revision label")
    parser.add_argument("--out", required=True, type=Path, help="write a new standalone HTML file")
    args = parser.parse_args()
    try:
        page = render_html(load_view(args)).encode("utf-8")
        with TemporaryDirectory(dir=args.out.parent) as temporary:
            staged = Path(temporary) / "map.html"
            staged.write_bytes(page)
            os.link(staged, args.out)
    except (OSError, ValueError, RecursionError) as error:
        print(f"render_map.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
