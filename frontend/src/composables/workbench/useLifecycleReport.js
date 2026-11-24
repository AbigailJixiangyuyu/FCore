import { computed, onScopeDispose, ref, watch } from 'vue'

import { matchesContext } from '../../api/analysis.js'
import { postJsonLines } from '../../api/client.js'
import { readPaperReport, writePaperReport } from '../../domain/paperReport.js'
import { forecastEvidence, structureEvidence } from '../../domain/reportEvidence.js'

export function useLifecycleReport(workbench) {
  const { context, store, selected, patternResult, queryResult, anomalyQuery, anomalyResponse, prediction, matchingPrediction } = workbench
  const stage = computed(() => store.stage === 'present' ? 'current' : store.stage)
  const slots = ref({})
  const completedReport = ref(null)
  const draftReport = ref(null)
  const report = computed(() => draftReport.value ?? completedReport.value)
  const turns = ref([])
  const pendingTurn = ref(null)
  const question = ref('')
  const error = ref('')
  const replyError = ref('')
  const requestKind = ref(null)
  const generating = computed(() => requestKind.value === 'report')
  const answering = computed(() => requestKind.value === 'follow-up')
  const busy = computed(() => requestKind.value !== null)
  let activeRequest = null
  let activeContext = null

  function cancel() {
    activeRequest?.abort()
    activeRequest = null
    requestKind.value = null
  }

  function resetDiscussion(draft = '') {
    turns.value = []
    pendingTurn.value = null
    question.value = draft
    replyError.value = ''
  }

  function resetReport(draft = '') {
    completedReport.value = null
    draftReport.value = null
    error.value = ''
    resetDiscussion(draft)
  }
  onScopeDispose(cancel)
  const paperView = computed(() => workbench.viewLayout?.value === 'paper')
  watch([context, paperView], ([next, paper], previous) => {
    const changed = !matchesContext(next, activeContext)
    if (changed) {
      cancel()
      slots.value = {}
      resetReport()
      activeContext = next
    }
    if (!paper || !next || (!changed && previous?.[1])) return
    const saved = readPaperReport(next)
    if (saved) {
      cancel()
      resetReport(saved.question)
      slots.value = saved.slots
      completedReport.value = saved.report
      turns.value = saved.turns
    }
  }, { immediate: true, flush: 'sync' })

  // Save completed replies atomically. A follow-up interrupted by a reload returns to the input.
  watch([paperView, slots, completedReport, turns, question, () => pendingTurn.value?.question], () => {
    if (paperView.value && activeContext) {
      writePaperReport(activeContext, {
        slots: slots.value, report: completedReport.value, turns: turns.value,
        question: question.value || pendingTurn.value?.question || '',
      })
    }
  })

  const candidate = computed(() => {
    if (!context.value || !store.analysisRunId) return null
    if (stage.value === 'future') {
      if (prediction.isFetching.value || prediction.isPlaceholderData.value) return null
      return forecastEvidence(context.value, matchingPrediction.value, store.futureParameters)
    }
    const query = stage.value === 'history' ? patternResult : queryResult
    if (!selected.value || !query.isSuccess.value || query.isFetching.value) return null
    if (stage.value === 'current' && !anomalyResponse.value && !anomalyQuery.isError.value) return null
    return structureEvidence(context.value, selected.value, anomalyResponse.value?.model_version)
  })
  const canSubmit = computed(() => !!candidate.value &&
    JSON.stringify(slots.value[stage.value]?.reference) !== JSON.stringify(candidate.value.reference))
  const ready = computed(() => Object.keys(slots.value).length > 0 &&
    matchesContext(context.value, activeContext))
  const canAsk = computed(() => ready.value && !!completedReport.value?.content?.trim())
  const canSend = computed(() => ready.value && !busy.value && (!canAsk.value || !!question.value.trim()))

  function submit() {
    if (!canSubmit.value) return
    cancel()
    slots.value = { ...slots.value, [stage.value]: candidate.value }
    resetReport(report.value ? '' : question.value)
  }

  function ask() {
    if (!canSend.value) return
    const followUp = canAsk.value
    const text = question.value.trim()
    if (followUp) question.value = ''
    return requestReply({ text, followUp })
  }

  function retry() {
    if (!pendingTurn.value || !replyError.value || !canAsk.value || busy.value) return
    return requestReply({ text: pendingTurn.value.question, followUp: true })
  }

  async function requestReply({ text, followUp }) {
    const controller = new AbortController()
    let thinkingStartedAt
    const body = { ...activeContext }
    for (const [key, slot] of Object.entries(slots.value)) body[key] = slot.reference
    activeRequest = controller
    requestKind.value = followUp ? 'follow-up' : 'report'
    if (followUp) {
      const { content, initial_prompt } = completedReport.value
      body.report_content = content
      if (initial_prompt) body.initial_prompt = initial_prompt
      body.turns = turns.value.map(({ question, answer }) => ({ question, answer }))
      body.question = text
      pendingTurn.value = { question: text, answer: '' }
      replyError.value = ''
    } else {
      if (text) body.initial_prompt = text
      error.value = ''
      draftReport.value = { content: '', initial_prompt: text }
    }
    try {
      const path = followUp ? '/reports/follow-up' : '/reports/generate'
      for await (const event of postJsonLines(path, body, { signal: controller.signal })) {
        if (activeRequest !== controller) return
        if (event.type === 'start') {
          if (!followUp) {
            draftReport.value.model = event.model
            draftReport.value.node_labels = event.node_labels
          }
        } else if (event.type === 'thinking') {
          const reply = followUp ? pendingTurn.value : draftReport.value
          thinkingStartedAt ??= performance.now()
          reply.thinking = (reply.thinking ?? '') + event.content
        } else if (event.type === 'delta') {
          if (thinkingStartedAt !== undefined && event.content.trim()) {
            const reply = followUp ? pendingTurn.value : draftReport.value
            reply.thinkingDurationMs ??= performance.now() - thinkingStartedAt
          }
          if (followUp) pendingTurn.value.answer += event.content
          else draftReport.value.content += event.content
        } else if (event.type === 'error') {
          throw new Error(event.detail)
        } else if (event.type === 'done') {
          if (followUp) {
            turns.value = [...turns.value, { ...pendingTurn.value }]
            pendingTurn.value = null
          } else {
            completedReport.value = draftReport.value
            draftReport.value = null
            resetDiscussion()
          }
          return
        }
      }
      throw new Error('The report stream was interrupted. Try again.')
    } catch (err) {
      if (activeRequest === controller) {
        if (followUp) {
          replyError.value = err.message
        } else {
          if (completedReport.value) draftReport.value = null
          error.value = err.message
        }
      }
    } finally {
      if (activeRequest === controller) {
        activeRequest = null
        requestKind.value = null
      }
    }
  }
  return {
    stage, slots, ready, canSubmit, submit, generating, report, error,
    busy, canAsk, canSend, answering, question, ask, retry, turns, pendingTurn, replyError,
  }
}
