import { useQuery } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'

import { getAggregate, getCatalog, getSnapshot, matchesContext } from '../../api/analysis.js'
import { PRESENT_SNAPSHOT_ID } from '../../domain/timeline.js'
import { HISTORY_LAYOUT_RANGE } from '../../graph/layoutReference.js'
import { readReportSession } from '../../domain/reportEvidence.js'
import { DEFAULT_DATASET_ID } from '../../stores/workbench.js'
import { useSystemStatus } from '../useSystemStatus.js'

export function useSnapshotQuery({ context, snapshotId, enabled, staleTime }) {
  return useQuery({
    queryKey: computed(function () {
      return ['snapshot', context.value, toValue(snapshotId)]
    }),
    queryFn: function ({ signal, queryKey: [, requestContext, id] }) {
      return getSnapshot(requestContext, id, { signal })
    },
    enabled,
    staleTime,
  })
}

export function useSnapshotQueries(store) {
  const system = useSystemStatus()
  let restoreDataset = readReportSession()?.context.dataset_id
  function selectDataset(item) {
    if (item.dataset_id !== store.datasetId) store.selectDataset(item.dataset_id, item.query_defaults)
  }

  const connected = computed(function () {
    return system.connectionState.value === 'connected'
  })
  watch(
    system.datasets,
    function (datasets) {
      if (!datasets.length) return
      if (restoreDataset) {
        const previous = datasets.find(item => item.dataset_id === restoreDataset)
        restoreDataset = null
        if (previous) selectDataset(previous)
      }
      if (
        !datasets.some(function (item) {
          return item.dataset_id === store.datasetId
        })
      ) {
        const fallback = datasets.find(function (item) {
          return item.dataset_id === DEFAULT_DATASET_ID
        }) || datasets[0]
        selectDataset(fallback)
      }
    },
    { immediate: true, flush: 'sync' },
  )
  const dataset = computed(function () {
    return system.datasets.value.find(function (item) {
      return item.dataset_id === store.datasetId
    })
  })
  const context = computed(function () {
    if (!dataset.value) return null
    return {
      dataset_id: dataset.value.dataset_id,
      dataset_version: dataset.value.dataset_version,
      observed_until: dataset.value.observed_until,
    }
  })
  const ready = computed(function () {
    return connected.value && !!context.value
  })
  const catalog = useQuery({
    queryKey: computed(function () {
      return ['catalog', context.value]
    }),
    queryFn: function ({ signal, queryKey: [, requestContext] }) {
      return getCatalog(requestContext.dataset_id, { signal })
    },
    enabled: ready,
  })
  const present = useSnapshotQuery({ context, snapshotId: PRESENT_SNAPSHOT_ID, enabled: ready })
  const layoutReference = useQuery({
    queryKey: computed(function () {
      return ['aggregate', context.value, HISTORY_LAYOUT_RANGE]
    }),
    queryFn: function ({ signal, queryKey: [, requestContext, range] }) {
      return getAggregate(requestContext, range, { signal })
    },
    staleTime: Infinity,
    enabled: ready,
  })
  const historical = useQuery({
    queryKey: computed(function () {
      return ['aggregate', context.value, store.historyRange]
    }),
    queryFn: function ({ signal, queryKey: [, requestContext, range] }) {
      return getAggregate(requestContext, range, { signal })
    },
    enabled: computed(function () {
      return ready.value && store.stage === 'history'
    }),
  })

  const snapshotQuery = computed(function () {
    if (store.stage === 'history') return historical
    return present
  })
  const snapshot = computed(function () {
    if (!connected.value) return null
    const query = snapshotQuery.value
    const frame = query.data.value
    if (!query.isSuccess.value || !matchesContext(frame, context.value)) return null
    if (store.stage !== 'history') return frame.snapshot_id === PRESENT_SNAPSHOT_ID ? frame : null
    const { start_snapshot_id, end_snapshot_id } = store.historyRange
    return frame.start_snapshot_id === start_snapshot_id && frame.end_snapshot_id === end_snapshot_id
      ? frame : null
  })

  return {
    system,
    selectDataset,
    connected,
    dataset,
    context,
    ready,
    catalog,
    present,
    snapshotQuery,
    snapshot,
    layoutReference,
  }
}
