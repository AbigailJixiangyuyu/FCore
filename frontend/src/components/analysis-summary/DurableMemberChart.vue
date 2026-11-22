<script setup>
import { computed } from 'vue'

import { snapshotId, snapshotIndex } from '../../domain/timeline.js'
import ChartCanvas from '../ChartCanvas.vue'

const props = defineProps({
  structure: { type: Object, required: true },
  selectedEnd: { type: Number, required: true },
})
const emit = defineEmits(['select-index'])
const evidence = computed(() => props.structure.evidence)
const endpoints = computed(() => evidence.value.analysis_snapshot_ids.slice(evidence.value.formation_start))

function selectEndpoint(index) {
  const id = endpoints.value[index]
  if (id) emit('select-index', snapshotIndex(id))
}

const option = computed(function () {
  const {
    formation_start: start, formation_end: formed, stable_end: last,
    analysis_snapshot_ids: snapshots, member_count_series: counts,
  } = evidence.value
  const beginning = snapshots[start]
  const formation = snapshots[formed]
  const selected = snapshotId(props.selectedEnd)
  const { color } = props.structure
  const markers = [{ xAxis: formation, lineStyle: { color } }]
  if (selected !== formation && endpoints.value.includes(selected)) {
    markers.push({ xAxis: selected, lineStyle: { color: '#9bb2db', type: 'dashed' } })
  }

  return {
    animationDuration: 180,
    grid: { top: 23, right: 16, bottom: 36, left: 34 },
    tooltip: {
      trigger: 'axis',
      formatter: function ([point]) {
        if (!point) return ''
        const end = endpoints.value[point.dataIndex]
        const window = end === beginning ? beginning : `${beginning}—${end}`
        return `${window}\n成员数 ${point.value} 人`
      },
    },
    xAxis: {
      type: 'category', data: endpoints.value, boundaryGap: false,
      name: `窗口终点（起点 ${beginning}）`, nameLocation: 'middle', nameGap: 22,
      nameTextStyle: { color: '#687b91' },
      axisLine: { lineStyle: { color: '#dce4ef' } },
      axisTick: { show: false },
      axisLabel: { color: '#687b91', interval: 0, margin: 4 },
    },
    yAxis: {
      type: 'value', name: '成员数', nameGap: 5, scale: true, minInterval: 1, splitNumber: 3,
      nameTextStyle: { color: '#687b91' },
      axisLabel: { color: '#7c8da3' },
      splitLine: { lineStyle: { color: '#f0f3f8' } },
    },
    series: [{
      name: '社区成员数', type: 'line', symbol: 'circle', symbolSize: 5,
      itemStyle: { color }, lineStyle: { width: 2 },
      label: { position: 'top', color: '#4b3a66', formatter: '{c}' },
      data: counts.map(function (value, index) {
        const end = start + index
        if (end === formed || end === last + 1) return { value, label: { show: true } }
        return value
      }),
      markLine: { silent: true, symbol: 'none', label: { show: false }, data: markers },
      markArea: {
        silent: true,
        label: { show: false },
        itemStyle: { color, opacity: 0.16 },
        data: last > formed ? [[{ xAxis: formation }, { xAxis: snapshots[last] }]] : [],
      },
    }],
  }
})
</script>

<template>
  <ChartCanvas
    class="durable-member-chart"
    :option="option"
    :height="92"
    :label="`固定起点 ${endpoints[0]} 的社区成员数`"
    interactive
    @select-index="selectEndpoint"
  />
</template>
