#!/bin/bash
# Builds the project each eval case runs in: a small chat app, adopted for promise with
# the plugin's own scripts. With --map it also has the starter map and an agreed doc
# whose one row, CAP-1, promises that a muted channel sends no push or badge.
# With --unadopted it stops before adopt: no config and no CLAUDE.md section, the
# project's first run.
# Called by each case's fixture.sh, in the run's empty workspace.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS="$REPO/skills/promise/scripts"
WITH_MAP=""
UNADOPTED=""
[ "${1:-}" = "--map" ] && WITH_MAP=1
[ "${1:-}" = "--unadopted" ] && UNADOPTED=1

git init -q .
git config user.name "Ana Tester"
git config user.email "ana@example.invalid"

mkdir -p app tests db
cat > app/settings.html <<'HTML'
<section id="channels">
  <h2>Channels</h2>
  <p class="empty">No channels yet.</p>
</section>
HTML
cat > app/notify.py <<'PY'
"""Notifications for channel messages."""

MUTED = set()


def mute(member, channel):
    MUTED.add((member, channel))


def unmute(member, channel):
    MUTED.discard((member, channel))


def should_push(member, channel):
    return (member, channel) not in MUTED


def badge_count(member, channel, unread):
    return unread
PY
cat > app/checkout.py <<'PY'
"""Checkout totals."""


def total(items):
    return sum(item["price"] * item["qty"] for item in items)
PY
cat > db/schema.sql <<'SQL'
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE
);
SQL
cat > tests/test_notify.py <<'PY'
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import notify  # noqa: E402


class Push(unittest.TestCase):
    def test_a_muted_channel_sends_no_push(self):
        notify.mute("ana", "general")
        self.assertFalse(notify.should_push("ana", "general"))
        notify.unmute("ana", "general")
        self.assertTrue(notify.should_push("ana", "general"))


if __name__ == "__main__":
    unittest.main()
PY
touch tests/__init__.py

if [ -z "$UNADOPTED" ]; then
python3 "$SCRIPTS/adopt.py" --docs-home docs/designs >/dev/null
python3 - <<'PY'
import json
p = ".claude/promise.config.json"
c = json.load(open(p))
c["commands"] = {"typeCheck": None, "test": "python3 -m unittest discover -s tests", "lint": None}
json.dump(c, open(p, "w"), indent=2)
PY
fi

if [ -n "$WITH_MAP" ]; then
  python3 "$SCRIPTS/start_map.py" --dest docs/capabilities >/dev/null
  mkdir -p docs/designs
  cp "$REPO/examples/minimap/docs/designs/channel-muting.md" docs/designs/channel-muting.md
  python3 - "$REPO" <<'PY'
import json, sys
repo = sys.argv[1]
example = json.load(open(f"{repo}/examples/minimap/map.json"))
cap1 = next(r for r in example["rows"] if r["id"] == "CAP-1")
cap1["tests"] = ["tests/test_notify.py::Push::test_a_muted_channel_sends_no_push"]
cap1["verdict"] = "under-proven"
p = "docs/capabilities/map.json"
m = json.load(open(p))
m["rows"] = [cap1]
json.dump(m, open(p, "w"), indent=2)
open(p, "a").write("\n")
PY
fi

git add -A
git commit -qm "the project before the ask"
