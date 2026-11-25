import { useQuery } from '@tanstack/vue-query'
import { computed, ref, toValue, watch } from 'vue'

import { getAggregate, getCatalog, getObservedAggregate, getSnapshot, matchesContext } from '../../api/analysis.js'
import { snapshotId } from '../../domain/timeline.js'
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

export function useSnapshotQueries(store, layout) {
  const system = useSystemStatus()
  const granularity = ref()
  const paper = computed(() => layout.value === 'paper')
  const preferenceKey = id => 'fcore:paper-granularity:' + id
  function selectGranularity(value) {
    if (!dataset.value?.granularities.includes(value)) return
    granularity.value = value
    if (paper.value) localStorage.setItem(preferenceKey(store.datasetId), value)
  }
  function selectDataset(item) {
    if (item.dataset_id === store.datasetId) return
    store.selectDataset(item)
    if (paper.value) localStorage.setItem('fcore:paper-dataset', item.dataset_id)
  }
  const connected = computed(() => system.connectionState.value === 'connected')
  const dataset = computed(() => system.datasets.value.find(item => item.dataset_id === store.datasetId))
  watch([system.datasets, paper], ([datasets, inPaper]) => {
    if (!inPaper || dataset.value || !datasets.length) return
    const savedId = localStorage.getItem('fcore:paper-dataset')
    selectDataset(datasets.find(item => item.dataset_id === savedId) ??
      datasets.find(item => item.dataset_id === DEFAULT_DATASET_ID) ?? datasets[0])
  }, { immediate: true })
  watch([() => dataset.value?.dataset_id, paper], ([id, inPaper]) => {
    if (!inPaper || !id) {
      granularity.value = undefined
      return
    }
    const saved = localStorage.getItem(preferenceKey(id))
    const choices = dataset.value.granularities
    granularity.value = choices.includes(saved) ? saved : choices[0]
  }, { immediate: true, flush: 'sync' })
  const catalog = useQuery({
    queryKey: computed(() => ['catalog', dataset.value?.dataset_id, dataset.value?.dataset_version, granularity.value]),
    queryFn: ({ signal, queryKey: [, id, , grain] }) => getCatalog(id, { signal }, grain),
    enabled: computed(() => connected.value && !!dataset.value && !!granularity.value),
  })
  const context = computed(() => {
    const view = catalog.data.value
    if (!granularity.value || !view || view.dataset_id !== dataset.value?.dataset_id) return null
    const { dataset_id, dataset_version, observed_until } = view
    return { dataset_id, dataset_version, observed_until }
  })
  watch(() => catalog.data.value?.dataset_version, version => {
    if (version) store.selectDataset(catalog.data.value)
  }, { immediate: true, flush: 'sync' })
  const ready = computed(() => connected.value && !!context.value)
  const present = useSnapshotQuery({ context, snapshotId: () => store.observedUntil, enabled: ready })
  const layoutReference = useQuery({
    queryKey: computed(function () {
      const range = store.presentIndex ? { start_snapshot_id: snapshotId(0), end_snapshot_id: snapshotId(store.presentIndex - 1) } : null
      return ['layout-reference', context.value, range]
    }),
    queryFn: function ({ signal, queryKey: [, requestContext, range] }) {
      if (!range) return getSnapshot(requestContext, requestContext.observed_until, { signal })
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

  const overview = useQuery({
    queryKey: computed(() => ['observed-aggregate', context.value]),
    queryFn: ({ signal, queryKey: [, ctx] }) => getObservedAggregate(ctx, { signal }),
    enabled: computed(() => ready.value && !store.stage),
  })
  const snapshotQuery = computed(function () {
    if (!store.stage) return overview
    if (store.stage === 'history') return historical
    return present
  })
  const snapshot = computed(function () {
    if (!connected.value) return null
    const query = snapshotQuery.value
    const frame = query.data.value
    if (!query.isSuccess.value || !matchesContext(frame, context.value)) return null
    if (!store.stage) return frame
    if (store.stage !== 'history') return frame.snapshot_id === store.observedUntil ? frame : null
    const { start_snapshot_id, end_snapshot_id } = store.historyRange
    return frame.start_snapshot_id === start_snapshot_id && frame.end_snapshot_id === end_snapshot_id
      ? frame : null
  })

  return {
    system,
    selectDataset,
    granularity,
    selectGranularity,
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
