import { computed, watch } from 'vue'

import { matchesContext } from '../../api/analysis.js'
import { currentAlgorithms } from '../workbenchContext.js'
import { useAnalysisQuery } from './useAnalysisQuery.js'

function byMembership(items, membershipHash) {
  return items.find(item => item.membership_hash === membershipHash)
}

function containingAccount(items, account) {
  return items.find(item => item.members.includes(account))
}

export function useStructureQueries(store, { context, ready }) {
  const runId = () => store.analysisRunId
  const queryResult = useAnalysisQuery({
    name: 'core-query',
    path: () => currentAlgorithms[store.currentAlgorithm].path,
    context,
    parameters: () => store.currentParameters,
    runId,
    enabled: computed(() => ready.value && store.stage === 'present'),
  })
  const currentResult = computed(function () {
    if (!ready.value || !runId() || store.stage !== 'present' || !queryResult.isSuccess.value) return null
    const response = queryResult.data.value
    if (!matchesContext(response, context.value)) return null
    if (response.method !== currentAlgorithms[store.currentAlgorithm].method) return null
    const { account, k, start_snapshot_id: start } = store.submitted
    const windowGraph = response.window_graph
    if (start) {
      if (
        windowGraph?.start_snapshot_id !== start ||
        windowGraph.end_snapshot_id !== context.value.observed_until
      ) return null
    } else if (windowGraph) return null
    if (store.currentAlgorithm === 'pkmc') {
      const matches = response.structures.every(function (structure) {
        return structure.origin === 'max_core' &&
          structure.parameters.algorithm === 'pkmc' &&
          structure.snapshot_id === store.currentParameters.snapshot_id
      })
      return matches ? response : null
    }
    if (response.structures.some(function (structure) {
      return structure.parameters.account !== account || structure.parameters.k !== k
    })) return null
    return response
  })
  const queryResults = computed(() => currentResult.value?.structures || [])
  const currentWindow = computed(() => currentResult.value?.window_graph || null)
  const patternResult = useAnalysisQuery({
    name: 'patterns',
    path: '/patterns/mine',
    context,
    parameters: () => store.historyParameters,
    runId,
    enabled: computed(() => ready.value && store.stage === 'history'),
  })
  const patternResponse = computed(function () {
    if (!ready.value || !runId() || store.stage !== 'history' || !patternResult.isSuccess.value) return null
    const response = patternResult.data.value
    if (!matchesContext(response, context.value)) return null
    const { start_snapshot_id: start, end_snapshot_id: end } = store.historyParameters
    const snapshots = response.analysis_snapshot_ids
    return snapshots?.[0] === start && snapshots.at(-1) === end ? response : null
  })
  const historyResults = computed(() => patternResponse.value?.structures || [])
  const selected = computed(function () {
    if (store.stage === 'history') return byMembership(historyResults.value, store.historySelection) || null
    if (store.stage === 'present') return byMembership(queryResults.value, store.querySelection) || null
    return null
  })

  watch(queryResults, function (items) {
    if (byMembership(items, store.querySelection)) return
    if (store.graphLocation?.source === 'member') store.graphLocation = null
    if (items.length) store.selectCurrent(items[0], { explicit: false })
    else store.querySelection = ''
  }, { immediate: true })
  watch(historyResults, function (items) {
    if (byMembership(items, store.historySelection)) return
    const match = containingAccount(items, store.historyAnchor) || items[0]
    store.historySelection = match?.membership_hash || ''
  })
  function matchHistoryAccount(account) {
    const match = containingAccount(historyResults.value, account)
    if (match) store.historySelection = match.membership_hash
  }

  function runQuery() {
    if (queryResult.isFetching.value) return
    store.commitQuery()
  }
  function runHistory() {
    if (patternResult.isFetching.value || !store.validHistoryParameters) return
    store.commitHistory()
  }

  return {
    queryResult, queryResults, currentWindow, patternResult, patternResponse, historyResults,
    selected, matchHistoryAccount, runQuery, runHistory,
  }
}
