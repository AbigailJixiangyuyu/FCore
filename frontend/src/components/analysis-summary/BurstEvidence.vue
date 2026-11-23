<script setup>
import { computed } from 'vue'

import { snapshotId, snapshotIndex } from '../../domain/timeline.js'
import ChartCanvas from '../ChartCanvas.vue'

const props = defineProps({
  structure: { type: Object, required: true },
  selectedRange: { type: Array, required: true },
})
const emit = defineEmits(['select-index'])
const snapshots = computed(() => props.structure.evidence.analysis_snapshot_ids)
const witness = computed(function () {
  const account = props.structure.parameters.account
  return props.structure.evidence.nodes.find(node => node.account === account)
})

const witnessRange = computed(function () {
  const { witness_start_snapshot_id: first, witness_end_snapshot_id: last } = witness.value
  return `${first}—${last}`
})
const msd = computed(() => witness.value.max_average_degree.toFixed(2))
const threshold = computed(() => props.structure.parameters.delta.toFixed(2))

function selectSnapshot(index) {
  const id = snapshots.value[index]
  if (id) emit('select-index', snapshotIndex(id))
}

const option = computed(function () {
  const node = witness.value
  const { l } = props.structure.parameters
  const [start, end] = props.selectedRange
  const view = snapshots.value.filter(id => {
    const position = snapshotIndex(id)
    return position >= start && position <= end
  })
  const selectedEnd = snapshotId(end)
  const inWitness = index => index >= node.witness_start && index <= node.witness_end
  return {
    animationDuration: 180,
    grid: { top: 10, right: 6, bottom: 24, left: 33 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: function ([point]) {
        if (!point) return ''
        const degree = `${point.axisValueLabel} · Internal degree ${node.degree_sequence[point.dataIndex]}`
        if (!inWitness(point.dataIndex)) return degree
        return `${degree}\n${witnessRange.value} · MSD ${msd.value}\nMin. length ℓ = ${l} snapshots · δ = ${threshold.value}`
      },
    },
    xAxis: {
      type: 'category',
      data: snapshots.value,
      axisLine: { lineStyle: { color: '#dce4ef' } },
      axisTick: { show: false },
      axisLabel: { color: '#687b91', interval: 0 },
    },
    yAxis: {
      type: 'value', min: 0, minInterval: 1, splitNumber: 3,
      axisLabel: { color: '#7c8da3' },
      splitLine: { lineStyle: { color: '#f0f3f8' } },
    },
    series: [{
      name: 'Internal degree',
      type: 'bar',
      barMaxWidth: 20,
      data: node.degree_sequence.map((value, index) => ({
        value,
        itemStyle: { color: inWitness(index) ? props.structure.color : '#cbd7e5' },
      })),
      markLine: {
        silent: true,
        symbol: 'none',
        label: { show: false },
        data: snapshots.value.includes(selectedEnd) ? [{
          xAxis: selectedEnd,
          lineStyle: { color: '#9bb2db', type: 'dashed' },
        }] : [],
      },
      markArea: {
        silent: true,
        itemStyle: { color: 'rgba(71, 123, 231, 0.09)' },
        data: view.length ? [[{ xAxis: view[0] }, { xAxis: view.at(-1) }]] : [],
      },
    }, {
      name: 'Maximum ℓ-Segment Density',
      type: 'line',
      silent: true,
      symbol: 'none',
      tooltip: { show: false },
      lineStyle: { color: '#205956', width: 2 },
      data: node.degree_sequence.map((_, index) => inWitness(index) ? node.max_average_degree : null),
    }],
  }
})
</script>

<template>
  <div v-if="witness" class="pattern-evidence">
    <div class="pattern-facts">
      <span title="Highest average internal degree over segments of at least ℓ snapshots">
        Maximum ℓ-Segment Density (MSD) <strong>{{ msd }}</strong> · δ = {{ threshold }}
      </span>
    </div>
    <ChartCanvas
      :option="option"
      :height="104"
      :label="`Internal degree by snapshot for vertex ${witness.account}. MSD ${msd} on ${witnessRange}`"
      interactive
      @select-index="selectSnapshot"
    />
  </div>
</template>
