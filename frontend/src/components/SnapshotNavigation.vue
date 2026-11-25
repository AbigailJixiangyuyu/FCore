<script setup>
import { ArrowDown, Files, Plus, Timer } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useWorkbench } from '../composables/workbenchContext.js'
import { forecastSnapshotId } from '../domain/timeline.js'
import { formatNumber } from '../domain/format.js'
import DatasetImportDialog from './DatasetImportDialog.vue'
import HistoryRangeSelector from './HistoryRangeSelector.vue'
import QueryState from './QueryState.vue'

const { store, system, dataset, catalog, granularity, ready, selectGranularity, selectDataset, selectTime } = useWorkbench()
const importOpen = ref(false)
const appendMode = ref(false)
const datasets = system.datasets
const snapshots = computed(function () {
  return ready.value ? catalog.data.value.snapshots : []
})
const history = computed(() => snapshots.value.filter((meta) => meta.kind === 'history'))
const stageStops = computed(() => snapshots.value.filter((meta) => meta.kind !== 'history'))
const nextSnapshot = computed(() => dataset.value && forecastSnapshotId(dataset.value.observed_until, 1))
const snapshotInterval = computed(function () {
  const minutes = dataset.value?.snapshot_minutes
  const days = minutes / (24 * 60)
  if (days > 0 && Number.isInteger(days)) {
    return `${formatNumber(days)} ${days === 1 ? 'day' : 'days'}`
  }
  if (days > 1) return `≈${formatNumber(days, 2)} days`
  return `${formatNumber(minutes)} min`
})

const granularityOptions = computed(() => {
  const labels = { weekly: 'Weekly (7 days)', monthly: 'Monthly (30 days)' }
  return (dataset.value?.granularities || []).map(key => ({
    key, label: labels[key] ?? `Original (${snapshotInterval.value})`,
  }))
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
        <el-button class="time-setting-button" :icon="Files" aria-label="Datasets Loading">
          Datasets Loading<ArrowDown class="time-setting-caret" aria-hidden="true" />
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
      <el-dropdown trigger="click" placement="bottom-start" @command="selectGranularity">
        <el-button class="time-setting-button" :icon="Timer" :disabled="!dataset" :title="granularityOptions.find(option => option.key === granularity)?.label">
          Temporal Granularity<ArrowDown class="time-setting-caret" aria-hidden="true" />
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="option in granularityOptions" :key="option.key" :command="option.key"
              :aria-current="option.key === granularity">
              {{ option.label }} <span v-if="option.key === granularity" class="dataset-current">Selected</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button class="time-setting-button" :icon="Plus" :disabled="!ready" @click="appendMode = true; importOpen = true">
        Data Updates
      </el-button>
      <DatasetImportDialog v-model="importOpen" :append="appendMode" :next-snapshot="nextSnapshot" />
    </div>
    <QueryState v-if="granularity && !snapshots.length" :query="catalog" />
    <div v-else-if="snapshots.length" class="time-axis">
      <HistoryRangeSelector v-if="history.length" :key="catalog.data.value.dataset_version" :snapshots="history" />
      <span v-else class="helper">No historical snapshots at this granularity.</span>
      <button
        v-for="meta in stageStops"
        :key="meta.snapshot_id"
        type="button"
        class="time-stage"
        :class="`time-stage--${meta.kind}`"
        :title="`${meta.starts_at} – ${meta.ends_at}`"
        :aria-pressed="meta.index === store.timeIndex"
        @click="selectTime(meta.index)"
      >
        <span>{{ meta.kind === 'present' ? 'Current' : 'Future' }}</span>
        <strong>{{ meta.kind === 'future' ? '…' : meta.snapshot_id }}</strong>
      </button>
    </div>
  </section>
</template>
