<script setup>
import { Search } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useWorkbench } from '../composables/workbenchContext.js'
import { currentAlgorithms } from '../domain/algorithms.js'
import { snapshotId } from '../domain/timeline.js'
import AlgorithmPicker from './AlgorithmPicker.vue'
import QueryAccountField from './QueryAccountField.vue'
import QueryCoreField from './QueryCoreField.vue'
import QueryForm from './QueryForm.vue'
import QueryState from './QueryState.vue'

const { store, queryResult, queryResults, runQuery } = useWorkbench()
const startSnapshots = computed(() => Array.from({ length: store.presentIndex + 1 }, (_, i) => snapshotId(i)))
const usesParameters = computed(() => store.currentAlgorithm !== 'pkmc')
const validParameters = computed(function () {
  if (!usesParameters.value) return true
  const { account, k } = store.draftParameters
  return !!account.trim() && Number.isInteger(k) && k >= 0 && k <= 10000
})
</script>

<template>
  <AlgorithmPicker
    :model-value="store.currentAlgorithm"
    :algorithms="currentAlgorithms"
    label="Current Search Model Selection"
    @update:model-value="store.selectAlgorithm('currentAlgorithm', $event)"
  />
  <QueryForm :key="store.currentAlgorithm" v-slot="{ clearError }" @submit="validParameters && runQuery()">
    <template v-if="usesParameters">
      <h3>Parameters Configuration</h3>
      <div v-if="store.currentAlgorithm === 'tccs'" class="compact-field range-field" role="group" aria-labelledby="current-time-window">
        <span id="current-time-window">Time Window</span>
        <el-select v-model="store.draft.start_snapshot_id" aria-label="Start snapshot">
          <el-option v-for="id in startSnapshots" :key="id" :value="id" :label="id" />
        </el-select>
        <span aria-hidden="true">–</span>
        <output aria-label="End snapshot">{{ store.observedUntil }}</output>
      </div>
      <QueryAccountField v-model="store.draft.account" />
      <QueryCoreField
        id="k-input"
        v-model="store.draft.k"
        :account="store.draftParameters.account"
      />
    </template>
    <div class="control-actions">
      <el-button v-if="usesParameters" @click="store.resetQueryDraft(); clearError()">Reset</el-button>
      <el-button
        native-type="submit"
        type="primary"
        :icon="Search"
        :loading="queryResult.isFetching.value"
        :disabled="!validParameters"
      >Run Query</el-button>
    </div>
  </QueryForm>
  <p v-if="store.hasPendingParameters" class="helper query-status pending">
    Run the query to apply your changes.
  </p>
  <QueryState
    v-if="store.analysisRunId"
    :query="queryResult"
    :empty="!queryResults.length"
    empty-text="No matching community"
  />
</template>
