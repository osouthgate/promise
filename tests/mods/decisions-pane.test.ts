// Tests for hooks/decisions-pane.js, the decision pane mod. Run from the repo root with
// `claude plugin test`: no session, sign-in or network. The sheet below has the shape
// `decisions.py sheet --json` prints (tests/test_decisions.py checks that side), one item
// of each kind the pane draws differently.
import { expect, test } from 'claude-code/testing'

const SHEET = {
  format: 'promise-sheet',
  version: 1,
  id: 'abc123',
  title: 'Muting',
  intro: '',
  counts: { later: 0, laterBlocking: 0 },
  unclear: [],
  items: [
    {
      id: 'docs/muting.md#Q1', kind: 'question', doc: 'docs/muting.md', q: 'Q1', docTitle: 'Channel muting',
      blocking: true, text: 'Which plan tiers can mute channels?', why: 'Plans differ.',
      ifNoAnswer: 'Every tier can.', code: '- old\n+ new',
      evidence: [{ ref: 'docs/muting.md:20', note: 'the signal' }],
      alsoAnswers: [{ id: 'docs/threads.md#Q2', kind: 'question', doc: 'docs/threads.md', q: 'Q2' }],
      replies: [
        { code: 'a', label: 'Every tier (Recommended): a', value: 'Every tier', recommended: true },
        { code: 'b', label: 'None of these: reply with your own words', value: null, recommended: false },
        { code: 'c', label: 'Paid tiers only', value: 'Paid tiers only', recommended: false, because: 'revenue' },
      ],
      replyWords: true,
    },
    {
      id: 'docs/muting.md#Q3', kind: 'question', doc: 'docs/muting.md', q: 'Q3', docTitle: 'Channel muting',
      blocking: false, text: 'Is a muted channel greyed out?', replies: [], replyWords: true,
    },
    {
      id: 'copy', kind: 'approve', text: 'Approve the copy',
      replies: [
        { code: 'a', label: 'Approve', value: 'Approved', recommended: false },
        { code: 'b', label: 'Request changes', value: 'Changes requested', recommended: false, noteAsk: 'what', noteRequired: true },
        { code: 'c', label: 'Reject', value: 'Rejected', recommended: false },
      ],
      replyWords: false,
    },
    {
      id: 'docs/muting.md#D4', kind: 'decided', doc: 'docs/muting.md', decision: '4', docTitle: 'Channel muting',
      text: 'The page opens on the Personal tab.', why: 'most visits need it',
      replies: [{ code: 'a', label: 'Ask me instead', value: 'Ask me instead', recommended: false, noteAsk: 'why' }],
      replyWords: false,
    },
  ],
}

const APPLIED = {
  written: [{ doc: 'docs/muting.md', q: 'Q1', line: 'Answer (2026-01-05, Ana): Every tier. only yearly' }],
  skipped: [],
  forAgent: [{ id: 'copy', value: 'Changes requested. shorter' }],
  dryRun: false,
  notAnswered: [],
}

const PANE = {
  plugin: 'promise',
  component: 'Pane',
  requestId: 'promise-decisions',
  viewport: { columns: 160, rows: 40 },
  props: {
    title: 'promise: decisions',
    isFocused: true,
    bodyColumns: 70,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

// Every call the mod makes in Claude Code's place, recording what it was asked.
function stubs(on, opts: { surfaces?: string[]; placed?: boolean; sheet?: unknown; built?: unknown;
  missing?: string[]; python2?: string[]; applyOut?: string[]; applyFails?: string; closeFails?: boolean } = {}) {
  const seen = { runs: [] as any[], submitted: [] as string[], toasts: [] as string[], logs: [] as string[], opened: 0, closed: 0 }
  on('session.start', () => ({ cwd: '/work' }))
  on('session.surfaces', () => ({ value: opts.surfaces ?? ['terminal'] }))
  on('session.cwd', () => ({ value: '/work' }))
  on('command.register', ($, e) => {
    seen.command = e
    return { value: undefined }
  })
  on('tool.register', ($, e) => {
    seen.tool = e
    return { value: undefined }
  })
  on('fs.read', () => ({ value: JSON.stringify(opts.sheet ?? SHEET) }))
  on('ui.open', () => {
    seen.opened += 1
    return { value: { isPlaced: opts.placed ?? true, reason: opts.placed === false ? 'narrow' : undefined } }
  })
  on('ui.close', () => {
    seen.closed += 1
    return opts.closeFails ? { deny: 'the pane is gone' } : { value: undefined }
  })
  on('ui.toast', ($, e) => {
    seen.toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.log', ($, e) => {
    seen.logs.push(e.text)
    return { value: undefined }
  })
  on('prompt.submit', ($, e) => {
    seen.submitted.push(e.text)
    return { text: e.text }
  })
  on('process.run', ($, e) => {
    seen.runs.push({ argv: e.argv, init: e.init })
    // An interpreter in opts.missing is not installed: the run rejects, as it does on a host without it.
    if ((opts.missing ?? []).includes(e.argv[0])) return { deny: 'cannot start ' + e.argv[0] }
    // The probe: is this Python 3.8 or later? An interpreter in opts.python2 says no.
    if (e.argv.includes('-c')) return { value: { exitCode: (opts.python2 ?? []).includes(e.argv[0]) ? 1 : 0, stdout: '', stderr: '' } }
    if (e.argv[0] === 'git') return { value: { exitCode: 0, stdout: 'Ana\n', stderr: '' } }
    // Python runs in UTF-8 mode, whatever the host's code page.
    expect(e.argv.slice(1, 3)).toEqual(['-X', 'utf8'])
    if (e.argv.includes('sheet')) {
      return { value: { exitCode: 0, stdout: JSON.stringify(opts.built ?? SHEET), stderr: '' } }
    }
    if (opts.applyFails) return { value: { exitCode: 2, stdout: '', stderr: opts.applyFails } }
    const out = opts.applyOut?.shift()
    return { value: { exitCode: 0, stdout: out ?? JSON.stringify(APPLIED), stderr: '' } }
  })
  return seen
}

const START = { surface: 'terminal', isInteractive: true, cwd: '/work' }

test('the tool is offered only where a pane can show; the command always', async ($, on) => {
  const seen = stubs(on, { surfaces: [] })
  await $.session.start(START)
  expect(seen.command.name).toBe('promise-decide')
  expect(seen.tool).toBeUndefined()
  const answer = await $.command.run({ command: 'promise-decide', args: '' })
  expect(answer.text).toMatch(/Nothing draws a pane/)
})

test('the tool registers as decision_pane where the terminal draws', async ($, on) => {
  const seen = stubs(on)
  await $.session.start(START)
  expect(seen.tool.name).toBe('decision_pane')
  expect(seen.tool.inputSchema.required).toEqual(['sheet'])
})

test('a file that is not a sheet is refused with what to pass', async ($, on) => {
  stubs(on, { sheet: { format: 'promise-answers' } })
  const out = await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'x.json' })
  expect(out.deny).toMatch(/not a promise sheet/)
})

test('a narrow terminal leaves a notice and tells the agent to end its turn', async ($, on) => {
  const seen = stubs(on, { placed: false })
  const out = await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  expect(out.result).toMatch(/run \/promise-decide/)
  expect(seen.toasts[0]).toMatch(/3 decisions and 1 agent decisions to look over for you/)
})

test('the picks go to apply on standard input as promise-picks, and the agent hears back', async ($, on) => {
  const seen = stubs(on)
  const out = await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  expect(out.result).toMatch(/pane is open with 3 decisions and 1 agent decisions to look over/)

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: '1. BLOCKING · Channel muting · question' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '0 of 3 answered · 1 blocking left' })).toBeDefined()
  // The Recommended pick with a note, the item's own words, a changes request, and an
  // "Ask me instead" on what the agent decided.
  await ui.press({ key: 'recommended' })
  await ui.input({ key: 'note-1', text: 'only yearly' })
  await ui.select({ key: 'pick-2', value: 'own' })
  await ui.input({ key: 'words-2', text: 'No, it keeps its colour.' })
  await ui.select({ key: 'pick-3', value: 'b' })
  await ui.input({ key: 'note-3', text: 'shorter' })
  await ui.select({ key: 'pick-4', value: 'a' })
  await ui.input({ key: 'note-4', text: 'tabs are a product call' })
  await ui.press({ key: 'save' })

  const apply = seen.runs.find((r) => r.argv.includes('apply'))
  expect(apply.argv[3].endsWith('/skills/promise/scripts/decisions.py')).toBe(true)
  expect(apply.argv.slice(4)).toEqual(['apply', '-', '--json', '--cwd', '/work', '--by', 'Ana'])
  // Picks, not answers: decisions.py reads each as a chat reply's code (answer_entry),
  // so the note, own words and the question Q1 also settles are written there.
  const sent = JSON.parse(apply.init.stdin)
  expect(sent.format).toBe('promise-picks')
  expect(sent.sheet.id).toBe('abc123')
  expect(sent.picks).toEqual([
    { n: 1, code: 'a', note: 'only yearly' },
    { n: 2, code: null, note: 'No, it keeps its colour.' },
    { n: 3, code: 'b', note: 'shorter' },
    { n: 4, code: 'a', note: 'tabs are a product call' },
  ])
  expect(seen.closed).toBe(1)
  expect(seen.submitted[0]).toMatch(/wrote docs\/muting\.md Q1: Answer \(2026-01-05, Ana\): Every tier\. only yearly/)
  expect(seen.submitted[0]).toMatch(/- copy: Changes requested\. shorter/)
})

test('a pick decisions.py cannot read keeps the pane open with its reason', async ($, on) => {
  const reason = 'decisions.py: the answers could not be read: 3a: item 3 has choices a to c'
  const seen = stubs(on, { applyFails: reason })
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.select({ key: 'pick-3', value: 'a' })
  await ui.press({ key: 'save' })
  expect(await ui.find({ type: 'Text', text: reason })).toBeDefined()
  expect(seen.closed).toBe(0)
  expect(seen.submitted).toEqual([])
})

test('an empty words field is named, and nothing is sent', async ($, on) => {
  const seen = stubs(on)
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.select({ key: 'pick-3', value: 'a' })
  await ui.select({ key: 'pick-1', value: 'b' })
  expect(await ui.find({ key: 'words-1' })).toBeDefined()
  // Picked but without its words, the BLOCKING item is still left.
  expect(await ui.find({ type: 'Text', text: '1 of 3 answered · 1 blocking left' })).toBeDefined()
  await ui.press({ key: 'save' })
  expect(await ui.find({ type: 'Text', text: 'Item 1 needs its field filled in, or "Not now".' })).toBeDefined()
  expect(seen.runs.some((r) => r.argv.includes('apply'))).toBe(false)
})

test('a request for changes with nothing said is named before Save sends anything', async ($, on) => {
  const seen = stubs(on)
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-3', value: 'b' })
  await ui.press({ key: 'save' })
  expect(await ui.find({ type: 'Text', text: 'Item 3 needs its field filled in, or "Not now".' })).toBeDefined()
  expect(seen.runs.some((r) => r.argv.includes('apply'))).toBe(false)
  await ui.input({ key: 'note-3', text: 'shorter' })
  await ui.press({ key: 'save' })
  expect(seen.runs.some((r) => r.argv.includes('apply'))).toBe(true)
})

test('the agent cannot replace its own earlier sheet while the person has picks on it', async ($, on) => {
  const seen = stubs(on)
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-1', value: 'a' })
  const out = await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'other.json' })
  expect(out.deny).toMatch(/picks not yet saved/)
  expect(seen.opened).toBe(1)
})

test('the agent cannot replace a sheet the person has picks on', async ($, on) => {
  const seen = stubs(on)
  await $.session.start(START)
  await $.command.run({ command: 'promise-decide', args: '' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-3', value: 'a' })
  const out = await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  expect(out.deny).toMatch(/picks not yet saved/)
  expect(seen.opened).toBe(1)
})

test('/promise-decide naming docs never replaces the person\'s own unsaved picks', async ($, on) => {
  const seen = stubs(on)
  await $.session.start(START)
  await $.command.run({ command: 'promise-decide', args: '' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-3', value: 'a' })
  const answer = await $.command.run({ command: 'promise-decide', args: 'docs/other.md' })
  expect(answer.text).toMatch(/picks not yet saved/)
  expect(seen.runs.filter((r) => r.argv.includes('sheet')).length).toBe(1)
})

test('a sheet the person opened logs what is for the agent', async ($, on) => {
  const seen = stubs(on)
  await $.session.start(START)
  await $.command.run({ command: 'promise-decide', args: '' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-3', value: 'a' })
  await ui.press({ key: 'save' })
  expect(seen.logs[0]).toBe('wrote 1 answers into §9; for the agent: copy: Changes requested. shorter')
})

test('the brief is on the card: what to leave, the code, sources, each choice\'s reason, the note asked for', async ($, on) => {
  stubs(on)
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: 'If you leave it: Every tier can.' })).toBeDefined()
  expect(await ui.find({ type: 'Code' })).toMatchObject({ props: { source: '- old\n+ new' } })
  expect(await ui.find({ type: 'Text', text: 'Source: docs/muting.md:20 — the signal' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'c) Paid tiers only — revenue' })).toBeDefined()
  await ui.select({ key: 'pick-3', value: 'b' })
  expect(await ui.find({ key: 'note-3' })).toMatchObject({ props: { label: 'What to change' } })
  await ui.select({ key: 'pick-4', value: 'a' })
  expect(await ui.find({ key: 'note-4' })).toMatchObject({ props: { label: 'Why' } })
})

test('a sheet with words a person cannot follow never reaches the pane', async ($, on) => {
  const seen = stubs(on, { sheet: { ...SHEET, unclear: ['copy: leans on Q4'] } })
  const out = await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  expect(out.deny).toMatch(/cannot follow without the doc open.*copy: leans on Q4/)
  expect(seen.opened).toBe(0)
})

test('an image sends the agent to the Artifact page', async ($, on) => {
  const withImage = { ...SHEET, items: [{ ...SHEET.items[2], image: 'https://example.com/a.png' }] }
  const seen = stubs(on, { sheet: withImage })
  const out = await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  expect(out.deny).toMatch(/carries an image.*Artifact page/)
  expect(seen.opened).toBe(0)
})

test('items left for a later round are shown and handed back', async ($, on) => {
  const seen = stubs(on, { sheet: { ...SHEET, counts: { later: 28, laterBlocking: 3 } } })
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: '28 more wait for a later round (3 BLOCKING): this round first.' })).toBeDefined()
  await ui.select({ key: 'pick-3', value: 'a' })
  await ui.press({ key: 'save' })
  expect(seen.submitted[0]).toMatch(/28 more wait for a later round \(3 BLOCKING\): build the next round/)
})

test('a pane that will not close still hands the answers back', async ($, on) => {
  const seen = stubs(on, { closeFails: true })
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-3', value: 'a' })
  await ui.press({ key: 'save' })
  expect(seen.submitted.length).toBe(1)
})

test('Python 2 is passed over for the next interpreter', async ($, on) => {
  const seen = stubs(on, { python2: ['python3'] })
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-3', value: 'a' })
  await ui.press({ key: 'save' })
  expect(seen.runs.find((r) => r.argv.includes('apply')).argv[0]).toBe('python')
})

test('saving with nothing picked writes nothing, and still hands back to the agent', async ($, on) => {
  // A sheet of agent decisions alone has nothing to answer: Save is how the person says they stand.
  const decidedOnly = { ...SHEET, items: [SHEET.items[3]] }
  const seen = stubs(on, { sheet: decidedOnly })
  const out = await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  expect(out.result).toMatch(/open with 0 decisions and 1 agent decisions to look over/)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'save' })
  expect(seen.runs.some((r) => r.argv.includes('apply'))).toBe(false)
  expect(seen.closed).toBe(1)
  expect(seen.submitted[0]).toMatch(/without answering anything: nothing was written, and every agent decision stands/)
})

test('an apply that fails leaves Save usable, and a second press writes', async ($, on) => {
  const seen = stubs(on, { applyOut: ['not json'] })
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-3', value: 'a' })
  await ui.press({ key: 'save' })
  expect(seen.closed).toBe(0)
  expect(await ui.find({ key: 'save' })).toMatchObject({ props: { label: 'Save answers' } })
  await ui.press({ key: 'save' })
  expect(seen.runs.filter((r) => r.argv.includes('apply')).length).toBe(2)
  expect(seen.closed).toBe(1)
})

test('python3 missing: python answers the probe, and apply runs once', async ($, on) => {
  const seen = stubs(on, { missing: ['python3'] })
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'pick-3', value: 'a' })
  await ui.press({ key: 'save' })
  const applies = seen.runs.filter((r) => r.argv.includes('apply'))
  expect(applies.length).toBe(1)
  expect(applies[0].argv[0]).toBe('python')
})

test('/promise-decide naming docs never replaces the sheet the agent is waiting on', async ($, on) => {
  const seen = stubs(on)
  await $.session.start(START)
  await $.tool.call({ tool: 'mcp__promise__decision_pane', sheet: 'sheet.json' })
  const answer = await $.command.run({ command: 'promise-decide', args: 'docs/other.md' })
  expect(answer.text).toMatch(/agent is waiting on the sheet it sent/)
  expect(seen.runs.some((r) => r.argv.includes('sheet'))).toBe(false)
  expect(await $.command.run({ command: 'promise-decide', args: '' })).toEqual({})
  expect(seen.opened).toBe(2)
})

test('/promise-decide builds a sheet of the docs named, passed after --, and opens the pane', async ($, on) => {
  const seen = stubs(on)
  await $.session.start(START)
  const answer = await $.command.run({ command: 'promise-decide', args: 'docs/muting.md --all' })
  expect(answer).toEqual({})
  const sheetRun = seen.runs.find((r) => r.argv.includes('sheet'))
  expect(sheetRun.argv.slice(4)).toEqual(['sheet', '--json', '--cwd', '/work', '--', 'docs/muting.md', '--all'])
  expect(seen.opened).toBe(1)
  // A sheet opened by the person reports in the transcript, not as a new turn.
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'recommended' })
  await ui.press({ key: 'save' })
  expect(seen.submitted).toEqual([])
  expect(seen.logs[0]).toMatch(/wrote 1 answers into §9; for the agent: copy/)
})

test('/promise-decide with nothing open says so', async ($, on) => {
  stubs(on, { built: { ...SHEET, items: [] } })
  await $.session.start(START)
  const answer = await $.command.run({ command: 'promise-decide', args: '' })
  expect(answer.text).toBe('No decisions are waiting on you.')
})
