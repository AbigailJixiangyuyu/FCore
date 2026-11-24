<script setup>
import { ArrowDown, Files, Plus, Timer } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useWorkbench } from '../composables/workbenchContext.js'
import { formatNumber } from '../domain/format.js'
import DatasetImportDialog from './DatasetImportDialog.vue'
import HistoryRangeSelector from './HistoryRangeSelector.vue'
import QueryState from './QueryState.vue'

const { store, system, dataset, catalog, selectDataset, selectTime } = useWorkbench()
const importOpen = ref(false)
const appendMode = ref(false)
const datasets = system.datasets
const snapshots = computed(function () {
  return catalog.data.value?.snapshots || []
})
const history = computed(() => snapshots.value.filter((meta) => meta.kind === 'history'))
const stageStops = computed(() => snapshots.value.filter((meta) => meta.kind !== 'history'))
const nextSnapshot = computed(() => snapshots.value.find((meta) => meta.kind === 'future'))
const snapshotInterval = computed(function () {
  const minutes = dataset.value?.snapshot_minutes
  const days = minutes / (24 * 60)
  if (days > 0 && Number.isInteger(days)) {
    return `${formatNumber(days)} ${days === 1 ? 'day' : 'days'}`
  }
  return `${formatNumber(minutes)} min`
})

function handleDatasetCommand(command) {
  if (command === 'import') {
    appendMode.value = false
    importOpen.value = true
    return
  }
  selectDataset(command)
}
</script>

<template>
  <section class="panel time-navigation" aria-label="Dataset Setup and Time Window Selection">
    <div class="time-navigation-settings" role="group" aria-label="Dataset Setup">
      <el-dropdown trigger="click" placement="bottom-start" @command="handleDatasetCommand">
        <el-button class="time-setting-button" :icon="Files" :title="dataset?.name">
          Dataset Loading<ArrowDown class="time-setting-caret" aria-hidden="true" />
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="item in datasets"
              :key="item.dataset_id"
              :command="item"
              :aria-current="item.dataset_id === store.datasetId ? 'true' : undefined"
            >
              {{ item.name }}
              <span v-if="item.dataset_id === store.datasetId" class="dataset-current">Selected</span>
            </el-dropdown-item>
            <el-dropdown-item command="import" :divided="datasets.length > 0">Import Dataset…</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-popover trigger="click" placement="bottom-start" :width="190">
        <template #reference>
          <el-button class="time-setting-button" :icon="Timer" :disabled="!dataset">
            Temporal Granularity<ArrowDown class="time-setting-caret" aria-hidden="true" />
          </el-button>
        </template>
        <div class="snapshot-granularity">
          <span>Snapshot interval</span>
          <strong>{{ snapshotInterval }} per snapshot</strong>
        </div>
      </el-popover>
      <el-button class="time-setting-button" :icon="Plus" :disabled="!nextSnapshot" @click="appendMode = true; importOpen = true">
        Data Updates
      </el-button>
      <DatasetImportDialog v-model="importOpen" :append="appendMode" :next-snapshot="nextSnapshot?.snapshot_id" />
    </div>
    <QueryState v-if="dataset && !snapshots.length" :query="catalog" />
    <div v-else-if="snapshots.length" class="time-axis">
      <HistoryRangeSelector :key="store.datasetId" :snapshots="history" />
      <button
        v-for="meta in stageStops"
        :key="meta.snapshot_id"
        type="button"
        class="time-stage"
        :class="`time-stage--${meta.kind}`"
        :aria-pressed="meta.index === store.timeIndex"
        @click="selectTime(meta.index)"
      >
        <span>{{ meta.kind === 'present' ? 'Current' : 'Future' }}</span>
        <strong>{{ meta.kind === 'future' ? '…' : meta.snapshot_id }}</strong>
      </button>
    </div>
  </section>
</template>
