import { useQuery } from '@tanstack/vue-query'
import { computed, toValue } from 'vue'

import { analyze } from '../../api/analysis.js'

// Read the route and payload from the key that started this request.
export function useAnalysisQuery({ name, path, context, parameters, enabled, version, runId }) {
  return useQuery({
    queryKey: computed(function () {
      return [name, toValue(path), context.value, toValue(parameters), toValue(version), toValue(runId)]
    }),
    queryFn: function ({ signal, queryKey: [, requestPath, requestContext, requestParameters] }) {
      return analyze(requestPath, requestContext, requestParameters, { signal })
    },
    enabled: computed(() => toValue(enabled) && (!runId || toValue(runId) != null)),
    staleTime: runId ? Infinity : undefined,
  })
}
