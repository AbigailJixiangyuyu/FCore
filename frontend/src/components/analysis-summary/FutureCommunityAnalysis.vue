<script setup>
import { computed } from 'vue'

import { formatNumber } from '../../domain/format.js'

const props = defineProps({
  prediction: { type: Object, required: true },
  observedFrame: { type: Object, default: null },
  anomalyResponse: { type: Object, default: null },
})

const comparison = computed(() => props.prediction.comparison)
const exitedNodes = computed(function () {
  const { observed_until: snapshotId } = props.prediction
  const frame = props.observedFrame
  const coreNumbers = frame?.snapshot_id === snapshotId ? frame.core_numbers : null
  const response = props.anomalyResponse
  const accounts = response?.status === 'ok' && response.snapshot_id === snapshotId
    ? response.accounts
    : []
  const scores = new Map(accounts.map(({ account_id, score }) => [account_id, score]))
  return (comparison.value?.exited ?? []).map(id => ({
    id,
    coreness: coreNumbers?.[id],
    score: scores.get(id),
  }))
})
const changeLabels = {
  retained: 'Retained',
  added: 'Added',
  exited: 'Exited',
}
</script>

<template>
  <div class="summary-line forecast-overview">
    <strong v-if="comparison">
      {{ prediction.observed_until }} observed {{ formatNumber(comparison.retained.length + comparison.exited.length) }}
      → {{ prediction.target_snapshot }} predicted {{ formatNumber(prediction.members.length) }}
    </strong>
    <strong v-else>No membership comparison available</strong>
  </div>
  <template v-if="comparison">
    <dl class="summary-metrics forecast-metrics" aria-label="Community membership changes">
      <div v-for="(label, change) in changeLabels" :key="change">
        <dt>{{ label }}</dt>
        <dd>
          <el-popover v-if="comparison[change].length" trigger="click" placement="top" :width="235">
            <template #reference>
              <el-button link type="primary" :aria-label="`Show ${label.toLowerCase()} nodes`">
                {{ formatNumber(comparison[change].length) }}
              </el-button>
            </template>
            <ul class="forecast-member-list" :aria-label="`${label} node IDs`" tabindex="0">
              <li v-for="id in comparison[change]" :key="id">{{ id }}</li>
            </ul>
          </el-popover>
          <template v-else>0</template>
        </dd>
      </div>
    </dl>
    <h3 id="forecast-exits-heading" class="forecast-exits-heading">Nodes Predicted to Exit</h3>
    <div
      v-if="exitedNodes.length"
      class="member-table forecast-exit-table"
      role="region"
      aria-labelledby="forecast-exits-heading"
      tabindex="0"
    >
      <table>
        <thead>
          <tr>
            <th scope="col">Node ID</th>
            <th scope="col">Current Coreness</th>
            <th scope="col">Current SLADE Score</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="node in exitedNodes" :key="node.id">
            <td>{{ node.id }}</td>
            <td>{{ formatNumber(node.coreness) }}</td>
            <td>{{ node.score?.toFixed(4) ?? 'Unscored' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="summary-empty forecast-comparison-note" role="status">
      No predicted exits.
    </p>
  </template>
  <p v-else class="summary-empty forecast-comparison-note" role="status">
    {{ prediction.message || 'No prediction to compare.' }}
  </p>
</template>
