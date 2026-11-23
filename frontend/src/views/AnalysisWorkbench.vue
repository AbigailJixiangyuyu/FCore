<script setup>
import { provide } from 'vue'

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
import { FUTURE_INDEX, PRESENT_INDEX } from '../domain/timeline.js'

const workbench = useWorkbenchData()
provide(workbenchKey, workbench)
const { store, system, connected, catalog, selectTime } = workbench
const datasets = system.datasets
const stages = [
  { id: 'history', label: 'History', title: 'Historical Community Mining' },
  { id: 'present', label: 'Current', title: 'Current Community Search' },
  { id: 'future', label: 'Future', title: 'Future Community Prediction' },
]

function selectStage(stage) {
  if (stage === 'history') selectTime(store.historyEndIndex)
  else selectTime(stage === 'present' ? PRESENT_INDEX : FUTURE_INDEX)
}
</script>

<template>
  <main class="workbench">
    <template v-if="connected && datasets.length">
      <SnapshotNavigation />
      <QueryState v-if="catalog.isError.value" :query="catalog" />
      <div class="workspace">
        <aside class="panel control-panel" aria-labelledby="query-setup-title">
          <div class="sidebar-heading">
            <h2 id="query-setup-title">Query Setup</h2>
          </div>
          <div class="control-stages">
            <el-radio-group
              :model-value="store.stage"
              class="full-segment"
              aria-label="Analysis stage"
              @update:model-value="selectStage"
            >
              <el-radio-button v-for="stage in stages" :key="stage.id" :value="stage.id" :title="stage.title">
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
        <aside class="panel anomaly-panel" aria-labelledby="risk-assessment-title">
          <div class="sidebar-heading">
            <h2 id="risk-assessment-title">Risk Assessment</h2>
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
