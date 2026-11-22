<script setup>
import { useWorkbench } from '../composables/workbenchContext.js'
import { HISTORY_LENGTH, snapshotId } from '../domain/timeline.js'

const { store } = useWorkbench()
const snapshots = Array.from({ length: HISTORY_LENGTH }, function (_, index) {
  return snapshotId(index)
})
</script>

<template>
  <div class="compact-field range-field">
    <span>范围</span>
    <el-select
      v-model="store.historyDraft.start_snapshot_id"
      aria-label="挖掘起始快照"
    >
      <el-option
        v-for="snapshot in snapshots"
        :key="snapshot"
        :value="snapshot"
        :label="snapshot"
        :disabled="snapshot > store.historyDraft.end_snapshot_id"
      />
    </el-select>
    <span aria-hidden="true">至</span>
    <el-select
      v-model="store.historyDraft.end_snapshot_id"
      aria-label="挖掘结束快照"
    >
      <el-option
        v-for="snapshot in snapshots"
        :key="snapshot"
        :value="snapshot"
        :label="snapshot"
        :disabled="snapshot < store.historyDraft.start_snapshot_id"
      />
    </el-select>
  </div>
</template>
