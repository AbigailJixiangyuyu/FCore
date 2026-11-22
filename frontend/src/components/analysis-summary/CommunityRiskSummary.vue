<script setup>
import { computed } from 'vue'

import { probabilityLabel } from '../../composables/workbenchContext.js'
import ChartCanvas from '../ChartCanvas.vue'

const props = defineProps({
  risk: { type: Object, required: true },
  memberCount: { type: Number, required: true },
})

const muted = '#687b91'
const blue = '#4776b7'

const option = computed(function () {
  const { box, median } = props.risk
  const { lowerWhisker, q1, q3, upperWhisker, minimum, maximum } = box
  const category = 'Community members'
  const collapsed = lowerWhisker === upperWhisker
  const center = collapsed
    ? { type: 'scatter', symbolSize: 7, itemStyle: { color: blue }, data: [[median, category]] }
    : {
        type: 'boxplot',
        layout: 'horizontal',
        boxWidth: [14, 18],
        itemStyle: { color: '#dce8fa', borderColor: blue, borderWidth: 1.5 },
        data: [[lowerWhisker, q1, median, q3, upperWhisker]],
      }

  return {
    animation: false,
    grid: { top: 7, right: 18, bottom: 42, left: 18 },
    tooltip: {
      trigger: 'item',
      formatter(point) {
        if (point.seriesIndex === 1) {
          return `Box plot outlier\nNode ${point.name} · Anomaly score ${point.value[0].toFixed(4)}`
        }
        return [
          `Median ${median.toFixed(4)}`,
          `Middle 50% ${q1.toFixed(4)}–${q3.toFixed(4)}`,
          `Whiskers ${lowerWhisker.toFixed(4)}–${upperWhisker.toFixed(4)}`,
        ].join('\n')
      },
    },
    xAxis: {
      name: 'SLADE anomaly score',
      nameLocation: 'middle',
      nameGap: 27,
      nameTextStyle: { color: muted },
      type: 'value',
      min: Math.max(0, (Math.floor(minimum * 100) - 1) / 100),
      max: Math.min(1, (Math.ceil(maximum * 100) + 1) / 100),
      minInterval: 0.01,
      splitNumber: 4,
      axisLine: { show: true, lineStyle: { color: '#dce4ef' } },
      axisTick: { show: false },
      axisLabel: { color: muted, hideOverlap: true, formatter: value => value.toFixed(2) },
      splitLine: { show: false },
    },
    yAxis: { type: 'category', data: [category], show: false },
    series: [center, {
      type: 'scatter',
      symbolSize: 7,
      itemStyle: { color: '#b66540' },
      data: box.outliers.map(({ account_id, score }) => ({ name: account_id, value: [score, category] })),
    }],
  }
})
</script>

<template>
  <dl class="summary-metrics risk-metrics">
    <div title="Mean SLADE anomaly score (0–1) among scored members">
      <dt>Mean Score</dt>
      <dd>{{ risk.mean.toFixed(4) }}</dd>
    </div>
    <div title="Median SLADE anomaly score (0–1) among scored members">
      <dt>Median Score</dt>
      <dd>{{ risk.median.toFixed(4) }}</dd>
    </div>
  </dl>
  <ChartCanvas
    class="community-risk-chart"
    :option="option"
    :height="102"
    label="Box plot of SLADE anomaly scores for community members"
  />
  <div class="summary-line risk-top-count" title="Share of community members in the full graph top 10 for anomaly score">
    <span>Members in Top 10</span>
    <strong>{{ risk.topCount }} / {{ memberCount }} ({{ probabilityLabel(risk.topCount / memberCount) }})</strong>
  </div>
</template>
