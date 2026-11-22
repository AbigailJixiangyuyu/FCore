<script setup>
import { computed } from 'vue'

import { metricLabels, probabilityLabel, useWorkbench } from '../../composables/workbenchContext.js'
import { formatCount, formatNumber } from '../../domain/format.js'

const props = defineProps({
  track: { type: Object, default: null },
  risk: { type: Object, default: null },
})
const { store, selected, metric, matchingPrediction, activePredictionModel } = useWorkbench()

function timeFeatures({ label, members, parameters, evidence }) {
  const scope = `${label} has ${formatCount(members.length, 'member')}.`
  if (!evidence) return scope
  if (parameters.pattern === 'periodic')
    return `${scope} It repeats every ${formatCount(evidence.period, 'snapshot')} from ${evidence.start_index_snapshot_id} to ${evidence.end_index_snapshot_id}, with ${formatCount(evidence.frequency, 'cycle')}.`
  if (parameters.pattern === 'durable') {
    const formed = `${scope} It formed during ${evidence.formation_start_snapshot_id}–${evidence.formation_end_snapshot_id}.`
    return evidence.duration > 0
      ? `${formed} Membership stayed fixed through ${evidence.stable_end_snapshot_id} for ${formatCount(evidence.duration, 'snapshot')}.`
      : `${formed} Its stability duration was 0 snapshots.`
  }
  if (parameters.pattern === 'burst') {
    const peak = evidence.nodes.reduce((best, node) => (
      !best || node.max_average_degree > best.max_average_degree ? node : best
    ), null)
    if (peak) return `${scope} Node ${peak.account} had the highest average internal degree of ${peak.max_average_degree.toFixed(2)} in ${peak.witness_start_snapshot_id}–${peak.witness_end_snapshot_id}.`
  }
  if (parameters.pattern === 'frequency')
    return `${scope} It has ${formatCount(evidence.qualified_edges.length, 'edge')} meeting the frequency threshold.`
  return scope
}

function evolution(points) {
  const [start, end] = [store.historyStartIndex, store.timeIndex]
  const view = points.filter(point => point.index >= start && point.index <= end)
  if (!view.length) return 'The displayed range is outside the mining range.'
  const range = view.length === 1 ? view[0].snapshot_id : `${view[0].snapshot_id}—${view.at(-1).snapshot_id}`
  const visible = view.filter(point => point.status === 'ok')
  if (!visible.length) return `No selected members appear in ${range}.`
  const label = metricLabels[metric.value]
  const peak = visible.reduce((best, point) => Number(point.value) > Number(best.value) ? point : best)
  const first = visible[0]
  const last = visible.at(-1)
  const maximum = `In ${range}, ${label.toLowerCase()} peaked at ${formatNumber(Number(peak.value), 2)} in ${peak.snapshot_id}.`
  if (first === last) return maximum
  const delta = Number(last.value) - Number(first.value)
  const change = delta === 0 ? 'stayed the same' : `${delta > 0 ? 'rose' : 'fell'} by ${formatNumber(Math.abs(delta), 2)}`
  return `${maximum} The value ${change} from ${first.snapshot_id} to ${last.snapshot_id}.`
}

const rows = computed(function () {
  if (store.stage === 'future') {
    const result = matchingPrediction.value
    if (!result) return []
    const { members, edges, k, account, status, message } = result
    const findings = [{
      label: 'Prediction',
      text: status === 'ok'
        ? `In ${result.target_snapshot}, the predicted ${k}-core containing node ${account} has ${formatCount(members.length, 'member')} and ${formatCount(edges.length, 'edge')}.`
        : message,
    }]
    if (edges.length) {
      const retained = edges.filter(edge => edge.currently_connected).length
      findings.push({
        label: 'Edge Status',
        text: `Of the predicted edges, ${formatNumber(retained)} were present in ${result.observed_until} and ${formatNumber(edges.length - retained)} were absent.`,
      })
    }
    return findings
  }
  if (!selected.value) return []
  if (store.stage === 'history') {
    const result = [{ label: 'Time Pattern', text: timeFeatures(selected.value) }]
    if (props.track) result.push({ label: 'Change', text: evolution(props.track.points) })
    return result
  }
  if (store.stage === 'present' && props.risk) {
    const { topCount, focus } = props.risk
    const size = selected.value.members.length
    const result = [{
      label: 'Top 10 Share',
      text: `${topCount} of ${size} members (${probabilityLabel(topCount / size)}) are in the S12 top 10 for anomaly score.`,
    }]
    if (focus) {
      const { account_id, score, temporal_contrast_score, memory_generation_score } = focus
      result.push({
        label: 'Score Details',
        text: `Node ${account_id} has an anomaly score of ${score.toFixed(4)}, a temporal contrast score of ${temporal_contrast_score.toFixed(4)}, and a memory generation score of ${memory_generation_score.toFixed(4)}.`,
      })
    } else result.push({ label: 'Score Details', text: 'No members have anomaly scores.' })
    return result
  }
  return []
})
const source = computed(function () {
  if (store.stage === 'history') return 'History · Snapshot evidence'
  if (store.stage === 'present') return 'Current · SLADE'
  return activePredictionModel.value?.name || 'Link prediction'
})
</script>

<template>
  <section class="summary-column report-summary" aria-labelledby="report-summary-title">
    <div class="summary-heading">
      <h2 id="report-summary-title">LLM-based Report</h2>
      <span class="summary-context">Template Summary</span>
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
    <p v-else class="summary-empty">No analysis summary yet.</p>
  </section>
</template>
