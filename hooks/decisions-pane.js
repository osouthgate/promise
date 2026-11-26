// promise's decision pane: the rich surface for references/decision-sheet.md, drawn inside
// Claude Code (the terminal, and the Desktop app's Code tab) by a mod.
//
// It decides nothing itself. `decisions.py sheet --json` builds the sheet, with each
// item's lettered `replies` as a chat reply would pick them; the pane draws one picker per
// item; Save hands the picks to `decisions.py apply -` on standard input, which reads them
// as it reads a chat reply (answer_entry) and writes them into §9. Where nothing draws
// (claude -p, the VS Code panel, a cloud session) the tool is never offered, and the
// skill uses the surfaces decision-sheet.md already names.
//
// Two ways in:
// - the agent calls the `decision_pane` tool (mcp__promise__decision_pane) with the
//   path of a sheet it built, ends its turn, and gets the result back as a message;
// - the person runs /promise-decide [doc ...], which builds a sheet of the open §9
//   questions (or reopens the one the agent sent) and opens the pane.

const PANE = 'promise-decisions'
const TOOL = 'mcp__promise__decision_pane'
// How the tool's result starts when the sheet is on the pane: open, or waiting for a wider
// terminal that /promise-decide opens. session_report.py counts these as the sheet shown,
// and tests/test_session_report.py checks the two spellings agree.
const PANE_SHOWN = 'The decision pane is'
const SKIP = 'skip'
const OWN = 'own'
// The interpreters SKILL.md's Phase 0 tries, in its order; the probe also refuses Python 2.
const PYTHONS = [['python3'], ['python'], ['py', '-3']]
const PY3 = 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'
// One Code element draws at most this many characters.
const CODE_LIMIT = 10000

// The sheet on screen, and what the person has picked so far. Lost on a reload, which
// only happens while someone edits this file; the sheet can be sent again.
let pending = null
let canDraw = false
// The interpreter that answered `--version`, found once, so a script never runs twice.
let pythonCmd = null

function freshState(sheet, fromTool) {
  return { sheet, fromTool, picks: {}, words: {}, notes: {}, status: '', busy: false }
}

// Runs decisions.py with the first of `python3`, `python` and `py -3` that is Python 3.8
// or later. Only the probe falls through to the next one: the script itself runs once, so
// apply is never repeated.
async function python($, args, init) {
  if (!pythonCmd) {
    for (const exe of PYTHONS) {
      try {
        const probe = await $.process.run([...exe, '-c', PY3], { timeoutMs: 10000 })
        if (probe.exitCode === 0) {
          pythonCmd = exe
          break
        }
      } catch {
        // Not installed here: try the next spelling.
      }
    }
    if (!pythonCmd) throw new Error('none of python3, python or py -3 is Python 3.8 or later here, and decisions.py needs one')
  }
  // -X utf8: the sheet's text crosses as UTF-8 both ways, whatever the host's code page.
  return $.process.run([...pythonCmd, '-X', 'utf8', $.plugin.root + '/skills/promise/scripts/decisions.py', ...args], init)
}

function isSheet(data) {
  return data && data.format === 'promise-sheet' && Array.isArray(data.items)
}

// Why a sheet must not reach the pane, or null. The words decisions.py found unclear stop
// every surface it renders (sheet --out, --chat, ...); an image needs the Artifact page.
function refusal(sheet) {
  if ((sheet.unclear || []).length) {
    return 'the sheet leans on what a person cannot follow without the doc open, so it was not shown ' +
      '(references/decision-sheet.md §4): ' + sheet.unclear.join('; ')
  }
  if (sheet.items.some((i) => i.image)) {
    return 'the sheet carries an image, which the pane cannot show: publish the Artifact page instead ' +
      '(references/decision-sheet.md §2)'
  }
  return null
}

// How many items wait for a later round, as the page and the chat message say.
function laterLine(sheet) {
  const c = sheet.counts || {}
  if (!c.later) return ''
  return c.later + ' more wait for a later round' + (c.laterBlocking ? ' (' + c.laterBlocking + ' BLOCKING)' : '')
}

// Items the person answers; what the agent decided is shown too, but needs no answer.
function asked(sheet) {
  return sheet.items.filter((i) => i.kind !== 'decided')
}

function replyFor(item, code) {
  return (item.replies || []).find((r) => r.code === code)
}

// Whether a pick takes the person's words in place of a choice.
function wantsWords(item, pick) {
  const reply = replyFor(item, pick)
  return pick === OWN || Boolean(reply && reply.value === null)
}

// Picked, and with its words or required note where it needs them: for the progress line,
// and so Save never sends a field left empty. Whether a pick reads as an answer is
// decisions.py's to say; noteRequired is its word that this one needs the note.
function isAnswered(state, item) {
  const pick = state.picks[item.id] || SKIP
  if (pick === SKIP) return false
  if (wantsWords(item, pick)) return Boolean((state.words[item.id] || '').trim())
  const reply = replyFor(item, pick)
  return !(reply && reply.noteRequired) || Boolean((state.notes[item.id] || '').trim())
}

// promise-picks for `decisions.py apply -`: the sheet as drawn and one pick per item
// answered, by number. apply reads each as a chat reply's code (answer_entry), so the
// note, the person's own words and the questions an answer also settles are its to write.
function buildPicks(state) {
  const picks = []
  state.sheet.items.forEach((item, index) => {
    const pick = state.picks[item.id] || SKIP
    if (pick === SKIP) return
    if (wantsWords(item, pick)) {
      const reply = replyFor(item, pick)
      picks.push({ n: index + 1, code: reply ? reply.code : null, note: state.words[item.id] || '' })
    } else {
      picks.push({ n: index + 1, code: pick, note: state.notes[item.id] || '' })
    }
  })
  return { format: 'promise-picks', version: 1, sheet: state.sheet, picks }
}

function progress(state) {
  const items = asked(state.sheet)
  const done = items.filter((i) => isAnswered(state, i)).length
  const blockingLeft = items.filter((i) => i.blocking === true && !isAnswered(state, i)).length
  return done + ' of ' + items.length + ' answered · ' +
    (blockingLeft ? blockingLeft + ' blocking left' : 'no blocking questions left')
}

// What the agent reads when the person saves: what apply wrote, and what is now its to do.
function reportFor(result) {
  const lines = (result.written || []).length || (result.forAgent || []).length || (result.skipped || []).length
    ? ['The person answered the decision pane; decisions.py apply ran on their answers.']
    : ['The person saved the decision pane without answering anything: nothing was written, and every agent decision stands.']
  for (const w of result.written || []) lines.push('- wrote ' + w.doc + ' ' + (w.q || '') + ': ' + w.line)
  if ((result.forAgent || []).length) {
    lines.push('For you to act on (answers that name no doc question):')
    for (const f of result.forAgent) lines.push('- ' + f.id + ': ' + f.value)
  }
  for (const s of result.skipped || []) lines.push('- skipped ' + (s.id || s.index) + ': ' + s.reason)
  if ((result.notAnswered || []).length) lines.push('Not answered: ' + result.notAnswered.join(', '))
  if (result.later) lines.push(result.later + ': build the next round from what is still open.')
  return lines.join('\n')
}

async function openPane($, state) {
  pending = state
  return $.ui.open({ id: PANE, title: 'promise: decisions', focus: true, closeOnEscape: true })
}

async function save($) {
  const state = pending
  if (!state || state.busy) return
  // One empty field would make apply refuse every answer with it: name the item instead.
  const unfinished = state.sheet.items
    .map((item, index) => ((state.picks[item.id] || SKIP) !== SKIP && !isAnswered(state, item) ? index + 1 : 0))
    .filter(Boolean)
  if (unfinished.length) {
    state.status = 'Item ' + unfinished.join(', ') + ' needs its field filled in, or "Not now".'
    $.ui.invalidate('ui.render')
    return
  }
  const data = buildPicks(state)
  state.busy = true
  state.status = data.picks.length ? 'Writing ' + data.picks.length + ' answers…' : ''
  $.ui.invalidate('ui.render')
  let result
  try {
    result = data.picks.length
      ? await applyAnswers($, data)
      : { written: [], skipped: [], forAgent: [], notAnswered: asked(state.sheet).map((i) => i.id) }
  } catch (error) {
    // The answers may or may not be written: say what failed, and let Save be pressed again
    // (apply never writes the same answer twice).
    state.busy = false
    state.status = String((error && error.message) || error)
    $.ui.invalidate('ui.render')
    return
  }
  result.later = laterLine(state.sheet)
  // Another sheet may have replaced this one while apply ran (the agent sent one): keep it.
  const stillShown = pending === state
  if (stillShown) pending = null
  // The agent ended its turn on the tool's word; this starts the turn that carries on. It
  // goes first, so nothing below can keep the agent from hearing back. Not awaited: it
  // resolves when that turn starts, after this press has long returned.
  if (state.fromTool) {
    $.prompt.submit({ text: reportFor(result) }).catch((error) => {
      $.ui.log('could not hand the answers back to the agent (' + error.message + '); tell it they are written')
    })
  }
  // The record in the transcript first: for a sheet the person opened, its "for the
  // agent" answers reach the agent only through this line.
  $.ui.log('wrote ' + (result.written || []).length + ' answers into §9' +
    ((result.forAgent || []).length
      ? '; for the agent: ' + result.forAgent.map((f) => f.id + ': ' + f.value).join('; ')
      : '') +
    (result.later ? '; ' + result.later : ''))
  try {
    if (stillShown) await $.ui.close({ id: PANE })
  } catch {
    // The answers are written and handed back; a pane that would not close changes neither.
  }
}

// decisions.py apply on the answers, with the person's git name as --by; its JSON result.
async function applyAnswers($, data) {
  const cwd = await $.session.cwd()
  const args = ['apply', '-', '--json', '--cwd', cwd]
  try {
    const name = await $.process.run(['git', 'config', 'user.name'], { cwd })
    if (name.exitCode === 0 && name.stdout.trim()) args.push('--by', name.stdout.trim())
  } catch {
    // No git: the answer lines carry the date alone, as apply writes them without --by.
  }
  const run = await python($, args, { cwd, stdin: JSON.stringify(data) })
  if (run.exitCode !== 0) {
    throw new Error((run.stderr || run.stdout).trim() || 'decisions.py apply exited ' + run.exitCode)
  }
  return JSON.parse(run.stdout)
}

function pickAllRecommended(state) {
  for (const item of asked(state.sheet)) {
    if ((state.picks[item.id] || SKIP) !== SKIP) continue
    const rec = (item.replies || []).find((r) => r.recommended)
    if (rec) state.picks[item.id] = rec.code
  }
}

function optionsFor(item) {
  const options = [{ value: SKIP, label: item.kind === 'decided' ? "Keep the agent's choice" : 'Not now' }]
  for (const r of item.replies || []) options.push({ value: r.code, label: r.code + ') ' + r.label })
  if (item.replyWords && !(item.replies || []).some((r) => r.value === null)) {
    options.push({ value: OWN, label: 'In my own words' })
  }
  return options
}


// Whether a sheet has picks the person has not saved yet: nothing may replace it.
function hasPicks(state) {
  return Boolean(state) && Object.values(state.picks).some((p) => p !== SKIP)
}

// What /promise-decide prints: nothing once the pane shows, else why it could not.
function placed(opened) {
  return opened.isPlaced ? {} : { text: 'The pane could not open here (' + (opened.reason || 'not placed') + ').' }
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    try {
      canDraw = (await $.session.surfaces()).length > 0
    } catch (error) {
      canDraw = false
      $.ui.log('cannot tell whether a pane can draw here, so the decision pane is off: ' + error.message)
    }
    try {
      await $.command.register({
        name: 'promise-decide',
        description: "Answer promise's open decisions in a pane",
        argumentHint: '[doc ...]',
        immediate: true,
      })
    } catch (error) {
      $.ui.log('/promise-decide is not available: ' + error.message)
    }
    // Offered only where a pane can show: the skill reads the tool's presence as the surface.
    if (canDraw) {
      try {
        await $.tool.register({
          name: 'decision_pane',
          description:
            "Show promise's decision sheet to the person in a pane inside Claude Code, where they pick each " +
            'answer; it is the rich surface of references/decision-sheet.md, ahead of an Artifact. Pass `sheet`, ' +
            'the path of a file holding the output of `decisions.py sheet ... --json`. When it says the pane is ' +
            'open, end your turn without asking the questions in chat: the answers are written with ' +
            '`decisions.py apply` and come back to you as a message, with what is left for you to act on.',
          inputSchema: {
            type: 'object',
            properties: { sheet: { type: 'string', description: 'Path of the sheet JSON file' } },
            required: ['sheet'],
          },
        })
      } catch (error) {
        $.ui.log('the decision pane tool is not available: ' + error.message)
      }
    }
    return next(e)
  })

  on('tool.call', { tool: TOOL }, async ($, e) => {
    let sheet
    try {
      sheet = JSON.parse(await $.fs.read(e.sheet))
    } catch (error) {
      return { deny: 'Could not read a sheet from ' + e.sheet + ': ' + error.message + '. Write the output of decisions.py sheet ... --json to a file and pass its path.' }
    }
    if (!isSheet(sheet)) {
      return { deny: e.sheet + ' is not a promise sheet: pass the output of decisions.py sheet ... --json.' }
    }
    if (!sheet.items.length) return { result: 'The sheet has no items: nothing is waiting on the person.' }
    const refused = refusal(sheet)
    if (refused) return { deny: 'Not shown: ' + refused + '.' }
    if (hasPicks(pending)) {
      return {
        deny: 'Not shown: the person has another decision sheet open with picks not yet saved. Tell them to ' +
          'save it (/promise-decide reopens it), then call this again.',
      }
    }
    const others = sheet.items.length - asked(sheet).length
    const count = asked(sheet).length + ' decisions' + (others ? ' and ' + others + ' agent decisions to look over' : '')
    const opened = await openPane($, freshState(sheet, true))
    if (!opened.isPlaced) {
      $.ui.toast('promise has ' + count + ' for you: run /promise-decide to open them')
      return {
        result:
          PANE_SHOWN + ' waiting for a wider terminal (' + (opened.reason || 'not placed') + '); a notice told ' +
          'the person to run /promise-decide, which opens it. End your turn now; the answers come back as a ' +
          'message.',
      }
    }
    return {
      result:
        PANE_SHOWN + ' open with ' + count + '. End your turn now and do not ask them in chat; the ' +
        'answers come back as a message once the person saves.',
    }
  })

  on('command.run', { command: 'promise-decide' }, async ($, e) => {
    if (!canDraw) {
      return { text: 'Nothing draws a pane in this session. Ask the agent for the decision sheet instead.' }
    }
    const docs = (e.args || '').trim() ? e.args.trim().split(/\s+/) : []
    if (pending && pending.fromTool && docs.length) {
      // Replacing it would leave the agent waiting on answers that never come back.
      return { text: 'The agent is waiting on the sheet it sent: run /promise-decide alone to answer it first.' }
    }
    if (hasPicks(pending) && docs.length) {
      return { text: 'The open sheet has picks not yet saved: run /promise-decide alone to save them first.' }
    }
    if (pending && !docs.length) return placed(await openPane($, pending))
    const cwd = await $.session.cwd()
    let run
    try {
      run = await python($, ['sheet', '--json', '--cwd', cwd, '--', ...docs], { cwd })
    } catch (error) {
      return { text: String(error.message || error) }
    }
    if (run.exitCode !== 0) return { text: (run.stderr || run.stdout).trim() }
    let sheet
    try {
      sheet = JSON.parse(run.stdout)
    } catch {
      return { text: 'decisions.py sheet printed something that is not a sheet: ' + run.stdout.trim().slice(0, 200) }
    }
    if (!isSheet(sheet) || !sheet.items.length) return { text: 'No decisions are waiting on you.' }
    const refused = refusal(sheet)
    if (refused) return { text: 'Not shown: ' + refused + '.' }
    return placed(await openPane($, freshState(sheet, false)))
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== PANE || !pending) return next(e)
    const state = pending
    const { Box, Text, Button, Select, Input, Code } = $.ui.resolve(e)
    const dim = (text) => Text({ dimColor: true, wrap: 'wrap', children: [text] })
    const redraw = () => $.ui.invalidate('ui.render')
    const rows = []

    rows.push(Text({ bold: true, children: [state.sheet.title || 'Decisions waiting on you'] }))
    if (state.sheet.intro) rows.push(Text({ wrap: 'wrap', children: [state.sheet.intro] }))
    rows.push(Text({ dimColor: true, children: [progress(state)] }))
    if (laterLine(state.sheet)) rows.push(dim(laterLine(state.sheet) + ': this round first.'))

    state.sheet.items.forEach((item, index) => {
      const n = index + 1
      const pick = state.picks[item.id] || SKIP
      const reply = replyFor(item, pick)
      const head = n + '. ' + (item.blocking === true ? 'BLOCKING · ' : '') +
        (item.docTitle ? item.docTitle + ' · ' : '') + (item.kindTag || 'question')
      const card = [
        Text({ children: [' '] }),
        Text({ bold: true, children: [head] }),
        Text({ wrap: 'wrap', children: [item.text] }),
      ]
      // The brief the page shows, in its order: what an answer needs to be made cold.
      if (item.why) card.push(dim((item.kind === 'decided' ? 'Because: ' : 'Why: ') + item.why))
      if (item.blocks) card.push(dim('Blocks: ' + item.blocks))
      if (item.ifNoAnswer) card.push(dim('If you leave it: ' + item.ifNoAnswer))
      if (item.example) card.push(dim('Example: ' + item.example))
      if (item.detail) card.push(dim(item.detail))
      if (item.rollback) card.push(dim('Rollback: ' + item.rollback))
      if (item.reversibleUntil) card.push(dim('Reversible until: ' + item.reversibleUntil))
      if (item.code) card.push(Code({ source: String(item.code).slice(0, CODE_LIMIT) }))
      for (const ev of item.evidence || []) card.push(dim('Source: ' + ev.ref + (ev.note ? ' — ' + ev.note : '')))
      for (const l of item.links || []) card.push(dim('Link: ' + (l.label ? l.label + ' ' : '') + (l.url || '')))
      for (const o of item.alsoAnswers || []) card.push(dim('Also settles: ' + (o.docTitle ? o.docTitle + ': ' : '') + (o.text || o.id)))
      // Each choice's own reasons, as the page lays them out under its options.
      for (const r of item.replies || []) {
        const brief = [r.detail, r.because, r.commits && 'Commits: ' + r.commits, r.think && 'Think: ' + r.think,
          r.then && 'Then: ' + r.then].filter(Boolean)
        if (brief.length) card.push(dim(r.code + ') ' + r.label + ' — ' + brief.join(' · ')))
      }
      card.push(Select({
        key: 'pick-' + n,
        label: 'Answer',
        options: optionsFor(item),
        value: pick,
        onSelect: (value) => {
          if (state.busy) return  // Save has already sent the picks
          state.picks[item.id] = value
          state.status = ''
          redraw()
        },
      }))
      if (wantsWords(item, pick)) {
        card.push(Input({
          key: 'words-' + n,
          label: 'Your words',
          placeholder: 'Type the answer as it should be written in the doc',
          value: state.words[item.id] || '',
          submitLabel: 'keep',
          onInput: (value) => { if (!state.busy) state.words[item.id] = value },
          onSubmit: (value) => {
            if (state.busy) return
            state.words[item.id] = value
            redraw()
          },
        }))
      } else if (pick !== SKIP) {
        card.push(Input({
          key: 'note-' + n,
          label: reply && reply.noteAsk === 'what' ? 'What to change' : reply && reply.noteAsk === 'why' ? 'Why' : 'Note',
          placeholder: reply && reply.noteAsk === 'what' ? 'Needed: what should change' : 'Optional: written after the answer',
          value: state.notes[item.id] || '',
          submitLabel: 'keep',
          onInput: (value) => { if (!state.busy) state.notes[item.id] = value },
          onSubmit: (value) => {
            if (state.busy) return
            state.notes[item.id] = value
            redraw()
          },
        }))
      }
      rows.push(Box({ flexDirection: 'column', children: card }))
    })

    rows.push(Text({ children: [' '] }))
    if (state.status) rows.push(Text({ color: 'yellow', wrap: 'wrap', children: [state.status] }))
    rows.push(Box({
      flexDirection: 'row',
      columnGap: 2,
      children: [
        Button({ key: 'save', label: state.busy ? 'Saving…' : 'Save answers', onPress: () => save($) }),
        Button({
          key: 'recommended',
          label: 'Pick every Recommended',
          onPress: () => {
            if (state.busy) return
            pickAllRecommended(state)
            redraw()
          },
        }),
        // Esc closes it too; either way the picks stay, and /promise-decide reopens the sheet.
        Button({ key: 'close', label: 'Close (keeps picks)', onPress: () => $.ui.close({ id: PANE }).catch(() => {}) }),
      ],
    }))
    return Box({ flexDirection: 'column', children: rows })
  })
}
