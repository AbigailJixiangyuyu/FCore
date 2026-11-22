import assert from 'node:assert/strict'
import test from 'node:test'
import { effectScope, reactive, ref } from 'vue'
import { useLifecycleReport } from '../src/composables/workbench/useLifecycleReport.js'
import { readReportSession, saveReportSession } from '../src/domain/reportEvidence.js'

const encoder = new TextEncoder()

function setupReport(t) {
  const memory = new Map()
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: {
    getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key),
  } })
  t.after(() => { delete globalThis.sessionStorage })
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
  const scope = effectScope()
  t.after(() => scope.stop())
  const restore = () => scope.run(() => useLifecycleReport(workbench))
  return { context, workbench, restore, fetch, openStream, textLine, flushStream }
}

test('manual generation displays report chunks and ignores chunks from replaced evidence', async t => {
  const { context, workbench, restore, fetch, openStream, textLine, flushStream } = setupReport(t)
  const report = restore()
  report.submit()
  workbench.store.stage = 'present'
  workbench.selected.value = { ...context.value, origin: 'max_core', method: 'pkmc', structure_id: 'M1',
    membership_hash: 'c', snapshot_id: 'S12', parameters: { algorithm: 'pkmc' } }
  report.submit()
  workbench.store.stage = 'future'
  workbench.matchingPrediction.value = { ...context.value, result_fingerprint: 'f', account: 'q', k: 4,
    model: 'zebra', threshold: 0.5, model_version: 'z', target_snapshot: 'S13' }
  workbench.prediction.isPlaceholderData.value = true
  assert.equal(report.canSubmit.value, false)
  workbench.prediction.isPlaceholderData.value = false
  report.submit()
  assert.equal(report.count.value, 3)
  assert.equal(fetch.mock.callCount(), 0)
  const generation = report.generate()
  await report.generate()
  assert.equal(fetch.mock.callCount(), 1)
  const oldStream = openStream()
  oldStream.enqueue(textLine({ type: 'start', model: 'test', node_labels: {} }))
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
  saveReportSession({ ...readReportSession(), report: { sentences: ['Saved report.', 'Second sentence.'], model: 'old' } })
  const restored = restore()
  assert.equal(restored.slots.value.future.reference.threshold, 0.6)
  assert.equal(restored.report.value.content, 'Saved report. Second sentence.')
  assert.equal(restored.canAsk.value, false)
  const nextGeneration = restored.generate()
  const stream = openStream()
  const result = { content: '13 members overlap.\n\nN001（q） is forecast to remain.', model: 'test', node_labels: { N001: 'q' } }
  stream.enqueue(textLine({ type: 'start', model: result.model, node_labels: result.node_labels }))
  const delta = textLine({ type: 'delta', content: result.content })
  const split = delta.indexOf(encoder.encode('（')[0]) + 1
  stream.enqueue(delta.slice(0, split))
  stream.enqueue(delta.slice(split))
  stream.enqueue(textLine({ type: 'done' }))
  stream.close()
  await nextGeneration
  assert.deepEqual(restored.report.value, result)
  assert.deepEqual(readReportSession().report, result)
  assert.equal(restored.canAsk.value, true)
  context.value = { ...context.value, dataset_version: 'v2' }
  assert.equal(restored.count.value, 0)
  assert.equal(fetch.mock.callCount(), 2)
})

test('follow-ups carry completed turns, replace an interrupted reply on retry, and restore on refresh', async t => {
  const { context, workbench, restore, fetch, openStream, textLine, flushStream } = setupReport(t)
  const slots = Object.fromEntries(['history', 'current', 'future'].map(stage => [
    stage, { reference: { ...context.value, stage } },
  ]))
  const initialReport = { model: 'test', content: 'N001 belongs to the overlap of 13 members.', node_labels: { N001: 'q' } }
  saveReportSession({ context: context.value, slots, report: initialReport })
  const discussion = restore()
  const start = { type: 'start', model: initialReport.model, node_labels: initialReport.node_labels }
  const latestRequest = () => JSON.parse(fetch.mock.calls.at(-1).arguments[1].body)

  discussion.question.value = '  '
  await discussion.ask()
  assert.equal(fetch.mock.callCount(), 0)

  discussion.question.value = '  How many members are shared?  '
  const first = discussion.ask()
  const firstRequest = latestRequest()
  assert.equal(fetch.mock.calls[0].arguments[0], '/api/reports/follow-up')
  assert.deepEqual(firstRequest, {
    ...context.value, ...Object.fromEntries(Object.entries(slots).map(([key, slot]) => [key, slot.reference])),
    report_content: initialReport.content, turns: [], question: 'How many members are shared?',
  })
  const firstStream = openStream()
  firstStream.enqueue(textLine(start))
  firstStream.enqueue(textLine({ type: 'delta', content: '13 members' }))
  await flushStream()
  assert.equal(discussion.answering.value, true)
  assert.equal(discussion.pendingTurn.value.answer, '13 members')
  assert.deepEqual(readReportSession().turns, [])
  firstStream.enqueue(textLine({ type: 'delta', content: ' form the shared group.' }))
  firstStream.enqueue(textLine({ type: 'done' }))
  firstStream.close()
  await first
  const firstTurn = { question: firstRequest.question, answer: '13 members form the shared group.' }
  assert.deepEqual(discussion.turns.value, [firstTurn])

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
  assert.deepEqual(readReportSession().turns, [firstTurn])

  const retry = discussion.retry()
  assert.deepEqual(latestRequest(), secondRequest)
  const retryStream = openStream()
  retryStream.enqueue(textLine(start))
  retryStream.enqueue(textLine({ type: 'delta', content: '其中有 8 人。' }))
  retryStream.enqueue(textLine({ type: 'done' }))
  retryStream.close()
  await retry
  const restored = restore()
  assert.deepEqual(restored.report.value, initialReport)
  assert.deepEqual(restored.turns.value, [firstTurn, { question: secondRequest.question, answer: '其中有 8 人。' }])
  assert.equal(restored.pendingTurn.value, null)

  restored.question.value = '为什么？'
  const stale = restored.ask()
  const staleStream = openStream()
  staleStream.enqueue(textLine(start))
  context.value = { ...context.value, dataset_version: 'v2' }
  staleStream.enqueue(textLine({ type: 'delta', content: 'Old dataset' }))
  staleStream.close()
  await stale
  assert.equal(restored.report.value, null)
  assert.deepEqual(restored.turns.value, [])
  assert.equal(restored.canAsk.value, false)
})
