#!/bin/bash
# The chat app, plus a working prototype of channel pinning that is already committed.
set -euo pipefail
bash "$(dirname "$0")/../_fixture/make-project.sh"
cat > app/pins.py <<'PY'
"""Prototype: pin a message to the top of a channel."""

PINS = {}


def pin(channel, message_id):
    PINS.setdefault(channel, [])
    if message_id not in PINS[channel]:
        PINS[channel].append(message_id)


def unpin(channel, message_id):
    if message_id in PINS.get(channel, []):
        PINS[channel].remove(message_id)


def pinned(channel):
    return list(PINS.get(channel, []))
PY
git add -A
git commit -qm "prototype: channel pinning"
