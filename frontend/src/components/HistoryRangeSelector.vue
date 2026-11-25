<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useWorkbench } from '../composables/workbenchContext.js'
import { formatCount } from '../domain/format.js'
import { snapshotId } from '../domain/timeline.js'

const props = defineProps({
  snapshots: { type: Array, required: true },
})

const { store, selectHistoryRange } = useWorkbench()
const lastIndex = computed(() => props.snapshots.length - 1)
const tickStride = computed(() => Math.ceil(props.snapshots.length / 11))
const boundaries = ['start', 'end']
const preview = ref(null)
const committedRange = computed(() =>
  store.stage === 'history' ? [store.historyStartIndex, store.historyEndIndex] : null,
)
const selection = computed(() => preview.value ?? committedRange.value)
const selectionStyle = computed(() => {
  if (!selection.value) return {}
  const [start, end] = selection.value
  return {
    left: `${(start / props.snapshots.length) * 100}%`,
    right: `${((lastIndex.value - end) / props.snapshots.length) * 100}%`,
  }
})
function coverage(meta) {
  const days = (Date.parse(meta.ends_at) - Date.parse(meta.starts_at)) / 86_400_000
  return days >= 1 ? `${Number(days.toFixed(2))} days` : `${Number((days * 1440).toFixed(2))} min`
}
function shortWindowLabel(meta) {
  if (!meta || !props.snapshots.length) return ''
  const presentWidth = props.snapshots.at(-1)
  const duration = m => Date.parse(m.ends_at) - Date.parse(m.starts_at)
  return duration(meta) < duration(presentWidth) ? ` · ${meta.snapshot_id}: ${coverage(meta)}` : ''
}
const caption = computed(() => {
  if (!selection.value) return `History · S01–${snapshotId(lastIndex.value)}${shortWindowLabel(props.snapshots[0])}`
  const [start, end] = selection.value
  const range = start === end ? snapshotId(start) : `${snapshotId(start)}—${snapshotId(end)}`
  return `History · ${range} · ${formatCount(end - start + 1, 'snapshot')}`
})

// Dragging only changes the local selection. The workbench reads the committed range.
let gesture = null

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function shiftRange([start, end], step) {
  const shift = clamp(step, -start, lastIndex.value - end)
  return [start + shift, end + shift]
}

function horizontalStep(event) {
  if (event.altKey || event.ctrlKey || event.metaKey) return 0
  if (event.key === 'ArrowLeft') return -1
  if (event.key === 'ArrowRight') return 1
  return 0
}

function beginDrag(event) {
  if (event.button !== 0 || !event.isPrimary || gesture) return
  const rail = event.currentTarget
  const bounds = rail.getBoundingClientRect()
  if (!bounds.width) return
  const handle = event.target.closest('[data-boundary]')
  const selectedRange = event.target.closest('.history-selection')
  const mode = handle?.dataset.boundary ?? (selectedRange ? 'move' : 'draw')
  gesture = {
    rail,
    mode,
    pointerId: event.pointerId,
    originX: event.clientX,
    lastX: event.clientX,
    left: bounds.left,
    cellWidth: bounds.width / props.snapshots.length,
    range: committedRange.value,
  }
  const control = handle ?? selectedRange
  control?.focus({ preventScroll: true })
  rail.setPointerCapture(event.pointerId)
  window.addEventListener('keydown', onDragKeydown)
  window.addEventListener('blur', cancelDrag)
}

function moveDrag(event) {
  if (event.pointerId !== gesture?.pointerId) return
  gesture.lastX = event.clientX
  const { originX, left, cellWidth, mode, range } = gesture
  const delta = event.clientX - originX
  if (!preview.value && Math.abs(delta) < 4) return

  if (mode === 'draw') {
    const first = clamp(Math.floor((originX - left) / cellWidth), 0, lastIndex.value)
    const last = clamp(Math.floor((event.clientX - left) / cellWidth), 0, lastIndex.value)
    preview.value = [Math.min(first, last), Math.max(first, last)]
    return
  }

  const [start, end] = range
  const step = Math.round(delta / cellWidth)
  if (mode === 'start') preview.value = [clamp(start + step, 0, end), end]
  else if (mode === 'end') preview.value = [start, clamp(end + step, start, lastIndex.value)]
  else preview.value = shiftRange(range, step)
}

function finishDrag(event) {
  if (event.pointerId !== gesture?.pointerId) return
  moveDrag(event)
  const range = preview.value
  cancelDrag()
  if (range) selectHistoryRange(...range)
}

function cancelDrag() {
  if (!gesture) return
  const { rail, pointerId } = gesture
  gesture = null
  preview.value = null
  if (rail.hasPointerCapture(pointerId)) rail.releasePointerCapture(pointerId)
  window.removeEventListener('keydown', onDragKeydown)
  window.removeEventListener('blur', cancelDrag)
}

function cancelPointerDrag(event) {
  if (event.pointerId === gesture?.pointerId) cancelDrag()
}

function onDragKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    cancelDrag()
    return
  }
  if (gesture?.mode !== 'move') return
  const step = horizontalStep(event)
  if (!step) return
  event.preventDefault()
  const range = preview.value ?? gesture.range
  const next = shiftRange(range, step)
  if (next[0] === range[0]) return
  preview.value = next
  // Continue pointer movement from this range so releasing does not undo the key step.
  gesture.range = next
  gesture.originX = gesture.lastX
}

function shiftSelection(event) {
  if (gesture || event.defaultPrevented || !committedRange.value) return
  const step = horizontalStep(event)
  if (!step) return
  event.preventDefault()
  const range = committedRange.value
  const next = shiftRange(range, step)
  if (next[0] !== range[0]) selectHistoryRange(...next)
}

function adjustBoundary(event, boundary) {
  if (gesture || !committedRange.value) return
  const [start, end] = committedRange.value
  const isStart = boundary === 'start'
  const current = isStart ? start : end
  const min = isStart ? 0 : start
  const max = isStart ? end : lastIndex.value
  let next
  switch (event.key) {
    case 'ArrowLeft':
    case 'ArrowDown':
      next = Math.max(min, current - 1)
      break
    case 'ArrowRight':
    case 'ArrowUp':
      next = Math.min(max, current + 1)
      break
    case 'Home':
      next = min
      break
    case 'End':
      next = max
      break
    default:
      return
  }
  event.preventDefault()
  if (next !== current) selectHistoryRange(isStart ? next : start, isStart ? end : next)
}

watch([() => store.stage, committedRange], cancelDrag)
onBeforeUnmount(cancelDrag)
</script>

<template>
  <div
    class="historical-timeline"
    role="group"
    aria-label="Historical snapshots"
    :style="{ '--history-length': props.snapshots.length }"
    @keydown="shiftSelection"
  >
    <div class="history-caption">
      <span>{{ caption }}</span>
      <span v-if="preview" class="history-preview">Preview</span>
    </div>
    <div
      class="history-track"
      :class="{ 'is-previewing': preview }"
      @pointerdown="beginDrag"
      @pointermove="moveDrag"
      @pointerup="finishDrag"
      @pointercancel="cancelPointerDrag"
      @lostpointercapture="cancelPointerDrag"
    >
      <div class="history-track-cells" title="Drag to select a historical range" aria-hidden="true">
        <span v-for="meta in snapshots" :key="meta.snapshot_id"></span>
      </div>
      <div
        v-if="selection"
        class="history-selection"
        :style="selectionStyle"
        :tabindex="committedRange ? 0 : -1"
        role="group"
        aria-label="Move the historical range"
        aria-keyshortcuts="ArrowLeft ArrowRight"
        title="Drag or press the left and right arrow keys to move the range"
      >
        <div
          v-for="(boundary, index) in boundaries"
          :key="boundary"
          class="history-handle"
          :class="`history-handle--${boundary}`"
          :data-boundary="boundary"
          role="slider"
          :tabindex="committedRange ? 0 : -1"
          :aria-hidden="committedRange ? undefined : 'true'"
          :aria-label="boundary === 'start' ? 'Start of historical range' : 'End of historical range'"
          :aria-valuemin="boundary === 'start' ? 0 : selection[0]"
          :aria-valuemax="boundary === 'start' ? selection[1] : lastIndex"
          :aria-valuenow="selection[index]"
          :aria-valuetext="snapshotId(selection[index])"
          :title="boundary === 'start' ? 'Drag to adjust the start' : 'Drag to adjust the end'"
          @keydown="adjustBoundary($event, boundary)"
        ></div>
      </div>
    </div>
    <div class="history-ticks">
      <button
        v-for="meta in snapshots"
        :key="meta.snapshot_id"
        type="button"
        :class="{ 'in-range': selection && meta.index >= selection[0] && meta.index <= selection[1] }"
        :title="`${meta.snapshot_id} · ${coverage(meta)} · ${meta.starts_at} – ${meta.ends_at}`"
        :aria-label="`View snapshot ${meta.snapshot_id}`"
        :aria-pressed="committedRange?.[0] === meta.index && committedRange?.[1] === meta.index"
        @click="selectHistoryRange(meta.index, meta.index)"
      >
        <span v-if="(meta.index % tickStride === 0 && lastIndex - meta.index >= tickStride / 2) || meta.index === lastIndex">{{ meta.snapshot_id }}</span>
      </button>
    </div>
  </div>
</template>
