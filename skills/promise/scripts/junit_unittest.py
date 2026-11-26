#!/usr/bin/env python3
"""Run a project's standard-library unittest suite and write the run as JUnit XML.

    python3 junit_unittest.py --out <path.xml> [-s <start dir>] [-p <pattern>] [-t <top dir>] [--cwd DIR]

``python -m unittest`` writes no JUnit, so ``map_report.py`` has no run to join a
map to. This script runs the same discovery (``-s``, ``-p`` and ``-t`` mean what
they mean to ``python -m unittest discover``; the defaults are ``.``, ``test*.py``
and the start dir), prints the usual unittest output, and writes one
``<testcase>`` per test with its ``file`` (the test module's path relative to
``--cwd``), ``classname`` (the TestCase class) and ``name`` (the test method), so a
map citation ``tests/test_notes.py::test_save`` or
``tests/test_notes.py::TestNotes::test_save`` finds it. A module that fails to
import is one failing case, ``<its file>::import``. Python 3 stdlib only.

Exit codes: 0 when every test passed (skips included), 1 when any failed or
errored, 2 on a usage error. The XML is written in every case but a usage error.
"""

from __future__ import annotations

import argparse
import inspect
import os
import re
import sys
import time
import traceback
import unittest
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional


class RecordingResult(unittest.TextTestResult):
    """The usual text result, which also keeps one record per test."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.records: List[Dict[str, Any]] = []
        self._started: Dict[str, float] = {}

    def startTest(self, test: unittest.TestCase) -> None:
        self._started[test.id()] = time.perf_counter()
        super().startTest(test)

    def _record(self, test: Any, outcome: str, detail: str = "") -> None:
        began = self._started.pop(test.id(), None)
        seconds = time.perf_counter() - began if began is not None else 0.0
        self.records.append({"test": test, "outcome": outcome, "detail": detail, "seconds": seconds})

    def addSuccess(self, test: unittest.TestCase) -> None:
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:
        super().addFailure(test, err)
        self._record(test, "failure", self._exc_info_to_string(err, test))

    def addError(self, test: Any, err: Any) -> None:
        super().addError(test, err)
        self._record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)

    def addExpectedFailure(self, test: unittest.TestCase, err: Any) -> None:
        super().addExpectedFailure(test, err)
        self._record(test, "passed")

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:
        super().addUnexpectedSuccess(test)
        self._record(test, "failure", "unexpected success")

    def addSubTest(self, test: unittest.TestCase, subtest: Any, err: Any) -> None:
        super().addSubTest(test, subtest, err)
        if err is not None:
            # A failing subtest fails its test: record it once, under the test's own name.
            kind = "failure" if issubclass(err[0], test.failureException) else "error"
            if not any(r["test"] is test for r in self.records):
                self._record(test, kind, self._exc_info_to_string(err, test))


def _source_file(test: Any, cwd: str) -> Optional[str]:
    try:
        path = inspect.getsourcefile(type(test))
    except (TypeError, OSError):
        return None
    if not path:
        return None
    rel = os.path.relpath(os.path.abspath(path), cwd)
    return None if rel.startswith("..") else rel.replace(os.sep, "/")


FIXTURE_RE = re.compile(r"^(setUpModule|tearDownModule|setUpClass|tearDownClass) \(([\w.]+)\)$")


def _module_file(module: str, base: str, cwd: str) -> Optional[str]:
    """The file of a dotted module name, counted from the import root ``base``."""
    path = os.path.join(base, *module.split(".")) + ".py"
    if not os.path.isfile(path):
        path = os.path.join(base, *module.split("."), "__init__.py")
    if not os.path.isfile(path):
        return None
    return os.path.relpath(os.path.abspath(path), cwd).replace(os.sep, "/")


def _case_fields(test: Any, cwd: str, base: str = ".") -> Dict[str, str]:
    """``file``, ``classname`` and ``name`` for one test, as ``map_report.py`` reads them.
    ``base`` is the import root discovery used (``-t``, else ``-s``), which module names
    count from."""
    if isinstance(test, unittest.TestCase) and type(test).__module__ == "unittest.loader":
        # A module that failed to import: one failing case, named after its file.
        module = test._testMethodName
        fields = {"classname": module, "name": "import"}
        where = _module_file(module, base, cwd)
        if where:
            fields["file"] = where
        return fields
    if isinstance(test, unittest.TestCase):
        fields = {"classname": type(test).__name__, "name": test._testMethodName}
        where = _source_file(test, cwd)
        if where:
            fields["file"] = where
        return fields
    # A failed class or module fixture: "setUpClass (tests.test_x.TestX)". The tests it
    # guards never ran; this case names the fixture, its class and its file.
    ident = test.id() if hasattr(test, "id") else str(test)
    m = FIXTURE_RE.match(ident)
    if m:
        hook, dotted = m.groups()
        parts = dotted.split(".")
        is_class = hook.endswith("Class")
        module = ".".join(parts[:-1]) if is_class else dotted
        fields = {"classname": parts[-1] if is_class else module, "name": hook}
        where = _module_file(module, base, cwd)
        if where:
            fields["file"] = where
        return fields
    return {"classname": ident, "name": ident}


def to_junit(records: List[Dict[str, Any]], cwd: str, base: str = ".") -> ET.ElementTree:
    counts = {"failure": 0, "error": 0, "skipped": 0}
    suite = ET.Element("testsuite", name="unittest")
    for record in records:
        case = ET.SubElement(suite, "testcase", **_case_fields(record["test"], cwd, base),
                             time=f"{record['seconds']:.3f}")
        outcome = record["outcome"]
        if outcome in counts:
            counts[outcome] += 1
            child = ET.SubElement(case, outcome, message=(record["detail"].strip().splitlines() or [""])[-1][:200])
            child.text = record["detail"]
    suite.set("tests", str(len(records)))
    suite.set("failures", str(counts["failure"]))
    suite.set("errors", str(counts["error"]))
    suite.set("skipped", str(counts["skipped"]))
    root = ET.Element("testsuites")
    root.append(suite)
    return ET.ElementTree(root)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run unittest discovery and write the run as JUnit XML.")
    parser.add_argument("--out", required=True, help="the JUnit XML file to write")
    parser.add_argument("-s", "--start-directory", default=".", help="where discovery starts (default: .)")
    parser.add_argument("-p", "--pattern", default="test*.py", help="test file pattern (default: test*.py)")
    parser.add_argument("-t", "--top-level-directory", default=None, help="the project's import root")
    parser.add_argument("--cwd", default=None, help="the project root (default: the current directory)")
    args = parser.parse_args(argv)
    cwd = os.path.abspath(args.cwd or os.getcwd())
    if not os.path.isdir(cwd):
        print(f"junit_unittest.py: no such directory: {cwd}", file=sys.stderr)
        return 2
    os.chdir(cwd)
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    try:
        suite = unittest.defaultTestLoader.discover(args.start_directory, pattern=args.pattern,
                                                    top_level_dir=args.top_level_directory)
    except (ImportError, TypeError, OSError) as exc:
        print(f"junit_unittest.py: discovery failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 2
    runner = unittest.TextTestRunner(resultclass=RecordingResult, verbosity=1)
    result = runner.run(suite)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tree = to_junit(result.records, cwd, args.top_level_directory or args.start_directory)
    ET.indent(tree) if hasattr(ET, "indent") else None
    tree.write(out, encoding="utf-8", xml_declaration=True)
    print(f"junit_unittest.py: wrote {len(result.records)} cases to {os.path.relpath(out, cwd)}", file=sys.stderr)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
