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
  const category = '社区成员'
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
          return `箱线图离群点\n账户 ${point.name} · 异常分 ${point.value[0].toFixed(4)}`
        }
        return [
          `中位数 ${median.toFixed(4)}`,
          `中间 50% ${q1.toFixed(4)}–${q3.toFixed(4)}`,
          `箱须 ${lowerWhisker.toFixed(4)}–${upperWhisker.toFixed(4)}`,
        ].join('\n')
      },
    },
    xAxis: {
      name: 'SLADE 异常分',
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
    <div title="已评分社区成员的平均 SLADE 异常分，范围 0–1">
      <dt>平均异常分</dt>
      <dd>{{ risk.mean.toFixed(4) }}</dd>
    </div>
    <div title="已评分社区成员的 SLADE 异常分中位数，范围 0–1">
      <dt>中位异常分</dt>
      <dd>{{ risk.median.toFixed(4) }}</dd>
    </div>
  </dl>
  <ChartCanvas
    class="community-risk-chart"
    :option="option"
    :height="102"
    label="社区成员 SLADE 异常分箱线图"
  />
  <div class="summary-line risk-top-count" title="进入全图 SLADE 排名前 10 的人数占社区总人数的比例">
    <span>全图 Top-10 命中</span>
    <strong>{{ risk.topCount }} / {{ memberCount }}（{{ probabilityLabel(risk.topCount / memberCount) }}）</strong>
  </div>
</template>
