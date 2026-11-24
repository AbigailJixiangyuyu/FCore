<script setup>
import { Search } from '@element-plus/icons-vue'
import { computed } from 'vue'

import { useWorkbench } from '../composables/workbenchContext.js'
import { historyAlgorithms } from '../domain/algorithms.js'
import AlgorithmPicker from './AlgorithmPicker.vue'
import HistoryRangeFields from './HistoryRangeFields.vue'
import QueryAccountField from './QueryAccountField.vue'
import QueryForm from './QueryForm.vue'
import QueryState from './QueryState.vue'
const { store, patternResult, patternResponse, historyResults, runHistory } = useWorkbench()
const thresholdInput = { min: 0, step: 0.01, precision: 2, controls: false }
const requiredSnapshots = computed(function () {
  if (store.pattern === 'burst') return store.historyDraft.l
  if (store.pattern === 'frequency') return store.historyDraft.t
  return 0
})
</script>

<template>
  <AlgorithmPicker
    class="history-models"
    :model-value="store.pattern"
    :algorithms="historyAlgorithms"
    label="Historical Mining Model Selection"
    @update:model-value="store.selectAlgorithm('pattern', $event)"
  />
  <QueryForm :key="store.pattern" v-slot="{ clearError }" @submit="runHistory">
    <h3>Parameters Configuration</h3>
    <HistoryRangeFields />
    <QueryAccountField
      v-if="store.historyUsesAccount"
      v-model="store.historyDraft.account"
    />
    <div v-if="store.pattern !== 'burst'" class="field-row">
      <div class="compact-field number-field">
        <label for="history-k-input">Core k</label>
        <el-input-number
          id="history-k-input"
          v-model="store.historyDraft.k"
          :min="1"
          :step="1"
          :precision="0"
          :controls="false"
        />
      </div>
      <div v-if="store.pattern === 'periodic'" class="compact-field number-field">
        <label for="history-epsilon-input" title="Minimum Jaccard similarity between periods">Similarity ε</label>
        <el-input-number
          id="history-epsilon-input"
          v-model="store.historyDraft.epsilon"
          v-bind="thresholdInput"
          :max="1"
        />
      </div>
      <div v-else-if="store.pattern === 'frequency'" class="compact-field number-field short-number-field">
        <label for="history-t-input" title="Minimum active snapshots for a temporal edge">Min. active t</label>
        <el-input-number
          id="history-t-input"
          v-model="store.historyDraft.t"
          :min="1"
          :max="store.presentIndex"
          :step="1"
          :precision="0"
          :controls="false"
        />
      </div>
    </div>
    <div v-else class="field-row">
      <div class="compact-field number-field short-number-field">
        <label for="history-length-input" title="Minimum segment length in snapshots">Min. length ℓ</label>
        <el-input-number
          id="history-length-input"
          v-model="store.historyDraft.l"
          :min="2"
          :max="store.presentIndex"
          :step="1"
          :precision="0"
          :controls="false"
        />
      </div>
      <div class="compact-field number-field">
        <label for="history-delta-input" title="Threshold for maximum ℓ-segment density">Threshold δ</label>
        <el-input-number
          id="history-delta-input"
          v-model="store.historyDraft.delta"
          v-bind="thresholdInput"
        />
      </div>
    </div>
    <div v-if="store.pattern === 'frequency'" class="compact-field number-field">
      <label for="history-f-input" title="Minimum t-frequency for an edge to qualify">t-Frequency f</label>
      <el-input-number
        id="history-f-input"
        v-model="store.historyDraft.f"
        v-bind="thresholdInput"
        :max="1"
      />
    </div>
    <p v-if="requiredSnapshots > store.historySearchLength" class="helper query-status">
      At least {{ requiredSnapshots }} snapshots required. The selected range has {{ store.historySearchLength }}.
    </p>
    <div class="control-actions">
      <el-button @click="store.resetHistoryDraft(); clearError()">Reset</el-button>
      <el-button
        native-type="submit"
        type="primary"
        :icon="Search"
        :loading="patternResult.isFetching.value"
        :disabled="!store.validHistoryParameters"
      >Run Query</el-button>
    </div>
  </QueryForm>
  <p v-if="store.hasPendingHistoryParameters" class="helper query-status pending">
    Run the query to apply your changes.
  </p>
  <QueryState
    v-if="store.analysisRunId"
    :query="patternResult"
    :empty="!historyResults.length"
    :empty-text="patternResponse?.message || 'No matching community'"
  />
</template>
