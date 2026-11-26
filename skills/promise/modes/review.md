Read before this: references/anti-rationalizations.md · outcome-framework.md § The framework as a review rubric · § Section rules
Phase 0 line: mode `review` (say if inferred), framework source (the rubric's authority), docs home and its source, whether a map is configured (orient's `mapUsable`), and whether the project is adopted.
Writes: nothing in the repo, unless the user asks for a file copy. Findings are delivered inline in chat.

# Review — a doc authored elsewhere

The framework doubles as a review rubric — framework § The framework as a
review rubric is the authority; run it from the section, not from memory.

1. **Read 100% of the source** — chunked if large. State what fraction you
   read if you couldn't finish. Never review a skim. A URL is readable only
   when the session has a fetch tool; otherwise ask for a paste. Never review
   from memory of what a page probably says.
2. **Verify before critiquing.** Spot-check every load-bearing
   current-state claim against live code, with file:line. Three outcome
   classes, all valuable: confirmed (say so — it builds the doc's
   credibility), wrong (invented identifiers, stale claims), and
   **understated** — the code is worse than the doc admits. The sharpest
   findings are usually here. A negative, design-constraining claim ("can't",
   "cannot", "doesn't have", "no way to", "unavailable", "only X has") is a
   fourth class of its own — rubric item 9, framework § The framework as a
   review rubric: check §1 as much as §5, since that is usually where this
   kind of claim is first written down. A true citation is not the same
   claim as the conclusion drawn from it, so check it has a Load-bearing
   premises row (always in §5, even for a §1 claim) whose `Evidence` names
   the source's whole field set, not just the field the doc checked, and
   whose `Existing join searched` names every repository or doc the
   capability touches. The lint's own coverage check is literal, not
   semantic — a row that paraphrases the claim instead of quoting or closely
   restating it still reads as unlisted, so judge a near-miss yourself.
3. **Run the rubric.** If the target is a file, also run `python3
   "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc>` and fold its
   findings in as the shape half of the rubric. The doc belongs to this
   project, a map is configured (orient's `mapUsable`) and its `Status:` is
   past `draft` → also run `python3
   "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" <doc> --strict` (so
   drift is an error, not a warning) and fold those findings in too: an
   edited §6 `Then` cell surfaces as `THEN_NOT_IN_MAP`, an edited `Altitude`
   cell as `ALTITUDE_NOT_IN_MAP`, a deleted `Altitude` column as
   `ALTITUDE_MISSING` (info here, and a lint warning), a stripped snapshot
   line as `SNAPSHOT_LINE_MISSING`, and each is a finding against the doc,
   since §6 is a snapshot after the bridge. An `ALTITUDE_MISSING` is not a
   finding only when the doc never had the column (an older doc: `git log
   -p` on the file shows it). `NOT_BRIDGED` and `MAP_NOT_CONFIGURED`
   mean there is nothing to check, not a finding. A doc at `agreed` whose §6
   has no `Row` cell at all and no snapshot line has not been armed; report
   those findings as "run `arm`", not as drift or as a finding against the
   doc. The lint checks shape
   mechanically; it cannot check depth — invariants argued with mechanism
   and boundary, evidence pinned to a commit, design-vs-description
   flagged, alternatives rejected with receipts. That half stays yours to
   judge, against the framework section, not memory of it.
4. **On a re-review, diff against the prior revision** for the three
   erosion classes — framework § The framework as a review rubric: an OPEN
   decision silently asserted; §0 membership changed without confirmation;
   operational content deleted with no stated home. Credit what improved,
   and verify any NEW claims the revision introduced — revisions add claims
   too.
5. **Judge pushback on its merits.** If the doc's author rejected earlier
   feedback with an argument, engage the argument — accept it, or counter
   with a better mechanism. Don't re-assert.
6. **Deliver findings inline in chat**, as a numbered, paste-ready fenced
   markdown block, most severe first, each item actionable by the other
   agent without this conversation. Files can be unreachable across app
   boundaries — inline is the contract; a file copy is optional extra.
7. **Track convergence.** When the doc approaches framework shape, say what
   separates it from `agreed` — usually the human half — and offer to close
   it via the pending interview rather than another review round.
