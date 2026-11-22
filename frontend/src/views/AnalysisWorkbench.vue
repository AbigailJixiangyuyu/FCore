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
import { FUTURE_INDEX, PRESENT_INDEX } from '../domain/timeline.js'

const workbench = useWorkbenchData()
provide(workbenchKey, workbench)
const { store, system, connected, catalog, currentWindow, selectTime } = workbench
const datasets = system.datasets
const stages = [
  { id: 'history', label: '历史挖掘' },
  { id: 'present', label: '当前搜索' },
  { id: 'future', label: '未来预测' },
]

function selectStage(stage) {
  if (stage === 'history') selectTime(store.historyEndIndex)
  else selectTime(stage === 'present' ? PRESENT_INDEX : FUTURE_INDEX)
}
const title = computed(function () {
  if (store.stage === 'history') return '历史：选择时间区间，查看挖掘出的社区'
  if (store.stage === 'future') return '未来：查询预测快照中的 k-core 社区'
  return '现在：查询图结构，检查异常信息'
})
const timeContext = computed(function () {
  if (store.stage === 'history') return store.historyRangeLabel
  if (store.stage === 'future') return 'S12 → S13'
  return currentWindow.value ? store.currentWindowLabel : 'S12'
})
</script>

<template>
  <main class="workbench">
    <template v-if="connected && datasets.length">
      <SnapshotNavigation />
      <div class="page-intro">
        <h1>{{ title }}</h1>
        <span class="count-chip">账户层 · {{ timeContext }}</span>
      </div>
      <QueryState v-if="catalog.isError.value" :query="catalog" />
      <div class="workspace">
        <aside class="panel control-panel" aria-label="方法与参数">
          <div class="sidebar-heading">
            <span class="panel-number">02</span>
            <h2>方法与参数</h2>
          </div>
          <div class="control-stages">
            <el-radio-group
              :model-value="store.stage"
              class="full-segment"
              aria-label="分析阶段"
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
        <aside class="panel anomaly-panel" aria-label="异常信息">
          <div class="sidebar-heading">
            <span class="panel-number">04</span>
            <h2>异常信息</h2>
            <span class="heading-hint">ANOMALY</span>
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
          connected ? '当前没有已接入的数据集' : '连接分析服务后加载工作台'
        "
        ><p class="helper">
          {{
            connected
              ? '请准备本地数据集，重新连接后读取数据集清单。'
              : '确认后端服务已启动后，点击下方按钮重新连接。'
          }}
        </p>
        <p
          v-for="error in system.errors.value"
          :key="error.endpoint"
          class="helper"
        >
          {{ error.endpoint }}：{{ error.message }}
        </p>
        <el-button
          class="startup-retry"
          type="primary"
          :loading="system.connectionState.value === 'checking'"
          @click="system.refresh()"
          >{{ connected ? '重新加载数据集' : '重新连接' }}</el-button
        ></el-empty
      >
    </section>
  </main>
</template>
