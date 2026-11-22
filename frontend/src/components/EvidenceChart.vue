<script setup>
import { computed } from 'vue'

import { HISTORY_LENGTH, snapshotId } from '../domain/timeline.js'
import ChartCanvas from './ChartCanvas.vue'

const props = defineProps({
  track: { type: Object, required: true },
  unit: { type: String, required: true },
  metricLabel: { type: String, required: true },
  selectedIndex: { type: Number, required: true },
  selectedRange: { type: Array, required: true },
})
defineEmits(['select-index'])

const ticks = Array.from({ length: HISTORY_LENGTH }, (_, index) => snapshotId(index))
const option = computed(function () {
  const points = new Map(props.track.points.map(point => [point.index, point.value]))
  const [start, end] = props.selectedRange
  return {
    animationDuration: 180,
    grid: { top: 10, right: 16, bottom: 24, left: 38 },
    tooltip: {
      trigger: 'axis',
      formatter: function ([point]) {
        if (!point) return ''
        const value = point.value == null ? '成员未出现' : `${point.value} ${props.unit}`
        return `${point.axisValueLabel}\n${props.metricLabel} ${value}`
      },
    },
    xAxis: {
      type: 'category',
      data: ticks,
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#dce4ef' } },
      axisTick: { show: false },
      axisLabel: { color: '#687b91', interval: 0 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      minInterval: 1,
      splitNumber: 3,
      axisLabel: { color: '#7c8da3' },
      splitLine: { lineStyle: { color: '#f0f3f8' } },
    },
    series: [{
      name: props.track.label,
      type: 'line',
      symbolSize: 5,
      lineStyle: { width: 2 },
      itemStyle: { color: props.track.color },
      areaStyle: { opacity: 0.05, color: props.track.color },
      data: ticks.map(function (_, index) {
        const value = points.get(index)
        return value == null ? null : Number(value)
      }),
      markLine: {
        silent: true,
        symbol: 'none',
        label: { show: false },
        lineStyle: { color: '#9bb2db', type: 'dashed' },
        data: [{ xAxis: ticks[props.selectedIndex] }],
      },
      markArea: {
        silent: true,
        itemStyle: { color: 'rgba(71, 123, 231, 0.09)' },
        label: { show: false },
        data: [[{ xAxis: ticks[start] }, { xAxis: ticks[end] }]],
      },
    }],
  }
})
</script>

<template>
  <ChartCanvas
    :option="option"
    :height="126"
    :label="`固定成员的${metricLabel}轨迹`"
    :data-range-start="selectedRange[0]"
    :data-range-end="selectedRange[1]"
    interactive
    @select-index="$emit('select-index', $event)"
  />
</template>
