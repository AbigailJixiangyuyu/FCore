import { computed } from 'vue'

import { matchesContext } from '../../api/analysis.js'
import { useSnapshotQuery } from './useSnapshotQueries.js'

export function usePeriodicCommunity({ store, context, ready, snapshot, selected }) {
  const periodic = computed(function () {
    if (store.stage !== 'history' || store.pattern !== 'periodic') return null
    const { start_snapshot_id: start, end_snapshot_id: end } = store.historyRange
    const structure = selected.value
    const evidence = structure?.parameters.pattern === 'periodic' ? structure.evidence : null
    const index = evidence?.analysis_snapshot_ids?.indexOf(end)
    const indicator = evidence?.kcore_series?.[index]
    const state = indicator === 0 || indicator === 1 ? indicator : null

    return { start, end, state, k: structure?.parameters.k, outsideSearch: index === -1 }
  })
  const needsEndpoint = computed(function () {
    return periodic.value?.state === 1 && periodic.value.start !== periodic.value.end
  })
  const endpoint = useSnapshotQuery({
    context,
    snapshotId: computed(() => periodic.value?.end),
    enabled: computed(() => ready.value && needsEndpoint.value),
    staleTime: Infinity,
  })
  const communityFrame = computed(function () {
    if (periodic.value?.state !== 1) return null
    const { end } = periodic.value
    if (!needsEndpoint.value) return snapshot.value && { ...snapshot.value, snapshot_id: end }

    const frame = endpoint.data.value
    if (!endpoint.isSuccess.value || !matchesContext(frame, context.value)) return null
    return frame.snapshot_id === end ? frame : null
  })
  const pendingEndpoint = computed(function () {
    return needsEndpoint.value && !communityFrame.value ? endpoint : null
  })

  return { periodic, communityFrame, pendingEndpoint }
}
