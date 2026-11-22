<script setup>
import { computed } from 'vue'

import { useWorkbench } from '../../composables/workbenchContext.js'
import { summarizeGraph } from '../../domain/analysisSummary.js'
import { formatCount, formatNumber } from '../../domain/format.js'
import { PRESENT_SNAPSHOT_ID } from '../../domain/timeline.js'
import QueryState from '../QueryState.vue'

const { store, snapshot, snapshotQuery, currentWindow } =
  useWorkbench()
const stats = computed(function () {
  const frame = currentWindow.value || snapshot.value
  return frame ? summarizeGraph(frame) : null
})
const scope = computed(function () {
  if (store.stage === 'history') return store.historyRangeLabel
  if (store.stage === 'future') return `${PRESENT_SNAPSHOT_ID} · Observed`
  return currentWindow.value ? store.currentWindowLabel : PRESENT_SNAPSHOT_ID
})
const counts = computed(function () {
  if (!stats.value) return []
  const { nodeCount, transactionCount, edgeCount, density } = stats.value
  return [
    { label: 'Nodes', value: formatNumber(nodeCount) },
    { label: 'Interactions', value: formatNumber(transactionCount) },
    { label: 'Edges', value: formatNumber(edgeCount), title: 'Unique undirected node pairs in this range' },
    {
      label: 'Density',
      value: density == null ? '—' : `${formatNumber(density * 100, 2)}%`,
      title: 'Share of all possible node pairs that are connected',
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
      <span class="panel-number">05</span>
      <h2 id="dataset-summary-title">Dataset Statistics</h2>
      <span class="summary-context">{{ scope }}</span>
    </div>
    <template v-if="stats">
      <dl class="summary-metrics dataset-metrics">
        <div v-for="item in counts" :key="item.label" :title="item.title">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
        </div>
      </dl>
      <dl class="summary-facts">
        <div title="Node degree in the undirected graph, including isolated nodes">
          <dt>Mean / Median Degree</dt>
          <dd>{{ formatNumber(stats.averageDegree, 2) }} / {{ formatNumber(stats.medianDegree, 2) }}</dd>
        </div>
        <div>
          <dt>Highest-Degree Nodes</dt>
          <dd :title="stats.maxDegreeAccounts.join(', ')">
            <template v-if="highest">{{ highest }} <small>(degree {{ formatNumber(stats.maxDegree) }})</small></template>
            <template v-else>—</template>
          </dd>
        </div>
        <div title="Highest coreness and number of nodes in the maximum core">
          <dt>Maximum Core</dt>
          <dd v-if="stats.maxCore !== null">{{ stats.maxCore }}-core · {{ formatCount(stats.maxCoreSize, 'node') }}</dd>
          <dd v-else>—</dd>
        </div>
        <div title="Size of the largest connected component relative to the full graph">
          <dt>Largest Component</dt>
          <dd>{{ largestComponent }}</dd>
        </div>
        <div v-if="stats.averageTransactionsPerSnapshot !== null" title="Total interactions divided by the number of snapshots in the range">
          <dt>Interactions / Snapshot</dt>
          <dd>{{ formatNumber(stats.averageTransactionsPerSnapshot, 2) }}</dd>
        </div>
      </dl>
    </template>
    <QueryState v-else :query="snapshotQuery" />
  </section>
</template>
