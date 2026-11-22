import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { matchesContext } from '../api/analysis.js'
import {
  LAYOUT_VERSION,
  normalizeReference,
  referenceFingerprint,
} from '../graph/layoutReference.js'

const cache = new Map()

export function useGraphLayout(referenceQuery, currentQuery, context, ready) {
  const layout = shallowRef(null)
  const loading = ref(false)
  const error = ref('')
  const attempt = ref(0)
  let worker = null
  let generation = 0

  function stopWorker() {
    worker?.terminate()
    worker = null
  }
  function cancel() {
    generation++
    stopWorker()
  }

  watch(
    [context, ready, referenceQuery.data, currentQuery.data, attempt],
    async function ([requestContext, enabled, frame, current]) {
      cancel()
      const token = generation
      layout.value = null
      error.value = ''
      loading.value = false
      if (
        !enabled ||
        !matchesContext(frame, requestContext) ||
        !matchesContext(current, requestContext)
      )
        return
      loading.value = true
      try {
        const reference = normalizeReference(frame, current)
        const fingerprint = await referenceFingerprint(reference)
        if (token !== generation) return
        const key = JSON.stringify([
          requestContext.dataset_id,
          requestContext.dataset_version,
          LAYOUT_VERSION,
          fingerprint,
        ])
        if (cache.has(key)) {
          layout.value = cache.get(key)
          loading.value = false
          return
        }
        worker = new Worker(
          new URL('../graph/layout.worker.js', import.meta.url),
          { type: 'module' },
        )
        worker.onmessage = function ({ data }) {
          if (token !== generation || data.key !== key) return
          stopWorker()
          loading.value = false
          if (data.error) {
            error.value = data.error
            return
          }
          const result = { ...data.layout, key, fingerprint }
          cache.set(key, result)
          if (cache.size > 8) cache.delete(cache.keys().next().value)
          layout.value = result
        }
        worker.onerror = function (event) {
          if (token !== generation) return
          error.value = event.message || 'Could not start the graph layout'
          loading.value = false
          stopWorker()
        }
        worker.postMessage({ key, reference })
      } catch (failure) {
        if (token !== generation) return
        stopWorker()
        loading.value = false
        error.value = failure.message
      }
    },
    { immediate: true },
  )

  function retry() {
    if (referenceQuery.isError.value) referenceQuery.refetch()
    else if (currentQuery.isError.value) currentQuery.refetch()
    else attempt.value++
  }
  onBeforeUnmount(cancel)
  return {
    layout,
    loading: computed(function () {
      return loading.value || referenceQuery.isPending.value || currentQuery.isPending.value
    }),
    error: computed(() => error.value || currentQuery.error.value?.message),
    retry,
  }
}
