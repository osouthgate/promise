#!/usr/bin/env python3
"""PreToolUse hook: stop the model editing §0 of an agreed outcome doc.

Claude Code runs this before every Edit, MultiEdit and Write (hooks/hooks.json).
It reads the tool call from stdin, works out the file's text after the call,
and compares §0 before and after with diff_outcome.py's rule: on a doc that is
``agreed``, ``building`` or ``shipped``, only the rule tags and the
``**Scenarios:**`` count may change, unless the same edit sets ``Status:
draft``. A call that breaks the rule is blocked: exit 2, with the reason on
stderr, which Claude Code shows to the model.

Everything else passes: a file that is not Markdown, not an outcome doc, not
yet on disk, or not ratified; an edit whose ``old_string`` is not in the file
(the tool itself will refuse it). The hook fails open: any error of its own
exits 0, so a bug here never stops unrelated work. It sees only the model's
own Edit, MultiEdit and Write calls -- a person's edits in an editor, and a
shell command that writes the file, are not checked here; CI
(``diff_outcome.py --dir … --base …``) checks every change on the pull request.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Callable, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "skills", "promise", "scripts")


def _apply_edits(before: str, edits) -> Optional[str]:
    if not isinstance(edits, list):
        return None
    text = before
    for edit in edits:
        if not isinstance(edit, dict):
            return None
        old = edit.get("old_string")
        new = edit.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str) or not old or old not in text:
            return None
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return text


def planned_writes(tool: str, tool_input: dict) -> List[Tuple[str, Callable[[str], Optional[str]]]]:
    """(path, before -> after) for every file the call would change.

    Accepts both spellings of the payload: ``content`` or ``file_text`` for a
    whole-file write, ``edits`` (old/new strings) or ``file_edits`` (one
    ``file_path`` + ``file_text`` per file) for MultiEdit."""
    path = tool_input.get("file_path")
    if tool == "Write" and isinstance(path, str):
        content = tool_input.get("content", tool_input.get("file_text"))
        if isinstance(content, str):
            return [(path, lambda before, c=content: c)]
    if tool == "Edit" and isinstance(path, str):
        return [(path, lambda before: _apply_edits(before, [tool_input]))]
    if tool == "MultiEdit":
        if isinstance(path, str) and "edits" in tool_input:
            return [(path, lambda before: _apply_edits(before, tool_input.get("edits")))]
        out = []
        for item in tool_input.get("file_edits") or []:
            if isinstance(item, dict) and isinstance(item.get("file_path"), str):
                if isinstance(item.get("file_text"), str):
                    out.append((item["file_path"], lambda before, c=item["file_text"]: c))
                elif "edits" in item:
                    out.append((item["file_path"], lambda before, e=item["edits"]: _apply_edits(before, e)))
        return out
    return []


def main() -> int:
    try:
        event = json.load(sys.stdin)
        tool = event.get("tool_name")
        tool_input = event.get("tool_input") or {}
        if tool not in ("Edit", "MultiEdit", "Write") or not isinstance(tool_input, dict):
            return 0
        sys.path.insert(0, os.path.normpath(SCRIPTS))
        import diff_outcome  # noqa: E402

        for path, after_of in planned_writes(tool, tool_input):
            if not path.lower().endswith(".md"):
                continue
            if not os.path.isabs(path):
                path = os.path.join(event.get("cwd") or os.getcwd(), path)
            if not os.path.isfile(path):
                continue
            before = diff_outcome.read_file(path)
            if before is None or "## 0. TLDR" not in before:
                continue
            after = after_of(before)
            if after is None:
                continue
            blocking = [f for f in diff_outcome.compare(before, after) if f["severity"] == "error"]
            if blocking:
                block(path, blocking[0]["message"])
                return 2
    except Exception:  # fail open: never block work because of a bug here
        return 0
    return 0


def block(path: str, message: str) -> None:
    print(
        f"promise: blocked. This edit changes §0 of {path}, and §0 is the human's block. "
        f"{message}. Do not retry it. Tell the human the exact change you want to make, "
        "as a numbered agent note under §0. Only when they confirm that exact text, make "
        "the edit again and set Status: draft in the same edit, so that they re-agree "
        "the doc (modes/revise.md).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    sys.exit(main())
