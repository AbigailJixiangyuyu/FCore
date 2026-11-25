<script setup>
import { DataAnalysis } from '@element-plus/icons-vue'
import { computed } from 'vue'

import { metricLabels, useWorkbench } from '../../composables/workbenchContext.js'
import { algorithmLabel, structureAlgorithm } from '../../domain/algorithms.js'
import { formatCount, formatNumber } from '../../domain/format.js'
import EvidenceChart from '../EvidenceChart.vue'
import QueryState from '../QueryState.vue'
import BurstEvidence from './BurstEvidence.vue'
import CommunityRiskSummary from './CommunityRiskSummary.vue'
import CorePatternTimeline from './CorePatternTimeline.vue'
import FrequencyEvidence from './FrequencyEvidence.vue'
import FutureCommunityAnalysis from './FutureCommunityAnalysis.vue'
import HistoricalCoreResults from './HistoricalCoreResults.vue'
import MemberAnomalyScores from './MemberAnomalyScores.vue'
import TemporalCoreResults from './TemporalCoreResults.vue'

defineProps({
  track: { type: Object, default: null },
  risk: { type: Object, default: null },
})

const {
  store, ready, selected, patternResult, patternResponse, queryResult, metric, evidenceResult,
  historyResults, selectHistoryResult, selectTime, selectHistoryRange,
  snapshot, currentWindow, anomalyQuery, anomalyResponse,
  matchingPrediction, predictionRequest, predictionMessage,
} = useWorkbench()
const members = computed(() => selected.value?.members || [])
const selectedAlgorithmLabel = computed(function () {
  if (!selected.value) return ''
  const algorithm = structureAlgorithm(selected.value)
  return algorithm ? algorithmLabel(algorithm) : selected.value.label
})
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
  if (index >= 0 && index < store.presentIndex) selectTime(index)
}

function locateMember(accountId) {
  if (store.stage !== 'present' || !members.value.includes(accountId)) return
  store.graphLocation = { accountId, source: 'member' }
}
</script>

<template>
  <section class="summary-column result-summary" aria-labelledby="result-summary-title">
    <div class="summary-heading">
      <h2 id="result-summary-title" class="section-title">
        <DataAnalysis aria-hidden="true" />
        Result Analysis
      </h2>
      <span v-if="analysisRange" class="summary-context">
        Range {{ analysisRange }}
      </span>
      <span v-else-if="selected" class="summary-context risk-coverage">
        {{ selected.observed_until }}<template v-if="risk"> · {{ risk.scoredCount }}/{{ members.length }} scored</template> ·
        <el-popover trigger="click" placement="top-end" :width="235">
          <template #reference>
            <el-button link type="primary" :aria-label="`Show coreness for all ${members.length} community members`">
              Coreness
            </el-button>
          </template>
          <div class="member-table" role="region" aria-label="Community member coreness" tabindex="0">
            <table>
              <thead>
                <tr>
                  <th scope="col">Vertex ID</th>
                  <th scope="col" title="Highest k for which the vertex belongs to the k-core of the query graph">
                    Coreness · {{ store.currentWindowLabel || selected.snapshot_id }}
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
    <template v-if="ready && store.stage === 'future'">
      <FutureCommunityAnalysis
        v-if="matchingPrediction"
        :key="matchingPrediction.request_id"
        :prediction="matchingPrediction"
        :observed-frame="snapshot"
        :anomaly-response="anomalyResponse"
      />
      <QueryState v-else-if="predictionRequest" :query="predictionRequest" />
      <p v-else class="summary-empty">{{ predictionMessage }}</p>
    </template>
    <component
      :is="store.historyResultWindow === 'submitted' ? HistoricalCoreResults : TemporalCoreResults"
      v-else-if="store.stage === 'history' && store.historyResultWindow && historyResults.length"
      :key="store.analysisRunId"
      :results="historyResults"
      :selected-id="store.historySelection"
      @select="selectHistoryResult"
    />
    <template v-else-if="!selected">
      <p v-if="ready && !store.analysisRunId" class="summary-empty">
        Run a query to see the community.
      </p>
      <QueryState
        v-else-if="query.isFetching.value || query.isError.value"
        :query="query"
      />
      <p v-else-if="ready" class="summary-empty">{{ patternResponse?.message || 'No matching community.' }}</p>
    </template>
    <template v-else-if="store.stage === 'history'">
      <div class="summary-line">
        <span><i class="group-dot" :style="{ '--group': selected.color }"></i>
          {{ selectedAlgorithmLabel }} · {{ formatCount(members.length, 'member') }}
        </span>
        <el-select
          v-if="!patternView"
          v-model="store.metric"
          aria-label="Analysis metric"
          class="summary-metric-select"
        >
          <el-option label="Automatic" value="auto" />
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
        <p v-else class="summary-empty">No algorithm evidence for this result.</p>
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
      <dl class="summary-metrics community-metrics" aria-label="Community structure">
        <div>
          <dt>Vertices</dt>
          <dd>{{ formatNumber(selected.metrics.node_count) }}</dd>
        </div>
        <div title="Number of undirected edges within the community">
          <dt>Internal Edges</dt>
          <dd>{{ formatNumber(selected.metrics.internal_edges) }}</dd>
        </div>
        <div title="Share of possible edges present within the community">
          <dt>Density</dt>
          <dd>{{ formatNumber(selected.metrics.density * 100, 2) }}%</dd>
        </div>
      </dl>
      <CommunityRiskSummary v-if="risk?.scoredCount" :risk="risk" :member-count="members.length" />
      <QueryState v-else-if="anomalyQuery.isFetching.value || anomalyQuery.isError.value" :query="anomalyQuery" />
      <p v-else class="summary-empty">{{ anomalyResponse?.message || 'No SLADE scores for this community.' }}</p>
    </template>
  </section>
</template>
