<script setup>
import { computed, ref } from 'vue'

import { formatNumber } from '../../domain/format.js'
import { snapshotIndex } from '../../domain/timeline.js'

const props = defineProps({
  structure: { type: Object, required: true },
  selectedRange: { type: Array, required: true },
})
const emit = defineEmits(['select-range'])

const pageSize = 4
const page = ref(0)
const snapshots = computed(() => props.structure.evidence.analysis_snapshot_ids)
const edges = computed(() => (
  [...props.structure.evidence.qualified_edges].sort((a, b) => a.frequency - b.frequency)
))
const minDegree = computed(function () {
  const degrees = new Map(props.structure.members.map(id => [id, 0]))
  for (const { u, v } of edges.value) {
    degrees.set(u, degrees.get(u) + 1)
    degrees.set(v, degrees.get(v) + 1)
  }
  return Math.min(...degrees.values())
})
const first = computed(() => page.value * pageSize)
const last = computed(() => Math.min(first.value + pageSize, edges.value.length))
const visibleEdges = computed(() => edges.value.slice(first.value, last.value))
const pageRange = computed(function () {
  const start = first.value + 1
  return start === last.value ? start : `${start}–${last.value}`
})

function percent(value) {
  return `${formatNumber(value * 100, 2)}%`
}

function rangeLabel(edge) {
  const { witness_start_snapshot_id: start, witness_end_snapshot_id: end } = edge
  return start === end ? start : `${start}—${end}`
}

function showsWindow(edge) {
  return (
    snapshotIndex(edge.witness_start_snapshot_id) === props.selectedRange[0] &&
    snapshotIndex(edge.witness_end_snapshot_id) === props.selectedRange[1]
  )
}

function selectWindow(edge) {
  emit(
    'select-range',
    snapshotIndex(edge.witness_start_snapshot_id),
    snapshotIndex(edge.witness_end_snapshot_id),
  )
}
</script>

<template>
  <div
    class="pattern-evidence frequency-evidence"
    :style="{ '--snapshot-count': snapshots.length, '--pattern-color': structure.color }"
  >
    <div class="pattern-facts frequency-facts">
      <span>Min. qualified degree <strong>{{ minDegree }}</strong> (k = {{ structure.parameters.k }})</span>
      <span><strong>{{ structure.parameters.t }}</strong> min. active · t-Frequency ≥ <strong>{{ percent(structure.parameters.f) }}</strong></span>
    </div>
    <table class="frequency-table" aria-label="Best windows and t-frequencies for qualifying edges">
      <colgroup><col class="edge-column" /><col /><col class="score-column" /></colgroup>
      <thead>
        <tr>
          <th scope="col" title="Unordered vertex pair">Edge</th>
          <th scope="col" aria-label="Best interaction window">
            <div class="frequency-axis">
              <span v-for="id in snapshots" :key="id">{{ id }}</span>
            </div>
          </th>
          <th scope="col" title="Active snapshots / total snapshots in the window, with the resulting t-frequency">t-Frequency</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="edge in visibleEdges" :key="`${edge.u}—${edge.v}`">
          <th scope="row" :title="`${edge.u}—${edge.v}`">{{ edge.u }}—{{ edge.v }}</th>
          <td>
            <div class="frequency-track">
              <button
                class="frequency-window"
                :class="{ 'is-viewed': showsWindow(edge) }"
                :style="{ gridColumn: `${edge.witness_start + 1} / ${edge.witness_end + 2}` }"
                :title="`${rangeLabel(edge)} · ${edge.numerator} of ${edge.denominator} snapshots active`"
                :aria-label="`View window ${rangeLabel(edge)} for edge ${edge.u}–${edge.v}`"
                type="button"
                @click="selectWindow(edge)"
              >{{ rangeLabel(edge) }}</button>
            </div>
          </td>
          <td><span>{{ edge.numerator }}/{{ edge.denominator }}</span> · <strong>{{ percent(edge.frequency) }}</strong></td>
        </tr>
      </tbody>
    </table>
    <div class="frequency-footer">
      <span>Select a window to view its graph</span>
      <nav class="frequency-pages" aria-label="Qualifying edge pages">
        <button
          v-if="edges.length > pageSize"
          type="button"
          aria-label="Previous page of edges"
          :disabled="first === 0"
          @click="page--"
        >‹</button>
        <span aria-live="polite">{{ pageRange }} of {{ edges.length }}</span>
        <button
          v-if="edges.length > pageSize"
          type="button"
          aria-label="Next page of edges"
          :disabled="last === edges.length"
          @click="page++"
        >›</button>
      </nav>
    </div>
  </div>
</template>

<style scoped>
.frequency-evidence {
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.frequency-facts,
.frequency-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 4px 8px;
}

.frequency-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
}

.edge-column { width: 50px; }
.score-column { width: 96px; }

.frequency-table th,
.frequency-table td {
  padding: 1px 0;
  text-align: left;
}

.frequency-table thead th {
  font-weight: 400;
  white-space: nowrap;
}

.frequency-table tbody th {
  color: #415977;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.frequency-table :is(th, td):last-child { text-align: right; }
.frequency-table strong { color: #20334b; }

.frequency-axis,
.frequency-track {
  --column-width: calc(100% / var(--snapshot-count));
  display: grid;
  grid-template-columns: repeat(var(--snapshot-count), minmax(0, 1fr));
  text-align: center;
  border-radius: 3px;
  background: repeating-linear-gradient(
    to right, #f3f6fa 0 calc(var(--column-width) - 1px), white 0 var(--column-width)
  );
}

.frequency-window {
  height: 18px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--pattern-color) 54%, white);
  border-radius: 3px;
  background: color-mix(in srgb, var(--pattern-color) 22%, white);
  color: #5c4523;
  line-height: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.frequency-window:hover,
.frequency-window.is-viewed {
  background: color-mix(in srgb, var(--pattern-color) 38%, white);
  border-color: #a8792c;
}

.frequency-footer {
  min-height: 20px;
}

.frequency-pages {
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}

.frequency-pages button {
  width: 21px;
  height: 19px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: #f8fafd;
  color: #415977;
  line-height: 1;
}

.frequency-pages button:disabled { opacity: 0.42; }
</style>
