**Channel muting decisions**: 4 to decide.

Four things wait on you before channel muting can be built: one open question in the doc, the toggle copy, a limit, and one step only you can run. Each one says why it is asked, what waits on it and what happens if you leave it.

- **badge**: The red number on the app icon that counts unread messages.
- **push**: A notification that shows on the phone's lock screen.

**1.** When a member mutes a channel, should its threads go quiet too? (examples/channel-muting.md Q1)
Why: The doc says muting ships without thread-level muting, but its **How we'll know** signal says Ana gets zero notifications from the channel for a day. Thread replies notify today, so the doc as written can fail its own signal.
  a) Muting a channel also mutes its threads (Recommended): it is the only answer under which the doc's own signal holds for every channel.
  b) None of these: reply with your own words
  c) Threads keep notifying; thread muting is a later doc

**2.** Approve the settings copy for the mute toggle · approval
Why: The toggle is the only place a member learns what muting does. The doc's first rule (no push and no badge from a muted channel) means the copy has to say both.
  a) Approve
  b) Request changes (say what after a dash)
  c) Reject
```
- Turn off notifications
+ Mute channel
+ You won't get pushes or badges from this channel until you unmute it.
```

**3.** How many channels may one member mute? · a value
Why: The send path reads the mute table before every notification. With no limit, one member with thousands of muted channels makes every send slower for everyone.
  a) 500 (proposed)
  or reply `3: <the value>`

**4.** Turn the mute flag on in staging · to do
Why: The red tests in phase 1 run against staging, and they fail for the wrong reason while the flag is off.
  a) Done
  b) Not yet
```
./scripts/flags.sh set channel-mute on --env staging
```

Reply with `all recommended`, or one code per item, like `1a 2c`. Add a note after a dash (`2b - fix the wording`); for your own words, `3: <your words>`.

<details><summary>Full detail</summary>

# Channel muting decisions

Four things wait on you before channel muting can be built: one open question in the doc, the toggle copy, a limit, and one step only you can run. Each one says why it is asked, what waits on it and what happens if you leave it.

- **badge**: The red number on the app icon that counts unread messages.
- **push**: A notification that shows on the phone's lock screen.

4 items, 0 blocking. Reply with `all recommended`, or one code per item, like `1a 2c`. Add a note after a dash (`2b - fix the wording`); for your own words, `3: <your words>`.

## Channel muting

`examples/channel-muting.md` · Status: draft

> **Outcome:** A member can mute a channel so it stops notifying them.

### 1 · Q1 · non-blocking · owner: Ollie

id: `examples/channel-muting.md#Q1`

When a member mutes a channel, should its threads go quiet too?

In the doc: should muting a channel also mute its threads? Not decided yet; ships without thread-level muting.

**Why:** The doc says muting ships without thread-level muting, but its **How we'll know** signal says Ana gets zero notifications from the channel for a day. Thread replies notify today, so the doc as written can fail its own signal.  
**Waits on it:** §5 Mechanism (which notifier reads the mute table) and a fourth acceptance row, if threads are included. Phase 1 of the build can start either way.  
**If you don't answer:** The doc ships as written: threads keep notifying, and the signal is checked only in channels with no threads.  

- a) **Muting a channel also mutes its threads** (Recommended) — it is the only answer under which the doc's own signal holds for every channel.
- b) **None of these — reply with your own words**
- c) **Threads keep notifying; thread muting is a later doc** — the doc as written: it ships without thread-level muting.

More, if you need it:

- Example: Ana mutes #general at 09:00. At 11:00 Ben replies in a thread Ana started last week. With threads muted, Ana gets nothing. Without, she gets a push from a channel she muted.
- Muting a channel also mutes its threads, commits you to: one mute check read by both the channel and the thread notifier; no per-thread mute in this doc.
- Muting a channel also mutes its threads, think about: a member who follows one thread closely loses it until they unmute the whole channel.
- Muting a channel also mutes its threads, then: the agent adds an acceptance row to §6 Acceptance (AT-4: a thread reply in a muted channel sends nothing), cites the thread send path in §5 Mechanism, and moves the question to §8 Decisions as a decision.
- Threads keep notifying; thread muting is a later doc, commits you to: a follow-up doc for thread muting, and a narrower signal in §0 TLDR.
- Threads keep notifying; thread muting is a later doc, think about: the signal fails for any channel with active threads, so §0 TLDR needs your edit before the doc can move on.
- Threads keep notifying; thread muting is a later doc, then: the agent opens a thread-muting doc as a thin draft and shows you the §0 TLDR line the signal would need.
- Evidence: `examples/channel-muting.md:20` the signal: zero notifications from the channel for a day
- Evidence: `examples/channel-muting.md:68` every channel member is notified on every message (`messages.ts:88`); thread replies take the same path
- Evidence: `examples/channel-muting.md:102` the question as the doc asks it

## Other decisions

### 2 · copy-review · approval

id: `copy-review`

Approve the settings copy for the mute toggle

**Why:** The toggle is the only place a member learns what muting does. The doc's first rule (no push and no badge from a muted channel) means the copy has to say both.  
**Waits on it:** The settings screen in build phase 1.  
**If you don't answer:** Phase 1 ships with the old label, which says nothing about badges.  

```
- Turn off notifications
+ Mute channel
+ You won't get pushes or badges from this channel until you unmute it.
```

- a) Approve
- b) Request changes (say what after a dash)
- c) Reject

More, if you need it:

- Evidence: `examples/channel-muting.md:18` rule 1: no push or badge count until unmuted

### 3 · mute-limit · value

id: `mute-limit`

How many channels may one member mute?

**Why:** The send path reads the mute table before every notification. With no limit, one member with thousands of muted channels makes every send slower for everyone.  
**Waits on it:** The schema in build phase 1 (the index on the mute table).  
**If you don't answer:** No limit is set; the agent flags it as UNENFORCED in §4 Invariants.  

- a) 500 (proposed)
- or reply `3: <the value>`

More, if you need it:

- Example: Ben is in 800 channels and mutes 600 of them. At 500 he is told he has reached the limit and must unmute one first.
- Evidence: `examples/channel-muting.md:69` the send path checks the mute table before writing a notification

### 4 · staging-flag · to do

id: `staging-flag`

Turn the mute flag on in staging

**Why:** The red tests in phase 1 run against staging, and they fail for the wrong reason while the flag is off.  
**Waits on it:** Arming the doc: the red gate commit needs staging with the flag on.  
**If you don't answer:** The agent waits. It cannot turn the flag on: that needs your staging credentials.  

```
./scripts/flags.sh set channel-mute on --env staging
```

- a) Done
- b) Not yet

</details>

<!-- promise-sheet:v1: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 -->
