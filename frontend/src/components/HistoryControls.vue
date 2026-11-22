<script setup>
import { computed } from 'vue'

import { useWorkbench } from '../composables/workbenchContext.js'
import { HISTORY_LENGTH } from '../domain/timeline.js'
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
const paperTitles = {
  periodic: 'Periodic Community Search in Temporal Graphs: Time Series-based Methods',
  durable: 'Effective Durable Community Search in Large Temporal Graph',
  burst: 'Mining Bursting Core in Large Temporal Graphs',
  frequency: 'Efficient Frequency-Aware k-Core Query on Temporal Graphs',
}
</script>

<template>
  <section class="algorithm-picker">
    <h3>Algorithm</h3>
    <el-radio-group
      :model-value="store.pattern"
      class="paper-options"
      aria-label="Historical mining algorithm"
      @update:model-value="store.selectAlgorithm('pattern', $event)"
    >
      <el-radio v-for="(title, pattern) in paperTitles" :key="pattern" :value="pattern">
        {{ title }}
      </el-radio>
    </el-radio-group>
  </section>
  <QueryForm :key="store.pattern" v-slot="{ clearError }" @submit="runHistory">
    <h3>Parameters</h3>
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
        <label for="history-epsilon-input">Similarity ε</label>
        <el-input-number
          id="history-epsilon-input"
          v-model="store.historyDraft.epsilon"
          v-bind="thresholdInput"
          :max="1"
        />
      </div>
      <div v-else-if="store.pattern === 'frequency'" class="compact-field number-field short-number-field">
        <label for="history-t-input" title="A node pair counts once per snapshot">Min. active t</label>
        <el-input-number
          id="history-t-input"
          v-model="store.historyDraft.t"
          :min="1"
          :max="HISTORY_LENGTH"
          :step="1"
          :precision="0"
          :controls="false"
        />
      </div>
    </div>
    <div v-else class="field-row">
      <div class="compact-field number-field short-number-field">
        <label for="history-length-input" title="Minimum window length in snapshots">Span l</label>
        <el-input-number
          id="history-length-input"
          v-model="store.historyDraft.l"
          :min="2"
          :max="HISTORY_LENGTH"
          :step="1"
          :precision="0"
          :controls="false"
        />
      </div>
      <div class="compact-field number-field">
        <label for="history-delta-input" title="Minimum average internal degree">Avg. deg. δ</label>
        <el-input-number
          id="history-delta-input"
          v-model="store.historyDraft.delta"
          v-bind="thresholdInput"
        />
      </div>
    </div>
    <div v-if="store.pattern === 'frequency'" class="compact-field number-field">
      <label for="history-f-input" title="Minimum share of active snapshots in a qualifying window">Min. freq. f</label>
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
