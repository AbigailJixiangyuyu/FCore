import { useQueries } from '@tanstack/vue-query'
import { computed } from 'vue'

import { getCapabilities, getDatasets, getHealth } from '../api/system.js'

const endpoints = [
  { key: 'health', label: '服务状态', load: getHealth },
  { key: 'capabilities', label: '功能模块', load: getCapabilities },
  { key: 'datasets', label: '数据集', load: getDatasets },
]

export function useSystemStatus() {
  const queries = useQueries({
    queries: endpoints.map(function (endpoint) {
      return {
        queryKey: ['system', endpoint.key],
        queryFn: function ({ signal }) {
          return endpoint.load({ signal })
        },
        networkMode: 'always',
      }
    }),
  })

  const isChecking = computed(function () {
    return queries.value.some(function (query) {
      return query.isPending || query.isFetching
    })
  })

  const errors = computed(function () {
    return queries.value.flatMap(function (query, index) {
      if (!query.isError) {
        return []
      }

      return [{ endpoint: endpoints[index].label, message: query.error.message }]
    })
  })

  const connectionState = computed(function () {
    if (isChecking.value) {
      return 'checking'
    }
    if (errors.value.length > 0) {
      return 'error'
    }
    return 'connected'
  })

  const datasets = computed(function () {
    return queries.value[2].data?.datasets ?? []
  })

  async function refresh() {
    if (isChecking.value) {
      return
    }

    await Promise.all(queries.value.map(function (query) {
      return query.refetch()
    }))
  }

  function refreshDatasets() {
    return queries.value[2].refetch({ throwOnError: true })
  }

  return { connectionState, datasets, errors, refresh, refreshDatasets }
}
