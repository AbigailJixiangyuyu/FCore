<script setup>
import { computed } from 'vue'

import { metricLabels, useWorkbench } from '../../composables/workbenchContext.js'
import { formatNumber } from '../../domain/analysisSummary.js'
import { PRESENT_INDEX } from '../../domain/timeline.js'
import EvidenceChart from '../EvidenceChart.vue'
import QueryState from '../QueryState.vue'
import BurstEvidence from './BurstEvidence.vue'
import CommunityRiskSummary from './CommunityRiskSummary.vue'
import CorePatternTimeline from './CorePatternTimeline.vue'
import FrequencyEvidence from './FrequencyEvidence.vue'
import FutureCommunityAnalysis from './FutureCommunityAnalysis.vue'
import MemberAnomalyScores from './MemberAnomalyScores.vue'

defineProps({
  track: { type: Object, default: null },
  risk: { type: Object, default: null },
})

const {
  store, selected, patternResult, patternResponse, queryResult, metric, evidenceResult, selectTime, selectHistoryRange,
  snapshot, currentWindow, anomalyQuery, anomalyResponse,
  matchingPrediction, predictionRequest, predictionMessage,
} = useWorkbench()
const members = computed(() => selected.value?.members || [])
const memberCoreNumbers = computed(() => {
  const frame = store.currentAlgorithm === 'tccs' ? currentWindow.value : snapshot.value
  return frame?.core_numbers
})
const historyRange = computed(() => [store.historyStartIndex, store.historyEndIndex])
const analysisRange = computed(function () {
  const snapshots = patternResponse.value?.analysis_snapshot_ids
  if (!snapshots?.length) return ''
  return snapshots.length === 1 ? snapshots[0] : `${snapshots[0]}—${snapshots.at(-1)}`
})
const patternViews = {
  periodic: CorePatternTimeline,
  durable: CorePatternTimeline,
  burst: BurstEvidence,
  frequency: FrequencyEvidence,
}
const patternView = computed(() => patternViews[selected.value?.parameters.pattern])
const query = computed(() => store.stage === 'history' ? patternResult : queryResult)
function selectEvidenceTime(index) {
  if (index >= 0 && index < PRESENT_INDEX) selectTime(index)
}

function locateMember(accountId) {
  if (store.stage !== 'present' || !members.value.includes(accountId)) return
  store.graphLocation = { accountId, source: 'member' }
}
</script>

<template>
  <section class="summary-column result-summary" aria-labelledby="result-summary-title">
    <div class="summary-heading">
      <h2 id="result-summary-title">查询结果分析</h2>
      <span v-if="analysisRange" class="summary-context">
        挖掘范围 {{ analysisRange }}
      </span>
      <span v-else-if="selected" class="summary-context risk-coverage">
        {{ selected.observed_until }}<template v-if="risk"> 已评分 {{ risk.scoredCount }}/{{ members.length }}</template> ·
        <el-popover trigger="click" placement="top-end" :width="235">
          <template #reference>
            <el-button link type="primary" :aria-label="`查看全部 ${members.length} 个社区成员的核数`">
              成员核数
            </el-button>
          </template>
          <div class="member-table" role="region" aria-label="社区成员核数" tabindex="0">
            <table>
              <thead>
                <tr>
                  <th scope="col">节点 ID</th>
                  <th scope="col" title="节点在查询图中所属的最高 k-core 阶数">
                    核数 · {{ store.currentWindowLabel || selected.snapshot_id }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="id in members" :key="id">
                  <td>{{ id }}</td>
                  <td>{{ formatNumber(memberCoreNumbers?.[id]) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </el-popover>
        <MemberAnomalyScores
          v-if="risk"
          :key="selected.membership_hash"
          :scores="risk.memberScores"
          @locate="locateMember"
        />
      </span>
    </div>
    <template v-if="store.stage === 'future'">
      <FutureCommunityAnalysis
        v-if="matchingPrediction"
        :key="matchingPrediction.request_id"
        :prediction="matchingPrediction"
      />
      <QueryState v-else-if="predictionRequest" :query="predictionRequest" />
      <p v-else class="summary-empty">{{ predictionMessage }}</p>
    </template>
    <template v-else-if="!selected">
      <p v-if="!store.analysisRunId" class="summary-empty">
        {{ store.stage === 'history' ? '点击「开始挖掘」查看结果。' : '点击「开始查询」查看结果。' }}
      </p>
      <QueryState
        v-else-if="query.isFetching.value || query.isError.value"
        :query="query"
      />
      <p v-else class="summary-empty">{{ patternResponse?.message || '当前没有匹配的查询结构。' }}</p>
    </template>
    <template v-else-if="store.stage === 'history'">
      <div class="summary-line">
        <span><i class="group-dot" :style="{ '--group': selected.color }"></i>
          {{ selected.label }} · {{ formatNumber(members.length) }} 个成员
        </span>
        <el-select
          v-if="!patternView"
          v-model="store.metric"
          aria-label="分析视图"
          class="summary-metric-select"
        >
          <el-option label="自动选择指标" value="auto" />
          <el-option v-for="(label, value) in metricLabels" :key="value" :label="label" :value="value" />
        </el-select>
      </div>
      <template v-if="patternView">
        <component
          :is="patternView"
          v-if="selected.evidence"
          :key="selected.membership_hash"
          :structure="selected"
          :selected-range="historyRange"
          @select-index="selectEvidenceTime"
          @select-range="selectHistoryRange"
        />
        <p v-else class="summary-empty">暂无算法判定依据。</p>
      </template>
      <EvidenceChart
        v-else-if="track"
        :track="track"
        :unit="evidenceResult.data.value.unit"
        :metric-label="metricLabels[metric]"
        :selected-index="store.timeIndex"
        :selected-range="historyRange"
        @select-index="selectEvidenceTime"
      />
      <QueryState v-else :query="evidenceResult" />
    </template>
    <template v-else-if="store.stage === 'present'">
      <dl class="summary-metrics community-metrics" aria-label="社区结构">
        <div>
          <dt>节点数</dt>
          <dd>{{ formatNumber(selected.metrics.node_count) }}</dd>
        </div>
        <div title="社区内部的无向简单边数">
          <dt>内部边数</dt>
          <dd>{{ formatNumber(selected.metrics.internal_edges) }}</dd>
        </div>
        <div title="社区内部边数占所有可能无向连边的比例">
          <dt>密度</dt>
          <dd>{{ formatNumber(selected.metrics.density * 100, 2) }}%</dd>
        </div>
      </dl>
      <CommunityRiskSummary v-if="risk?.scoredCount" :risk="risk" :member-count="members.length" />
      <QueryState v-else-if="anomalyQuery.isFetching.value || anomalyQuery.isError.value" :query="anomalyQuery" />
      <p v-else class="summary-empty">{{ anomalyResponse?.message || '该社区暂无 SLADE 评分。' }}</p>
    </template>
  </section>
</template>
