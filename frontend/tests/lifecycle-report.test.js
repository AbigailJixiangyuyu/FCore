import assert from 'node:assert/strict'
import test from 'node:test'
import { effectScope, nextTick, reactive, ref } from 'vue'
import { useLifecycleReport } from '../src/composables/workbench/useLifecycleReport.js'
import { evidenceMethodName } from '../src/domain/reportEvidence.js'

const encoder = new TextEncoder()

test('paper refresh restores submitted evidence, Markdown, turns and drafts for the matching dataset only', async t => {
  const records = new Map()
  globalThis.window = { localStorage: { getItem: key => records.get(key) ?? null, setItem: (key, value) => records.set(key, value) } }
  t.after(() => { delete globalThis.window })
  const { context, workbench, createReport, selectCurrent, selectFuture, fetch, openStream, textLine } = setupReport(t)
  workbench.viewLayout = ref('paper')
  const original = createReport()
  original.submit()
  await nextTick()
  assert.deepEqual(createReport().slots.value, original.slots.value)
  selectCurrent()
  original.submit()
  selectFuture()
  original.submit()
  for (const [question, answer] of [['Summarize', '**49** remained.'], ['Why?', 'It belongs to all three groups.']]) {
    original.question.value = question
    const request = original.ask()
    const stream = openStream()
    for (const event of [{ type: 'start', model: 'test' }, { type: 'thinking', content: 'Checking evidence.' }, { type: 'delta', content: answer }, { type: 'done' }]) {
      stream.enqueue(textLine(event))
    }
    stream.close()
    await request
  }
  original.question.value = 'Which members left?'
  await nextTick()
  const restored = createReport()
  assert.equal(restored.report.value.thinking, 'Checking evidence.')
  assert.equal(restored.turns.value[0].thinking, 'Checking evidence.')
  assert.deepEqual(restored.report.value, original.report.value)
  assert.deepEqual(restored.turns.value, original.turns.value)
  assert.equal(restored.question.value, original.question.value)
  assert.equal(restored.canSend.value, true)
  assert.equal(fetch.mock.callCount(), 2)
  workbench.viewLayout.value = 'video'
  assert.equal(createReport().report.value, null)
  workbench.viewLayout.value = 'paper'
  context.value = { ...context.value, dataset_version: 'v2' }
  assert.deepEqual(restored.slots.value, {})
  assert.equal(restored.report.value, null)
  context.value = { ...context.value, dataset_version: 'v1' }
  assert.equal(restored.report.value.initial_prompt, 'Summarize')
})

function setupReport(t) {
  let finish
  const fetch = t.mock.method(globalThis, 'fetch', () => new Promise(resolve => { finish = resolve }))
  const textLine = event => encoder.encode(JSON.stringify(event) + '\n')
  const flushStream = () => new Promise(resolve => setImmediate(resolve))
  function openStream() {
    let writer
    finish(new Response(new ReadableStream({
      start(controller) { writer = controller },
    }), { headers: { 'Content-Type': 'application/jsonl' } }))
    return writer
  }
  const context = ref({ dataset_id: 'test', dataset_version: 'v1', observed_until: 'S12' })
  const query = () => ({ isSuccess: ref(true), isFetching: ref(false), isPlaceholderData: ref(false) })
  const workbench = {
    context, store: reactive({ stage: 'history', analysisRunId: 1, futureParameters: { threshold: 0.5, horizon: 1 } }),
    selected: ref({ ...context.value, origin: 'pattern', method: 'tcq', structure_id: 'TCQ', membership_hash: 'h',
      snapshot_id: 'S10', parameters: { pattern: 'temporal_core' }, evidence: { analysis_snapshot_ids: ['S10'] } }),
    patternResult: query(), queryResult: query(), anomalyQuery: { isError: ref(false) },
    anomalyResponse: ref({ model_version: 'slade' }), prediction: query(), matchingPrediction: ref(null),
  }
  function selectCurrent() {
    workbench.store.stage = 'present'
    workbench.selected.value = { ...context.value, origin: 'max_core', method: 'pkmc', structure_id: 'M1',
      membership_hash: 'c', snapshot_id: 'S12', parameters: { algorithm: 'pkmc' } }
  }
  function selectFuture() {
    workbench.store.stage = 'future'
    workbench.matchingPrediction.value = { ...context.value, result_fingerprint: 'f', account: 'q', k: 4,
      model: 'zebra', threshold: 0.5, model_version: 'z', target_snapshot: 'S13' }
  }
  const scope = effectScope()
  t.after(() => scope.stop())
  const createReport = () => scope.run(() => useLifecycleReport(workbench))
  return { context, workbench, createReport, selectCurrent, selectFuture, fetch, openStream, textLine, flushStream }
}

test('follow-ups to a saved legacy paper report send its original node IDs', async t => {
  const { context, workbench, createReport, fetch, openStream, textLine } = setupReport(t)
  const saved = {
    slots: { history: { reference: { ...context.value } } },
    report: { content: '**N001** remained.', thinking: 'Checking N002.', node_labels: { N001: 'E025', N002: 'E031' } },
    turns: [{ question: 'E031呢？', answer: '历史成员N002。', thinking: 'Check N001.' }],
    question: 'E025 呢？',
  }
  globalThis.window = { localStorage: { getItem: () => JSON.stringify(saved), setItem() {} } }
  t.after(() => { delete globalThis.window })
  workbench.viewLayout = ref('paper')
  const discussion = createReport()
  assert.equal(discussion.report.value.thinking, 'Checking E031.')
  assert.equal(discussion.turns.value[0].thinking, 'Check E025.')
  const request = discussion.ask()
  const body = JSON.parse(fetch.mock.calls.at(-1).arguments[1].body)
  assert.equal(body.report_content, '**E025** remained.')
  assert.deepEqual(body.turns, [{ question: 'E031呢？', answer: '历史成员E031。' }])
  assert.equal(body.question, 'E025 呢？')
  const stream = openStream()
  stream.enqueue(textLine({ type: 'delta', content: 'E025 remained.' }))
  stream.enqueue(textLine({ type: 'done' }))
  stream.close()
  await request
})

test('paper view restores partial reports and adding evidence starts a new comparison', async t => {
  const records = new Map()
  globalThis.window = { localStorage: { getItem: key => records.get(key), setItem: (key, value) => records.set(key, value) } }
  t.after(() => { delete globalThis.window })
  const { workbench, createReport, selectFuture, fetch, openStream, textLine } = setupReport(t)
  workbench.viewLayout = ref('paper')
  const report = createReport()
  report.submit()
  for (const stages of [['history'], ['history', 'future']]) {
    const request = report.ask()
    const [url, options] = fetch.mock.calls.at(-1).arguments
    assert.equal(url, '/api/reports/generate')
    const body = JSON.parse(options.body)
    assert.deepEqual(['history', 'current', 'future'].filter(stage => stage in body), stages)
    assert.equal('initial_prompt' in body, false)
    const stream = openStream()
    for (const event of [{ type: 'start', model: 'test' }, { type: 'delta', content: stages.join(' + ') }, { type: 'done' }]) {
      stream.enqueue(textLine(event))
    }
    stream.close()
    await request
    await nextTick()
    const restored = createReport()
    assert.deepEqual(restored.report.value, report.report.value)
    assert.equal(restored.canAsk.value, true)
    if (stages.length === 1) {
      selectFuture()
      report.submit()
      assert.equal(report.report.value, null)
      assert.equal(report.canSend.value, true)
    }
  }
})

test('each submission enables sending and updated evidence replaces an obsolete stream', async t => {
  const { context, workbench, createReport, selectCurrent, selectFuture, fetch, openStream, textLine, flushStream } = setupReport(t)
  const report = createReport()
  assert.equal(report.question.value, '')
  assert.equal(report.ready.value, false)
  assert.equal(report.canSend.value, false)
  const firstQuestion = 'Compare the current and future communities.'
  report.question.value = firstQuestion
  await report.ask()
  report.submit()
  assert.deepEqual(Object.keys(report.slots.value), ['history'])
  assert.equal(report.canSend.value, true)
  selectCurrent()
  report.submit()
  assert.deepEqual(Object.keys(report.slots.value), ['history', 'current'])
  assert.equal(report.canSend.value, true)
  selectFuture()
  workbench.prediction.isPlaceholderData.value = true
  assert.equal(report.canSubmit.value, false)
  workbench.prediction.isPlaceholderData.value = false
  report.submit()
  assert.equal(report.ready.value, true)
  assert.deepEqual(Object.values(report.slots.value).map(evidenceMethodName), ['OTCD', 'PKMC', 'Zebra'])
  assert.equal(report.slots.value.future.window, 'S13')
  assert.equal(fetch.mock.callCount(), 0)
  assert.equal(report.question.value, firstQuestion)
  assert.equal(report.canSend.value, true)
  const generation = report.ask()
  await report.ask()
  assert.equal(fetch.mock.callCount(), 1)
  assert.equal(fetch.mock.calls[0].arguments[0], '/api/reports/generate')
  const firstRequest = JSON.parse(fetch.mock.calls[0].arguments[1].body)
  assert.equal(firstRequest.initial_prompt, report.question.value)
  assert.equal(firstRequest.future.threshold, 0.5)
  const oldStream = openStream()
  oldStream.enqueue(textLine({ type: 'start', model: 'test' }))
  oldStream.enqueue(textLine({ type: 'delta', content: 'First part.' }))
  await flushStream()
  assert.equal(report.generating.value, true)
  assert.equal(report.report.value.content, 'First part.')
  workbench.store.futureParameters.threshold = 0.6
  assert.equal(report.canSubmit.value, false)
  workbench.matchingPrediction.value = { ...workbench.matchingPrediction.value, result_fingerprint: 'next', threshold: 0.6 }
  report.submit()
  oldStream.enqueue(textLine({ type: 'delta', content: 'Obsolete reply' }))
  oldStream.close()
  await generation
  assert.equal(report.report.value, null)
  assert.equal(report.slots.value.future.reference.threshold, 0.6)
  assert.equal(report.canAsk.value, false)
  assert.equal(report.question.value, '')
  const nextGeneration = report.ask()
  const nextRequest = JSON.parse(fetch.mock.calls[1].arguments[1].body)
  assert.equal('initial_prompt' in nextRequest, false)
  assert.equal(nextRequest.future.result_fingerprint, 'next')
  const stream = openStream()
  const result = {
    content: '13 members overlap.\n\nq（query node） is forecast to remain.', model: 'test', initial_prompt: '',
  }
  stream.enqueue(textLine({ type: 'start', model: result.model }))
  const delta = textLine({ type: 'delta', content: result.content })
  const split = delta.indexOf(encoder.encode('（')[0]) + 1
  stream.enqueue(delta.slice(0, split))
  stream.enqueue(delta.slice(split))
  stream.enqueue(textLine({ type: 'done' }))
  stream.close()
  await nextGeneration
  assert.deepEqual(report.report.value, result)
  assert.equal(report.canAsk.value, true)
  assert.equal(report.question.value, '')
  context.value = { ...context.value, dataset_version: 'v2' }
  assert.deepEqual(report.slots.value, {})
  assert.equal(report.ready.value, false)
  assert.equal(fetch.mock.callCount(), 2)
})

test('follow-ups carry completed turns and a fresh page starts with an empty report', async t => {
  const { context, workbench, createReport, selectCurrent, selectFuture, fetch, openStream, textLine, flushStream } = setupReport(t)
  const discussion = createReport()
  discussion.submit()
  selectCurrent()
  discussion.submit()
  selectFuture()
  discussion.submit()
  const slots = discussion.slots.value
  const question = 'Compare the historical and current communities.'
  const initialReport = {
    model: 'test', content: '- **q** belongs to the overlap of 13 members. 〔C01〕',
    initial_prompt: question,
  }
  const start = { type: 'start', model: initialReport.model }
  discussion.question.value = question
  const generation = discussion.ask()
  const reportStream = openStream()
  reportStream.enqueue(textLine(start))
  reportStream.enqueue(textLine({ type: 'delta', content: initialReport.content }))
  reportStream.enqueue(textLine({ type: 'done' }))
  reportStream.close()
  await generation
  const latestRequest = () => JSON.parse(fetch.mock.calls.at(-1).arguments[1].body)

  discussion.question.value = '  '
  await discussion.ask()
  assert.equal(fetch.mock.callCount(), 1)

  discussion.question.value = '  How many members are shared?  '
  const first = discussion.ask()
  const firstRequest = latestRequest()
  assert.equal(fetch.mock.calls[1].arguments[0], '/api/reports/follow-up')
  assert.deepEqual(firstRequest, {
    ...context.value, ...Object.fromEntries(Object.entries(slots).map(([key, slot]) => [key, slot.reference])),
    initial_prompt: initialReport.initial_prompt, report_content: initialReport.content,
    turns: [], question: 'How many members are shared?',
  })
  const firstStream = openStream()
  let clockMs = 1000
  t.mock.method(performance, 'now', () => clockMs)
  firstStream.enqueue(textLine(start))
  firstStream.enqueue(textLine({ type: 'thinking', content: 'Checking ' }))
  firstStream.enqueue(textLine({ type: 'thinking', content: 'overlap.' }))
  await flushStream()
  assert.equal(discussion.pendingTurn.value.thinking, 'Checking overlap.')
  assert.equal(discussion.pendingTurn.value.answer, '')
  clockMs += 300
  firstStream.enqueue(textLine({ type: 'delta', content: '13 members' }))
  await flushStream()
  assert.equal(discussion.answering.value, true)
  assert.equal(discussion.pendingTurn.value.answer, '13 members')
  assert.equal(discussion.pendingTurn.value.thinkingDurationMs, 300)
  clockMs += 700
  assert.deepEqual(discussion.turns.value, [])
  firstStream.enqueue(textLine({ type: 'delta', content: ' form the shared group.' }))
  firstStream.enqueue(textLine({ type: 'done' }))
  firstStream.close()
  await first
  const firstTurn = { question: firstRequest.question, answer: '13 members form the shared group.' }
  const displayedTurn = { ...firstTurn, thinking: 'Checking overlap.', thinkingDurationMs: 300 }
  assert.deepEqual(discussion.turns.value, [displayedTurn])

  workbench.store.stage = 'future'
  workbench.store.futureParameters.threshold = 0.7
  discussion.question.value = '其中还有多少预计留在 S13？'
  const second = discussion.ask()
  const secondRequest = latestRequest()
  assert.deepEqual(secondRequest, { ...firstRequest, turns: [firstTurn], question: '其中还有多少预计留在 S13？' })
  const interrupted = openStream()
  interrupted.enqueue(textLine(start))
  interrupted.enqueue(textLine({ type: 'delta', content: 'Partial reply' }))
  interrupted.enqueue(textLine({ type: 'error', detail: 'Interrupted.' }))
  interrupted.close()
  await second
  assert.equal(discussion.pendingTurn.value.answer, 'Partial reply')
  assert.equal(discussion.replyError.value, 'Interrupted.')
  assert.deepEqual(discussion.turns.value, [displayedTurn])

  const retry = discussion.retry()
  assert.deepEqual(latestRequest(), secondRequest)
  const retryStream = openStream()
  retryStream.enqueue(textLine(start))
  retryStream.enqueue(textLine({ type: 'delta', content: '其中有 8 人。' }))
  retryStream.enqueue(textLine({ type: 'done' }))
  retryStream.close()
  await retry
  assert.deepEqual(discussion.report.value, initialReport)
  assert.deepEqual(discussion.turns.value, [displayedTurn, { question: secondRequest.question, answer: '其中有 8 人。' }])
  assert.equal(discussion.pendingTurn.value, null)
  const fresh = createReport()
  assert.deepEqual(fresh.slots.value, {})
  assert.equal(fresh.ready.value, false)
  assert.equal(fresh.question.value, '')
  assert.equal(fresh.report.value, null)
  assert.deepEqual(fresh.turns.value, [])

  discussion.question.value = '为什么？'
  const stale = discussion.ask()
  const staleStream = openStream()
  staleStream.enqueue(textLine(start))
  context.value = { ...context.value, dataset_version: 'v2' }
  staleStream.enqueue(textLine({ type: 'delta', content: 'Old dataset' }))
  staleStream.close()
  await stale
  assert.equal(discussion.report.value, null)
  assert.deepEqual(discussion.turns.value, [])
  assert.equal(discussion.canAsk.value, false)
})
