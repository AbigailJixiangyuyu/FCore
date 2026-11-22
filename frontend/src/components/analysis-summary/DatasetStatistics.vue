<script setup>
import { computed } from 'vue'

import { useWorkbench } from '../../composables/workbenchContext.js'
import { formatNumber, summarizeGraph } from '../../domain/analysisSummary.js'
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
  if (store.stage === 'future') return `${PRESENT_SNAPSHOT_ID} · 已观测`
  return currentWindow.value ? store.currentWindowLabel : PRESENT_SNAPSHOT_ID
})
const counts = computed(function () {
  if (!stats.value) return []
  const { nodeCount, transactionCount, edgeCount, density } = stats.value
  return [
    { label: '节点数', value: formatNumber(nodeCount) },
    { label: '交易次数', value: formatNumber(transactionCount) },
    { label: '聚合边数', value: formatNumber(edgeCount), title: '按方向合并重复交易' },
    {
      label: '图密度',
      value: density == null ? '—' : `${formatNumber(density * 100, 2)}%`,
      title: '按无向简单图统计，已相连的节点对占全部可能节点对的比例',
    },
  ]
})
const highest = computed(function () {
  const accounts = stats.value?.maxDegreeAccounts || []
  const ids = accounts.slice(0, 3).join('、')
  return accounts.length > 3 ? `${ids} 等 ${formatNumber(accounts.length)} 个` : ids
})
const largestComponent = computed(function () {
  if (!stats.value?.nodeCount) return '—'
  const { nodeCount, largestComponentSize } = stats.value
  const coverage = formatNumber(largestComponentSize / nodeCount * 100, 2)
  return `${formatNumber(largestComponentSize)} / ${formatNumber(nodeCount)}（${coverage}%）`
})
</script>

<template>
  <section class="summary-column dataset-summary" aria-labelledby="dataset-summary-title">
    <div class="summary-heading">
      <span class="panel-number">05</span>
      <h2 id="dataset-summary-title">数据集统计信息</h2>
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
        <div title="度数按无向简单图统计，包含孤立节点">
          <dt>平均度 / 中位度</dt>
          <dd>{{ formatNumber(stats.averageDegree, 2) }} / {{ formatNumber(stats.medianDegree, 2) }}</dd>
        </div>
        <div>
          <dt>最大度节点 ID</dt>
          <dd :title="stats.maxDegreeAccounts.join('、')">
            <template v-if="highest">{{ highest }} <small>（度 {{ formatNumber(stats.maxDegree) }}）</small></template>
            <template v-else>—</template>
          </dd>
        </div>
        <div title="当前窗口整图的最高核阶及该核的成员数">
          <dt>最大核</dt>
          <dd v-if="stats.maxCore !== null">{{ stats.maxCore }}-core · {{ formatNumber(stats.maxCoreSize) }} 个节点</dd>
          <dd v-else>—</dd>
        </div>
        <div title="最大连通分量的节点数 / 整图节点数及其占比">
          <dt>最大连通分量</dt>
          <dd>{{ largestComponent }}</dd>
        </div>
        <div v-if="stats.averageTransactionsPerSnapshot !== null" title="窗口内的交易总数除以快照数">
          <dt>每快照平均交易次数</dt>
          <dd>{{ formatNumber(stats.averageTransactionsPerSnapshot, 2) }}</dd>
        </div>
      </dl>
    </template>
    <QueryState v-else :query="snapshotQuery" />
  </section>
</template>
