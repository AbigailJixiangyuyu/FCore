<script setup>
import { Histogram } from '@element-plus/icons-vue'
import { computed } from 'vue'

import { useWorkbench } from '../../composables/workbenchContext.js'
import { summarizeGraph } from '../../domain/analysisSummary.js'
import { formatCount, formatNumber } from '../../domain/format.js'
import QueryState from '../QueryState.vue'

const { store, ready, snapshot, snapshotQuery, currentWindow } =
  useWorkbench()
const stats = computed(function () {
  const frame = currentWindow.value || snapshot.value
  return frame ? summarizeGraph(frame) : null
})
const scope = computed(function () {
  if (!store.stage) return 'All observed snapshots'
  if (store.stage === 'history') return store.historyRangeLabel
  if (store.stage === 'future') return `${store.observedUntil} · Observed`
  return currentWindow.value ? store.currentWindowLabel : store.observedUntil
})
const counts = computed(function () {
  if (!stats.value) return []
  const { nodeCount, transactionCount, edgeCount, density } = stats.value
  return [
    { label: 'Vertices', value: formatNumber(nodeCount) },
    { label: 'Interactions', value: formatNumber(transactionCount) },
    { label: 'Edges', value: formatNumber(edgeCount), title: 'Unique undirected vertex pairs in this range' },
    {
      label: 'Density',
      value: density == null ? '—' : `${formatNumber(density * 100, 2)}%`,
      title: 'Share of all possible vertex pairs that are connected',
    },
  ]
})
const highest = computed(function () {
  const accounts = stats.value?.maxDegreeAccounts || []
  const ids = accounts.slice(0, 3).join(', ')
  return accounts.length > 3 ? `${ids} and ${formatNumber(accounts.length - 3)} more` : ids
})
const largestComponent = computed(function () {
  if (!stats.value?.nodeCount) return '—'
  const { nodeCount, largestComponentSize } = stats.value
  const coverage = formatNumber(largestComponentSize / nodeCount * 100, 2)
  return `${formatNumber(largestComponentSize)} / ${formatNumber(nodeCount)} (${coverage}%)`
})
</script>

<template>
  <section class="summary-column dataset-summary" aria-labelledby="dataset-summary-title">
    <div class="summary-heading">
      <h2 id="dataset-summary-title" class="section-title">
        <Histogram aria-hidden="true" />
        Dataset Statistics
      </h2>
      <span v-if="ready" class="summary-context">{{ scope }}</span>
    </div>
    <template v-if="stats">
      <dl class="summary-metrics dataset-metrics">
        <div v-for="item in counts" :key="item.label" :title="item.title">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
        </div>
      </dl>
      <dl class="summary-facts">
        <div title="Vertex degree in the undirected graph, including isolated vertices">
          <dt>Mean / Median Degree</dt>
          <dd>{{ formatNumber(stats.averageDegree, 2) }} / {{ formatNumber(stats.medianDegree, 2) }}</dd>
        </div>
        <div>
          <dt>Highest-Degree Vertices</dt>
          <dd :title="stats.maxDegreeAccounts.join(', ')">
            <template v-if="highest">{{ highest }} <small>(degree {{ formatNumber(stats.maxDegree) }})</small></template>
            <template v-else>—</template>
          </dd>
        </div>
        <div title="Highest coreness and number of vertices in the maximum k-core">
          <dt>Maximum k-Core</dt>
          <dd v-if="stats.maxCore !== null">{{ stats.maxCore }}-core · {{ formatCount(stats.maxCoreSize, 'vertex', 'vertices') }}</dd>
          <dd v-else>—</dd>
        </div>
        <div title="Size of the largest connected component relative to the full graph">
          <dt>Largest Component</dt>
          <dd>{{ largestComponent }}</dd>
        </div>
        <div v-if="stats.snapshotCount > 1" title="Total interactions divided by the number of snapshots in the range">
          <dt>Interactions / Snapshot</dt>
          <dd>{{ formatNumber(stats.averageTransactionsPerSnapshot, 2) }}</dd>
        </div>
      </dl>
    </template>
    <QueryState v-else :query="snapshotQuery" />
  </section>
</template>
