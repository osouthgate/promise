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
