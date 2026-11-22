<script setup>
import { computed } from 'vue'

import { metricLabels, probabilityLabel, useWorkbench } from '../../composables/workbenchContext.js'
import { formatNumber } from '../../domain/analysisSummary.js'

const props = defineProps({
  track: { type: Object, default: null },
  risk: { type: Object, default: null },
})
const { store, selected, metric, matchingPrediction, activePredictionModel } = useWorkbench()

function timeFeatures({ label, members, parameters, evidence }) {
  const scope = `${label}包含 ${formatNumber(members.length)} 个成员。`
  if (!evidence) return scope
  if (parameters.pattern === 'periodic')
    return `${scope}${evidence.start_index_snapshot_id}—${evidence.end_index_snapshot_id} 内每 ${evidence.period} 个快照重复，出现 ${evidence.frequency} 轮。`
  if (parameters.pattern === 'durable') {
    const formed = `${scope}在 ${evidence.formation_start_snapshot_id}—${evidence.formation_end_snapshot_id} 形成。`
    return evidence.duration > 0
      ? `${formed}成员保持到 ${evidence.stable_end_snapshot_id}，稳定时长为 ${evidence.duration} 个快照。`
      : `${formed}形成后的稳定时长为 0。`
  }
  if (parameters.pattern === 'burst') {
    const peak = evidence.nodes.reduce((best, node) => (
      !best || node.max_average_degree > best.max_average_degree ? node : best
    ), null)
    if (peak) return `${scope}账户 ${peak.account} 在 ${peak.witness_start_snapshot_id}—${peak.witness_end_snapshot_id} 的平均度最高（${peak.max_average_degree.toFixed(2)}）。`
  }
  if (parameters.pattern === 'frequency')
    return `${scope}其中 ${formatNumber(evidence.qualified_edges.length)} 对连边达到频率阈值。`
  return scope
}

function evolution(points) {
  const [start, end] = [store.historyStartIndex, store.timeIndex]
  const view = points.filter(point => point.index >= start && point.index <= end)
  if (!view.length) return '当前展示区间超出本次挖掘范围。'
  const range = view.length === 1 ? view[0].snapshot_id : `${view[0].snapshot_id}—${view.at(-1).snapshot_id}`
  const visible = view.filter(point => point.status === 'ok')
  if (!visible.length) return `${range} 内未观测到所选成员。`
  const label = metricLabels[metric.value]
  const peak = visible.reduce((best, point) => Number(point.value) > Number(best.value) ? point : best)
  const first = visible[0]
  const last = visible.at(-1)
  const maximum = `${range} 内${label}峰值为 ${formatNumber(Number(peak.value), 2)}（${peak.snapshot_id}）。`
  if (first === last) return maximum
  const delta = Number(last.value) - Number(first.value)
  const change = delta === 0 ? '持平' : `${delta > 0 ? '增加' : '减少'} ${formatNumber(Math.abs(delta), 2)}`
  return `${maximum}${first.snapshot_id} 至 ${last.snapshot_id} ${change}。`
}

const rows = computed(function () {
  if (store.stage === 'future') {
    const result = matchingPrediction.value
    if (!result) return []
    const { members, edges, k, account, status, message } = result
    const findings = [{
      label: '社区预测',
      text: status === 'ok'
        ? `${result.target_snapshot} 中包含 ${account} 的 ${k}-core 社区有 ${formatNumber(members.length)} 个成员及 ${formatNumber(edges.length)} 条预测边。`
        : message,
    }]
    if (edges.length) {
      const retained = edges.filter(edge => edge.currently_connected).length
      findings.push({
        label: '连边构成',
        text: `社区内 ${formatNumber(retained)} 条预测边在 ${result.observed_until} 已连接，${formatNumber(edges.length - retained)} 条在该快照未连接。`,
      })
    }
    return findings
  }
  if (!selected.value) return []
  if (store.stage === 'history') {
    const result = [{ label: '时序特征', text: timeFeatures(selected.value) }]
    if (props.track) result.push({ label: '演化分析', text: evolution(props.track.points) })
    return result
  }
  if (store.stage === 'present' && props.risk) {
    const { topCount, focus } = props.risk
    const size = selected.value.members.length
    const result = [{
      label: '异常成员占比',
      text: `社区有 ${topCount} / ${size} 名成员（${probabilityLabel(topCount / size)}）进入 S12 异常排名 Top-10。`,
    }]
    if (focus) {
      const { account_id, score, temporal_contrast_score, memory_generation_score } = focus
      result.push({
        label: '成员异常分析',
        text: `账户 ${account_id} 的异常分为 ${score.toFixed(4)}，与自身历史的差异为 ${temporal_contrast_score.toFixed(4)}，与邻域推断状态的差异为 ${memory_generation_score.toFixed(4)}。`,
      })
    } else result.push({ label: '成员异常分析', text: '该社区没有已评分成员。' })
    return result
  }
  return []
})
const source = computed(function () {
  if (store.stage === 'history') return '历史挖掘 · 逐快照证据'
  if (store.stage === 'present') return '社区查询 · SLADE'
  return activePredictionModel.value?.name || '链接预测'
})
</script>

<template>
  <section class="summary-column report-summary" aria-labelledby="report-summary-title">
    <div class="summary-heading">
      <h2 id="report-summary-title">LLM-based Report</h2>
      <span class="summary-context">前端摘要</span>
    </div>
    <template v-if="rows.length">
      <p class="report-source">{{ source }}</p>
      <dl class="report-findings">
        <div v-for="row in rows" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.text }}</dd>
        </div>
      </dl>
    </template>
    <p v-else class="summary-empty">暂无分析摘要。</p>
  </section>
</template>
