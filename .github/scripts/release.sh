#!/usr/bin/env bash
# Tag a promise release and publish its GitHub release. The release-tags workflow runs
# this on every push to main; a maintainer runs it by hand, from an up-to-date main,
# when Actions cannot run.
#
#   bash .github/scripts/release.sh           # tag plugin.json's version, move v1, publish its release
#   bash .github/scripts/release.sh --all     # the same, and a release for every vX.Y.Z tag with none
#   bash .github/scripts/release.sh --check   # exit 1 when plugin.json's version on main has no tag
#
# The tag goes on the first commit on main whose plugin.json names the version, so a
# run after later commits tags the release, not the newest commit. A release tag never
# moves; the major tag (v1) follows the newest release tag. Publishing needs gh, signed
# in (GH_TOKEN in Actions). Re-running is safe: what exists is left as it is.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
here=.github/scripts
mode=${1:-}
case "$mode" in ""|--all|--check) ;; *) echo "usage: release.sh [--all|--check]"; exit 2 ;; esac

git fetch --quiet --force origin main 'refs/tags/*:refs/tags/*'
version_at() { git show "$1:.claude-plugin/plugin.json" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['version'])" 2>/dev/null || true; }
# Release tags only, vX.Y.Z: a v1.2.3-rc1 or a v1.2.3.4 is never a release, nor the newest.
releases() { git tag -l 'v*' | grep -E "^v${1:-[0-9]+}\.[0-9]+\.[0-9]+$" | sort -V || true; }
version=$(version_at origin/main)
if ! [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "plugin.json version on main is not X.Y.Z: $version; nothing tagged"
  exit 1
fi
tag="v$version"

if [[ "$mode" == --check ]]; then
  if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
    echo "$tag is tagged"
    exit 0
  fi
  echo "$tag has no tag: run bash $here/release.sh"
  exit 1
fi

if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
  echo "$tag is already tagged at $(git rev-parse --short "$tag^{commit}"); a release tag never moves"
else
  # The start of main's latest run of commits naming the version: walk back from the
  # newest, and stop at the first that names another. A bump that was reverted and made
  # again is tagged where it was made again.
  commit=""
  for c in $(git log --first-parent --format=%H origin/main -- .claude-plugin/plugin.json); do
    if [[ "$(version_at "$c")" == "$version" ]]; then commit=$c; else break; fi
  done
  [[ -n "$commit" ]] || { echo "no commit on main names $version"; exit 1; }
  git tag "$tag" "$commit"
  git push origin "refs/tags/$tag"
  echo "$tag tagged at $(git rev-parse --short "$commit")"
fi

major="v${version%%.*}"
# The major tag follows the newest release of its own major: a 1.x backport moves v1
# after a v2.0.0 exists.
newest=$(releases "${version%%.*}" | tail -1)
if [[ "$(git rev-parse -q --verify "refs/tags/$major^{commit}" || true)" != "$(git rev-parse "$newest^{commit}")" ]]; then
  git tag -f "$major" "$newest^{commit}"
  git push -f origin "refs/tags/$major"
  echo "$major moved to $newest"
fi

notes=$(mktemp)
changelog=$(mktemp)
trap 'rm -f "$notes" "$changelog"' EXIT
# The notes come from main, as the tag does: not from whatever is checked out.
git show origin/main:CHANGELOG.md > "$changelog"
latest_release=$(releases | tail -1)
publish() {
  local t=$1 v=${1#v} latest=false
  if gh release view "$t" >/dev/null 2>&1; then echo "$t: release exists"; return; fi
  [[ "$t" == "$latest_release" ]] && latest=true
  python3 "$here/changelog_entry.py" "$v" --tag "$t" --changelog "$changelog" > "$notes"
  gh release create "$t" --title "promise $v" --notes-file "$notes" --latest="$latest" --verify-tag
}
if [[ "$mode" == --all ]]; then
  for t in $(releases); do publish "$t"; done
else
  publish "$tag"
fi
