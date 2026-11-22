<script setup>
import { computed } from 'vue'

import { snapshotIndex } from '../../domain/timeline.js'
import DurableMemberChart from './DurableMemberChart.vue'

const props = defineProps({
  structure: { type: Object, required: true },
  selectedRange: { type: Array, required: true },
})
defineEmits(['select-index'])

const evidence = computed(() => props.structure.evidence)
const periodic = computed(() => props.structure.parameters.pattern === 'periodic')
const snapshots = computed(() => evidence.value.analysis_snapshot_ids)
const coreLabel = computed(() => `${props.structure.parameters.k}-core`)

function rangeLabel(first, last) {
  const start = snapshots.value[first]
  const end = snapshots.value[last]
  return start === end ? start : `${start}—${end}`
}

const bands = computed(function () {
  if (periodic.value) {
    const { start_index: start, period, frequency } = evidence.value
    return Array.from({ length: frequency }, (_, index) => {
      const first = start + index * period
      const last = first + period - 1
      const label = `第 ${index + 1} 轮`
      return { first, last, label, kind: 'period', title: `${label} · ${rangeLabel(first, last)}` }
    })
  }
  const { formation_start: start, formation_end: formed, stable_end: last } = evidence.value
  const result = [{
    first: start, last: formed, kind: 'formation', label: '形成',
    title: `${rangeLabel(start, formed)} 形成 ${coreLabel.value}`,
  }]
  if (last > formed) {
    result.push({
      first: formed + 1, last, kind: 'stable', label: '稳定',
      title: `${rangeLabel(formed, last)} 成员保持不变`,
    })
  }
  return result
})

function snapshotLabel(id, index) {
  if (periodic.value) {
    const formed = evidence.value.kcore_series[index] === 1
    return `${id} · ${formed ? '形成' : '未形成'} ${coreLabel.value}`
  }
  if (index === evidence.value.formation_end) return `${id} · 社区形成`
  if (index > evidence.value.formation_end && index <= evidence.value.stable_end)
    return `${id} · 成员保持不变`
  return id
}

const ticks = computed(() => snapshots.value.map((id, index) => ({
  id,
  index: snapshotIndex(id),
  label: snapshotLabel(id, index),
  state: evidence.value.kcore_series?.[index],
  formationEnd: !periodic.value && index === evidence.value.formation_end,
})))
</script>

<template>
  <div class="pattern-evidence" :style="{ '--pattern-color': structure.color }">
    <div v-if="periodic" class="pattern-facts">
      <span>周期长 <strong>{{ evidence.period }}</strong> 个快照</span>
      <span :title="`各轮之间的 Jaccard 相似度至少为 ${structure.parameters.epsilon.toFixed(2)}`">
        重复 <strong>{{ evidence.frequency }}</strong> 次
      </span>
    </div>
    <div
      class="core-pattern-timeline"
      :style="{ '--snapshot-count': snapshots.length }"
      role="group"
      :aria-label="periodic ? 'k-core 状态序列' : '社区形成与稳定区间'"
    >
      <span
        v-for="band in bands"
        :key="band.first"
        class="core-pattern-band"
        :class="band.kind"
        :style="{ gridColumn: `${band.first + 1} / ${band.last + 2}` }"
        :title="band.title"
      >{{ band.label }}</span>
      <button
        v-for="(tick, column) in ticks"
        :key="tick.id"
        type="button"
        class="core-pattern-tick"
        :class="{
          'in-range': tick.index >= selectedRange[0] && tick.index <= selectedRange[1],
          'at-end': tick.index === selectedRange[1],
          'formation-end': tick.formationEnd,
        }"
        :style="{ gridColumn: column + 1 }"
        :aria-current="tick.index === selectedRange[1] ? 'true' : undefined"
        :aria-label="tick.label"
        :title="tick.label"
        @click="$emit('select-index', tick.index)"
      >
        <span v-if="periodic" class="core-pattern-state" :class="{ formed: tick.state === 1 }">
          {{ tick.state }}
        </span>
        <span>{{ tick.id }}</span>
      </button>
    </div>
    <p v-if="periodic" class="pattern-key">1 形成 {{ coreLabel }} <span>0 未形成</span></p>
    <DurableMemberChart
      v-if="!periodic && evidence.member_count_series?.length"
      :structure="structure"
      :selected-end="selectedRange[1]"
      @select-index="$emit('select-index', $event)"
    />
  </div>
</template>
