<script setup>
import { TrendCharts } from '@element-plus/icons-vue'
import { useWorkbench } from '../composables/workbenchContext.js'
import { predictionAlgorithms } from '../domain/algorithms.js'
import { forecastSnapshotId } from '../domain/timeline.js'
import QueryAccountField from './QueryAccountField.vue'
import QueryCoreField from './QueryCoreField.vue'
import QueryForm from './QueryForm.vue'
import QueryState from './QueryState.vue'
const {
  store, snapshot, predictionModels, availableHorizons, draftModel, prediction, canRunPrediction, needsModelCheck, runPrediction, recheckPredictionModel,
} = useWorkbench()
const { zebra } = predictionAlgorithms
</script>

<template>
  <section class="algorithm-picker" aria-labelledby="forecast-model-selection">
    <h3 id="forecast-model-selection">Model Selection</h3>
    <p :title="zebra.paperTitle">
      {{ zebra.topic }} ({{ zebra.name }})<span class="visually-hidden">. {{ zebra.paperTitle }}</span>
    </p>
    <QueryState :query="predictionModels" />
    <p v-if="draftModel && draftModel.status !== 'ready'" class="helper">{{ draftModel.message }}</p>
  </section>
  <QueryForm v-slot="{ clearError }" @submit="runPrediction">
    <h3>Parameters Configuration</h3>
    <div class="compact-field forecast-target">
      <label for="forecast-target-input">Target snapshot</label>
      <el-select
        id="forecast-target-input"
        :model-value="availableHorizons.includes(store.futureDraft.horizon) ? store.futureDraft.horizon : undefined"
        :disabled="!availableHorizons.length"
        placeholder="Unavailable"
        @update:model-value="store.futureDraft.horizon = $event"
        aria-label="Target snapshot"
        size="small"
      >
        <el-option
          v-for="horizon in availableHorizons"
          :key="horizon"
          :value="horizon"
          :label="forecastSnapshotId(store.observedUntil, horizon)"
        />
      </el-select>
    </div>
    <QueryAccountField v-model="store.futureDraft.account" />
    <QueryCoreField
      id="forecast-k-input"
      v-model="store.futureDraft.k"
      :account="store.futureDraftParameters.account"
      :core-numbers="snapshot?.core_numbers"
    />
    <div class="compact-field forecast-threshold">
      <span>Probability threshold</span>
      <el-slider
        v-model="store.futureDraft.threshold"
        aria-label="Edge probability threshold"
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
      <el-button @click="store.resetFutureDraft(); clearError()">Reset</el-button>
      <el-button
        native-type="submit"
        type="primary"
        :icon="TrendCharts"
        :loading="canRunPrediction && prediction.isFetching.value"
        :disabled="!canRunPrediction || !store.validFutureParameters"
      >Run Prediction</el-button>
    </div>
  </QueryForm>
  <p v-if="store.hasPendingFutureParameters" class="helper query-status pending">
    Run the prediction to apply your changes.
  </p>
  <el-button v-if="needsModelCheck" plain @click="recheckPredictionModel">Check Model</el-button>
</template>
