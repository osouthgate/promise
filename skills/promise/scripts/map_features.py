#!/usr/bin/env python3
"""Read a map's features, whichever key the map uses.

A map groups its rows by product feature. The primary keys are ``features``
(top level: a list of ``{"id", "name", "plain"}``) and ``feature`` (on a row:
one feature id). The alias spellings ``areas`` and ``area`` mean exactly the
same and stay accepted, so an existing map keeps working.

A map must use one spelling. A map with both ``features`` and ``areas``, a
row with both ``feature`` and ``area``, rows that mix ``feature`` and
``area``, or a top level whose spelling its rows do not use, is the error
``FEATURE_AND_AREA``: two keys for one fact can disagree, and a reader that
knows one spelling silently drops the other.

Shared by ``lint_github_text.py`` and ``changed_rows.py``. The starter map's
``capability_find.py`` is a standalone copy, so it holds its own small version
of the same rule.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

FEATURE_AND_AREA = "FEATURE_AND_AREA"


def feature_list(top: Any) -> Any:
    """The map's feature list under whichever key holds it (None when neither)."""
    if not isinstance(top, dict):
        return None
    return top["features"] if top.get("features") is not None else top.get("areas")


def row_feature(row: Any) -> Any:
    """A row's feature id under whichever key holds it (None when neither)."""
    if not isinstance(row, dict):
        return None
    return row["feature"] if "feature" in row else row.get("area")


def conflicts(data: Any, rows: Optional[List[Any]] = None) -> List[str]:
    """Every use of both spellings: the map's top level, each row, the rows
    against each other, and the rows against the top level."""
    found: List[str] = []
    top = None
    if isinstance(data, dict):
        if "features" in data and "areas" in data:
            found.append(f"{FEATURE_AND_AREA}: the map has both 'features' and 'areas'; keep 'features'")
        elif "features" in data:
            top = "features"
        elif "areas" in data:
            top = "areas"
    if rows is None and isinstance(data, dict):
        rows = data.get("rows")
    by_key: Dict[str, List[str]] = {"feature": [], "area": []}
    for i, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        label = str(row.get("id")) if row.get("id") is not None else f"rows[{i}]"
        if "feature" in row and "area" in row:
            found.append(f"{FEATURE_AND_AREA}: row {label} has both 'feature' and 'area'; keep 'feature'")
        elif "feature" in row:
            by_key["feature"].append(label)
        elif "area" in row:
            by_key["area"].append(label)
    if by_key["feature"] and by_key["area"]:
        found.append(f"{FEATURE_AND_AREA}: the rows mix the spellings: row {by_key['feature'][0]} has "
                     f"'feature' and row {by_key['area'][0]} has 'area'; use 'feature' on every row")
    elif top == "features" and by_key["area"]:
        found.append(f"{FEATURE_AND_AREA}: the map lists 'features' but row {by_key['area'][0]} has 'area'; "
                     "use 'feature'")
    elif top == "areas" and by_key["feature"]:
        found.append(f"{FEATURE_AND_AREA}: the map lists 'areas' but row {by_key['feature'][0]} has 'feature'; "
                     "use one spelling: 'features' and 'feature'")
    return found


def features_by_id(top: Any) -> Dict[str, Dict[str, Any]]:
    """The feature entries by id (empty when there are none)."""
    return {str(a["id"]): a for a in feature_list(top) or []
            if isinstance(a, dict) and a.get("id")}
