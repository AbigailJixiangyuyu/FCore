<script setup>
import { computed } from 'vue'
import { currentAlgorithms, useWorkbench } from '../composables/workbenchContext.js'
import { PRESENT_INDEX, PRESENT_SNAPSHOT_ID, snapshotId } from '../domain/timeline.js'
import QueryAccountField from './QueryAccountField.vue'
import QueryCoreField from './QueryCoreField.vue'
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
    <h3>选择算法</h3>
    <el-radio-group
      :model-value="store.currentAlgorithm"
      class="paper-options"
      aria-label="当前搜索算法"
      @update:model-value="store.selectAlgorithm('currentAlgorithm', $event)"
    >
      <el-radio v-for="(algorithm, id) in currentAlgorithms" :key="id" :value="id">
        {{ algorithm.paperTitle }}
      </el-radio>
    </el-radio-group>
  </section>
  <form @submit.prevent="validParameters && runQuery()" class="control-parameters">
    <template v-if="usesParameters">
      <h3>参数设置</h3>
      <div v-if="store.currentAlgorithm === 'tccs'" class="compact-field range-field">
        <span>时间范围</span>
        <el-select v-model="store.draft.start_snapshot_id" aria-label="起始快照 Start">
          <el-option v-for="id in startSnapshots" :key="id" :value="id" :label="id" />
        </el-select>
        <span aria-hidden="true">至</span>
        <output aria-label="结束快照 End">{{ PRESENT_SNAPSHOT_ID }}</output>
      </div>
      <QueryAccountField v-model="store.draft.account" />
      <QueryCoreField
        id="k-input"
        v-model="store.draft.k"
        :account="store.draftParameters.account"
      />
    </template>
    <div class="control-actions">
      <el-button v-if="usesParameters" @click="store.resetQueryDraft()">重置</el-button>
      <el-button
        native-type="submit"
        type="primary"
        :loading="queryResult.isFetching.value"
        :disabled="!validParameters"
      >开始查询</el-button>
    </div>
  </form>
  <p v-if="store.hasPendingParameters" class="helper query-status pending">
    参数已修改，提交后更新结果。
  </p>
  <QueryState
    v-if="store.analysisRunId"
    :query="queryResult"
    :empty="!queryResults.length"
    empty-text="当前条件没有匹配结构"
  />
</template>
