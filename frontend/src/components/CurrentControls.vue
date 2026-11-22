<script setup>
import { computed } from 'vue'
import { currentAlgorithms, useWorkbench } from '../composables/workbenchContext.js'
import { PRESENT_INDEX, PRESENT_SNAPSHOT_ID, snapshotId } from '../domain/timeline.js'
import QueryAccountField from './QueryAccountField.vue'
import QueryCoreField from './QueryCoreField.vue'
import QueryForm from './QueryForm.vue'
import QueryState from './QueryState.vue'

const { store, queryResult, queryResults, runQuery } = useWorkbench()
const startSnapshots = Array.from({ length: PRESENT_INDEX + 1 }, function (_, index) {
  return snapshotId(index)
})
const usesParameters = computed(() => store.currentAlgorithm !== 'pkmc')
const validParameters = computed(function () {
  if (!usesParameters.value) return true
  const { account, k } = store.draftParameters
  return !!account.trim() && Number.isInteger(k) && k >= 0 && k <= 10000
})
</script>

<template>
  <section class="algorithm-picker">
    <h3>Algorithm</h3>
    <el-radio-group
      :model-value="store.currentAlgorithm"
      class="paper-options"
      aria-label="Current search algorithm"
      @update:model-value="store.selectAlgorithm('currentAlgorithm', $event)"
    >
      <el-radio v-for="(algorithm, id) in currentAlgorithms" :key="id" :value="id">
        {{ algorithm.paperTitle }}
      </el-radio>
    </el-radio-group>
  </section>
  <QueryForm :key="store.currentAlgorithm" v-slot="{ clearError }" @submit="validParameters && runQuery()">
    <template v-if="usesParameters">
      <h3>Parameters</h3>
      <div v-if="store.currentAlgorithm === 'tccs'" class="compact-field range-field">
        <span>Range</span>
        <el-select v-model="store.draft.start_snapshot_id" aria-label="Start snapshot">
          <el-option v-for="id in startSnapshots" :key="id" :value="id" :label="id" />
        </el-select>
        <span aria-hidden="true">–</span>
        <output aria-label="End snapshot">{{ PRESENT_SNAPSHOT_ID }}</output>
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
