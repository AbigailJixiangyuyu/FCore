<script setup>
import { Search } from '@element-plus/icons-vue'
import { useQuery } from '@tanstack/vue-query'
import { computed, watchEffect } from 'vue'
import { getWindowCoreness, matchesContext } from '../api/analysis.js'
import { useWorkbench } from '../composables/workbenchContext.js'
import { currentAlgorithms } from '../domain/algorithms.js'
import { snapshotId } from '../domain/timeline.js'
import AlgorithmPicker from './AlgorithmPicker.vue'
import QueryAccountField from './QueryAccountField.vue'
import QueryCoreField from './QueryCoreField.vue'
import QueryForm from './QueryForm.vue'
import QueryState from './QueryState.vue'

const { store, snapshot, context, ready, queryResult, queryResults, runQuery } = useWorkbench()
const startSnapshots = computed(() => Array.from({ length: store.presentIndex + 1 }, (_, i) => snapshotId(i)))
const usesParameters = computed(() => store.currentAlgorithm !== 'pkmc')
const start = computed(() => store.draft.start_snapshot_id ?? store.observedUntil)
const spansSnapshots = computed(() => start.value !== store.observedUntil)
const windowQuery = useQuery({
  queryKey: computed(() => ['window-coreness', context.value, start.value]),
  queryFn: ({ queryKey: [, scope, first], signal }) => getWindowCoreness(scope, first, { signal }),
  enabled: computed(() => ready.value && spansSnapshots.value),
  staleTime: Infinity,
})
const coreNumbers = computed(() => {
  if (!spansSnapshots.value) return snapshot.value?.core_numbers
  const result = windowQuery.data.value
  if (ready.value && matchesContext(result, context.value) && result.start_snapshot_id === start.value)
    return result.core_numbers
})

function selectWindow(first) {
  if (first === start.value) return
  store.draft.start_snapshot_id = first
  store.draft.k = null // Await this window's coreness before offering to run the query.
}

watchEffect(() => {
  if (store.currentAlgorithm !== 'tccs' || store.draft.k !== null) return
  const account = store.draftParameters.account
  if (coreNumbers.value && Object.hasOwn(coreNumbers.value, account)) {
    const k = coreNumbers.value[account]
    if (k <= 10000) store.draft.k = k
  }
})
const validParameters = computed(function () {
  if (!usesParameters.value) return true
  const { account, k } = store.draftParameters
  return !!account.trim() && Number.isInteger(k) && k >= 0 && k <= 10000
})
</script>

<template>
  <AlgorithmPicker
    :model-value="store.currentAlgorithm"
    :disabled="!ready"
    :algorithms="currentAlgorithms"
    label="Current Search Model Selection"
    @update:model-value="store.selectAlgorithm('currentAlgorithm', $event)"
  />
  <QueryForm :key="store.currentAlgorithm" v-slot="{ clearError }" @submit="ready && validParameters && runQuery()">
    <template v-if="usesParameters">
      <h3>Parameters Configuration</h3>
      <div v-if="store.currentAlgorithm === 'tccs'" class="compact-field range-field" role="group" aria-labelledby="current-time-window">
        <span id="current-time-window">Time Window</span>
        <el-select :model-value="ready ? start : undefined" :disabled="!ready" placeholder=" " aria-label="Start snapshot" @update:model-value="selectWindow">
          <el-option v-for="id in startSnapshots" :key="id" :value="id" :label="id" />
        </el-select>
        <span aria-hidden="true">–</span>
        <output aria-label="End snapshot">{{ ready ? store.observedUntil : '' }}</output>
      </div>
      <QueryAccountField :model-value="ready ? store.draft.account : ''" :disabled="!ready" @update:model-value="store.draft.account = $event" />
      <QueryCoreField
        id="k-input"
        :model-value="ready ? store.draft.k : undefined"
        :disabled="!ready"
        @update:model-value="store.draft.k = $event ?? undefined"
        :account="store.draftParameters.account"
        :core-numbers="coreNumbers"
      />
      <QueryState v-if="spansSnapshots && windowQuery.isError.value" :query="windowQuery" />
    </template>
    <div class="control-actions">
      <el-button v-if="usesParameters" :disabled="!ready" @click="store.resetQueryDraft(); clearError()">Reset</el-button>
      <el-button
        native-type="submit"
        type="primary"
        :icon="Search"
        :loading="queryResult.isFetching.value"
        :disabled="!ready || !validParameters"
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
