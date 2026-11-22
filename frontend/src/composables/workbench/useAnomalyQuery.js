import { computed, watch } from 'vue'

import { matchesContext } from '../../api/analysis.js'
import { PRESENT_INDEX } from '../../domain/timeline.js'
import { useAnalysisQuery } from './useAnalysisQuery.js'

export function useAnomalyQuery(store, { connected, context, ready }, selectTime) {
  const anomalyQuery = useAnalysisQuery({
    name: 'anomaly-accounts',
    path: '/anomalies/discover',
    context,
    version: 'slade-v1',
    // 05 needs community-wide scores. The ranking views still show ten rows.
    parameters: () => ({ snapshot_id: context.value?.observed_until, top_r: null }),
    enabled: ready,
  })
  const anomalyResponse = computed(function () {
    const response = anomalyQuery.data.value
    return connected.value && anomalyQuery.isSuccess.value &&
      !anomalyQuery.isFetching.value && matchesContext(response, context.value)
      ? response : null
  })
  const anomalyResults = computed(() => anomalyResponse.value?.accounts.slice(0, 10) || [])

  function selectAnomaly(account) {
    if (store.stage !== 'present') selectTime(PRESENT_INDEX)
    store.graphLocation = { accountId: account.account_id, source: 'anomaly' }
  }
  watch(
    function () {
      return anomalyQuery.data.value
    },
    function (response, previous) {
      if (!response || !store.anomalyAccount) return
      if (
        response.model_version !== previous?.model_version ||
        !response.accounts.slice(0, 10).some(function (item) {
          return item.account_id === store.anomalyAccount
        })
      )
        store.graphLocation = null
    },
  )

  return { anomalyQuery, anomalyResponse, anomalyResults, selectAnomaly }
}
