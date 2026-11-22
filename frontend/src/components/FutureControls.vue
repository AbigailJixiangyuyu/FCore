<script setup>
import { useWorkbench } from '../composables/workbenchContext.js'
import QueryAccountField from './QueryAccountField.vue'
import QueryCoreField from './QueryCoreField.vue'
import QueryState from './QueryState.vue'
const {
  store, predictionModels, prediction, canPredict, needsModelCheck, runPrediction, recheckPredictionModels,
} = useWorkbench()

function modelLabel(model) {
  if (model.status === 'ready')
    return model.probability_calibration ? `${model.name} · 历史校准` : model.name
  if (model.status === 'conflict') return `${model.name} · 版本不匹配`
  return `${model.name} · 未就绪`
}
</script>

<template>
  <section class="algorithm-picker">
    <h3 id="prediction-algorithm-heading">选择算法</h3>
    <el-select
      :model-value="store.predictionModel"
      aria-labelledby="prediction-algorithm-heading"
      class="full"
      @update:model-value="store.selectAlgorithm('predictionModel', $event)"
    >
      <el-option
        v-for="model in predictionModels.data.value?.models || []"
        :key="model.id"
        :label="modelLabel(model)"
        :value="model.id"
        :disabled="model.status !== 'ready'"
      />
    </el-select>
    <QueryState :query="predictionModels" />
  </section>
  <form class="control-parameters" @submit.prevent="runPrediction">
    <h3>参数设置</h3>
    <QueryAccountField v-model="store.futureDraft.account" />
    <QueryCoreField
      id="forecast-k-input"
      v-model="store.futureDraft.k"
      :account="store.futureDraftParameters.account"
    />
    <div class="compact-field forecast-threshold">
      <span>连边阈值</span>
      <el-slider
        v-model="store.futureDraft.threshold"
        aria-label="连边阈值"
        size="small"
        :min="0"
        :max="1"
        :step="0.1"
        :show-tooltip="false"
        show-stops
      />
      <output>{{ store.futureDraft.threshold.toFixed(2) }}</output>
    </div>
    <div class="control-actions">
      <el-button @click="store.resetFutureDraft()">重置</el-button>
      <el-button
        native-type="submit"
        type="primary"
        :loading="canPredict && prediction.isFetching.value"
        :disabled="!canPredict || !store.validFutureParameters"
      >开始预测</el-button>
    </div>
  </form>
  <p v-if="store.hasPendingFutureParameters" class="helper query-status pending">
    参数已修改，提交后更新结果。
  </p>
  <el-button v-if="needsModelCheck" plain @click="recheckPredictionModels">重新检查模型</el-button>
</template>
