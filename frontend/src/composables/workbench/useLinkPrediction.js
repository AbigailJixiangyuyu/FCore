import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { computed } from 'vue'

import { getPredictionModels, matchesContext } from '../../api/analysis.js'
import { FORECAST_HORIZONS } from '../../domain/timeline.js'
import { matchesCommunityPrediction } from '../../graph/prediction.js'
import { useAnalysisQuery } from './useAnalysisQuery.js'

function usePredictionModel(context, horizon, enabled) {
  const query = useQuery({
    queryKey: computed(function () {
      return ['prediction-models', context.value, horizon()]
    }),
    queryFn: function ({ signal, queryKey: [, requestContext, horizon] }) {
      return getPredictionModels(requestContext, horizon, { signal })
    },
    enabled,
  })
  const model = computed(function () {
    const response = query.data.value
    if (
      !query.isSuccess.value ||
      !matchesContext(response, context.value) ||
      response.horizon !== horizon()
    ) return null
    return response.models.find(function (model) {
      return model.id === 'zebra'
    }) || null
  })
  return { query, model }
}

export function useLinkPrediction(store, { context, ready }) {
  const inFuture = computed(() => ready.value && store.stage === 'future')
  const targets = FORECAST_HORIZONS.map(horizon => ({
    horizon, ...usePredictionModel(context, () => horizon, inFuture),
  }))
  const availableHorizons = computed(() => targets.filter(t => t.model.value?.status === 'ready').map(t => t.horizon))
  const draftTarget = computed(() => targets[store.futureDraft.horizon - 1])
  const predictionModels = computed(() => draftTarget.value.query)
  const draftModel = computed(() => draftTarget.value.model.value)
  const hasActiveRun = computed(() => inFuture.value && !!store.analysisRunId)
  const { query: submittedModels, model: activePredictionModel } = usePredictionModel(
    context, () => store.futureSubmitted.horizon, hasActiveRun,
  )
  const canRunPrediction = computed(() => inFuture.value && draftModel.value?.status === 'ready')
  const canPredict = computed(() => hasActiveRun.value && activePredictionModel.value?.status === 'ready')
  const prediction = useAnalysisQuery({
    name: 'future-community',
    path: '/link-prediction/community',
    context,
    version: () => activePredictionModel.value?.model_version,
    runId: () => store.analysisRunId,
    parameters: () => store.futureParameters,
    enabled: canPredict,
    placeholderData: keepPreviousData,
  })
  const matchingPrediction = computed(function () {
    if (!canPredict.value || !prediction.isSuccess.value) return null
    const response = prediction.data.value
    const parameters = { ...store.futureParameters }
    if (prediction.isPlaceholderData.value) parameters.threshold = response?.threshold
    return matchesCommunityPrediction(response, context.value, parameters, activePredictionModel.value)
      ? response : null
  })
  const predictionRequest = computed(function () {
    if (submittedModels.isFetching.value || submittedModels.isError.value) return submittedModels
    if (canPredict.value &&
      (prediction.isFetching.value || prediction.isError.value)) return prediction
    return null
  })
  const modelChanged = computed(() => canPredict.value && prediction.isSuccess.value &&
    !prediction.isPlaceholderData.value && !matchingPrediction.value)
  const draftUsesSubmittedModel = computed(() => store.futureDraft.horizon === store.futureSubmitted.horizon)
  const needsModelCheck = computed(() => draftModel.value && (
    draftModel.value.status !== 'ready' || (draftUsesSubmittedModel.value && modelChanged.value)
  ))
  const predictionMessage = computed(function () {
    if (matchingPrediction.value) return matchingPrediction.value.message
    const model = activePredictionModel.value
    if (model?.status !== 'ready') return model?.message || 'The prediction model is unavailable for this dataset.'
    if (modelChanged.value) return 'The model version changed. Check the model before running the prediction again.'
    if (!store.analysisRunId) return 'Run a prediction to see the community.'
    return 'No predicted community.'
  })

  function runPrediction() {
    if (!canRunPrediction.value || !store.validFutureParameters || prediction.isFetching.value) return
    store.commitFuture()
  }

  function recheckPredictionModel() {
    if (draftUsesSubmittedModel.value && modelChanged.value) store.clearAnalysis()
    for (const target of targets) target.query.refetch()
  }

  return {
    predictionModels, availableHorizons, draftModel, activePredictionModel, prediction, matchingPrediction, predictionMessage,
    predictionRequest, canRunPrediction, needsModelCheck, runPrediction, recheckPredictionModel,
  }
}
