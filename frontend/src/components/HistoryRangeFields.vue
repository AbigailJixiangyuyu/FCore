<script setup>
import { useWorkbench } from '../composables/workbenchContext.js'
import { computed } from 'vue'
import { snapshotIndex, snapshotId } from '../domain/timeline.js'

const { store } = useWorkbench()
const snapshots = computed(() => Array.from({ length: store.presentIndex }, (_, i) => snapshotId(i)))
</script>

<template>
  <div class="compact-field range-field" role="group" aria-labelledby="history-time-window">
    <span id="history-time-window">Time Window</span>
    <el-select
      v-model="store.historyDraft.start_snapshot_id"
      aria-label="Start snapshot"
    >
      <el-option
        v-for="snapshot in snapshots"
        :key="snapshot"
        :value="snapshot"
        :label="snapshot"
        :disabled="snapshotIndex(snapshot) > snapshotIndex(store.historyDraft.end_snapshot_id)"
      />
    </el-select>
    <span aria-hidden="true">–</span>
    <el-select
      v-model="store.historyDraft.end_snapshot_id"
      aria-label="End snapshot"
    >
      <el-option
        v-for="snapshot in snapshots"
        :key="snapshot"
        :value="snapshot"
        :label="snapshot"
        :disabled="snapshotIndex(snapshot) < snapshotIndex(store.historyDraft.start_snapshot_id)"
      />
    </el-select>
  </div>
</template>
