import { useQuery } from '@tanstack/vue-query'
import { computed } from 'vue'

import { getPredictionModels, matchesContext } from '../../api/analysis.js'
import { matchesCommunityPrediction } from '../../graph/prediction.js'
import { useAnalysisQuery } from './useAnalysisQuery.js'

export function useLinkPrediction(store, { context, ready }) {
  const predictionModels = useQuery({
    queryKey: computed(function () {
      return ['prediction-models', context.value]
    }),
    queryFn: function ({ signal, queryKey }) {
      return getPredictionModels(queryKey[1], { signal })
    },
    enabled: computed(function () {
      return ready.value && store.stage === 'future'
    }),
  })
  const activePredictionModel = computed(function () {
    const response = predictionModels.data.value
    if (!predictionModels.isSuccess.value || !matchesContext(response, context.value)) return null
    return response.models.find(function (model) {
      return model.id === store.predictionModel
    }) || null
  })
  const canPredict = computed(function () {
    return (
      ready.value &&
      store.stage === 'future' &&
      activePredictionModel.value?.status === 'ready'
    )
  })
  const prediction = useAnalysisQuery({
    name: 'future-community',
    path: '/link-prediction/community',
    context,
    version: () => activePredictionModel.value?.model_version,
    runId: () => store.analysisRunId,
    parameters: () => store.futureParameters,
    enabled: canPredict,
  })
  const matchingPrediction = computed(function () {
    if (!store.analysisRunId || !canPredict.value || !prediction.isSuccess.value) return null
    const response = prediction.data.value
    return matchesCommunityPrediction(response, context.value, store.futureParameters, activePredictionModel.value)
      ? response : null
  })
  const predictionRequest = computed(function () {
    if (predictionModels.isFetching.value || predictionModels.isError.value) return predictionModels
    if (store.analysisRunId && canPredict.value &&
      (prediction.isFetching.value || prediction.isError.value)) return prediction
    return null
  })
  const needsModelCheck = computed(function () {
    const model = activePredictionModel.value
    if (!model) return false
    return model.status !== 'ready' ||
      (!!store.analysisRunId && prediction.isSuccess.value && !matchingPrediction.value)
  })
  const predictionMessage = computed(function () {
    if (matchingPrediction.value) return matchingPrediction.value.message
    const model = activePredictionModel.value
    if (model?.status !== 'ready') return model?.message || '当前数据集的预测模型未就绪。'
    if (needsModelCheck.value) return '预测结果的模型版本已变化，请重新检查模型。'
    if (!store.analysisRunId) return '点击「开始预测」查看结果。'
    return '暂无预测社区。'
  })

  function runPrediction() {
    if (!canPredict.value || !store.validFutureParameters || prediction.isFetching.value) return
    store.commitFuture()
  }

  function recheckPredictionModels() {
    store.clearAnalysis()
    predictionModels.refetch()
  }

  return {
    predictionModels, activePredictionModel, prediction, matchingPrediction, predictionMessage,
    predictionRequest, canPredict, needsModelCheck, runPrediction, recheckPredictionModels,
  }
}
