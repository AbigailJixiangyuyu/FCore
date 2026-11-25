<script setup>
import { SetUp, Warning } from '@element-plus/icons-vue'
import { onBeforeUnmount, onMounted, provide, ref } from 'vue'

import AnalysisSummaryPanel from '../components/AnalysisSummaryPanel.vue'
import AnomalyInformation from '../components/AnomalyInformation.vue'
import CurrentControls from '../components/CurrentControls.vue'
import FutureControls from '../components/FutureControls.vue'
import GraphPanel from '../components/GraphPanel.vue'
import HistoryControls from '../components/HistoryControls.vue'
import PredictionNavigation from '../components/PredictionNavigation.vue'
import SnapshotNavigation from '../components/SnapshotNavigation.vue'
import { useWorkbenchData } from '../composables/useWorkbenchData.js'
import { workbenchKey } from '../composables/workbenchContext.js'

const DEFAULT_LAYOUT = 'video'
const layout = ref(DEFAULT_LAYOUT)

function syncLayout() {
  const hash = window.location.hash.slice(1)
  layout.value = hash === 'paper' || hash === 'video' ? hash : DEFAULT_LAYOUT
}

syncLayout()
onMounted(() => {
  window.addEventListener('hashchange', syncLayout)
})
onBeforeUnmount(() => window.removeEventListener('hashchange', syncLayout))

const workbench = useWorkbenchData(layout)
provide(workbenchKey, { ...workbench, viewLayout: layout })
const { store, system, connected, ready, selectTime } = workbench
const datasets = system.datasets
const stages = [
  { id: 'history', label: 'Historical Mining' },
  { id: 'present', label: 'Current Search' },
  { id: 'future', label: 'Future Prediction' },
]

function selectStage(stage) {
  if (stage === 'history') selectTime(store.historyEndIndex)
  else selectTime(stage === 'present' ? store.presentIndex : store.presentIndex + 1)
}
</script>

<template>
  <main class="workbench" :data-layout="layout">
    <SnapshotNavigation v-if="system.connectionState.value !== 'error'" />
    <template v-if="system.connectionState.value === 'checking' || (connected && datasets.length)">
      <div class="workspace">
        <aside class="panel control-panel" aria-labelledby="query-setup-title">
          <div class="sidebar-heading">
            <h2 id="query-setup-title" class="section-title">
              <SetUp aria-hidden="true" />
              Query Setup
            </h2>
          </div>
          <div class="control-stages">
            <el-radio-group
              :model-value="store.stage ?? ''"
              :disabled="!ready"
              class="full-segment"
              aria-label="Temporal Community Search &amp; Prediction"
              @update:model-value="selectStage"
            >
              <el-radio-button v-for="stage in stages" :key="stage.id" :value="stage.id" :disabled="stage.id === 'history' && !store.presentIndex" :title="stage.label">
                {{ stage.label }}
              </el-radio-button>
            </el-radio-group>
          </div>
          <div class="sidebar-content">
            <template v-if="ready">
              <HistoryControls v-if="store.stage === 'history'" />
              <CurrentControls v-else-if="store.stage === 'present'" />
              <FutureControls v-else-if="store.stage === 'future'" />
            </template>
          </div>
        </aside>
        <GraphPanel />
        <aside class="panel anomaly-panel" aria-labelledby="risk-assessment-title">
          <div class="sidebar-heading">
            <h2 id="risk-assessment-title" class="section-title">
              <Warning aria-hidden="true" />
              Online Risk Assessment
            </h2>
          </div>
          <div class="sidebar-content">
            <AnomalyInformation v-if="ready" />
          </div>
          <PredictionNavigation v-if="ready" />
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
              ? 'Choose Import Dataset… in Datasets Loading to add your first dataset.'
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
