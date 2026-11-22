import { watch } from 'vue'

import { PRESENT_INDEX } from '../domain/timeline.js'
import { useWorkbenchStore } from '../stores/workbench.js'
import { useAnomalyQuery } from './workbench/useAnomalyQuery.js'
import { useEvidenceQuery } from './workbench/useEvidenceQuery.js'
import { useLinkPrediction } from './workbench/useLinkPrediction.js'
import { useSnapshotQueries } from './workbench/useSnapshotQueries.js'
import { useStructureQueries } from './workbench/useStructureQueries.js'

export function useWorkbenchData() {
  const store = useWorkbenchStore()
  const snapshots = useSnapshotQueries(store)
  const { matchHistoryAccount, ...structures } = useStructureQueries(store, snapshots)
  const anomalies = useAnomalyQuery(store, snapshots, selectTime)
  const evidence = useEvidenceQuery(store, snapshots, structures.selected)
  const prediction = useLinkPrediction(store, snapshots)
  watch(() => snapshots.context.value?.dataset_version, store.clearAnalysis, { flush: 'sync' })

  function prepareHistorySelection() {
    if (store.stage === 'history') return
    store.historyAnchor =
      store.stage === 'future' ? store.futureSubmitted.account : store.currentAnchor
  }

  function selectTime(index) {
    if (index < PRESENT_INDEX) prepareHistorySelection()
    store.selectTime(index)
  }

  function selectHistoryRange(start, end) {
    prepareHistorySelection()
    store.selectHistoryRange(start, end)
  }

  function focusAccount(account) {
    store.focusAccount(account)
    if (store.stage === 'history') matchHistoryAccount(account)
  }

  return {
    store, ...snapshots, ...structures, ...anomalies, ...evidence, ...prediction,
    selectTime, selectHistoryRange, focusAccount,
  }
}
