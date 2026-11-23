import { computed, onScopeDispose, ref, watch } from 'vue'

import { matchesContext } from '../../api/analysis.js'
import { postJsonLines } from '../../api/client.js'
import { forecastEvidence, reportEvidenceDraft, reportStages, structureEvidence } from '../../domain/reportEvidence.js'

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

  function resetDiscussion() {
    turns.value = []
    pendingTurn.value = null
    question.value = ''
    replyError.value = ''
  }

  function resetReport() {
    completedReport.value = null
    draftReport.value = null
    error.value = ''
    resetDiscussion()
  }
  onScopeDispose(cancel)
  watch(context, (next) => {
    if (!next || matchesContext(next, activeContext)) return
    cancel()
    slots.value = {}
    resetReport()
    activeContext = next
  }, { immediate: true, flush: 'sync' })

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
  const ready = computed(() => Object.keys(reportStages).every(key => slots.value[key]) &&
    matchesContext(context.value, activeContext))
  const canAsk = computed(() => ready.value && !!completedReport.value?.content?.trim())
  const canSend = computed(() => ready.value && !busy.value && (!canAsk.value || !!question.value.trim()))

  function submit() {
    if (!canSubmit.value) return
    cancel()
    slots.value = { ...slots.value, [stage.value]: candidate.value }
    resetReport()
  }

  function ask() {
    if (!canSend.value) return
    const followUp = canAsk.value
    const message = question.value.trim()
    const text = followUp ? message : [reportEvidenceDraft(slots.value), message].filter(Boolean).join('\n\n')
    if (followUp) question.value = ''
    return requestReply({ text, followUp })
  }

  function retry() {
    if (!pendingTurn.value || !replyError.value || !canAsk.value || busy.value) return
    return requestReply({ text: pendingTurn.value.question, followUp: true })
  }

  async function requestReply({ text, followUp }) {
    const controller = new AbortController()
    const body = { ...activeContext }
    for (const key of Object.keys(reportStages)) body[key] = slots.value[key].reference
    activeRequest = controller
    requestKind.value = followUp ? 'follow-up' : 'report'
    if (followUp) {
      const { content, initial_prompt } = completedReport.value
      body.report_content = content
      if (initial_prompt) body.initial_prompt = initial_prompt
      body.turns = turns.value
      body.question = text
      pendingTurn.value = { question: text, answer: '' }
      replyError.value = ''
    } else {
      body.initial_prompt = text
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
        } else if (event.type === 'delta') {
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
