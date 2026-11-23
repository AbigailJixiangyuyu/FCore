<script setup>
import { useWorkbench } from '../composables/workbenchContext.js'
import { predictionAlgorithms } from '../domain/algorithms.js'
import { FORECAST_HORIZONS, forecastSnapshotId } from '../domain/timeline.js'
import QueryAccountField from './QueryAccountField.vue'
import QueryCoreField from './QueryCoreField.vue'
import QueryForm from './QueryForm.vue'
import QueryState from './QueryState.vue'
const {
  store, predictionModels, prediction, canRunPrediction, needsModelCheck, runPrediction, recheckPredictionModel,
} = useWorkbench()
const { zebra } = predictionAlgorithms
</script>

<template>
  <section class="algorithm-picker">
    <h3>Algorithm</h3>
    <p :title="zebra.paperTitle">
      {{ zebra.name }}<span class="visually-hidden">. {{ zebra.paperTitle }}</span>
    </p>
    <QueryState :query="predictionModels" />
  </section>
  <QueryForm v-slot="{ clearError }" @submit="runPrediction">
    <h3>Parameters</h3>
    <div class="compact-field forecast-target">
      <label for="forecast-target-input">Target snapshot</label>
      <el-select
        id="forecast-target-input"
        v-model="store.futureDraft.horizon"
        aria-label="Target snapshot"
        size="small"
      >
        <el-option
          v-for="horizon in FORECAST_HORIZONS"
          :key="horizon"
          :value="horizon"
          :label="forecastSnapshotId(horizon)"
        />
      </el-select>
    </div>
    <QueryAccountField v-model="store.futureDraft.account" />
    <QueryCoreField
      id="forecast-k-input"
      v-model="store.futureDraft.k"
      :account="store.futureDraftParameters.account"
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
