import { useQueries, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'

import { getCapabilities, getDatasets, getHealth } from '../api/system.js'

const endpoints = [
  { key: 'health', label: 'Service status', load: getHealth },
  { key: 'capabilities', label: 'Capabilities', load: getCapabilities },
  { key: 'datasets', label: 'Datasets', load: getDatasets },
]

export function useSystemStatus() {
  const client = useQueryClient()
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
    if (queries.value.some(query => query.isPending)) {
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

  async function updateDataset(dataset) {
    const key = ['system', 'datasets']
    await client.cancelQueries({ queryKey: key, exact: true })
    client.setQueryData(key, previous => {
      const items = [...(previous?.datasets ?? [])]
      const index = items.findIndex(item => item.dataset_id === dataset.dataset_id)
      if (index < 0) items.push(dataset)
      else items[index] = dataset
      return { datasets: items }
    })
  }

  return { connectionState, datasets, errors, refresh, updateDataset }
}
