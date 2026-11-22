<script setup>
import { computed } from 'vue'

import { useWorkbench } from '../composables/workbenchContext.js'
import { HISTORY_LENGTH } from '../domain/timeline.js'
import HistoryRangeFields from './HistoryRangeFields.vue'
import QueryAccountField from './QueryAccountField.vue'
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
    <h3>选择算法</h3>
    <el-radio-group
      :model-value="store.pattern"
      class="paper-options"
      aria-label="历史挖掘算法"
      @update:model-value="store.selectAlgorithm('pattern', $event)"
    >
      <el-radio v-for="(title, pattern) in paperTitles" :key="pattern" :value="pattern">
        {{ title }}
      </el-radio>
    </el-radio-group>
  </section>
  <form @submit.prevent="runHistory" class="control-parameters">
    <h3>参数设置</h3>
    <HistoryRangeFields />
    <QueryAccountField
      v-if="store.historyUsesAccount"
      v-model="store.historyDraft.account"
    />
    <div v-if="store.pattern !== 'burst'" class="field-row">
      <div class="compact-field number-field">
        <label for="history-k-input">核心阶数 k</label>
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
        <label for="history-epsilon-input">相似度阈值 ε</label>
        <el-input-number
          id="history-epsilon-input"
          v-model="store.historyDraft.epsilon"
          v-bind="thresholdInput"
          :max="1"
        />
      </div>
      <div v-else-if="store.pattern === 'frequency'" class="compact-field number-field short-number-field">
        <label for="history-t-input" title="同一对账户在同一快照中只计一次">最少活跃快照 t</label>
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
        <label for="history-length-input">最小长度 l</label>
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
        <label for="history-delta-input">平均度阈值 δ</label>
        <el-input-number
          id="history-delta-input"
          v-model="store.historyDraft.delta"
          v-bind="thresholdInput"
        />
      </div>
    </div>
    <div v-if="store.pattern === 'frequency'" class="compact-field number-field">
      <label for="history-f-input" title="最密集的合格区间内，活跃快照数占区间快照数的比例">最低频率 f</label>
      <el-input-number
        id="history-f-input"
        v-model="store.historyDraft.f"
        v-bind="thresholdInput"
        :max="1"
      />
    </div>
    <p v-if="requiredSnapshots > store.historySearchLength" class="helper query-status">
      当前范围只有 {{ store.historySearchLength }} 个快照，所设参数至少需要 {{ requiredSnapshots }} 个。
    </p>
    <div class="control-actions">
      <el-button @click="store.resetHistoryDraft()">重置</el-button>
      <el-button
        native-type="submit"
        type="primary"
        :loading="patternResult.isFetching.value"
        :disabled="!store.validHistoryParameters"
      >开始挖掘</el-button>
    </div>
  </form>
  <p v-if="store.hasPendingHistoryParameters" class="helper query-status pending">
    参数已修改，提交后更新结果。
  </p>
  <QueryState
    v-if="store.analysisRunId"
    :query="patternResult"
    :empty="!historyResults.length"
    :empty-text="patternResponse?.message || '当前条件没有匹配模式'"
  />
</template>
