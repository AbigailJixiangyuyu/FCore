<script setup>
import { computed } from 'vue'

import { formatCount } from '../domain/format.js'
import { useWorkbench } from '../composables/workbenchContext.js'
import { snapshotId } from '../domain/timeline.js'
import ChartCanvas from './ChartCanvas.vue'

const props = defineProps({
  track: { type: Object, required: true },
  unit: { type: String, required: true },
  metricLabel: { type: String, required: true },
  selectedIndex: { type: Number, required: true },
  selectedRange: { type: Array, required: true },
})
defineEmits(['select-index'])

const { store } = useWorkbench()
const option = computed(function () {
  const ticks = Array.from({ length: store.presentIndex }, (_, index) => snapshotId(index))
  const points = new Map(props.track.points.map(point => [point.index, point]))
  const [start, end] = props.selectedRange
  return {
    animationDuration: 180,
    grid: { top: 10, right: 16, bottom: 24, left: 38 },
    tooltip: {
      trigger: 'axis',
      formatter: function ([point]) {
        if (!point) return ''
        const entry = points.get(point.dataIndex)
        const missing = entry?.status === 'unavailable' ? 'Interactions unavailable' : 'Members absent'
        return `${point.axisValueLabel}\n${entry?.value == null ? missing : formatCount(entry.value, props.unit.replace(/s$/, ''))}`
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
        return points.get(index)?.value ?? null
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
    :label="`${metricLabel} over time for the selected members`"
    :data-range-start="selectedRange[0]"
    :data-range-end="selectedRange[1]"
    interactive
    @select-index="$emit('select-index', $event)"
  />
</template>
