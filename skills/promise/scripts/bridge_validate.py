#!/usr/bin/env python3
"""Check a bridged outcome doc's §6 rows against the project's capability map.

    python3 bridge_validate.py doc.md
    python3 bridge_validate.py doc.md --cwd path/to/project --json
    python3 bridge_validate.py doc.md --strict
    python3 bridge_validate.py doc.md --linking

Once a doc is bridged (architecture.md § The bridge), §6's `Row` column is a
citation into the project's capability map, not a second copy of the
scenarios. This script is the staleness check: it confirms every acceptance
row that must be mapped has a `Row` id, that each id matches the project's
`map.rowIdPattern`, that the doc records a snapshot line, and that each
row's `Then` and `Altitude` are still one of the map's scenarios for that
row — read through `adapter.py`, never a shell string composed from
configuration plus doc content, so a row id (however it is spelled) always
travels as exactly one argv element.

The comparison is exact when `map.row` prints the row as a JSON object with
a `scenarios` list, as the starter map's reader does: the doc's `Then` must
equal one scenario's `then`, case and runs of whitespace aside
(THEN_NOT_IN_MAP), and that scenario's `altitude` must equal the doc's
`Altitude` (ALTITUDE_NOT_IN_MAP). This is the link rule `arm` follows
(modes/arm.md): a §6 line is linked to a row only on an exact `Then` and the
same altitude. When `map.row` prints anything else, the script cannot see
the scenarios: the `Then` check falls back to a normalised substring of the
text (both sides lower-cased, stripped of punctuation and of a leading
"Then"/"And"), no altitude is compared, and one ROW_TEXT_ONLY finding
(info) names the rows checked that way. The substring check is a canary,
not a proof of agreement.

A ``shipped`` doc needs proof that each §6 line was seen to fail
(outcome-framework.md § Lifecycle): the line went red (a ``Red gate:``
header line, the line not in ``Filed without red run:``), a ``Kill:`` line
names it, or it cites a row with ``origin: backfill`` and ``verdict:
proven``. SHIPPED_WITHOUT_GATE (error) names each §6 line no red run and no
Kill line covers whose row is not such a row, or whose row printed text, so
neither can be read. ``lint_outcome.py`` reports such a line with no
``Row`` at all (SHIPPED_NEEDS_GATE).

The two link findings are warnings: after the snapshot, the map is the source of
the scenarios and may move on. ``--linking`` is for the run that makes the
links (arm's bridge): it makes THEN_NOT_IN_MAP and ALTITUDE_NOT_IN_MAP
errors, because a link this run made that fails them is a wrong link.

A §6 line with no ``Altitude`` (an older doc whose table has no such
column; the lint warns ALTITUDE_MISSING) has no altitude to compare: it is
not drift, and one ALTITUDE_MISSING finding (info) names those lines.
Under ``--linking`` that finding is an error, because a link needs the same
altitude.

The doc's own `Status:` decides first. A `Status:` that is missing or not
one of the five tokens is reported as STATUS_UNKNOWN (error) and nothing
else runs — the script cannot tell whether such a doc has been bridged. A
doc still at `draft` or `superseded-by` has not been bridged at all:
`bridged: false` is reported and no other check runs, whether or not a map
is configured. Only once the doc's own status clears that does an
unconfigured map become the finding — there is nothing to validate a
bridged doc against. "Configured" means orient's `mapUsable`: a map that
is present but incomplete is MAP_NOT_CONFIGURED too, and the message names
the keys orient found missing.

Exit 0 when there are no error-severity findings; 1 when there are (or, under
--strict, any warning; under --linking, a Then or an altitude not in the
map); 2 on a usage error. Human output is one line per
finding: ``<path>:<line>: <RULE_ID> <message>``, then a summary line
``bridge: <n> rows, <m> mapped, <k> drifted``. ``--json`` prints one JSON
object; stdout is always exactly one parseable value under ``--json``.
Deterministic; every file is read tolerating a BOM and CRLF; never a
traceback on plausible input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import lint_outcome  # noqa: E402  (sibling-script import; see path insert above)
import orient  # noqa: E402
import outcome_rows  # noqa: E402

ADAPTER_PATH = os.path.join(_SCRIPTS_DIR, "adapter.py")

BRIDGE_REQUIRED_STATUSES = ("agreed", "building", "shipped")
NOT_BRIDGED_STATUSES = ("draft", "superseded-by")
VALID_STATUSES = ("draft", "agreed", "building", "shipped", "superseded-by")

MAP_INCOMPLETE_PREFIX = "map incomplete"

SNAPSHOT_LINE_RE = re.compile(r"^[`*]*\s*snapshot taken at\b", re.IGNORECASE)
LEADING_THEN_AND_RE = re.compile(r"^(then|and)\b[\s:,-]*", re.IGNORECASE)
NON_WORD_RE = re.compile(r"[^\w\s]")
WHITESPACE_RE = re.compile(r"\s+")


def finding(rule: str, line: Optional[int], message: str, severity: str) -> Dict[str, Any]:
    return {"rule": rule, "line": line, "message": message, "severity": severity}


def section6_heading_line(lines: List[str]) -> Optional[int]:
    """1-based line number of the ``## 6.`` heading, or None when there is none."""
    bounds = lint_outcome.section_bounds(lines, 6)
    return bounds[0] + 1 if bounds is not None else None


def has_snapshot_line(lines: List[str]) -> bool:
    """True when some line inside §6 starts (a leading backtick/asterisk
    tolerated) with "Snapshot taken at", case-insensitive."""
    bounds = lint_outcome.section_bounds(lines, 6)
    if bounds is None:
        return False
    start, end = bounds
    return any(SNAPSHOT_LINE_RE.match(lines[i].strip()) for i in range(start, end))


def exact_text(text: str) -> str:
    """Case-folded, with each run of whitespace made one space and the ends
    trimmed: the form in which a §6 ``Then`` must equal a scenario's
    ``then`` for an exact link. Punctuation and code spans stay as they are."""
    return WHITESPACE_RE.sub(" ", (text or "").strip()).casefold()


def row_payload(text: str) -> Optional[Dict[str, Any]]:
    """The row ``map.row`` printed, when it printed one JSON object (the
    starter map's ``--row`` output); None for anything else."""
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def row_scenarios(payload: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Optional[str]]]]:
    """The scenarios of a JSON row with a ``scenarios`` list, each as
    ``{"then", "altitude"}``; None when there is no such list, or it holds
    no scenario with a string ``then``. None means the link cannot be
    checked exactly."""
    if payload is None or not isinstance(payload.get("scenarios"), list):
        return None
    out: List[Dict[str, Optional[str]]] = []
    for scenario in payload["scenarios"]:
        if isinstance(scenario, dict) and isinstance(scenario.get("then"), str):
            altitude = scenario.get("altitude")
            out.append({"then": scenario["then"], "altitude": altitude if isinstance(altitude, str) else None})
    return out or None


def normalize(text: str) -> str:
    """Lower-case; drop a leading ``then``/``and`` keyword; strip punctuation
    to spaces; collapse whitespace. Used to compare a §6 ``Then`` against the
    map's own current scenario text without either side's exact wording of
    connectives or punctuation defeating a real match. The comparison itself
    is ``normalize(then) in normalize(map_text)`` — a substring check, so a
    map text that still contains the doc's sentence passes whatever else it
    now says around it."""
    lowered = (text or "").strip().lower()
    lowered = LEADING_THEN_AND_RE.sub("", lowered, count=1)
    no_punct = NON_WORD_RE.sub(" ", lowered)
    return WHITESPACE_RE.sub(" ", no_punct).strip()


def lookup_row(cwd: str, row_id: str) -> Tuple[bool, str]:
    """Run ``adapter.py --cwd cwd --json row row_id`` as a real subprocess.

    Returns ``(found, scenario_text)``. ``found`` is False whenever the
    adapter subprocess exits non-zero, prints nothing parseable, reports a
    non-zero child exit, or the child's own stdout is empty — every one of
    these means there is nothing to compare a ``Then`` against. This never
    composes a shell string: ``row_id`` reaches ``adapter.py`` as exactly
    one argv element, whatever characters it contains.
    """
    try:
        proc = subprocess.run(
            [sys.executable, ADAPTER_PATH, "--cwd", cwd, "--json", "row", row_id],
            shell=False,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False, ""
    stdout = proc.stdout or ""
    if proc.returncode != 0 or not stdout.strip():
        return False, ""
    try:
        payload = json.loads(stdout)
    except ValueError:
        return False, ""
    if not isinstance(payload, dict) or payload.get("exit") != 0:
        return False, ""
    child_stdout = payload.get("stdout")
    if not isinstance(child_stdout, str) or not child_stdout.strip():
        return False, ""
    return True, child_stdout


LINK_RULES = ("THEN_NOT_IN_MAP", "ALTITUDE_NOT_IN_MAP")


def finalize(
    doc_path: str,
    status: Optional[str],
    bridged: bool,
    map_configured: bool,
    rows_out: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
    strict: bool,
    mapped: int = 0,
    drifted: int = 0,
    linking: bool = False,
) -> Dict[str, Any]:
    for f in findings:
        if f["severity"] == "warn" and (strict or (linking and f["rule"] in LINK_RULES)):
            f["severity"] = "error"
    findings = sorted(findings, key=lambda f: (f["line"] if f["line"] is not None else 0, f["rule"]))
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warn")
    return {
        "path": doc_path,
        "status": status,
        "bridged": bridged,
        "mapConfigured": map_configured,
        "rows": rows_out,
        "findings": findings,
        "stats": {
            "rows": len(rows_out),
            "mapped": mapped,
            "drifted": drifted,
            "errors": errors,
            "warnings": warnings,
        },
    }


def _map_incomplete_reason(orientation: Dict[str, Any]) -> Optional[str]:
    """orient's own 'map incomplete: missing …' warning, when it issued one."""
    for warning in orientation.get("warnings") or []:
        if isinstance(warning, str) and warning.startswith(MAP_INCOMPLETE_PREFIX):
            return warning
    return None


def validate(doc_path: str, cwd: str, strict: bool, linking: bool = False) -> Dict[str, Any]:
    orientation = orient.build_orientation(None, cwd)
    map_value = orientation.get("map")
    # orient's mapUsable is the one source of "is a map configured": a
    # map that is present but incomplete counts as not configured here,
    # exactly as it does for the modes and for adapter.py.
    map_configured = isinstance(map_value, dict) and bool(orientation.get("mapUsable"))

    try:
        text = lint_outcome.read_text_tolerant(doc_path)
    except (OSError, UnicodeDecodeError) as exc:
        findings = [finding("UNREADABLE", None, f"cannot read {doc_path}: {exc}", "error")]
        return finalize(doc_path, None, False, map_configured, [], findings, strict)

    lines = text.splitlines()
    status = lint_outcome.get_status(lines)
    six_line = section6_heading_line(lines)

    # The doc's own Status: is read first, and a status the script cannot
    # place — missing, or not one of the five tokens — is its own error:
    # such a doc is neither bridged nor known to be unbridged, so nothing
    # below (ROW_MISSING included) can be judged and none of it runs.
    if status not in VALID_STATUSES:
        shown = status if status is not None else "(missing)"
        findings = [
            finding(
                "STATUS_UNKNOWN",
                None,
                f"Status: {shown} is not one of {', '.join(VALID_STATUSES)} — "
                "cannot tell whether this doc has been bridged",
                "error",
            )
        ]
        return finalize(doc_path, status, False, map_configured, [], findings, strict)

    # NOT_BRIDGED is checked on the doc's own status alone, before the map
    # check: a doc still at draft/superseded-by has not been bridged
    # regardless of whether a map is configured, so it must never report
    # MAP_NOT_CONFIGURED instead — that finding is specifically about a
    # doc that IS ready to check against a map and has nothing to check
    # against, not about one that has not reached that point yet.
    if status in NOT_BRIDGED_STATUSES:
        findings = [
            finding(
                "NOT_BRIDGED",
                six_line,
                f"Status: {status} — the bridge has not happened yet",
                "info",
            )
        ]
        return finalize(doc_path, status, False, map_configured, [], findings, strict)

    if not map_configured:
        message = "no map is configured for this project — there is nothing to validate the bridge against"
        if map_value is False:
            message = "map is false: this project keeps no map, on purpose — there is nothing to validate the bridge against"
        incomplete = _map_incomplete_reason(orientation) if isinstance(map_value, dict) else None
        if incomplete:
            message = f"{incomplete} — the map is treated as not configured; there is nothing to validate the bridge against"
        findings = [finding("MAP_NOT_CONFIGURED", six_line, message, "error")]
        return finalize(doc_path, status, False, False, [], findings, strict)

    data = outcome_rows.extract(doc_path)
    line_by_id = {r["id"]: r["line"] for r in lint_outcome.parse_acceptance_rows(lines)}
    row_required = status in BRIDGE_REQUIRED_STATUSES

    findings: List[Dict[str, Any]] = []

    # rowIdPattern has three states, not two: absent (NO_ROW_ID_PATTERN,
    # warn — ROW_ID_FORMAT is simply not checked), present but invalid
    # regex syntax (INVALID_ROW_ID_PATTERN, error — a misconfiguration,
    # never silently treated the same as absent), or present and usable.
    row_id_pattern = map_value.get("rowIdPattern")
    pattern_provided = isinstance(row_id_pattern, str) and bool(row_id_pattern)
    compiled_pattern = None
    if not pattern_provided:
        findings.append(
            finding(
                "NO_ROW_ID_PATTERN",
                six_line,
                "map.rowIdPattern is not configured; ROW_ID_FORMAT is not checked",
                "warn",
            )
        )
    else:
        try:
            compiled_pattern = re.compile(row_id_pattern)
        except re.error as exc:
            findings.append(
                finding(
                    "INVALID_ROW_ID_PATTERN",
                    six_line,
                    f"map.rowIdPattern {row_id_pattern!r} does not compile: {exc}; "
                    "ROW_ID_FORMAT is not checked",
                    "error",
                )
            )
    pattern_usable = compiled_pattern is not None

    # mapUsable already requires map.row to be a string; an empty string
    # still passes that and configures nothing, which is the one way this
    # finding is still reachable.
    row_command = map_value.get("row")
    row_command_configured = isinstance(row_command, str) and bool(row_command)
    if not row_command_configured:
        findings.append(
            finding(
                "NO_MAP_ROW_COMMAND",
                six_line,
                "map.row is not configured; the drift check against the map is skipped",
                "warn",
            )
        )

    rows_out: List[Dict[str, Any]] = []
    mapped = 0
    drifted = 0
    row_cache: Dict[str, Tuple[bool, str]] = {}
    text_only: List[str] = []
    no_altitude: List[str] = []
    # A shipped doc needs proof that each §6 line was seen to fail: a red run,
    # a Kill line, or a proven backfilled row (framework § Lifecycle). The
    # lines no red run and no Kill line covers must cite such a row.
    uncovered = (
        {u["id"] for u in lint_outcome.gate_uncovered_rows(lines)} if status == "shipped" else set()
    )
    shipped_check: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]], str]] = []

    for r in data["rows"]:
        row_id = r["id"]
        row_value = r["row"]
        line_no = line_by_id.get(row_id)
        entry: Dict[str, Any] = {
            "id": row_id, "row": row_value, "line": line_no, "found": None, "inSync": None, "exact": None,
        }

        if not row_value:
            if row_required:
                findings.append(
                    finding(
                        "ROW_MISSING",
                        line_no,
                        f"{row_id} has no Row value while Status: is {status}",
                        "error",
                    )
                )
            rows_out.append(entry)
            continue

        mapped += 1

        if pattern_usable and compiled_pattern.fullmatch(row_value) is None:
            findings.append(
                finding(
                    "ROW_ID_FORMAT",
                    line_no,
                    f"{row_id}'s Row value {row_value!r} does not match map.rowIdPattern {row_id_pattern!r}",
                    "error",
                )
            )
            rows_out.append(entry)
            continue

        if not row_command_configured:
            if row_id in uncovered:
                shipped_check.append((r, None, "no map.row command is configured"))
            rows_out.append(entry)
            continue

        if row_value not in row_cache:
            row_cache[row_value] = lookup_row(cwd, row_value)
        found, map_text = row_cache[row_value]
        entry["found"] = found

        if not found:
            findings.append(
                finding(
                    "ROW_NOT_FOUND",
                    line_no,
                    f"{row_id}'s row {row_value} was not found by map.row",
                    "error",
                )
            )
            rows_out.append(entry)
            continue

        payload = row_payload(map_text)
        scenarios = row_scenarios(payload)
        if row_id in uncovered:
            shipped_check.append((r, payload, "map.row printed text, not a JSON row"))
        entry["exact"] = scenarios is not None
        if scenarios is None:
            # The map printed text: the normalised-substring canary (see the
            # module docstring), with no altitude to compare.
            if row_value not in text_only:
                text_only.append(row_value)
            then_norm = normalize(r["then"])
            then_found = (not then_norm) or (then_norm in normalize(map_text))
            altitudes: List[Optional[str]] = []
        else:
            # The exact link rule: the Then equals one scenario's then, and
            # that scenario's altitude equals the doc's Altitude.
            then_exact = exact_text(r["then"])
            same_then = [s for s in scenarios if exact_text(s["then"]) == then_exact]
            then_found = (not then_exact) or bool(same_then)
            altitudes = [s["altitude"] for s in same_then]
            if not r["altitude"] and any(altitudes):
                # no Altitude cell (an older doc; the lint warns ALTITUDE_MISSING):
                # there is nothing to compare, so it is not drift
                no_altitude.append(row_id)
                altitudes = []
        altitude_ok = scenarios is None or not altitudes or r["altitude"] in altitudes
        entry["inSync"] = then_found and altitude_ok
        if not then_found:
            drifted += 1
            findings.append(
                finding(
                    "THEN_NOT_IN_MAP",
                    line_no,
                    f"{row_id}'s Then "
                    + ("no longer appears in" if scenarios is None else "is not the then of any scenario of")
                    + f" {row_value} in the map — the map has moved on since the snapshot, the row was "
                    "filed differently, or §6 was edited after the snapshot was taken",
                    "warn",
                )
            )
        elif not altitude_ok:
            drifted += 1
            shown = ", ".join(sorted({a or "(none)" for a in altitudes}))
            findings.append(
                finding(
                    "ALTITUDE_NOT_IN_MAP",
                    line_no,
                    f"{row_id}'s Then is a scenario of {row_value}, but at altitude {shown}, not "
                    f"{r['altitude'] or '(no Altitude in §6)'} — a link needs the same altitude: the "
                    "row was filed at another altitude, or §6 or the map changed it after the snapshot",
                    "warn",
                )
            )

        rows_out.append(entry)

    for r, payload, unread in shipped_check:
        if payload is None:
            why = f"{unread}, so its origin and verdict cannot be read"
        elif payload.get("origin") == "backfill" and payload.get("verdict") == "proven":
            continue
        else:
            why = f"it is origin {payload.get('origin')!r}, verdict {payload.get('verdict')!r}"
        findings.append(
            finding(
                "SHIPPED_WITHOUT_GATE",
                line_by_id.get(r["id"]),
                f"Status: shipped, {r['id']} has no red run and no 'Kill:' line, and it cites {r['row']}: "
                f"{why}. A shipped doc needs proof that each §6 line was seen to fail: a red run, a 'Kill:' "
                "line, or a row with origin 'backfill' and verdict 'proven'",
                "error",
            )
        )

    if no_altitude:
        findings.append(
            finding(
                "ALTITUDE_MISSING",
                six_line,
                f"§6 gives no Altitude for {', '.join(no_altitude)}, so the altitude of "
                + ("these links" if len(no_altitude) > 1 else "this link")
                + " was not compared with the map"
                + (": a link needs the same altitude, so write the Altitude first" if linking else ""),
                "error" if linking else "info",
            )
        )

    if text_only:
        findings.append(
            finding(
                "ROW_TEXT_ONLY",
                six_line,
                f"map.row printed text, not a JSON row with a scenarios list, for {', '.join(text_only)}: "
                "each Then was checked as a substring of that text and no Altitude was compared, so an "
                "exact link is not checked here",
                "info",
            )
        )

    if not has_snapshot_line(lines):
        findings.append(
            finding(
                "SNAPSHOT_LINE_MISSING",
                six_line,
                "§6 has no line beginning 'Snapshot taken at' — the bridge is not recorded",
                "error",
            )
        )

    return finalize(
        doc_path, status, True, True, rows_out, findings, strict, mapped=mapped, drifted=drifted, linking=linking
    )


def format_human(result: Dict[str, Any]) -> str:
    out = []
    for f in result["findings"]:
        line_part = f["line"] if f["line"] is not None else "?"
        out.append(f"{result['path']}:{line_part}: {f['rule']} {f['message']}")
    stats = result["stats"]
    out.append(f"bridge: {stats['rows']} rows, {stats['mapped']} mapped, {stats['drifted']} drifted")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridge_validate.py",
        description=(
            "Check a bridged outcome doc's §6 Row ids, snapshot line, Then text and altitude "
            "against the project's capability map."
        ),
    )
    parser.add_argument("doc", help="path to the outcome doc")
    parser.add_argument(
        "--cwd", default=None, help="project root to resolve the config against (default: current directory)"
    )
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of human-readable lines")
    parser.add_argument("--strict", action="store_true", help="promote warn findings to error")
    parser.add_argument(
        "--linking",
        action="store_true",
        help="the run that makes the links (arm's bridge): THEN_NOT_IN_MAP and ALTITUDE_NOT_IN_MAP are errors",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    if not os.path.isdir(cwd):
        print(f"bridge_validate.py: no such directory: {cwd}", file=sys.stderr)
        return 2
    doc_path = args.doc if os.path.isabs(args.doc) else os.path.join(cwd, args.doc)

    try:
        result = validate(doc_path, cwd, args.strict, args.linking)
    except Exception as exc:  # pragma: no cover - last-resort guard, never a traceback for the caller
        print(f"bridge_validate.py: internal error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_human(result))

    any_errors = any(f["severity"] == "error" for f in result["findings"])
    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())
