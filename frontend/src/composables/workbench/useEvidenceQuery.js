import { computed } from 'vue'

import { useAnalysisQuery } from './useAnalysisQuery.js'

export function useEvidenceQuery(store, { context, ready }, selected) {
  const metric = computed(function () {
    return store.metric === 'auto' ? 'transaction_count' : store.metric
  })
  const structures = computed(function () {
    const structure = selected.value
    if (!structure || ['frequency', 'temporal_core'].includes(structure.parameters.pattern)) return []
    return [structure]
  })
  const evidenceResult = useAnalysisQuery({
    name: 'evidence',
    path: '/evidence/series',
    context,
    parameters: () => ({
      structures: structures.value,
      metric: metric.value,
    }),
    enabled: computed(() => ready.value && store.stage === 'history' && structures.value.length > 0),
  })

  return { metric, evidenceResult }
}
