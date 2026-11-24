<script setup>
import { computed } from 'vue'
import { formatCount } from '../../domain/format.js'
import ChartCanvas from '../ChartCanvas.vue'

const props = defineProps({
  results: { type: Array, required: true },
  selectedId: { type: String, default: '' },
})
const emit = defineEmits(['select'])
const selected = computed(() => props.results.find(item => item.membership_hash === props.selectedId))
const snapshots = computed(() => selected.value?.evidence.analysis_snapshot_ids ?? [])
const counts = computed(() => selected.value?.evidence.qualifying_member_counts ?? [])

function describe(index) {
  const start = snapshots.value[0]
  const end = snapshots.value[index]
  const window = start === end ? start : `${start}–${end}`
  const core = selected.value
  return `${window} · ${counts.value[index]} of ${core.members.length} members in a ${core.parameters.k}-core`
}

const chartLabel = computed(() => snapshots.value.map((_, index) => describe(index)).join('. '))
const option = computed(() => ({
  animation: false,
  grid: { top: 16, bottom: 22, left: 31, right: 12 },
  tooltip: { trigger: 'axis', formatter: ([point]) => describe(point.dataIndex) },
  xAxis: {
    type: 'category', data: snapshots.value,
    axisTick: { show: false }, axisLabel: { hideOverlap: true, color: '#415977' },
    axisLine: { lineStyle: { color: '#dce4ef' } },
  },
  yAxis: {
    type: 'value', min: 0, minInterval: 1, splitNumber: 3,
    splitLine: { lineStyle: { color: '#edf1f7' } },
  },
  series: [{
    type: 'bar', data: counts.value, barMaxWidth: 30,
    itemStyle: { color: selected.value?.color },
    label: { show: true, position: 'top', color: '#20334b' },
  }],
}))
</script>

<template>
  <div class="summary-line component-selection">
    <strong>Historical {{ results[0].parameters.k }}-Core</strong>
    <el-select
      v-if="results.length > 1"
      :model-value="selectedId"
      aria-label="Historical community"
      placeholder="Select community"
      size="small"
      @update:model-value="emit('select', $event)"
    >
      <el-option
        v-for="(item, index) in results"
        :key="item.membership_hash"
        :label="`Community ${index + 1} · ${formatCount(item.members.length, 'vertex', 'vertices')}`"
        :value="item.membership_hash"
      />
    </el-select>
    <el-button v-else-if="!selected" link type="primary" @click="emit('select', results[0].membership_hash)">
      Show Query Result
    </el-button>
  </div>
  <template v-if="selected">
    <div class="summary-line core-metrics">
      <span>{{ formatCount(selected.metrics.node_count, 'vertex', 'vertices') }} ·
        {{ formatCount(selected.metrics.internal_edges, 'internal edge') }}</span>
      <span>Min. internal degree <strong>{{ selected.metrics.min_degree }}</strong></span>
    </div>
    <div class="summary-line">
      <strong>Members in a {{ selected.parameters.k }}-core</strong>
      <span>Window starts at {{ snapshots[0] }}</span>
    </div>
    <ChartCanvas :option="option" :label="chartLabel" :height="104" />
  </template>
</template>

<style scoped>
.component-selection { flex-wrap: wrap; gap: 4px 8px; }
.component-selection :deep(.el-select) { width: 170px; }
.core-metrics { flex-wrap: wrap; }
</style>
