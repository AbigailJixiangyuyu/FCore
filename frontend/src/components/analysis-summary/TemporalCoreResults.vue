<script setup>
import { computed } from 'vue'

import { formatCount, formatNumber } from '../../domain/format.js'
import ChartCanvas from '../ChartCanvas.vue'

const props = defineProps({
  results: { type: Array, required: true },
  selectedId: { type: String, default: '' },
})
const emit = defineEmits(['select'])

function windowLabel(start, end) {
  return start === end ? start : `${start}–${end}`
}

function tightestWindow({ witness_start_snapshot_id: start, witness_end_snapshot_id: end }) {
  return windowLabel(start, end)
}

const selected = computed(() => props.results.find(core => core.membership_hash === props.selectedId))
const threshold = computed(() => selected.value?.parameters.k)
const windows = computed(() => (selected.value?.evidence.window_comparison || []).map(window => ({
  ...window,
  label: windowLabel(window.start_snapshot_id, window.end_snapshot_id),
})))
const passingTrims = computed(() => windows.value.filter(window => (
  window.omitted_temporal_edges > 0 && window.min_internal_degree >= threshold.value
)))

function describeWindow(window) {
  const degree = formatNumber(window.min_internal_degree)
  const below = formatNumber(window.below_k_members)
  const members = formatNumber(selected.value.metrics.node_count)
  return [`${window.label} · Min. internal degree ${degree}`, `${below} / ${members} members below k`]
}

const chartLabel = computed(() => [
  `Minimum internal degree by window (k = ${threshold.value})`,
  ...windows.value.flatMap(describeWindow),
].join('. '))

const option = computed(function () {
  const rows = windows.value
  const k = threshold.value
  return {
    animation: false,
    grid: { top: 8, right: 29, bottom: 24, left: 76 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter([point]) {
        const window = rows[point?.dataIndex]
        return window ? describeWindow(window).join('\n') : ''
      },
    },
    xAxis: {
      type: 'value', min: 0, minInterval: 1, splitNumber: 4,
      max: ({ max }) => max + Math.max(1, Math.ceil(max * 0.1)),
      axisLabel: { color: '#687b91', hideOverlap: true },
      splitLine: { lineStyle: { color: '#edf1f7' } },
    },
    yAxis: {
      type: 'category', inverse: true,
      data: rows.map(window => window.label),
      axisLabel: { color: '#415977' },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#dce4ef' } },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 17,
      label: { show: true, position: 'right', color: '#20334b' },
      data: rows.map(window => ({
        value: window.min_internal_degree,
        itemStyle: { color: window.min_internal_degree >= k ? '#477be7' : '#aab9cc' },
      })),
      markLine: {
        silent: true, symbol: 'none', label: { show: false },
        lineStyle: { color: '#305ed1', type: 'dashed' },
        data: [{ xAxis: k }],
      },
    }],
  }
})
</script>

<template>
  <div class="temporal-core-results">
    <div class="summary-line temporal-core-overview">
      <div class="temporal-core-window">
        <span>Tightest Window</span>
        <el-select
          v-if="results.length > 1"
          :model-value="selectedId"
          aria-label="Tightest Window"
          placeholder="Select window"
          class="core-window-select"
          size="small"
          @update:model-value="emit('select', $event)"
        >
          <el-option
            v-for="result in results"
            :key="result.membership_hash"
            :label="tightestWindow(result.evidence)"
            :value="result.membership_hash"
          />
        </el-select>
        <el-button
          v-else
          link
          type="primary"
          :aria-pressed="!!selected"
          @click="emit('select', results[0].membership_hash)"
        >{{ tightestWindow(results[0].evidence) }}</el-button>
      </div>
      <span v-if="selected" class="temporal-core-size">
        <strong>{{ formatNumber(selected.metrics.node_count) }}</strong> Nodes ·
        <strong>{{ formatNumber(selected.metrics.internal_edges) }}</strong> Internal Edges
      </span>
    </div>
    <template v-if="windows.length">
      <div class="summary-line">
        <strong>Min. Internal Degree</strong>
        <span class="core-threshold">k = {{ threshold }}</span>
      </div>
      <ChartCanvas class="temporal-core-chart" :option="option" :label="chartLabel" :height="104" />
      <div v-if="passingTrims.length" class="trimmed-window-notes helper">
        <span v-for="window in passingTrims" :key="window.label">
          {{ window.label }} meets k · {{ formatCount(window.omitted_temporal_edges, 'fewer timestamped edge') }}
        </span>
      </div>
    </template>
    <p v-else class="summary-empty">
      {{ selected ? 'Window comparison unavailable.' : 'Select a window to view its core.' }}
    </p>
  </div>
</template>

<style scoped>
.temporal-core-results {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
}

.temporal-core-overview {
  flex-wrap: wrap;
  gap: 4px 10px;
  min-height: 28px;
}

.temporal-core-window,
.core-threshold {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.core-window-select { width: 111px; }
.temporal-core-window :deep(.el-button) { padding: 0; }
.temporal-core-size { font-variant-numeric: tabular-nums; }

.core-threshold::before {
  width: 14px;
  border-top: 1px dashed #305ed1;
  content: '';
}

.temporal-core-chart { flex: 1 0 104px; }
.trimmed-window-notes { display: grid; gap: 2px; }
</style>
