<script setup>
import { computed, provide } from 'vue'

import AnalysisSummaryPanel from '../components/AnalysisSummaryPanel.vue'
import AnomalyInformation from '../components/AnomalyInformation.vue'
import CurrentControls from '../components/CurrentControls.vue'
import FutureControls from '../components/FutureControls.vue'
import GraphPanel from '../components/GraphPanel.vue'
import HistoryControls from '../components/HistoryControls.vue'
import PredictionNavigation from '../components/PredictionNavigation.vue'
import QueryState from '../components/QueryState.vue'
import SnapshotNavigation from '../components/SnapshotNavigation.vue'
import { useWorkbenchData } from '../composables/useWorkbenchData.js'
import { workbenchKey } from '../composables/workbenchContext.js'
import { FUTURE_INDEX, PRESENT_INDEX, PRESENT_SNAPSHOT_ID } from '../domain/timeline.js'

const workbench = useWorkbenchData()
provide(workbenchKey, workbench)
const { store, system, connected, catalog, currentWindow, selectTime } = workbench
const datasets = system.datasets
const stages = [
  { id: 'history', label: 'History' },
  { id: 'present', label: 'Current' },
  { id: 'future', label: 'Future' },
]

function selectStage(stage) {
  if (stage === 'history') selectTime(store.historyEndIndex)
  else selectTime(stage === 'present' ? PRESENT_INDEX : FUTURE_INDEX)
}
const title = computed(function () {
  if (store.stage === 'history') return 'Mine Communities in Historical Snapshots'
  if (store.stage === 'future') return 'Predict a Future Community'
  return 'Explore Current Communities and Anomaly Scores'
})
const timeContext = computed(function () {
  if (store.stage === 'history') return store.historyRangeLabel
  if (store.stage === 'future') return `${PRESENT_SNAPSHOT_ID} → ${store.futureSnapshotId}`
  return currentWindow.value ? store.currentWindowLabel : 'S12'
})
</script>

<template>
  <main class="workbench">
    <template v-if="connected && datasets.length">
      <SnapshotNavigation />
      <div class="page-intro">
        <h1>{{ title }}</h1>
        <span class="count-chip">{{ timeContext }}</span>
      </div>
      <QueryState v-if="catalog.isError.value" :query="catalog" />
      <div class="workspace">
        <aside class="panel control-panel" aria-label="Methods &amp; Parameters">
          <div class="sidebar-heading">
            <span class="panel-number">02</span>
            <h2>Methods &amp; Parameters</h2>
          </div>
          <div class="control-stages">
            <el-radio-group
              :model-value="store.stage"
              class="full-segment"
              aria-label="Analysis stage"
              @update:model-value="selectStage"
            >
              <el-radio-button v-for="stage in stages" :key="stage.id" :value="stage.id">
                {{ stage.label }}
              </el-radio-button>
            </el-radio-group>
          </div>
          <div class="sidebar-content">
            <HistoryControls v-if="store.stage === 'history'" /><CurrentControls
              v-else-if="store.stage === 'present'"
            /><FutureControls v-else />
          </div>
        </aside>
        <GraphPanel />
        <aside class="panel anomaly-panel" aria-label="Anomaly Scores">
          <div class="sidebar-heading">
            <span class="panel-number">04</span>
            <h2>Anomaly Scores</h2>
          </div>
          <div class="sidebar-content">
            <AnomalyInformation />
          </div>
          <PredictionNavigation />
        </aside>
      </div>
      <AnalysisSummaryPanel />
    </template>
    <section v-else class="panel startup-state">
      <el-empty
        :image-size="64"
        :description="
          connected ? 'No datasets available' : 'Analysis service unavailable'
        "
        ><p class="helper">
          {{
            connected
              ? 'Load a local dataset and try again.'
              : 'Start the backend service and reconnect.'
          }}
        </p>
        <p
          v-for="error in system.errors.value"
          :key="error.endpoint"
          class="helper"
        >
          {{ error.endpoint }} — {{ error.message }}
        </p>
        <el-button
          class="startup-retry"
          type="primary"
          :loading="system.connectionState.value === 'checking'"
          @click="system.refresh()"
          >{{ connected ? 'Reload Datasets' : 'Reconnect' }}</el-button
        ></el-empty
      >
    </section>
  </main>
</template>
