#!/usr/bin/env python3
"""Say, in one line, whether this repository's promise pin is behind upstream.

    python3 pin_check.py [--cwd DIR] [--json] [--strict]

A repository pins promise in ``.claude/settings.json``: the promise marketplace's
``source.ref``, a release tag such as ``v1.33.0``. Claude Code's marketplace source
reads ``ref`` (a branch or tag) and nothing else, so a ``source.sha`` there, with no
``ref``, pins nothing: Claude Code follows the default branch, and this script says so.
The config's ``pinFiles`` names any other pin site (``[{"path": "scripts/promise/run.sh",
"pattern": "REF=([0-9a-f]{40})"}]``, plus ``"kind": "version"`` for a version such as a
``REF_VERSION``): the first group, or the whole match, is the value.

One ``git ls-remote`` (no clone) reads upstream's ``main`` and release tags, with no
credentials; for a private upstream, name a local promise checkout
(``--upstream-path``, ``PROMISE_UPSTREAM_PATH``, or the config's ``upstreamPath``): git
then runs in that checkout, with its own access, and fetches a commit it lacks into it
(objects only). The rest is the same either way; the newest
release tag is upstream's latest, or ``main`` while there is none. It prints one of:

    promise pin: up to date (1.33.0)
    promise pin: 1.31.0 (f7caec2), upstream 1.33.0 (1a2b3c4), 2 releases behind
    promise pin: upstream not reachable, not checked
    promise pin: pins disagree: .claude/settings.json v1.31.0, scripts/promise/run.sh 1.29.0

and a line more for each of: a ``sha`` pin Claude Code does not read, a ``ref`` that is a
branch (it moves), a promise section in ``CLAUDE.md`` or ``AGENTS.md`` not written by the
pinned release's template (agents read that section, not the changelog), and a machine
whose installed promise (Claude Code's ``installed_plugins.json``) is not the pinned
commit: ``pin_machine.py`` moves it.

It never changes a file: moving the pin is ``/promise upgrade``, its own pull request
(``scripts/upgrade.py``). It never fails a pull request for being behind: exit 0 when
behind, up to date, unpinned or offline. Exit 1 when two pin sites disagree, or a
configured pin site cannot be read: a defect, not a notice. ``--strict`` also exits 1
on every notice above. Every network call times out after ``--timeout`` seconds
(default 5). It sends no credentials: git runs outside the repository with no config,
no credential helper and no prompt, and a URL carrying a user or token is refused (exit
2). ``--upstream`` (an https or file URL, or a local path) and ``--raw-base`` (``https://``
or ``file://``, under which ``<sha>/<path>`` is the file at that commit) point at a mirror.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.dont_write_bytecode = True  # a vendored copy inside the repo must not leave files behind
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)

UPSTREAM = "https://github.com/osouthgate/promise.git"
RAW_BASE = "https://raw.githubusercontent.com/osouthgate/promise"
CONTENTS_API = "https://api.github.com/repos/osouthgate/promise/contents"
SETTINGS = ".claude/settings.json"
PLUGIN_JSON = ".claude-plugin/plugin.json"
CHANGELOG = "CHANGELOG.md"
TEMPLATE = "skills/promise/templates/claude-md-section.md"
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_VALUE_RE = re.compile(r"^v?(\d+\.\d+\.\d+)$")
RELEASE_RE = re.compile(r"^##\s+\[?v?(\d+\.\d+\.\d+)\]?", re.MULTILINE)
PREFIX = "promise pin:"
KINDS = ("sha", "version")
# A machine's trust store and git install, which reach the request with no credential in them.
KEEP_GIT_ENV = ("GIT_SSL_CAINFO", "GIT_SSL_CAPATH", "GIT_EXEC_PATH")


class PinError(Exception):
    """A pin site that is configured but cannot be read: exit 1."""


class Refused(Exception):
    """A flag this script will not use (a URL with credentials in it): exit 2."""


def short(value: Optional[str]) -> str:
    if not value:
        return "?"
    return value[:7] if SHA_RE.match(value) else value


def vtuple(v: str) -> Tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def settings_source(cwd: str) -> Optional[Dict[str, Any]]:
    """The promise marketplace's ``source`` object in ``.claude/settings.json``, or
    None when the file or the declaration is absent. A file that is not JSON, or a
    ``ref`` or ``sha`` that is not a string of the right shape, is a broken pin site."""
    path = os.path.join(cwd, SETTINGS)
    if not os.path.isfile(path):
        return None
    try:
        data = json.loads(orient.read_text_tolerant(path))
    except (OSError, ValueError) as exc:
        raise PinError(f"{SETTINGS} cannot be read: {exc}")
    markets = data.get("extraKnownMarketplaces") if isinstance(data, dict) else None
    market = markets.get("promise") if isinstance(markets, dict) else None
    source = market.get("source") if isinstance(market, dict) else None
    if not isinstance(source, dict):
        return None
    for key in ("ref", "sha"):
        if key in source and not (isinstance(source[key], str) and source[key].strip()):
            raise PinError(f"{SETTINGS}: the promise marketplace's source.{key} is not a string")
    sha = source.get("sha")
    if isinstance(sha, str) and not SHA_RE.match(sha.strip().lower()):
        raise PinError(f"{SETTINGS} pins promise to {sha!r}, which is not a commit sha")
    return source


def pin_file_specs(cwd: str) -> List[Dict[str, str]]:
    """The config's ``pinFiles``, checked: each a project-relative ``path``, a
    ``pattern`` that compiles, and a ``kind`` (``sha``, the default, or ``version``)."""
    config, path, _warnings = orient.load_config(cwd)
    if path and not isinstance(config, dict):
        raise PinError(f"{os.path.relpath(path, cwd)} cannot be read as a JSON object, so its pinFiles are unknown")
    raw = config.get("pinFiles") if isinstance(config, dict) else None
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise PinError("pinFiles is not a list of {path, pattern} objects")
    specs = []
    for i, item in enumerate(raw):
        if not (isinstance(item, dict) and isinstance(item.get("path"), str)
                and isinstance(item.get("pattern"), str) and item["path"] and item["pattern"]):
            raise PinError(f"pinFiles[{i}] is not an object with a path and a pattern")
        kind = item.get("kind", "sha")
        if kind not in KINDS:
            raise PinError(f"pinFiles[{i}] kind is {kind!r}; it is sha or version")
        rel = normalise_rel(item["path"])
        if rel is None:
            raise PinError(f"pinFiles[{i}] path escapes the project, or names no file: {item['path']}")
        try:
            re.compile(item["pattern"], re.MULTILINE)
        except re.error as exc:
            raise PinError(f"pinFiles[{i}] pattern does not compile: {exc}")
        vendored = item.get("vendored", False)
        if not isinstance(vendored, bool):
            raise PinError(f"pinFiles[{i}] vendored is not true or false")
        specs.append({"path": rel, "pattern": item["pattern"], "kind": kind, "vendored": vendored})
    return specs


def pin_file_matches(cwd: str, spec: Dict[str, str]) -> Tuple[str, List[Tuple[int, int, str]]]:
    """The file's text and every pin in it: (start, end, value) of the value's span.
    No file, no match, or a match that is not a sha (or a version) is a broken site."""
    path = os.path.join(cwd, spec["path"])
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            text = fh.read()
    except (OSError, ValueError) as exc:
        raise PinError(f"{spec['path']} cannot be read: {exc}")
    rx = re.compile(spec["pattern"], re.MULTILINE)
    group = 1 if rx.groups else 0
    kind = spec.get("kind", "sha")
    found = []
    for m in rx.finditer(text):
        value = m.group(group)
        if kind == "sha":
            ok = value is not None and SHA_RE.match(value.lower())
        else:
            ok = value is not None and VERSION_VALUE_RE.match(value)
        if not ok:
            raise PinError(f"{spec['path']}: pattern matched {m.group(0)!r}, which holds no "
                           f"{'commit sha' if kind == 'sha' else 'version'}")
        found.append((m.start(group), m.end(group), value.lower() if kind == "sha" else value))
    if not found:
        raise PinError(f"{spec['path']}: pattern {spec['pattern']!r} matches nothing")
    return text, found


def normalise_rel(path: str) -> Optional[str]:
    """One spelling per project file (``./.claude/x`` is ``.claude/x``), or None for a
    path outside the project or naming no file."""
    rel = posixpath.normpath(path.replace("\\", "/"))
    if os.path.isabs(rel) or rel in (".", "") or rel == ".." or rel.startswith("../"):
        return None
    return rel


def same_commit(a: str, b: str) -> bool:
    """Two shas name one commit when one is a prefix of the other."""
    return a.startswith(b) or b.startswith(a)


def pin_sites(cwd: str) -> List[Dict[str, str]]:
    """Every pin site, as {path, kind, value}: settings first (``ref``, then a
    ``sha``), then each pinFiles match."""
    sites = []
    source = settings_source(cwd)
    if source:
        if source.get("ref"):
            sites.append({"path": SETTINGS, "kind": "ref", "value": source["ref"].strip()})
        if source.get("sha"):
            sites.append({"path": SETTINGS, "kind": "sha", "value": source["sha"].strip().lower()})
    for spec in pin_file_specs(cwd):
        _text, found = pin_file_matches(cwd, spec)
        for _start, _end, value in found:
            sites.append({"path": spec["path"], "kind": spec["kind"], "value": value})
    return sites


def _release(value: str) -> Optional[str]:
    m = VERSION_VALUE_RE.match(value or "")
    return m.group(1) if m else None


def local_disagreement(sites: List[Dict[str, str]]) -> bool:
    """Sites that disagree without asking upstream: two shas, or two versions (a
    release-tag ref counts as its version)."""
    shas = [s["value"] for s in sites if s["kind"] == "sha"]
    versions = [s["value"].lstrip("v") for s in sites if s["kind"] == "version"]
    versions += [v for v in (_release(s["value"]) for s in sites if s["kind"] == "ref") if v]
    return (any(not same_commit(a, b) for i, a in enumerate(shas) for b in shas[i + 1:])
            or len(set(versions)) > 1)


def _refuse_credentials(url: str, flag: str) -> None:
    if url.startswith("-"):
        raise Refused(f"{flag} may not start with '-'")
    parts = urllib.parse.urlsplit(url)
    if flag == "--upstream" and parts.scheme not in ("https", "file") and not (
            os.path.isabs(url) or url.startswith(".")):
        raise Refused(f"{flag} must be an https:// or file:// URL, or a local path (ssh would use this machine's keys)")
    if parts.username or parts.password or ("@" in parts.netloc):
        raise Refused(f"{flag} carries a user or token; this script sends no credentials")


def isolated_git_env(scratch: str) -> Dict[str, str]:
    """The environment git runs in: no system or global config, a scratch HOME (no
    ``~/.netrc``), no prompt."""
    env = {k: v for k, v in os.environ.items()
           if not ((k.startswith("GIT_") and k not in KEEP_GIT_ENV) or k in ("SSH_ASKPASS", "XDG_CONFIG_HOME"))}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_ASKPASS="", SSH_ASKPASS="", GCM_INTERACTIVE="never", HOME=scratch,
               XDG_CONFIG_HOME=scratch)
    return env


def remote_refs(upstream: str, timeout: float) -> Optional[Dict[str, str]]:
    """Upstream's ``refs/heads/main`` and every ``refs/tags/*``, as ref → commit (an
    annotated tag's peeled commit), or None when it cannot be reached in time.

    git runs outside the repository, with no credential helper and no extra header: a
    checkout's own config can hold a token (``http.<url>.extraheader``), and none of it
    may reach the request."""
    import tempfile
    if not urllib.parse.urlsplit(upstream).scheme:
        upstream = os.path.abspath(upstream)  # git runs in a scratch directory
    with tempfile.TemporaryDirectory() as scratch:
        cmd = ["git", "-c", "credential.helper=", "-c", "core.askPass=", "-c", "http.extraHeader=",
               "ls-remote", upstream, "refs/heads/main", "refs/tags/*"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                  env=isolated_git_env(scratch), stdin=subprocess.DEVNULL, cwd=scratch)
        except (OSError, subprocess.TimeoutExpired):
            return None
    if proc.returncode != 0:
        return None
    return _parse_refs(proc.stdout)


def _parse_refs(stdout: str) -> Optional[Dict[str, str]]:
    refs: Dict[str, str] = {}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) != 2 or not FULL_SHA_RE.match(parts[0]):
            continue
        name = parts[1]
        if name.endswith("^{}"):
            refs[name[:-3]] = parts[0]  # the peeled commit wins over the tag object
        else:
            refs.setdefault(name, parts[0])
    return refs if "refs/heads/main" in refs else None


def latest_release(refs: Dict[str, str]) -> Optional[Tuple[str, str, str]]:
    """(tag, version, commit) of the newest release tag, or None with none."""
    best = None
    for name, sha in refs.items():
        if name.startswith("refs/tags/"):
            tag = name[len("refs/tags/"):]
            version = _release(tag)
            if version and (best is None or vtuple(version) > vtuple(best[1])):
                best = (tag, version, sha)
    return best


UPSTREAM_PATH_ENV = "PROMISE_UPSTREAM_PATH"
# A fetch into the checkout moves a commit's objects, not a list of refs: it gets this
# many times --timeout. Every other call gets --timeout.
FETCH_TIMEOUT_FACTOR = 4


def upstream_checkout(cwd: str, flag: Optional[str] = None,
                      timeout: float = 5.0) -> Tuple[Optional[str], Optional[str]]:
    """(the local promise checkout to read upstream through, why it cannot be used).

    From ``--upstream-path``, else ``PROMISE_UPSTREAM_PATH``, else the config's
    ``upstreamPath`` (from the project root; ``~`` expands). A checkout the person
    already keeps reads a private upstream with its own git access: no token passes
    through this script. (None, None) when none is named."""
    raw = flag or os.environ.get(UPSTREAM_PATH_ENV)
    if not raw:
        config, _p, _w = orient.load_config(cwd)
        value = config.get("upstreamPath") if isinstance(config, dict) else None
        if value is None:
            return None, None
        if not (isinstance(value, str) and value.strip()):
            return None, "upstreamPath is not a path"
        raw = value
    path = os.path.abspath(os.path.join(cwd, os.path.expanduser(raw.strip())))
    if not os.path.isdir(path):
        return None, f"the upstream checkout {raw!r} does not exist"
    top = _checkout_git(path, ["rev-parse", "--show-toplevel"], timeout)
    # git searches upward: a plain folder inside another repository (a vendored copy)
    # would read that repository's origin, so the path must be a checkout's own root.
    if top is None or os.path.realpath(top.stdout.strip()) != os.path.realpath(path):
        return None, f"the upstream checkout {raw!r} is not the root of a git checkout"
    project = _checkout_git(cwd, ["rev-parse", "--show-toplevel"], timeout)
    if project is not None and os.path.realpath(project.stdout.strip()) == os.path.realpath(path):
        return None, f"the upstream checkout {raw!r} is this repository itself"
    if _checkout_git(path, ["remote", "get-url", "origin"], timeout) is None:
        return None, f"the upstream checkout {raw!r} has no origin remote"
    return path, None


# Variables that point git at a repository: a pre-push hook sets GIT_DIR, which would
# win over -C and aim every command at the repository being checked.
GIT_LOCATION_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_PREFIX", "GIT_CEILING_DIRECTORIES")


def checkout_env() -> Dict[str, str]:
    """The person's own environment, config and credentials, but never a prompt (ssh
    in batch mode, unless they set their own ssh command), and never a variable that
    aims git at another repository."""
    env = {k: v for k, v in os.environ.items() if k not in GIT_LOCATION_ENV}
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return env


def _checkout_git(path: str, args: List[str], timeout: float) -> Optional[subprocess.CompletedProcess]:
    """git in the person's own checkout (``checkout_env``): this runs unattended."""
    try:
        proc = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=timeout,
                              env=checkout_env(), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc if proc.returncode == 0 else None


def checkout_refs(path: str, timeout: float) -> Optional[Dict[str, str]]:
    """Upstream's main and tags, read through the checkout's ``origin``."""
    proc = _checkout_git(path, ["ls-remote", "origin", "refs/heads/main", "refs/tags/*"], timeout)
    return _parse_refs(proc.stdout) if proc else None


def checkout_file(path: str, sha: str, name: str, timeout: float) -> Optional[str]:
    """A file at a commit, from the checkout; a commit it lacks is fetched into it
    first (its objects only: no branch or tag of the checkout moves)."""
    if not FULL_SHA_RE.match(sha):
        return None
    if _checkout_git(path, ["cat-file", "-e", f"{sha}^{{commit}}"], timeout) is None:
        if _checkout_git(path, ["fetch", "--quiet", "--no-tags", "--no-write-fetch-head", "origin", sha],
                         timeout * FETCH_TIMEOUT_FACTOR) is None:
            return None
    proc = _checkout_git(path, ["show", f"{sha}:{name}"], timeout)
    return proc.stdout.replace("\r\n", "\n") if proc else None


def upstream_refs(cwd: str, upstream: str, timeout: float,
                  flag: Optional[str] = None) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """(upstream's refs, why they could not be read): through the named checkout when
    there is one, else the network."""
    checkout, why = upstream_checkout(cwd, flag, timeout)
    if why:
        return None, why
    refs = checkout_refs(checkout, timeout) if checkout else remote_refs(upstream, timeout)
    if refs is None:
        return None, (f"upstream not reachable through {checkout}" if checkout
                      else "upstream not reachable (it may be private: name a local checkout in upstreamPath)")
    return refs, None


def _get(request: urllib.request.Request, timeout: float) -> Optional[bytes]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.read(2_000_000)
    except Exception:  # noqa: BLE001  any failure is "not read", never a crash
        return None


def fetch(raw_base: str, sha: str, path: str, timeout: float) -> Optional[str]:
    """The file at that commit, as text with LF line endings, or None. From the
    default raw host, GitHub's contents API is tried second (no token either)."""
    data = _get(urllib.request.Request(f"{raw_base.rstrip('/')}/{sha}/{path}"), timeout)
    if data is None and raw_base == RAW_BASE:
        data = _get(urllib.request.Request(f"{CONTENTS_API}/{path}?ref={sha}",
                                           headers={"Accept": "application/vnd.github.raw"}), timeout)
    if data is None:
        return None
    text = data.decode("utf-8", "replace")
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def plugin_version(text: Optional[str]) -> Optional[str]:
    try:
        value = json.loads(text).get("version") if text else None
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and orient.VERSION_RE.match(value) else None


def releases_between(changelog: Optional[str], old: Optional[str], new: Optional[str]) -> Optional[List[str]]:
    """The CHANGELOG headings newer than ``old`` and no newer than ``new``, newest first."""
    if not (changelog and old and new):
        return None
    seen = []
    for v in RELEASE_RE.findall(changelog):
        if vtuple(old) < vtuple(v) <= vtuple(new) and v not in seen:
            seen.append(v)
    return sorted(seen, key=vtuple, reverse=True)


def section_stamp(cwd: str) -> Tuple[Optional[str], Optional[str]]:
    """The promise section's file (project-relative) and the template stamp in its
    begin marker ("" when the marker has none); (None, None) with no section."""
    found = orient.detect_claude_md(cwd)
    path = found.get("sectionPath")
    if not path:
        return None, None
    rel = os.path.relpath(path, cwd).replace(os.sep, "/")
    try:
        lines = orient.read_text_tolerant(path).splitlines()
    except (OSError, ValueError):
        return rel, ""
    begin = next((l for l in lines if l.lstrip().startswith(orient.PROMISE_BEGIN_MARKER)), "")
    m = orient.SECTION_STAMP_RE.search(begin)
    return rel, (m.group(1) if m else "")


def vendored_copy(cwd: str) -> Optional[str]:
    """This skill's folder, project-relative, when it runs from a copy inside the
    repository: a pin no settings entry names."""
    skill = os.path.realpath(os.path.dirname(_SCRIPTS_DIR))
    root = os.path.realpath(cwd)
    if os.path.commonpath([skill, root]) != root or skill == root:
        return None
    top = _checkout_git(root, ["rev-parse", "--show-toplevel"], 5.0)
    if top is None or os.path.realpath(top.stdout.strip()) != root:
        return None  # not a repository's root: $HOME over the plugin cache, say
    if os.path.isdir(os.path.join(root, "skills", "promise")) and os.path.realpath(
            os.path.join(root, "skills", "promise")) == skill:
        return None  # promise's own repository
    return os.path.relpath(skill, root).replace(os.sep, "/")


def _upstream(refs: Optional[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Upstream's latest: the newest release tag, else main; None when not reached."""
    if not refs:
        return None
    latest = latest_release(refs)
    if latest:
        return {"ref": latest[0], "sha": latest[2], "version": latest[1]}
    return {"ref": "main", "sha": refs["refs/heads/main"], "version": None}


def _machine(cwd: str, pinned: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """This machine's promise install for this repository, and whether it is the
    pinned commit (or version, when the commit is not known)."""
    machine = orient.machine_plugin(cwd)
    if not machine:
        return None
    current = None
    if pinned.get("sha") and machine.get("gitCommitSha"):
        current = same_commit(pinned["sha"], machine["gitCommitSha"])
    elif pinned.get("version") and machine.get("version"):
        current = pinned["version"] == machine["version"]
    return dict(machine, current=current)


def check(cwd: str, upstream: str, raw_base: str, timeout: float,
          upstream_path: Optional[str] = None) -> Dict[str, Any]:
    """The report, as fields. ``state`` is one of ``disagree``, ``unpinned``,
    ``unreachable``, ``current`` or ``behind``; ``notices`` lists ``sha-pin`` (a sha
    Claude Code does not read), ``branch-ref`` (a branch), ``moving-tag`` (a tag such
    as ``v1``), ``missing-ref`` (a
    ref upstream does not have), ``untagged-release`` (main names a newer version than any
    tag), ``section`` and ``machine``."""
    report: Dict[str, Any] = {"state": None, "pins": [], "pinned": None, "upstream": None, "releases": None,
                              "behind": None, "section": None, "machine": None, "notices": [],
                              "via": "network", "unreachableWhy": None, "vendoredCopy": None}
    checkout, why = upstream_checkout(cwd, upstream_path, timeout)
    if checkout:
        report["via"] = checkout

        def refs_of() -> Optional[Dict[str, str]]:
            return checkout_refs(checkout, timeout)

        def file_at(sha: str, name: str) -> Optional[str]:
            return checkout_file(checkout, sha, name, timeout)
    elif why:  # a checkout was named and cannot be used: say so, never fall back quietly
        def refs_of() -> Optional[Dict[str, str]]:
            return None

        def file_at(sha: str, name: str) -> Optional[str]:
            return None
    else:
        def refs_of() -> Optional[Dict[str, str]]:
            return remote_refs(upstream, timeout)

        def file_at(sha: str, name: str) -> Optional[str]:
            return fetch(raw_base, sha, name, timeout)
    report["unreachableWhy"] = why
    sites = pin_sites(cwd)
    report["pins"] = sites
    if not sites:
        report["state"] = "unpinned"
        report["vendoredCopy"] = vendored_copy(cwd)
        return report
    if local_disagreement(sites):
        report["state"] = "disagree"
        report["upstream"] = _upstream(refs_of())
        return report
    ref = next((s["value"] for s in sites if s["kind"] == "ref"), None)
    shas = [s["value"] for s in sites if s["kind"] == "sha"]
    versions = [s["value"].lstrip("v") for s in sites if s["kind"] == "version"]
    settings_sha = any(s["kind"] == "sha" and s["path"] == SETTINGS for s in sites)
    if settings_sha and not ref:
        report["notices"].append("sha-pin")
    pinned: Dict[str, Any] = {"ref": ref, "sha": max(shas, key=len) if shas else None,
                              "version": _release(ref or "") or (versions[0] if versions else None)}
    report["pinned"] = pinned
    refs = refs_of()
    if refs is None:
        report["state"] = "unreachable"
        report["machine"] = _machine(cwd, pinned)
        if report["machine"] and report["machine"]["current"] is False:
            report["notices"].append("machine")
        return report
    if ref:
        tag_sha = refs.get(f"refs/tags/{ref}")
        branch_sha = refs.get(f"refs/heads/{ref}")
        if tag_sha is not None and not _release(ref):
            report["notices"].append("moving-tag")  # v1 moves with every release
        elif tag_sha is None and branch_sha is not None:
            report["notices"].append("branch-ref")
        elif tag_sha is None:
            report["notices"].append("missing-ref")
        resolved = tag_sha or branch_sha
        if resolved:
            if pinned["sha"] and not same_commit(pinned["sha"], resolved):
                report["state"] = "disagree"
                report["pins"] = sites + [{"path": f"{SETTINGS} ({ref})", "kind": "sha", "value": resolved}]
                report["upstream"] = _upstream(refs)
                return report
            pinned["sha"] = resolved
    up = _upstream(refs)
    report["upstream"] = up
    current = bool(pinned["sha"]) and same_commit(pinned["sha"], up["sha"])
    if not pinned["sha"] and pinned["version"] and up["version"]:
        current = pinned["version"] == up["version"]
    section_file, stamp = section_stamp(cwd)
    jobs: Dict[str, Tuple[str, str]] = {}
    if up["version"] is None:
        jobs["up"] = (up["sha"], PLUGIN_JSON)
    main_sha = refs.get("refs/heads/main")
    if up["ref"] != "main" and main_sha and main_sha != up["sha"]:
        jobs["main"] = (main_sha, PLUGIN_JSON)  # a release on main that no tag names yet
    if not current:
        jobs["log"] = (up["sha"], CHANGELOG)
        if pinned["version"] is None and pinned["sha"]:
            jobs["pin"] = (pinned["sha"], PLUGIN_JSON)
    tpl_at = up["sha"] if current else pinned["sha"]
    if section_file and tpl_at:
        jobs["tpl"] = (tpl_at, TEMPLATE)
    got: Dict[str, Optional[str]] = {}
    if jobs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {k: pool.submit(file_at, sha, path) for k, (sha, path) in jobs.items()}
            got = {k: f.result() for k, f in futures.items()}
    if up["version"] is None:
        up["version"] = plugin_version(got.get("up"))
    main_version = plugin_version(got.get("main"))
    if main_version and up["version"] and vtuple(main_version) > vtuple(up["version"]):
        report["untagged"] = main_version
        report["notices"].append("untagged-release")
    if pinned["version"] is None:
        pinned["version"] = up["version"] if current else plugin_version(got.get("pin"))
    if current:
        report["state"], report["behind"] = "current", 0
    else:
        report["state"] = "behind"
        releases = releases_between(got.get("log"), pinned["version"], up["version"])
        report["releases"] = releases
        report["behind"] = len(releases) if releases is not None else None
    if section_file and "tpl" in jobs:
        tpl = got.get("tpl")
        want = hashlib.sha256(tpl.encode("utf-8")).hexdigest()[:8] if tpl is not None else None
        report["section"] = {"path": section_file, "stamp": stamp or None, "pinnedStamp": want,
                             "current": None if want is None else stamp == want}
        if report["section"]["current"] is False:
            report["notices"].append("section")
    report["machine"] = _machine(cwd, pinned)
    if report["machine"] and report["machine"]["current"] is False:
        report["notices"].append("machine")
    return report


def _at(pinned: Dict[str, Any]) -> str:
    return pinned.get("version") or short(pinned.get("ref") or pinned.get("sha"))


def lines_for(report: Dict[str, Any]) -> List[str]:
    state = report["state"]
    if state == "disagree":
        return [f"{PREFIX} pins disagree: " + ", ".join(f"{s['path']} {short(s['value'])}" for s in report["pins"])]
    if state == "unpinned":
        out = [f"{PREFIX} no pin found ({SETTINGS} declares no promise marketplace, and no pinFiles), not checked"]
        if report.get("vendoredCopy"):
            out.append(f"{PREFIX} the skill runs from a copy inside this repository ({report['vendoredCopy']}): name "
                       "the file that records its commit in pinFiles, with \"vendored\": true")
        return out
    pinned, up = report["pinned"], report["upstream"]
    if state == "unreachable":
        out = [f"{PREFIX} upstream not reachable, not checked"]
        if report.get("unreachableWhy"):
            out.append(f"{PREFIX} {report['unreachableWhy']}")
        elif report.get("via") == "network":
            out.append(f"{PREFIX} upstream may be private: name a local promise checkout, whose own git access "
                       f"reads it, in the config's upstreamPath or {UPSTREAM_PATH_ENV}")
    elif state == "current":
        out = [f"{PREFIX} up to date ({up['version'] or short(up['sha'])})"]
    else:
        n = report["behind"]
        if n is None:
            tail = "releases behind not read"
        elif n == 0:
            tail = "same release, newer commits upstream"
        else:
            tail = f"{n} release{'s' if n != 1 else ''} behind"
        out = [f"{PREFIX} {pinned['version'] or '?'} ({short(pinned['sha'])}), "
               f"upstream {up['version'] or '?'} ({short(up['sha'])}), {tail}"]
    notices = report["notices"]
    if "sha-pin" in notices:
        out.append(f"{PREFIX} {SETTINGS} pins by source.sha, which Claude Code does not read: every machine "
                   "follows upstream's default branch. Pin a release tag in source.ref (/promise upgrade)")
    if "branch-ref" in notices:
        out.append(f"{PREFIX} source.ref {pinned['ref']!r} is a branch, which moves. Pin a release tag "
                   "(/promise upgrade)")
    if "moving-tag" in notices:
        out.append(f"{PREFIX} source.ref {pinned['ref']!r} is a tag that moves with each release. Pin a release "
                   "tag, vX.Y.Z (/promise upgrade)")
    if "untagged-release" in notices:
        out.append(f"{PREFIX} upstream main is at {report['untagged']}, but its newest release tag is "
                   f"{report['upstream']['ref']}: that release is not tagged yet, so nothing can pin it")
    if "missing-ref" in notices:
        out.append(f"{PREFIX} source.ref {pinned['ref']!r} names no tag upstream (a tag not pushed, or a branch "
                   "other than main): Claude Code cannot fetch it")
    if "section" in notices:
        at = _at(pinned)
        out.append(f"promise section: {report['section']['path']} was not written by the pinned {at} template; "
                   f"run /promise adopt at {at}")
    if "machine" in notices:
        m = report["machine"]
        out.append(f"promise machine: this machine runs {m['version'] or '?'} ({short(m['gitCommitSha'])}), "
                   f"the repo pins {_at(pinned)}: run pin_machine.py, then restart Claude Code")
    return out


def exit_code(report: Dict[str, Any], strict: bool) -> int:
    if report["state"] == "disagree":
        return 1
    # upstream's own untagged release is not this repository's to fix
    if strict and (report["state"] == "behind" or [n for n in report["notices"] if n != "untagged-release"]):
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--cwd", default=os.getcwd(), help="the repository to check (default: here)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON fields")
    ap.add_argument("--strict", action="store_true", help="also exit 1 when behind, or on any notice")
    ap.add_argument("--timeout", type=float, default=5.0, help="seconds per network call (default 5)")
    ap.add_argument("--upstream-path", help="a local promise checkout to read upstream through, with its own "
                    f"git access (default: {UPSTREAM_PATH_ENV}, else the config's upstreamPath)")
    ap.add_argument("--upstream", default=UPSTREAM, help=argparse.SUPPRESS)
    ap.add_argument("--raw-base", default=RAW_BASE, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        _refuse_credentials(args.upstream, "--upstream")
        _refuse_credentials(args.raw_base, "--raw-base")
        if urllib.parse.urlsplit(args.raw_base).scheme not in ("https", "file"):
            raise Refused("--raw-base must be an https:// or file:// URL")
    except Refused as exc:
        print(f"pin_check.py: {exc}", file=sys.stderr)
        return 2
    cwd = os.path.abspath(args.cwd)
    try:
        report = check(cwd, args.upstream, args.raw_base, args.timeout, args.upstream_path)
    except PinError as exc:
        report = {"state": "error", "error": str(exc)}
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"{PREFIX} a pin site cannot be read: {exc}")
        return 1
    if args.json:
        report["lines"] = lines_for(report)
        print(json.dumps(report, indent=2))
    else:
        print("\n".join(lines_for(report)))
    return exit_code(report, args.strict)


if __name__ == "__main__":
    sys.exit(main())
